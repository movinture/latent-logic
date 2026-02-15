#!/usr/bin/env python3
"""Generate a model-insights markdown block from comparison artifacts."""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
import glob


def load_json(path: Path) -> dict:
    with path.open() as f:
        return json.load(f)


def latest_comparison_json() -> Path:
    files = sorted(glob.glob("evaluation_results/runs/*/analysis/comparison_*.json"))
    if not files:
        raise FileNotFoundError("No run-scoped comparison JSON found under evaluation_results/runs/*/analysis")
    return Path(files[-1])


def pairwise_counts(pairwise: list[dict]) -> tuple[int, int, int]:
    scratch_wins = 0
    strands_wins = 0
    ties = 0
    for row in pairwise:
        s_valid = row.get("scratch_valid")
        t_valid = row.get("strands_valid")
        if s_valid and not t_valid:
            scratch_wins += 1
        elif t_valid and not s_valid:
            strands_wins += 1
        else:
            ties += 1
    return scratch_wins, strands_wins, ties


def tool_style(record: dict) -> str:
    avg_tool_calls = float(record.get("avg_tool_calls", 0.0))
    provenance = record.get("provenance", {}) or {}
    parametric = int(provenance.get("parametric", 0))
    if avg_tool_calls == 0 and parametric > 0:
        return "mostly parametric"
    if avg_tool_calls >= 1.25:
        return "multi-step tool use"
    if avg_tool_calls > 0:
        return "single-step tool use"
    return "limited tool execution"


def verdict_label(s_valid: int, s_runs: int, t_valid: int, t_runs: int) -> str:
    total_valid = s_valid + t_valid
    total_runs = s_runs + t_runs
    if total_valid == total_runs:
        return "Strong"
    if total_valid == 0:
        return "Weak"
    if total_valid >= total_runs - 1:
        return "Mostly Strong"
    if total_valid <= 1:
        return "Mostly Weak"
    return "Mixed"


def reason_line(record: dict) -> str:
    reasons = record.get("fail_reasons", {}) or {}
    cleaned = [f"{k}:{v}" for k, v in reasons.items() if k not in (None, "null")]
    if not cleaned:
        return "none"
    return ", ".join(cleaned)


def build_markdown(
    comparison: dict,
    prompts: dict,
    tag: str,
    canonical_path: str,
    comparison_path: str,
) -> str:
    by_model = comparison.get("by_model", {})
    all_models = sorted(by_model.keys())
    overall = comparison.get("overall", {})

    scratch_valid = int(overall.get("scratch_valid_verified", 0))
    scratch_runs = int(overall.get("scratch_verified", 0))
    strands_valid = int(overall.get("strands_valid_verified", 0))
    strands_runs = int(overall.get("strands_verified", 0))

    scratch_wins, strands_wins, ties = pairwise_counts(comparison.get("pairwise", []))

    prompt_version = prompts.get("version", "unknown")
    prompt_names = [p.get("name", "unknown_prompt") for p in prompts.get("prompts", [])]

    lines: list[str] = []
    lines.append(f"\n## Run Update: `{tag}`")
    lines.append("")
    lines.append("### Data Tag")
    lines.append(f"- Evaluation tag: `{tag}`")
    lines.append(f"- Prompt set: `prompts.json` (version `{prompt_version}`)")
    lines.append("- Prompts:")
    for name in prompt_names:
        lines.append(f"  - `{name}`")
    lines.append("- Frameworks compared:")
    lines.append("  - Scratch: `scratch_foundry/run_evaluation.py`")
    lines.append("  - Strands: `strands_foundry/run_strands_evaluation.py`")
    lines.append("- Canonical snapshot: `" + canonical_path + "`")
    lines.append("- Generated summaries used:")
    lines.append("  - `" + comparison_path + "`")
    lines.append("- Scope caveat:")
    lines.append("  - Single cohort; treat as operational tool-use signal, not broad capability ranking.")
    lines.append("")

    lines.append("### Scorecard Snapshot")
    lines.append("- Overall valid outputs:")
    lines.append(f"  - Scratch: `{scratch_valid}/{scratch_runs}`")
    lines.append(f"  - Strands: `{strands_valid}/{strands_runs}`")
    lines.append(f"- Pairwise head-to-head (`{len(comparison.get('pairwise', []))}` model-prompt pairs):")
    lines.append(f"  - Scratch wins: `{scratch_wins}`")
    lines.append(f"  - Strands wins: `{strands_wins}`")
    lines.append(f"  - Ties: `{ties}`")
    lines.append("")

    lines.append("### Capability Cards")
    lines.append("")

    for model in all_models:
        rec = by_model.get(model, {})
        s = rec.get("scratch", {})
        t = rec.get("strands", {})
        s_valid = int(s.get("valid_runs", 0))
        t_valid = int(t.get("valid_runs", 0))
        s_runs = int(s.get("verified_runs", 0))
        t_runs = int(t.get("verified_runs", 0))

        lines.append(f"#### {model}")
        lines.append(
            f"- Result: `{s_valid + t_valid}/{s_runs + t_runs}` valid "
            f"(Scratch `{s_valid}/{s_runs}`, Strands `{t_valid}/{t_runs}`)."
        )
        lines.append(
            f"- Tool profile: scratch `{tool_style(s)}` (avg tool calls `{s.get('avg_tool_calls', 0)}`), "
            f"strands `{tool_style(t)}` (avg tool calls `{t.get('avg_tool_calls', 0)}`)."
        )
        lines.append(
            f"- Failure signals: scratch `{reason_line(s)}`, strands `{reason_line(t)}`."
        )
        lines.append(f"- Verdict: `{verdict_label(s_valid, s_runs, t_valid, t_runs)}`.")
        lines.append("")

    lines.append("### Notes For Next Run")
    lines.append("- Add rubric auto-scoring and include numeric per-model totals.")
    lines.append("- Include at least one retry/error-injection prompt to test recovery behavior.")
    lines.append("- Add Anthropic models for a wider reasoning baseline.")

    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate model-insights markdown block.")
    parser.add_argument(
        "--comparison",
        default="",
        help="Path to comparison summary JSON. Defaults to latest run-scoped comparison.",
    )
    parser.add_argument(
        "--runtime",
        default="",
        help="Deprecated in current schema; kept for CLI compatibility.",
    )
    parser.add_argument(
        "--prompts",
        default="prompts.json",
        help="Path to prompts JSON.",
    )
    parser.add_argument(
        "--canonical",
        default="evaluation_results/runs/<run_group>/canonical/canonical_<prompt_version>.json",
        help="Canonical snapshot path to reference in output.",
    )
    parser.add_argument(
        "--tag",
        default=f"latent-logic_eval_{datetime.now().strftime('%Y-%m-%d')}_auto",
        help="Run tag used in the generated section heading.",
    )
    parser.add_argument(
        "--append",
        default="",
        help="If set, append the generated markdown block to this file.",
    )
    args = parser.parse_args()

    comparison_path = Path(args.comparison) if args.comparison else latest_comparison_json()
    prompts_path = Path(args.prompts)

    comparison = load_json(comparison_path)
    prompts = load_json(prompts_path)

    block = build_markdown(
        comparison,
        prompts,
        args.tag,
        args.canonical,
        str(comparison_path),
    )

    if args.append:
        out = Path(args.append)
        with out.open("a") as f:
            f.write("\n")
            f.write(block)
        print(f"Appended generated block to {out}")
    else:
        print(block)


if __name__ == "__main__":
    main()

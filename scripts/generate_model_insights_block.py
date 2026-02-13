#!/usr/bin/env python3
"""Generate a model-insights markdown block from latest evaluation summaries."""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path


def load_json(path: Path) -> dict:
    with path.open() as f:
        return json.load(f)


def avg_runtime_by_model(runtime_rows: list[dict]) -> dict[str, float]:
    buckets: dict[str, list[float]] = {}
    for row in runtime_rows:
        model = row.get("model")
        duration = row.get("duration_s")
        if model is None or duration is None:
            continue
        buckets.setdefault(model, []).append(float(duration))
    return {
        model: round(sum(values) / len(values), 2)
        for model, values in buckets.items()
        if values
    }


def pairwise_counts(pairwise: list[dict]) -> tuple[int, int, int]:
    scratch_wins = 0
    strands_wins = 0
    ties = 0
    for row in pairwise:
        s_valid = bool((row.get("scratch") or {}).get("valid"))
        t_valid = bool((row.get("strands") or {}).get("valid"))
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
    runtime: dict,
    prompts: dict,
    tag: str,
    canonical_path: str,
    comparison_path: str,
    runtime_path: str,
) -> str:
    scratch_rows = comparison["summary"]["scratch"]
    strands_rows = comparison["summary"]["strands"]
    scratch_by_model = {r["model"]: r for r in scratch_rows}
    strands_by_model = {r["model"]: r for r in strands_rows}

    all_models = sorted(set(scratch_by_model) | set(strands_by_model))

    scratch_valid = sum(int(r.get("valid", 0)) for r in scratch_rows)
    scratch_runs = sum(int(r.get("runs", 0)) for r in scratch_rows)
    strands_valid = sum(int(r.get("valid", 0)) for r in strands_rows)
    strands_runs = sum(int(r.get("runs", 0)) for r in strands_rows)

    scratch_wins, strands_wins, ties = pairwise_counts(comparison.get("pairwise", []))

    scratch_runtime = avg_runtime_by_model(runtime.get("scratch", []))
    strands_runtime = avg_runtime_by_model(runtime.get("strands", []))

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
    lines.append("  - `" + runtime_path + "`")
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
        s = scratch_by_model.get(model, {})
        t = strands_by_model.get(model, {})
        s_valid = int(s.get("valid", 0))
        t_valid = int(t.get("valid", 0))
        s_runs = int(s.get("runs", 0))
        t_runs = int(t.get("runs", 0))

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
            f"- Runtime: scratch avg `{scratch_runtime.get(model, 'n/a')}s`, "
            f"strands avg `{strands_runtime.get(model, 'n/a')}s`."
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
        default="evaluation_results/latest_comparison_summary.json",
        help="Path to latest comparison summary JSON.",
    )
    parser.add_argument(
        "--runtime",
        default="evaluation_results/latest_runtime_summary.json",
        help="Path to runtime summary JSON.",
    )
    parser.add_argument(
        "--prompts",
        default="prompts.json",
        help="Path to prompts JSON.",
    )
    parser.add_argument(
        "--canonical",
        default="evaluation_results/canonical/canonical_2026-02-12.json",
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

    comparison_path = Path(args.comparison)
    runtime_path = Path(args.runtime)
    prompts_path = Path(args.prompts)

    comparison = load_json(comparison_path)
    runtime = load_json(runtime_path)
    prompts = load_json(prompts_path)

    block = build_markdown(
        comparison,
        runtime,
        prompts,
        args.tag,
        args.canonical,
        str(comparison_path),
        str(runtime_path),
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

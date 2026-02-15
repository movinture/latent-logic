#!/usr/bin/env python3
"""Deterministic model-first comparison across scratch and Strands evaluation artifacts.

Outputs:
- evaluation_results/runs/<run_group>/latest_comparison_summary.json
- evaluation_results/runs/<run_group>/latest_runtime_summary.json
- evaluation_results/runs/<run_group>/analysis/comparison_<timestamp>.json
- evaluation_results/runs/<run_group>/analysis/comparison_<timestamp>.md
- evaluation_results/runs/<run_group>/analysis/interpretation_guide_<timestamp>.md
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def load_json(path: Path) -> Any:
    with path.open() as f:
        return json.load(f)


def save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as f:
        json.dump(data, f, indent=2)


def sanitize_model_folder(model: str) -> str:
    return re.sub(r"(?u)[^-\w.]", "", model.replace(" ", "_"))


def extract_run_id(path: Path) -> str | None:
    m = re.search(r"_(\d{8}_\d{6})_validation\.json$", path.name)
    return m.group(1) if m else None


def load_prompts(prompt_file: Path) -> list[str]:
    data = load_json(prompt_file)
    return [p["name"] for p in data.get("prompts", [])]


def choose_strands_run_id(base: Path, models: list[str], prompt_names: list[str]) -> tuple[str | None, dict[str, Any]]:
    run_map: dict[str, set[tuple[str, str]]] = defaultdict(set)
    model_folders = [sanitize_model_folder(m) for m in models]

    for folder in model_folders:
        model_dir = base / "strands" / folder
        if not model_dir.exists():
            continue
        for vf in model_dir.glob("*_validation.json"):
            run_id = extract_run_id(vf)
            if not run_id:
                continue
            try:
                payload = load_json(vf)
            except Exception:
                continue
            model = payload.get("model")
            prompt_name = payload.get("prompt_name")
            if model in models and prompt_name in prompt_names:
                run_map[run_id].add((model, prompt_name))

    if not run_map:
        return None, {}

    target = len(models) * len(prompt_names)
    ranked = sorted(run_map.items(), key=lambda kv: (len(kv[1]), kv[0]))
    best_run_id, keys = ranked[-1]
    return best_run_id, {
        "target_pairs": target,
        "best_pairs": len(keys),
        "coverage": round(len(keys) / target, 3) if target else 0.0,
        "available_run_ids": sorted(run_map.keys()),
    }


def parse_scratch_metrics(result_payload: Any) -> dict[str, Any]:
    messages = result_payload if isinstance(result_payload, list) else result_payload.get("messages", [])
    assistant_turns = 0
    tool_calls = 0
    for m in messages:
        if m.get("role") == "assistant":
            assistant_turns += 1
            tool_calls += len(m.get("tool_calls") or [])
    return {"assistant_turns": assistant_turns, "tool_calls": tool_calls}


def parse_strands_metrics(result_payload: dict[str, Any]) -> dict[str, Any]:
    messages = result_payload.get("messages", [])
    assistant_turns = 0
    tool_calls = 0
    for m in messages:
        if m.get("role") != "assistant":
            continue
        assistant_turns += 1
        for block in m.get("content", []):
            if "toolUse" in block:
                tool_calls += 1
    return {
        "assistant_turns": assistant_turns,
        "tool_calls": tool_calls,
        "final_text_source": result_payload.get("final_text_source", "unknown"),
    }


def load_record(
    framework: str,
    base: Path,
    model: str,
    prompt_name: str,
    run_id: str | None,
) -> dict[str, Any] | None:
    folder = base / framework / sanitize_model_folder(model)
    if not folder.exists():
        return None

    if framework == "scratch":
        vf = folder / f"{prompt_name}_validation.json"
        rf = folder / f"{prompt_name}.json"
    else:
        if run_id is None:
            return None
        vf = folder / f"{prompt_name}_{run_id}_validation.json"
        rf = folder / f"{prompt_name}_{run_id}.json"

    if not vf.exists() or not rf.exists():
        return None

    v = load_json(vf)
    r = load_json(rf)

    metrics = parse_scratch_metrics(r) if framework == "scratch" else parse_strands_metrics(r)
    val = v.get("validation", {})
    return {
        "framework": framework,
        "model": model,
        "prompt_name": prompt_name,
        "validation": val,
        "provenance": v.get("provenance"),
        "tool_used": v.get("tool_used"),
        "tool_names": v.get("tool_names", []),
        "eval_time_unix": v.get("eval_time_unix"),
        "data_hints": v.get("data_hints", {}),
        "metrics": metrics,
        "paths": {
            "validation": str(vf),
            "result": str(rf),
        },
    }


def summarize_model(records: list[dict[str, Any]]) -> dict[str, Any]:
    verified = [r for r in records if r["validation"].get("valid") is not None]
    valid = [r for r in verified if r["validation"].get("valid") is True]
    reasons = Counter(r["validation"].get("reason") for r in records if r["validation"].get("valid") is False)
    prov = Counter(r.get("provenance") for r in records)
    avg_turns = round(sum(r["metrics"].get("assistant_turns", 0) for r in records) / len(records), 2) if records else 0.0
    avg_tools = round(sum(r["metrics"].get("tool_calls", 0) for r in records) / len(records), 2) if records else 0.0
    return {
        "runs": len(records),
        "verified_runs": len(verified),
        "valid_runs": len(valid),
        "valid_rate_verified": round(len(valid) / len(verified), 3) if verified else None,
        "avg_assistant_turns": avg_turns,
        "avg_tool_calls": avg_tools,
        "provenance": dict(prov),
        "fail_reasons": {str(k): v for k, v in reasons.items() if k is not None},
    }


def _fmt_provenance(prov: dict[str, int]) -> str:
    keys = [
        "parametric",
        "tool-assisted",
        "hybrid_or_failed",
        "unverified_parametric",
        "unverified_tool_used",
    ]
    parts = [f"{k}:{prov.get(k, 0)}" for k in keys if prov.get(k, 0)]
    return ", ".join(parts) if parts else "none"


def build_markdown(summary: dict[str, Any], out_json_path: Path) -> str:
    lines: list[str] = []
    meta = summary["metadata"]
    lines.append("# Framework Comparison (Model-First)")
    lines.append("")
    lines.append(f"- Generated: `{meta['generated_at_utc']}`")
    lines.append(f"- Prompt file: `{meta['prompt_file']}`")
    lines.append(f"- Strands run_id used: `{meta['strands_run_id']}`")
    lines.append(f"- Models: {', '.join(meta['models'])}")
    lines.append(f"- Prompts: {', '.join(meta['prompt_names'])}")
    lines.append(f"- JSON summary: `{out_json_path}`")
    lines.append("")

    lines.append("## Headline")
    ov = summary["overall"]
    expected = summary["metadata"]["expected_pairs_per_framework"]
    lines.append(f"- Expected pairs per framework: `{expected}`")
    lines.append(f"- Scratch valid (verified): `{ov['scratch_valid_verified']}/{ov['scratch_verified']}`")
    lines.append(f"- Strands valid (verified): `{ov['strands_valid_verified']}/{ov['strands_verified']}`")
    lines.append(f"- Scratch unverified: `{expected - ov['scratch_verified']}`")
    lines.append(f"- Strands unverified: `{expected - ov['strands_verified']}`")
    lines.append(f"- Missing artifacts: `{len(summary['missing'])}`")
    lines.append(f"- Pairwise wins: scratch `{ov['scratch_wins']}`, strands `{ov['strands_wins']}`, ties `{ov['ties']}`")
    lines.append("")

    lines.append("## Model Summary")
    for model, data in summary["by_model"].items():
        s = data["scratch"]
        t = data["strands"]
        lines.append(f"- `{model}`: scratch `{s['valid_runs']}/{s['verified_runs']}`, strands `{t['valid_runs']}/{t['verified_runs']}`; turns scratch `{s['avg_assistant_turns']}`, strands `{t['avg_assistant_turns']}`")
        lines.append(f"  provenance scratch `{_fmt_provenance(s.get('provenance', {}))}` | strands `{_fmt_provenance(t.get('provenance', {}))}`")
    lines.append("")

    lines.append("## Notes")
    lines.append("- This report is model-primary. Framework comparison is secondary context.")
    lines.append("- Verified counts exclude prompts where `validation.valid` is `null`.")
    return "\n".join(lines) + "\n"


def build_interpretation_guide(summary: dict[str, Any], summary_path: Path, markdown_path: Path) -> str:
    meta = summary["metadata"]
    ov = summary["overall"]
    expected = meta["expected_pairs_per_framework"]
    return f"""# Evaluation Interpretation Guide

## Run Context
- Run group: `{meta.get('run_group')}`
- Generated at (UTC): `{meta.get('generated_at_utc')}`
- Prompt file: `{meta.get('prompt_file')}`
- Strands run id: `{meta.get('strands_run_id')}`
- Models: {", ".join(meta.get("models", []))}
- Prompts: {", ".join(meta.get("prompt_names", []))}

## Framework Context
- `scratch`: custom loop in `scratch_foundry/foundryAgent.py` + local tool wiring.
- `strands`: Strands agent loop with provider adapter in `strands_foundry/customprovider/`.

## Metric Glossary
- `expected_pairs_per_framework`: `#models * #prompts`.
- `verified`: rows where `validation.valid` is boolean (`true`/`false`).
- `unverified`: rows where `validation.valid` is `null` (for example canonical unavailable).
- `valid`: verified rows with `validation.valid == true`.
- `runs` (model-level): number of prompt records found for that model/framework.
- `verified_runs` (model-level): subset of `runs` with boolean validation.
- `valid_runs` (model-level): subset of `verified_runs` with `true`.
- `valid_rate_verified`: `valid_runs / verified_runs`.
- `avg_assistant_turns`: average assistant turns (loop iterations) per prompt.
- `avg_tool_calls`: average tool calls per prompt.
- `missing`: expected model/prompt records that were not produced.
- `pairwise wins`: per model+prompt comparison; framework with `valid=true` wins when the other is not `true`; otherwise tie.

## Provenance Labels
- `parametric`: no tool used; validation was boolean.
- `tool-assisted`: tool used and validation was `true`.
- `hybrid_or_failed`: tool used and validation was `false`.
- `unverified_parametric`: no tool used and validation unavailable (`null`).
- `unverified_tool_used`: tool used and validation unavailable (`null`).

## How To Read This Run
1. Open summary markdown: `{markdown_path}`
2. Open machine summary: `{summary_path}`
3. Open per-prompt metrics CSV: `analysis/turns_and_tools_*.csv`
4. Open per-model aggregates CSV: `analysis/model_aggregate_*.csv`
5. Use `missing` list + framework logs to explain data gaps.

## This Run Snapshot
- Scratch valid/verified: `{ov['scratch_valid_verified']}/{ov['scratch_verified']}`
- Strands valid/verified: `{ov['strands_valid_verified']}/{ov['strands_verified']}`
- Scratch unverified: `{expected - ov['scratch_verified']}`
- Strands unverified: `{expected - ov['strands_verified']}`
- Missing artifacts: `{len(summary['missing'])}`

## LLM Usage Notes
- Give the LLM this file plus `comparison_*.json`.
- Ask it to separate objective counts from interpretation.
- Ask it to call out unverified/missing rows before ranking models.
"""


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--models", nargs="+", required=True)
    parser.add_argument("--prompts", default="prompts.json")
    parser.add_argument(
        "--run-group",
        default="",
        help="Run group id under evaluation_results/runs/<id>. If omitted, legacy root layout is used.",
    )
    args = parser.parse_args()

    if args.run_group:
        base = Path("evaluation_results") / "runs" / args.run_group
    else:
        base = Path("evaluation_results")
    analysis_dir = base / "analysis"
    prompt_file = Path(args.prompts)

    prompt_names = load_prompts(prompt_file)
    strands_run_id, strands_meta = choose_strands_run_id(base, args.models, prompt_names)
    if not strands_run_id:
        raise RuntimeError("No eligible Strands run found for requested models/prompts.")

    rows: list[dict[str, Any]] = []
    missing: list[dict[str, Any]] = []
    for model in args.models:
        for prompt in prompt_names:
            s = load_record("scratch", base, model, prompt, None)
            t = load_record("strands", base, model, prompt, strands_run_id)
            if s is None:
                missing.append({"framework": "scratch", "model": model, "prompt": prompt})
            else:
                rows.append(s)
            if t is None:
                missing.append({"framework": "strands", "model": model, "prompt": prompt})
            else:
                rows.append(t)

    by_framework_model: dict[str, dict[str, list[dict[str, Any]]]] = {
        "scratch": defaultdict(list),
        "strands": defaultdict(list),
    }
    for r in rows:
        by_framework_model[r["framework"]][r["model"]].append(r)

    by_model: dict[str, Any] = {}
    for model in args.models:
        by_model[model] = {
            "scratch": summarize_model(by_framework_model["scratch"].get(model, [])),
            "strands": summarize_model(by_framework_model["strands"].get(model, [])),
        }

    # pairwise
    scratch_wins = strands_wins = ties = 0
    pairwise: list[dict[str, Any]] = []
    index: dict[tuple[str, str, str], dict[str, Any]] = {(r["model"], r["prompt_name"], r["framework"]): r for r in rows}
    for model in args.models:
        for prompt in prompt_names:
            s = index.get((model, prompt, "scratch"))
            t = index.get((model, prompt, "strands"))
            if not s or not t:
                continue
            sv = s["validation"].get("valid")
            tv = t["validation"].get("valid")
            if sv is True and tv is not True:
                scratch_wins += 1
            elif tv is True and sv is not True:
                strands_wins += 1
            else:
                ties += 1
            pairwise.append(
                {
                    "model": model,
                    "prompt_name": prompt,
                    "scratch_valid": sv,
                    "strands_valid": tv,
                    "scratch_reason": s["validation"].get("reason"),
                    "strands_reason": t["validation"].get("reason"),
                    "scratch_turns": s["metrics"].get("assistant_turns"),
                    "strands_turns": t["metrics"].get("assistant_turns"),
                    "scratch_tool_calls": s["metrics"].get("tool_calls"),
                    "strands_tool_calls": t["metrics"].get("tool_calls"),
                    "strands_final_text_source": t["metrics"].get("final_text_source"),
                }
            )

    scratch_verified = sum(1 for r in rows if r["framework"] == "scratch" and r["validation"].get("valid") is not None)
    strands_verified = sum(1 for r in rows if r["framework"] == "strands" and r["validation"].get("valid") is not None)
    scratch_valid_verified = sum(1 for r in rows if r["framework"] == "scratch" and r["validation"].get("valid") is True)
    strands_valid_verified = sum(1 for r in rows if r["framework"] == "strands" and r["validation"].get("valid") is True)

    generated = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    summary = {
        "metadata": {
            "generated_at_utc": generated,
            "run_group": args.run_group or None,
            "expected_pairs_per_framework": len(args.models) * len(prompt_names),
            "models": args.models,
            "prompt_names": prompt_names,
            "prompt_file": str(prompt_file),
            "strands_run_id": strands_run_id,
            "strands_run_selection": strands_meta,
        },
        "overall": {
            "scratch_verified": scratch_verified,
            "scratch_valid_verified": scratch_valid_verified,
            "strands_verified": strands_verified,
            "strands_valid_verified": strands_valid_verified,
            "scratch_wins": scratch_wins,
            "strands_wins": strands_wins,
            "ties": ties,
        },
        "by_model": by_model,
        "pairwise": pairwise,
        "missing": missing,
    }

    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    out_json = analysis_dir / f"comparison_{stamp}.json"
    out_md = analysis_dir / f"comparison_{stamp}.md"
    out_guide = analysis_dir / f"interpretation_guide_{stamp}.md"

    save_json(out_json, summary)
    (out_md).write_text(build_markdown(summary, out_json))
    (out_guide).write_text(build_interpretation_guide(summary, out_json, out_md))

    # compatibility outputs in the same base directory
    save_json(base / "latest_comparison_summary.json", summary)
    save_json(base / "latest_runtime_summary.json", {"note": "Use comparison summary metrics/tool-calls for runtime proxy in this version."})

    print(f"Wrote {out_json}")
    print(f"Wrote {out_md}")
    print(f"Wrote {out_guide}")
    print(f"Updated {base / 'latest_comparison_summary.json'}")


if __name__ == "__main__":
    main()

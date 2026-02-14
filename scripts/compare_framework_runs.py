#!/usr/bin/env python3
"""Deterministic model-first comparison across scratch and Strands evaluation artifacts.

Outputs:
- evaluation_results/latest_comparison_summary.json
- evaluation_results/latest_runtime_summary.json (placeholder-compatible structure)
- evaluation_results/analysis/comparison_<timestamp>.json
- evaluation_results/analysis/comparison_<timestamp>.md
- evaluation_results/analysis/llm_report_prompt_<timestamp>.md
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
    lines.append(f"- Scratch valid (verified): `{ov['scratch_valid_verified']}/{ov['scratch_verified']}`")
    lines.append(f"- Strands valid (verified): `{ov['strands_valid_verified']}/{ov['strands_verified']}`")
    lines.append(f"- Pairwise wins: scratch `{ov['scratch_wins']}`, strands `{ov['strands_wins']}`, ties `{ov['ties']}`")
    lines.append("")

    lines.append("## Model Summary")
    for model, data in summary["by_model"].items():
        s = data["scratch"]
        t = data["strands"]
        lines.append(f"- `{model}`: scratch `{s['valid_runs']}/{s['verified_runs']}`, strands `{t['valid_runs']}/{t['verified_runs']}`; turns scratch `{s['avg_assistant_turns']}`, strands `{t['avg_assistant_turns']}`")
    lines.append("")

    lines.append("## Notes")
    lines.append("- This report is model-primary. Framework comparison is secondary context.")
    lines.append("- Verified counts exclude prompts where `validation.valid` is `null`.")
    return "\n".join(lines) + "\n"


def build_llm_prompt(summary_path: Path, markdown_path: Path) -> str:
    return f"""# Task: Generate Standardized Evaluation Report

You are given a deterministic JSON comparison summary at:
`{summary_path}`

There is also a concise markdown snapshot at:
`{markdown_path}`

## Objective
Write a model-first report that:
1. Ranks models by verified correctness and robustness.
2. Explains framework effects (scratch vs strands) as secondary analysis.
3. Separates parametric vs tool-assisted behavior.
4. Highlights surprising patterns and likely root causes.
5. Distinguishes objective findings from interpretation.

## Required Structure
- Executive Summary
- Model-by-Model Findings
- Framework Effects (Secondary)
- Failure Modes and Root Causes
- Recommendations for Next Experiment

## Guardrails
- Use exact numbers from JSON.
- Do not invent data not present in artifacts.
- Explicitly call out unverified prompts (`validation.valid = null`) separately.
"""


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--models", nargs="+", required=True)
    parser.add_argument("--prompts", default="prompts.json")
    args = parser.parse_args()

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
    out_prompt = analysis_dir / f"llm_report_prompt_{stamp}.md"

    save_json(out_json, summary)
    (out_md).write_text(build_markdown(summary, out_json))
    (out_prompt).write_text(build_llm_prompt(out_json, out_md))

    # compatibility outputs
    save_json(base / "latest_comparison_summary.json", summary)
    save_json(base / "latest_runtime_summary.json", {"note": "Use comparison summary metrics/tool-calls for runtime proxy in this version."})

    print(f"Wrote {out_json}")
    print(f"Wrote {out_md}")
    print(f"Wrote {out_prompt}")
    print("Updated evaluation_results/latest_comparison_summary.json")


if __name__ == "__main__":
    main()

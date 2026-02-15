#!/usr/bin/env python3
"""Export easy-to-scan CSV tables from a comparison summary JSON."""

from __future__ import annotations

import argparse
import csv
import glob
import json
from pathlib import Path


def latest_comparison_json(base: Path) -> Path:
    files = sorted(glob.glob(str(base / "analysis" / "comparison_*.json")))
    if not files:
        raise FileNotFoundError(f"No comparison JSON found in {base / 'analysis'}")
    return Path(files[-1])


def load_json(path: Path) -> dict:
    with path.open() as f:
        return json.load(f)


def write_pairwise_csv(data: dict, out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "model",
        "prompt_name",
        "scratch_valid",
        "strands_valid",
        "scratch_reason",
        "strands_reason",
        "scratch_turns",
        "strands_turns",
        "scratch_tool_calls",
        "strands_tool_calls",
        "strands_final_text_source",
    ]
    with out_path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for row in data.get("pairwise", []):
            w.writerow({k: row.get(k) for k in fields})


def write_model_csv(data: dict, out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "model",
        "scratch_valid_runs",
        "scratch_verified_runs",
        "scratch_valid_rate_verified",
        "scratch_avg_assistant_turns",
        "scratch_avg_tool_calls",
        "strands_valid_runs",
        "strands_verified_runs",
        "strands_valid_rate_verified",
        "strands_avg_assistant_turns",
        "strands_avg_tool_calls",
    ]
    with out_path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for model, rec in data.get("by_model", {}).items():
            s = rec.get("scratch", {})
            t = rec.get("strands", {})
            w.writerow(
                {
                    "model": model,
                    "scratch_valid_runs": s.get("valid_runs"),
                    "scratch_verified_runs": s.get("verified_runs"),
                    "scratch_valid_rate_verified": s.get("valid_rate_verified"),
                    "scratch_avg_assistant_turns": s.get("avg_assistant_turns"),
                    "scratch_avg_tool_calls": s.get("avg_tool_calls"),
                    "strands_valid_runs": t.get("valid_runs"),
                    "strands_verified_runs": t.get("verified_runs"),
                    "strands_valid_rate_verified": t.get("valid_rate_verified"),
                    "strands_avg_assistant_turns": t.get("avg_assistant_turns"),
                    "strands_avg_tool_calls": t.get("avg_tool_calls"),
                }
            )


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--comparison", default="", help="Path to comparison JSON. Defaults to latest in analysis folder.")
    p.add_argument(
        "--run-group",
        default="",
        help="Run group id under evaluation_results/runs/<id>. If omitted, legacy root layout is used.",
    )
    args = p.parse_args()

    base = Path("evaluation_results") / "runs" / args.run_group if args.run_group else Path("evaluation_results")
    comparison_path = Path(args.comparison) if args.comparison else latest_comparison_json(base)
    data = load_json(comparison_path)

    stem = comparison_path.stem.replace("comparison_", "")
    out_pairwise = base / "analysis" / f"turns_and_tools_{stem}.csv"
    out_model = base / "analysis" / f"model_aggregate_{stem}.csv"

    write_pairwise_csv(data, out_pairwise)
    write_model_csv(data, out_model)

    print(f"comparison_json={comparison_path}")
    print(f"pairwise_csv={out_pairwise}")
    print(f"model_csv={out_model}")


if __name__ == "__main__":
    main()

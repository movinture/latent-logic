#!/usr/bin/env python3
"""Build a run-scoped LLM analysis package with context, artifacts, and logs.

This script does not compute metrics. It only packages existing artifacts.
"""

from __future__ import annotations

import argparse
import glob
import shutil
from datetime import datetime, timezone
from pathlib import Path


def latest_file(pattern: str) -> Path | None:
    files = sorted(glob.glob(pattern))
    return Path(files[-1]) if files else None


def must_exist(path: Path, description: str) -> None:
    if not path.exists():
        raise FileNotFoundError(f"{description} not found: {path}")


def copy_if_exists(src: Path, dst_dir: Path) -> bool:
    if src.exists():
        shutil.copy2(src, dst_dir / src.name)
        return True
    return False


def build_brief(run_group: str) -> str:
    return f"""# LLM Analysis Brief

## Project Context
You are analyzing an experiment from **Latent Logic**.

Primary goal:
- Compare model capabilities in reasoning, planning, tool use, and parametric knowledge.

Secondary goal:
- Compare how two agentic loop frameworks affect outcomes.
  - `scratch`: custom minimal loop
  - `strands`: Strands framework loop with Foundry custom provider

Tooling context:
- Agents receive primitive tool capability (primarily HTTP requests).
- API endpoint choice and request construction are generally model-driven.

## Required Analysis Behavior
1. Prioritize model-to-model comparison first.
2. Treat framework effects as secondary analysis.
3. Separate objective facts from interpretation.
4. Explicitly call out:
   - unverified rows
   - missing artifacts
   - canonical/source limitations
5. Use glossary definitions exactly.

## Recommended Report Structure
1. Executive Summary
2. Objective Scoreboard (model ranking by validated performance)
3. Prompt-Type Breakdown
4. Tool/Turn Behavior Analysis
5. Provenance Analysis (parametric vs tool-assisted)
6. Framework Effects (secondary)
7. Failure Modes + Root Causes
8. Recommendations for next run

## Run Group
- `{run_group}`

## Attached Files (Priority Order, <=10 Total)
1. `comparison_<timestamp>.json`
2. `turns_and_tools_<timestamp>.csv`
3. `model_aggregate_<timestamp>.csv`
4. `LLM_CONTEXT_BUNDLE.md`
5. `manifest.json`
6. `canonical_<prompt_version>.json`
7. `scratch_evaluation.log`
8. `strands_evaluation.log`
9. `comparison_<timestamp>.md`

## File Meanings (Do Not Guess)
- `comparison_<timestamp>.json`:
  - Primary machine-readable source of truth for summary metrics, model aggregates, pairwise rows, and missing rows.
- `turns_and_tools_<timestamp>.csv`:
  - Prompt-level behavior table. Use for tool-call and turn-count analysis by model/prompt.
- `model_aggregate_<timestamp>.csv`:
  - Model-level aggregate table for quick ranking checks.
- `comparison_<timestamp>.md`:
  - Human-readable summary derived from JSON; use as convenience only.
- `manifest.json`:
  - Run metadata (framework, models, prompts file/version, start times).
- `canonical_<prompt_version>.json`:
  - Canonical snapshot and canonical availability/errors; use to explain unverified rows.
- `scratch_evaluation.log` / `strands_evaluation.log`:
  - Execution traces and errors; use for root-cause analysis, not primary scoring.
- `LLM_CONTEXT_BUNDLE.md`:
  - Consolidated context file that includes:
    - interpretation guidance for this run
    - evaluation glossary terms
    - review workflow
    - relevant extracts from evaluation plan and technical notes

## Source-of-Truth Hierarchy
- For numeric conclusions: `comparison_<timestamp>.json` first, then CSVs.
- For terminology and method: `LLM_CONTEXT_BUNDLE.md` first.
- For run context: `manifest.json`, then `interpretation_guide_<timestamp>.md`.
- For causal explanations of failures: logs + canonical snapshot.
- For architectural rationale: use the technical section inside `LLM_CONTEXT_BUNDLE.md`.

## How To Use Bigger Docs Without Drifting
- Use `LLM_CONTEXT_BUNDLE.md` instead of attaching multiple long docs.
- Treat planning/architecture text as context only; do not convert it into measured outcomes.

## Output Constraints
- Start with objective findings and exact counts.
- Then provide interpretations and hypotheses, clearly labeled as interpretation.
- Flag data quality limits:
  - unverified rows
  - missing artifacts
  - canonical outages
"""


def build_attachment_list(copied: list[str], recommended: list[str]) -> str:
    lines = ["# Attachment List", "", "Attach these files to your LLM session:"]
    for name in recommended:
        lines.append(f"- `{name}`")
    lines.append("")
    lines.append("Optional supporting files copied into this packet (attach only if needed):")
    for name in copied:
        if name not in recommended:
            lines.append(f"- `{name}`")
    lines.append("")
    return "\n".join(lines)


def build_context_bundle(
    interpretation_text: str,
    glossary_text: str,
    review_text: str,
    eval_plan_text: str,
    technical_notes_text: str,
) -> str:
    return f"""# LLM Context Bundle

This file consolidates evaluation context to reduce attachment count limits.

## Section A: Run Interpretation Guide

{interpretation_text}

## Section B: Evaluation Glossary

{glossary_text}

## Section C: Results Review Workflow

{review_text}

## Section D: Evaluation Plan (Relevant Context)

Use this section for experiment intent and rubric framing.
Do not treat this section as measured outcome data.

{eval_plan_text}

## Section E: Technical Notes (Relevant Context)

Use this section for architecture/mechanism explanation only.
Do not infer performance ranking from architecture text.

{technical_notes_text}
"""


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--run-group", required=True, help="Run group id under evaluation_results/runs/<id>")
    args = p.parse_args()

    run_dir = Path("evaluation_results") / "runs" / args.run_group
    analysis_dir = run_dir / "analysis"
    must_exist(run_dir, "Run directory")
    must_exist(analysis_dir, "Analysis directory")

    comparison_json = latest_file(str(analysis_dir / "comparison_*.json"))
    comparison_md = latest_file(str(analysis_dir / "comparison_*.md"))
    interpretation_md = latest_file(str(analysis_dir / "interpretation_guide_*.md"))
    turns_csv = latest_file(str(analysis_dir / "turns_and_tools_*.csv"))
    model_csv = latest_file(str(analysis_dir / "model_aggregate_*.csv"))

    must_exist(comparison_json, "Latest comparison JSON")
    must_exist(comparison_md, "Latest comparison markdown")

    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    packet_dir = analysis_dir / f"llm_analysis_packet_{stamp}"
    packet_dir.mkdir(parents=True, exist_ok=True)

    copied: list[str] = []

    for src in [comparison_json, comparison_md, interpretation_md, turns_csv, model_csv]:
        if src and copy_if_exists(src, packet_dir):
            copied.append(src.name)

    # Run-level context
    interpretation_text = ""
    for src in [
        run_dir / "manifest.json",
        latest_file(str(run_dir / "canonical" / "canonical_*.json")),
        run_dir / "logs" / "scratch_evaluation.log",
        run_dir / "logs" / "strands_evaluation.log",
        run_dir / "latest_comparison_summary.json",
    ]:
        if src and copy_if_exists(src, packet_dir):
            copied.append(src.name)

    # Build one consolidated context file (instead of attaching many docs)
    if interpretation_md and interpretation_md.exists():
        interpretation_text = interpretation_md.read_text()

    glossary = Path("docs/EVALUATION_GLOSSARY.md")
    review = Path("docs/RESULTS_REVIEW_GUIDE.md")
    eval_plan = Path("docs/EVALUATION_PLAN.md")
    technical_notes = Path("docs/TECHNICAL_NOTES.md")

    glossary_text = glossary.read_text() if glossary.exists() else "_Missing: docs/EVALUATION_GLOSSARY.md_"
    review_text = review.read_text() if review.exists() else "_Missing: docs/RESULTS_REVIEW_GUIDE.md_"
    eval_plan_text = eval_plan.read_text() if eval_plan.exists() else "_Missing: docs/EVALUATION_PLAN.md_"
    technical_notes_text = technical_notes.read_text() if technical_notes.exists() else "_Missing: docs/TECHNICAL_NOTES.md_"

    (packet_dir / "LLM_CONTEXT_BUNDLE.md").write_text(
        build_context_bundle(
            interpretation_text,
            glossary_text,
            review_text,
            eval_plan_text,
            technical_notes_text,
        )
    )
    copied.append("LLM_CONTEXT_BUNDLE.md")

    # Prompt + attachment checklist
    (packet_dir / "LLM_ANALYSIS_BRIEF.md").write_text(build_brief(args.run_group))
    copied.append("LLM_ANALYSIS_BRIEF.md")

    recommended = [
        comparison_json.name,
        turns_csv.name if turns_csv else "",
        model_csv.name if model_csv else "",
        "LLM_CONTEXT_BUNDLE.md",
        "manifest.json",
        (latest_file(str(run_dir / "canonical" / "canonical_*.json")).name if latest_file(str(run_dir / "canonical" / "canonical_*.json")) else ""),
        "scratch_evaluation.log",
        "strands_evaluation.log",
        comparison_md.name,
    ]
    recommended = [x for x in recommended if x]
    (packet_dir / "ATTACHMENT_LIST.md").write_text(build_attachment_list(sorted(copied), recommended))
    copied.append("ATTACHMENT_LIST.md")

    print(f"Wrote {packet_dir}")
    print("Included files:")
    for name in sorted(copied):
        print(f"- {name}")


if __name__ == "__main__":
    main()

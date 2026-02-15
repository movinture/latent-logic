# Results Review Guide

Use this flow after each run group.

## 1) Start With Run Metadata
- Open `evaluation_results/runs/<run_group>/manifest.json`.
- Confirm:
  - models included
  - prompts file/version
  - both frameworks executed

## 2) Read Human Summary
- Open the newest file:
  - `evaluation_results/runs/<run_group>/analysis/comparison_<timestamp>.md`
- This gives headline validity, pairwise wins, and per-model summaries.

## 3) Use Glossary Before Judging
- Open `docs/EVALUATION_GLOSSARY.md`.
- Align terminology first:
  - verified vs unverified
  - valid vs invalid
  - missing
  - provenance labels

## 4) Inspect Prompt-Level Behavior
- Open:
  - `evaluation_results/runs/<run_group>/analysis/turns_and_tools_<timestamp>.csv`
- Use this to answer:
  - Which prompts needed more loop turns?
  - Which prompts triggered more tool calls?
  - Which prompts failed even after tool usage?

## 5) Inspect Model-Level Behavior
- Open:
  - `evaluation_results/runs/<run_group>/analysis/model_aggregate_<timestamp>.csv`
- Compare models on:
  - `valid_runs / verified_runs`
  - `avg_assistant_turns`
  - `avg_tool_calls`
  - provenance mix

## 6) Explain Gaps
- If `missing > 0`, inspect:
  - `evaluation_results/runs/<run_group>/logs/scratch_evaluation.log`
  - `evaluation_results/runs/<run_group>/logs/strands_evaluation.log`
- If unverified is high, inspect canonical snapshot:
  - `evaluation_results/runs/<run_group>/canonical/canonical_<prompt_version>.json`

## 7) LLM-Assisted Analysis Pack
Give the LLM these files together:
- `comparison_<timestamp>.json`
- `comparison_<timestamp>.md`
- `interpretation_guide_<timestamp>.md`
- `docs/EVALUATION_GLOSSARY.md`

Ask the LLM to:
- report objective counts first
- separate facts from interpretation
- call out unverified and missing rows before ranking models

# Evaluation Glossary

This glossary defines the metrics and labels used by the evaluation outputs so results are interpreted consistently.

## Scope Terms
- `run_group`: A single experiment cohort folder, for example `evaluation_results/runs/Run001_02142026/`.
- `framework`: One of:
  - `scratch` (custom loop in this repo)
  - `strands` (Strands loop with Foundry custom provider)
- `pair`: One `(model, prompt)` combination for one framework.

## Coverage Terms
- `expected_pairs_per_framework`: Number of models multiplied by number of prompts.
- `runs` (model summary): Number of result/validation records actually found for that model and framework.
- `missing`: Expected `(framework, model, prompt)` entries where artifacts were not found.

## Validation Terms
- `validation.valid`:
  - `true`: validated correct against canonical source and tolerance.
  - `false`: validated incorrect.
  - `null`: unverified (validator could not score, usually canonical unavailable).
- `verified`: Rows where `validation.valid` is boolean.
- `unverified`: Rows where `validation.valid` is `null`.
- `verified_runs`: Model-level count of verified rows.
- `valid_runs`: Model-level count where `validation.valid == true`.
- `valid_rate_verified`: `valid_runs / verified_runs`.

## Pairwise Comparison Terms
- `pairwise wins`: For each shared `(model, prompt)` across frameworks:
  - Scratch win: scratch is `true` and strands is not `true`.
  - Strands win: strands is `true` and scratch is not `true`.
  - Tie: all other cases (both `true`, both `false`, or both unverified).
- `ties`: Count of tie cases.

## Interaction/Behavior Terms
- `avg_assistant_turns`: Average number of assistant loop turns per prompt.
- `avg_tool_calls`: Average number of tool calls per prompt.
- `tool_used`: Whether at least one tool call was detected in the trace.
- `tool_names`: Distinct tools detected for that record.

## Provenance Labels
- `parametric`: No tool used and validation was boolean.
- `tool-assisted`: Tool used and validation is `true`.
- `hybrid_or_failed`: Tool used and validation is `false`.
- `unverified_parametric`: No tool used and validation is `null`.
- `unverified_tool_used`: Tool used and validation is `null`.

## Why Unverified Happens
- Canonical provider timeout/outage.
- Missing canonical key/config.
- Prompt type without implemented validator.

## Where To Read Results
- Human summary: `evaluation_results/runs/<run_group>/analysis/comparison_<timestamp>.md`
- Machine summary: `evaluation_results/runs/<run_group>/analysis/comparison_<timestamp>.json`
- Interpretation guide: `evaluation_results/runs/<run_group>/analysis/interpretation_guide_<timestamp>.md`
- Prompt-level behavior table: `evaluation_results/runs/<run_group>/analysis/turns_and_tools_<timestamp>.csv`
- Model-level aggregate table: `evaluation_results/runs/<run_group>/analysis/model_aggregate_<timestamp>.csv`

# Evaluation Plan for LLM Comparison

This document describes the current evaluation workflow to compare model capabilities (reasoning, tool use, recovery, and parametric knowledge) across both agent loops.

### 1. Define a Standardized Test Suite

Prompts are externalized in `prompts.json` (versioned). Current suite includes:

*   `current_weather_new_york_city` (`type: weather`)
*   `current_temperature_new_york_city` (`type: temperature`)
*   `lat_lon_times_square` (`type: location`)
*   `lat_lon_bluebells_school_delhi` (`type: location`, esoteric variant)
*   `iss_current_position` (`type: iss`)
*   `usd_eur_exchange_rate` (`type: exchange_rate`)

The suite intentionally mixes:
*   common vs esoteric location queries
*   static-ish vs highly dynamic data
*   direct retrieval vs multi-step tool behavior

### 2. Create a Standardized Evaluation Rubric

Rubric scoring is still planned (manual/subjective today). Current automated validation provides objective signals; rubric adds subjective quality grading.

**Evaluation Criteria:**

*   **Tool Use (1-5):**
    *   1: Fails to use any tool.
    *   3: Uses a tool, but with incorrect arguments or in an incorrect way.
    *   5: Correctly identifies and uses the right tool with the correct arguments.

*   **Error Handling (1-5):**
    *   1: Fails completely on error.
    *   3: Reports the error but doesn't try to recover.
    *   5: Gracefully handles the error and tries an alternative approach.

*   **Parametric Knowledge (1-5):**
    *   1: Shows no knowledge of the world or available tools.
    *   3: Shows some knowledge, but makes suboptimal choices (e.g., trying to use a private API without a key).
    *   5: Demonstrates excellent knowledge and makes smart choices (e.g., using a public API).

*   **Reasoning and Problem-Solving (1-5):**
    *   1: Shows no reasoning or problem-solving skills.
    *   3: Shows some reasoning, but gets stuck or needs guidance.
    *   5: Demonstrates excellent reasoning and can solve the problem autonomously.

*   **Response Quality (1-5):**
    *   1: The final response is unhelpful or poorly formatted.
    *   3: The response is helpful but could be better formatted or more concise.
    *   5: The response is clear, concise, well-formatted, and directly answers the user's question.

### 3. Create Standardized Test Scripts

We have two evaluation harnesses:

1. `scratch_foundry/run_evaluation.py` for the scratch Foundry agent loop.
2. `strands_foundry/run_strands_evaluation.py` for the Strands-based loop.

Both scripts:

1.  Takes a list of model names as a command-line argument.
2.  Runs each prompt in the test suite against each model.
3.  Supports `--run-group <id>` and writes all artifacts into one run folder: `evaluation_results/runs/<id>/...`.
4.  Saves the full conversation log for each model/prompt to JSON files in `evaluation_results/runs/<id>/scratch/` or `evaluation_results/runs/<id>/strands/`.
5.  Writes per-run logs to `evaluation_results/runs/<id>/logs/`.
6.  Loads prompts from `prompts.json` by default (configurable with `--prompts`).
7.  Produces a canonical snapshot per run in `evaluation_results/runs/<id>/canonical/`.
8.  Produces a sidecar validation file per prompt with provenance + verification fields.
9.  Adds run metadata (`run_group`, `started_at_human`, `started_at_utc`) to output JSON.
10. Updates `evaluation_results/runs/<id>/manifest.json` with framework-level run metadata.

Canonical providers currently used:
*   Location: Google Geocoding
*   Weather/Temperature: OpenWeather
*   ISS: `wheretheiss.at`
*   FX: `open.er-api.com`

ISS validation is time-aware (nearest/interpolated canonical position with dynamic distance allowance).  
Sidecars also include:
*   `eval_time_unix`
*   `data_hints` (tool URLs + date/time hints extracted from tool I/O)

### 4. Analyze the Results

Use deterministic comparison tooling first, then optional subjective analysis.

1. Deterministic comparison:
*   `scripts/compare_framework_runs.py`
*   Produces:
    * `evaluation_results/runs/<id>/latest_comparison_summary.json`
    * `evaluation_results/runs/<id>/analysis/comparison_<timestamp>.json`
    * `evaluation_results/runs/<id>/analysis/comparison_<timestamp>.md`
    * `evaluation_results/runs/<id>/analysis/interpretation_guide_<timestamp>.md` (definitions + how to read)

2. CSV exports for easier scanning:
*   `scripts/export_comparison_tables.py`
*   Produces:
    * `evaluation_results/runs/<id>/analysis/turns_and_tools_<timestamp>.csv`
    * `evaluation_results/runs/<id>/analysis/model_aggregate_<timestamp>.csv`

3. Subjective/rubric pass (optional):
*   Use generated artifacts to evaluate response quality, reasoning style, and notable behavioral patterns.
*   Use `docs/EVALUATION_GLOSSARY.md` for consistent terminology in human and LLM analysis.
*   Use `docs/RESULTS_REVIEW_GUIDE.md` as the standard review sequence.

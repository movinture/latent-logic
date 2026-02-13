# Model Insights (Capability Cards)

## Data Tag
- Evaluation tag: `latent-logic_eval_2026-02-12_nyc-weather-times-square_v2026-02-12`
- Prompt set: `prompts.json` (version `2026-02-12`)
- Prompts:
  - `current_weather_new_york_city`
  - `lat_lon_times_square`
- Frameworks compared:
  - Scratch: `scratch_foundry/run_evaluation.py`
  - Strands: `strands_foundry/run_strands_evaluation.py`
- Models included:
  - `gpt-4.1-mini`, `DeepSeek-V3.2`, `grok-4-fast-reasoning`, `Kimi-K2-Thinking`, `Kimi-K2.5`, `gpt-4o`, `Mistral-Large-3`, `gpt-4.1`
- Canonical snapshot: `evaluation_results/canonical/canonical_2026-02-12.json`
- Logs used:
  - `logs/scratch_evaluation.log`
  - `logs/strands_evaluation.log`
- Generated summaries used:
  - `evaluation_results/latest_comparison_summary.json`
  - `evaluation_results/latest_runtime_summary.json`
- Scope caveat:
  - This reflects one run on two prompts. Treat as operational tool-use signal, not a broad intelligence benchmark.

## Scorecard Snapshot
- Overall valid outputs:
  - Scratch: `12/16`
  - Strands: `13/16`
- Pairwise head-to-head (16 model-prompt pairs):
  - Scratch wins: `1`
  - Strands wins: `2`
  - Ties: `13`

## Capability Cards

### Kimi-K2.5
- Result: `4/4` valid (Scratch `2/2`, Strands `2/2`).
- Tool reasoning: reliable and concise, mostly one tool call then answer.
- Recovery behavior: stable, little churn.
- Efficiency: Scratch avg `8.37s`; Strands avg `9.64s`.
- Verdict: best all-around stability in this run.
- Evidence:
  - `evaluation_results/scratch/Kimi-K2.5/current_weather_new_york_city_validation.json`
  - `evaluation_results/strands/Kimi-K2.5/current_weather_new_york_city_20260212_193350_validation.json`

### gpt-4.1
- Result: `4/4` valid.
- Tool reasoning: strong mixed behavior; uses parametric coordinates where appropriate.
- Recovery behavior: not heavily dependent on retries.
- Efficiency: Scratch avg `1.64s`; Strands avg `1.47s`.
- Verdict: fast and consistent; strong baseline model.
- Evidence:
  - `evaluation_results/scratch/gpt-4.1/lat_lon_times_square_validation.json`
  - `evaluation_results/strands/gpt-4.1/lat_lon_times_square_20260212_193350_validation.json`

### gpt-4.1-mini
- Result: `4/4` valid.
- Tool reasoning: high compliance, including multi-step location flow when needed.
- Recovery behavior: good loop completion under both frameworks.
- Efficiency: Scratch avg `4.17s`; Strands avg `4.00s`.
- Verdict: very strong value profile for this benchmark.
- Evidence:
  - `evaluation_results/scratch/gpt-4.1-mini/lat_lon_times_square_validation.json`
  - `evaluation_results/strands/gpt-4.1-mini/lat_lon_times_square_20260212_193350_validation.json`

### grok-4-fast-reasoning
- Result: `4/4` valid.
- Tool reasoning: strong tool usage and final answer quality.
- Recovery behavior: can take longer paths in Strands for location.
- Efficiency: Scratch avg `11.77s`; Strands avg `14.39s` with a long outlier on location.
- Verdict: high capability, higher latency variance.
- Evidence:
  - `evaluation_results/scratch/grok-4-fast-reasoning/lat_lon_times_square_validation.json`
  - `evaluation_results/strands/grok-4-fast-reasoning/lat_lon_times_square_20260212_193350_validation.json`

### gpt-4o
- Result: `3/4` valid (Scratch `1/2`, Strands `2/2`).
- Tool reasoning: framework-sensitive in this run.
- Recovery behavior: Scratch weather path failed after invalid-key response; Strands weather succeeded with correct auth path.
- Efficiency: Scratch avg `1.68s`; Strands avg `2.54s`.
- Verdict: capable, but prompt/tool wiring sensitivity showed up.
- Evidence:
  - Scratch invalid-key pattern: `evaluation_results/scratch/gpt-4o/current_weather_new_york_city.json:21`
  - Strands success: `evaluation_results/strands/gpt-4o/current_weather_new_york_city_20260212_193350_validation.json`

### Mistral-Large-3
- Result: `3/4` valid (Scratch `1/2`, Strands `2/2`).
- Tool reasoning: can recover by switching strategy.
- Recovery behavior: Strands weather flow recovered from failed OpenWeather call to alternate source; scratch weather stopped at invalid key.
- Efficiency: Scratch avg `3.75s`; Strands avg `2.89s`.
- Verdict: medium reliability with strong upside when loop supports fallback behavior.
- Evidence:
  - Strands fallback sequence: `evaluation_results/strands/Mistral-Large-3/current_weather_new_york_city_20260212_193350.json`
  - Scratch weather failure: `evaluation_results/scratch/Mistral-Large-3/current_weather_new_york_city.json`

### Kimi-K2-Thinking
- Result: `3/4` valid (Scratch `2/2`, Strands `1/2`).
- Tool reasoning: generally strong; one Strands location failure appears to be output-shape extraction issue.
- Recovery behavior: Strands weather run had tool registry error signal.
- Efficiency: Scratch avg `13.36s`; Strands avg `7.03s`.
- Verdict: reasoning is good, but integration/output-shape robustness needs hardening.
- Evidence:
  - Empty `final_text` despite coordinate answer in reasoning: `evaluation_results/strands/Kimi-K2-Thinking/lat_lon_times_square_20260212_193350.json:19`
  - Tool registry error in log: `logs/strands_evaluation.log:39`

### DeepSeek-V3.2
- Result: `0/4` valid.
- Tool reasoning: weakest in this benchmark.
- Recovery behavior: often did not execute a usable tool call path.
- Efficiency: fast but unhelpful (Scratch avg `3.95s`; Strands avg `1.43s`).
- Verdict: currently not reliable for this tool-use task without model-specific adaptation.
- Evidence:
  - Scratch emitted fenced JSON tool intent but no executable call: `evaluation_results/scratch/DeepSeek-V3.2/current_weather_new_york_city.json:11`
  - Strands no-tool answer: `evaluation_results/strands/DeepSeek-V3.2/current_weather_new_york_city_20260212_193350.json`

## Good / Bad / Ugly (This Run)
- Good:
  - `Kimi-K2.5`, `gpt-4.1`, `gpt-4.1-mini`, `grok-4-fast-reasoning`
- Bad (inconsistent, not broken):
  - `gpt-4o`, `Mistral-Large-3`, `Kimi-K2-Thinking`
- Ugly:
  - `DeepSeek-V3.2`

## How To Update This File
- Keep using `docs/MODEL_INSIGHTS.md` as the main rolling capability card.
- Append a new `Data Tag` block and refreshed cards for each major run cohort.
- Keep prior run sections for drift tracking instead of replacing history.

## Run Template

Use this template for each new evaluation cohort.

```md
## Data Tag
- Evaluation tag: `<project>_eval_<YYYY-MM-DD>_<scenario>_v<prompt-version>`
- Prompt set: `<path>` (version `<version>`)
- Prompts:
  - `<prompt_name_1>`
  - `<prompt_name_2>`
- Frameworks compared:
  - Scratch: `<script path>`
  - Strands: `<script path>`
- Models included:
  - `<model_1>`, `<model_2>`, ...
- Canonical snapshot: `<path>`
- Logs used:
  - `<path>`
  - `<path>`
- Generated summaries used:
  - `<path>`
  - `<path>`
- Scope caveat:
  - `<single-run caveat and benchmark limits>`

## Scorecard Snapshot
- Overall valid outputs:
  - Scratch: `<x>/<n>`
  - Strands: `<y>/<n>`
- Pairwise head-to-head (`<n>` model-prompt pairs):
  - Scratch wins: `<count>`
  - Strands wins: `<count>`
  - Ties: `<count>`

## Capability Cards

### <Model Name>
- Result: `<valid_total>/<total>` (Scratch `<a>/<b>`, Strands `<c>/<d>`).
- Tool reasoning: `<short assessment>`.
- Recovery behavior: `<short assessment>`.
- Efficiency: Scratch avg `<x>s`; Strands avg `<y>s`.
- Verdict: `<one-line judgment>`.
- Evidence:
  - `<result/validation path>`
  - `<result/validation path>`

### <Model Name>
- Result: ...

## Good / Bad / Ugly (This Run)
- Good:
  - `<model>`, `<model>`
- Bad (inconsistent, not broken):
  - `<model>`, `<model>`
- Ugly:
  - `<model>`

## Notes For Next Run
- `<what to change in prompts/tools/rubric>`
- `<which model-specific issue to test>`
```


## Run Update: `latent-logic_eval_2026-02-12_autofill_demo`

### Data Tag
- Evaluation tag: `latent-logic_eval_2026-02-12_autofill_demo`
- Prompt set: `prompts.json` (version `2026-02-12`)
- Prompts:
  - `current_weather_new_york_city`
  - `lat_lon_times_square`
- Frameworks compared:
  - Scratch: `scratch_foundry/run_evaluation.py`
  - Strands: `strands_foundry/run_strands_evaluation.py`
- Canonical snapshot: `evaluation_results/canonical/canonical_2026-02-12.json`
- Generated summaries used:
  - `evaluation_results/latest_comparison_summary.json`
  - `evaluation_results/latest_runtime_summary.json`
- Scope caveat:
  - Single cohort; treat as operational tool-use signal, not broad capability ranking.

### Scorecard Snapshot
- Overall valid outputs:
  - Scratch: `12/16`
  - Strands: `13/16`
- Pairwise head-to-head (`16` model-prompt pairs):
  - Scratch wins: `1`
  - Strands wins: `2`
  - Ties: `13`

### Capability Cards

#### DeepSeek-V3.2
- Result: `0/4` valid (Scratch `0/2`, Strands `0/2`).
- Tool profile: scratch `limited tool execution` (avg tool calls `0.0`), strands `mostly parametric` (avg tool calls `0.0`).
- Runtime: scratch avg `3.95s`, strands avg `1.43s`.
- Failure signals: scratch `no_coordinates_found:1`, strands `no_temperature_found:1, no_coordinates_found:1`.
- Verdict: `Weak`.

#### Kimi-K2-Thinking
- Result: `3/4` valid (Scratch `2/2`, Strands `1/2`).
- Tool profile: scratch `multi-step tool use` (avg tool calls `1.5`), strands `multi-step tool use` (avg tool calls `1.5`).
- Runtime: scratch avg `13.36s`, strands avg `7.03s`.
- Failure signals: scratch `none`, strands `no_coordinates_found:1`.
- Verdict: `Mostly Strong`.

#### Kimi-K2.5
- Result: `4/4` valid (Scratch `2/2`, Strands `2/2`).
- Tool profile: scratch `single-step tool use` (avg tool calls `1.0`), strands `single-step tool use` (avg tool calls `1.0`).
- Runtime: scratch avg `8.37s`, strands avg `9.64s`.
- Failure signals: scratch `none`, strands `none`.
- Verdict: `Strong`.

#### Mistral-Large-3
- Result: `3/4` valid (Scratch `1/2`, Strands `2/2`).
- Tool profile: scratch `multi-step tool use` (avg tool calls `2.0`), strands `single-step tool use` (avg tool calls `1.0`).
- Runtime: scratch avg `3.75s`, strands avg `2.89s`.
- Failure signals: scratch `no_temperature_found:1`, strands `none`.
- Verdict: `Mostly Strong`.

#### gpt-4.1
- Result: `4/4` valid (Scratch `2/2`, Strands `2/2`).
- Tool profile: scratch `single-step tool use` (avg tool calls `0.5`), strands `single-step tool use` (avg tool calls `0.5`).
- Runtime: scratch avg `1.64s`, strands avg `1.47s`.
- Failure signals: scratch `none`, strands `none`.
- Verdict: `Strong`.

#### gpt-4.1-mini
- Result: `4/4` valid (Scratch `2/2`, Strands `2/2`).
- Tool profile: scratch `multi-step tool use` (avg tool calls `1.5`), strands `multi-step tool use` (avg tool calls `1.5`).
- Runtime: scratch avg `4.17s`, strands avg `4.0s`.
- Failure signals: scratch `none`, strands `none`.
- Verdict: `Strong`.

#### gpt-4o
- Result: `3/4` valid (Scratch `1/2`, Strands `2/2`).
- Tool profile: scratch `single-step tool use` (avg tool calls `0.5`), strands `single-step tool use` (avg tool calls `0.5`).
- Runtime: scratch avg `1.68s`, strands avg `2.54s`.
- Failure signals: scratch `no_temperature_found:1`, strands `none`.
- Verdict: `Mostly Strong`.

#### grok-4-fast-reasoning
- Result: `4/4` valid (Scratch `2/2`, Strands `2/2`).
- Tool profile: scratch `single-step tool use` (avg tool calls `1.0`), strands `multi-step tool use` (avg tool calls `1.5`).
- Runtime: scratch avg `11.77s`, strands avg `14.39s`.
- Failure signals: scratch `none`, strands `none`.
- Verdict: `Strong`.

### Notes For Next Run
- Add rubric auto-scoring and include numeric per-model totals.
- Include at least one retry/error-injection prompt to test recovery behavior.
- Add Anthropic models for a wider reasoning baseline.

# Latent Logic

  A practical sandbox for probing the reasoning, thinking patterns, and parametric knowledge of LLMs — using agentic loops, tool use, and evaluation harnesses to see how models behave in real tasks.

- Agentic loop from Scratch using Completions API with Foundry Models, custom loop, tools, and evaluation harness
- Use [Strands](https://strandsagents.com/latest/) agent loop with a custom Foundry provider
- Building an agentic loop from scratch with Gemini

## Prerequisites

1. [Install `uv`](https://docs.astral.sh/uv/getting-started/installation/)
2. Setup [Gemini Developer Key](https://ai.google.dev/gemini-api/docs/api-key)
3. [Azure & Foundry Setup](https://learn.microsoft.com/en-us/azure/ai-foundry/tutorials/quickstart-create-foundry-resources?view=foundry&tabs=azurecli): Set up Azure account, configure Foundry Resource & Project, Deploy Models.



## Quickstart

### 1) Install dependencies
```bash
uv sync --locked
```

### 2) Create `.env`
```
GEMINI_API_KEY="YOUR_GEMINI_API_KEY"
FOUNDRY_ENDPOINT="YOUR_FOUNDRY_ENDPOINT"
FOUNDRY_API_KEY="YOUR_FOUNDRY_API_KEY"
GOOGLE_GEOCODING_API_KEY="YOUR_GOOGLE_GEOCODING_API_KEY"
OPENWEATHER_API_KEY="YOUR_OPENWEATHER_API_KEY"
```

Notes:
- Enable the Google Geocoding API for the `GOOGLE_GEOCODING_API_KEY` project.
- Use an OpenWeather API key with current weather access.

### 3) Run
**Scratch (Foundry)**
```bash
uv run scratch_foundry/httpAgent.py --model Kimi-K2.5
```

**Strands (Foundry)**
```bash
uv run strands_foundry/foundry_strands_basic.py --model Kimi-K2.5
```

**Gemini scratch**
```bash
uv run gemini/scratchAgentStep4.py
```

## Evaluation Runs

### Scratch (Foundry)
- Script: `scratch_foundry/run_evaluation.py`
- Results: `evaluation_results/scratch/<model>/...`

Run example:
```bash
uv run scratch_foundry/run_evaluation.py --models "Kimi-K2.5" "Kimi-K2-Thinking"
```

### Strands (Foundry)
- Script: `strands_foundry/run_strands_evaluation.py`
- Results: `evaluation_results/strands/<model>/...`

Run example:
```bash
uv run strands_foundry/run_strands_evaluation.py --models "Kimi-K2.5" "Kimi-K2-Thinking"
```

## Evaluation Workflow

1. Validate canonical providers and keys:
```bash
uv run scripts/canonical_check.py
```

2. Run scratch evaluation:
```bash
uv run scratch_foundry/run_evaluation.py \
  --models "gpt-4.1-mini" "DeepSeek-V3.2" "grok-4-fast-reasoning" "Kimi-K2-Thinking" "Kimi-K2.5" "gpt-4o" "Mistral-Large-3" "gpt-4.1" \
  --prompts prompts.json
```

3. Run Strands evaluation:
```bash
uv run strands_foundry/run_strands_evaluation.py \
  --models "gpt-4.1-mini" "DeepSeek-V3.2" "grok-4-fast-reasoning" "Kimi-K2-Thinking" "Kimi-K2.5" "gpt-4o" "Mistral-Large-3" "gpt-4.1" \
  --prompts prompts.json
```

4. Generate model-insights block for documentation:
```bash
uv run scripts/generate_model_insights_block.py \
  --tag "latent-logic_eval_YYYY-MM-DD_<label>" \
  --append docs/MODEL_INSIGHTS.md
```

Outputs:
- Results: `evaluation_results/scratch/` and `evaluation_results/strands/`
- Canonical snapshots: `evaluation_results/canonical/`
- Comparison summaries: `evaluation_results/latest_comparison_summary.json`, `evaluation_results/latest_runtime_summary.json`
- Logs: `logs/scratch_evaluation.log`, `logs/strands_evaluation.log`



## Where to Look Next

- Technical deep dive: `docs/TECHNICAL_NOTES.md`
- Evaluation plan: `docs/EVALUATION_PLAN.md`


## Logging

All scripts log to console and `logs/`.

## Validation

Evaluation runs now generate a canonical snapshot per run using Google Geocoding and OpenWeather (requires `GOOGLE_GEOCODING_API_KEY` and `OPENWEATHER_API_KEY`). Validation sidecars are saved alongside results.
Rubric scoring is not yet auto-applied as a numeric score in output JSON files.

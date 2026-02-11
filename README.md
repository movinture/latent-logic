# Evaluating LLMs

A practical sandbox for evaluating model reasoning, thinking, and tool‑use behavior using agentic loops.

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
```

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



## Where to Look Next

- Technical deep dive: `docs/TECHNICAL_NOTES.md`
- Evaluation plan: `docs/EVALUATION_PLAN.md`


## Logging

All scripts log to console and `logs/`.

# Technical Notes

This file consolidates the technical details, architecture, journey, and nuances for the project.

## Overview
This repo is a hands-on testbed for building and comparing simple, tool-using agents across multiple LLM providers. It started from a Gemini tutorial and was extended to Azure Foundry-hosted models, with evaluation harnesses for subjective comparisons.

## Project Goals
- Build minimal agents “from scratch” to understand agentic loops (prompt → tool call → tool response → follow-up).
- Compare model behavior on tool use, error recovery, and parametric knowledge beyond benchmarks. Assess the thinking and reasoning capabilities of the LLM models.
- Keep the code approachable and inspectable for learning and experimentation.

## Project Journey (Condensed)
1. **Initial Setup:** Followed Phil Schmid’s Gemini agent article and implemented the `gemini/` scratch scripts.
2. **Foundry Agent:** Built a Foundry agent for `DeepSeek-V3.2`, later generalized into `scratch_foundry/foundryAgent.py`.
3. **HTTP Tool:** Added `scratch_foundry/http_tool.py` for generic HTTP calls.
4. **Specialized HTTP Agent:** Added `scratch_foundry/httpAgent.py` to test tools interactively.
5. **Recursive Tool Calling:** Refactored the scratch loop for chained tool calls.
6. **Evaluation Framework:** Added `scratch_foundry/run_evaluation.py` and `docs/EVALUATION_PLAN.md`.
7. **Model Evaluation:** Ran initial evaluations on DeepSeek, Kimi, and GPT models.
8. **Strands Integration:** Added a custom Strands provider and Strands-based evaluation harness.

## Architecture and Components

### Scratch Foundry Agent Loop
- Core agent class in `scratch_foundry/foundryAgent.py`.
- Uses `OpenAI(base_url=FOUNDRY_ENDPOINT)` with `FOUNDRY_API_KEY`.
- Maintains conversation state in `self.messages` using OpenAI chat format.
- Supports two tool-calling formats:
  - Standard OpenAI `tool_calls` with `function.arguments` JSON.
  - Custom DeepSeek format where the model emits `{ "tool_name": ..., "tool_arguments": ... }` in text.
- Implements recursive `_get_agent_response()` to execute tools and continue until a final response is returned.

### HTTP Agent (Foundry + File + HTTP Tools)
- CLI wrapper in `scratch_foundry/httpAgent.py`.
- Merges file system tools and HTTP tool into a single tool set.
- Intended for interactive testing of real-world data retrieval and API use.

### HTTP Tool
- Implemented in `scratch_foundry/http_tool.py`.
- Provides `http_request` with optional auth modes (Bearer, token, API key, basic).
- Returns formatted response: status, URL, content type, body.

### File System Tools
- Implemented in `scratch_foundry/fileTools.py` and `gemini/fileTools.py`.
- Tools: `read_file`, `write_file`, `list_dir`.
- The scratch version guards empty paths; the Gemini version does not.

### Strands + Foundry
- Custom provider: `strands_foundry/customprovider/foundry_model.py`.
- Uses Strands event loop, tool execution, and tool specs.
- Includes a DeepSeek JSON tool-call fallback.

### Gemini Scratch Agents
- Scripts live under `gemini/` and include their own `gemini/fileTools.py`.
- Gemini scratch agents are intentionally prompted to respond like Linus Torvalds (experimental persona).
- Foundry scratch and Strands code paths no longer enforce that persona.

## Evaluation Harnesses

### Scratch
- Runner: `scratch_foundry/run_evaluation.py`.
- Results: `evaluation_results/runs/<run_group>/scratch/<model>/...`.

### Strands
- Runner: `strands_foundry/run_strands_evaluation.py`.
- Results: `evaluation_results/runs/<run_group>/strands/<model>/...`.

### Canonical Validation
- Shared utilities are in `evaluation_utils.py`.
- Canonical providers:
  - Geocoding: Google Geocoding API (`GOOGLE_GEOCODING_API_KEY`)
  - Weather: OpenWeather API (`OPENWEATHER_API_KEY`)
  - ISS position: `wheretheiss.at`
  - FX rate: `open.er-api.com`
- Each run builds a canonical snapshot and saves it under `evaluation_results/runs/<run_group>/canonical/canonical_<prompt_version>.json`.
- Each model/prompt output writes a validation sidecar alongside the result JSON.
- Validation currently checks:
  - Weather temperature difference vs canonical (`max_diff_c`)
  - Location coordinate distance vs canonical (`max_km`)
  - ISS position with time-aware distance validation (nearest/interpolated canonical position and dynamic allowance)
  - USD/EUR exchange rate difference vs canonical (`max_diff`)
- Provenance labels are written as:
  - `parametric`
  - `tool-assisted`
  - `hybrid_or_failed`
  - `unverified_parametric` / `unverified_tool_used` (for prompt types without validators)
- Validation sidecars also include `data_hints` extracted from tool I/O for freshness/source clarity (tool URLs and date/time hints).
- Rubric scoring from `docs/EVALUATION_PLAN.md` is not yet auto-computed into numeric scores in result artifacts.

### Comparison Tooling
- Deterministic cross-framework comparison script: `scripts/compare_framework_runs.py`.
- It compares scratch vs Strands for one run group (`--run-group`), selecting the best-coverage Strands run id inside that group.
- It emits:
  - `evaluation_results/runs/<run_group>/latest_comparison_summary.json`
  - `evaluation_results/runs/<run_group>/analysis/comparison_<timestamp>.json`
  - `evaluation_results/runs/<run_group>/analysis/comparison_<timestamp>.md`
  - `evaluation_results/runs/<run_group>/analysis/interpretation_guide_<timestamp>.md`
- CSV exporter: `scripts/export_comparison_tables.py`, which writes:
  - `evaluation_results/runs/<run_group>/analysis/turns_and_tools_<timestamp>.csv`
  - `evaluation_results/runs/<run_group>/analysis/model_aggregate_<timestamp>.csv`

## Tool-Calling Nuances
- **DeepSeek-V3.2:** Requires JSON tool-call format (`tool_name`, `tool_arguments`).
- **Kimi + GPT models:** Use standard OpenAI `tool_calls`.
- **Recursive tool calling:** Implemented in the scratch loop to handle chained tool calls.

## API Comparison: Foundry vs. Gemini

### Foundry Models (`openai` library)
- Endpoint: `client.chat.completions.create`.
- System prompt as `role: "system"` message.
- Tool calling varies by model; DeepSeek needs JSON tool-call workaround.

### Gemini Models (`google-genai` library)
- Endpoint: `client.models.generate_content`.
- System prompt passed via `GenerateContentConfig.system_instruction`.
- Tool calling supported via `types.Tool` and `function_declarations`.

## Agentic Loop Comparison

### `scratch_foundry/foundryAgent.py`
- Recursive loop allows chained tool calls.
- Handles standard `tool_calls` and DeepSeek JSON format.
- Maintains full message history.

### `gemini/agent.py`
- Simpler recursive loop due to native function-calling support.

## Strands + Foundry Notes
- **Custom Provider:** `strands_foundry/` implements a Strands `Model` for Foundry OpenAI-compatible endpoints.
- **Tooling:** Strands examples use `strands_tools.http_request` instead of the local scratch tool.
- **Evaluation:** Strands harness mirrors scratch prompts but uses the Strands loop and tools.

## Logging
- Console output is mirrored to per-run log files under `evaluation_results/runs/<run_group>/logs/`.
- Scratch and Strands scripts each write their own log file.

## Known Issues and Gotchas
- `gemini/fileTools.py` lacks the empty-path guard that exists in `scratch_foundry/fileTools.py`.
- Some models emit chained tool calls; the recursive loop in `scratch_foundry/foundryAgent.py` is a workaround for this.
- Gemini scratch agents are prompted with a Linus Torvalds persona; Foundry scratch and Strands paths no longer enforce that persona.

## Output and Artifacts
- Evaluation logs are written as JSON to `evaluation_results/runs/<run_group>/scratch` and `evaluation_results/runs/<run_group>/strands`.
- Canonical snapshots are written to `evaluation_results/runs/<run_group>/canonical`.
- Validation sidecars are written next to each prompt result JSON in both scratch and Strands runs.

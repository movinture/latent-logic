# Subjective Evaluation Plan for LLMs

This document outlines a plan for using the scratch agent to subjectively evaluate and compare the capabilities of different LLMs.

### 1. Define a Standardized Test Suite

We will use an iterative approach to build our test suite. We will start with a simple test case and then add more complex ones as we go.

**Phase 1: Simple Tool Use**

*   **Prompt 1 (Current Weather):** "What is the current weather in New York City?"
*   **Goal:** Tests the agent's ability to use the `http_request` tool to get information from a public API.

*   **Prompt 2 (Location Query):** "Can you get me the latitude and longitude for Times Square in New York City?"
*   **Goal:** Tests the model's parametric knowledge and its ability to resolve ambiguities in location queries, potentially using an HTTP tool or internal knowledge.

### 2. Create a Standardized Evaluation Rubric

We can create a rubric to score the agent's performance on each prompt. The rubric would have different criteria, each with a scoring scale (e.g., 1-5).

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
3.  Saves the full conversation log for each model to a separate JSON file in `evaluation_results/scratch/` or `evaluation_results/strands/`.
4.  Loads prompts from `prompts.json` by default (configurable with `--prompts`).

### 4. Analyze the Results

After running the tests, we can manually review the conversation logs and use the evaluation rubric to score each model's performance. The results can then be compiled into a comparison table, which would provide a clear overview of the strengths and weaknesses of each model.

import argparse
import json
import os
import re
import sys
import logging
from datetime import datetime

from dotenv import load_dotenv
from strands import Agent
from strands_tools import http_request

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from strands_foundry import FoundryCompletionsModel
from evaluation_utils import (
    load_prompts,
    detect_tool_use_strands,
    validate_result,
    classify_provenance,
    build_canonical_snapshot,
)

logger = logging.getLogger(__name__)


def setup_logging() -> logging.Logger:
    repo_root = os.path.dirname(os.path.dirname(__file__))
    log_dir = os.path.join(repo_root, "logs")
    os.makedirs(log_dir, exist_ok=True)
    log_path = os.path.join(log_dir, "strands_evaluation.log")

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=[logging.FileHandler(log_path), logging.StreamHandler()],
    )
    return logging.getLogger(__name__)


def sanitize_filename(text: str) -> str:
    s = str(text).strip().replace(" ", "_")
    s = re.sub(r"(?u)[^-\w.]", "", s)
    return s


def extract_text(message: dict) -> str:
    blocks = message.get("content", [])
    parts = [block.get("text", "") for block in blocks if "text" in block]
    return "\n".join([p for p in parts if p])


def create_agent(model_name: str) -> Agent:
    model = FoundryCompletionsModel(
        model_id=model_name,
        endpoint=os.getenv("FOUNDRY_ENDPOINT", ""),
        api_key=os.getenv("FOUNDRY_API_KEY", ""),
        params={"temperature": 0.2},
    )

    system_prompt = (
        "You are a helpful assistant. Use tools when needed. "
        "Respond with the final answer only. Do not include analysis or scratch work."
    )

    return Agent(model=model, tools=[http_request], system_prompt=system_prompt)


def run_evaluation(models: list[str], prompt_file: str) -> None:
    prompt_data = load_prompts(prompt_file)
    prompts = prompt_data["prompts"]
    prompt_version = prompt_data.get("version", "unknown")

    canonical_snapshot = build_canonical_snapshot(prompt_data)
    canonical_dir = os.path.join("evaluation_results", "canonical")
    os.makedirs(canonical_dir, exist_ok=True)
    canonical_path = os.path.join(canonical_dir, f"canonical_{prompt_version}.json")
    with open(canonical_path, "w") as f:
        json.dump(canonical_snapshot, f, indent=2)
    logger.info("Canonical snapshot saved to %s", canonical_path)

    results_root = os.path.join("evaluation_results", "strands")
    if not os.path.exists(results_root):
        os.makedirs(results_root)

    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")

    for model_name in models:
        sanitized_model_name = sanitize_filename(model_name)
        model_results_dir = os.path.join(results_root, sanitized_model_name)
        if not os.path.exists(model_results_dir):
            os.makedirs(model_results_dir)

        logger.info("--- Running Strands evaluation for model: %s ---", model_name)
        for prompt_obj in prompts:
            prompt_name = prompt_obj["name"]
            prompt_text = prompt_obj["text"]
            
            logger.info("  - Running prompt: '%s'", prompt_text)
            try:
                agent = create_agent(model_name)
                result = agent(prompt_text)

                log_path = os.path.join(model_results_dir, f"{prompt_name}_{run_id}.json")
                payload = {
                    "model": model_name,
                    "prompt_name": prompt_name,
                    "prompt_version": prompt_version,
                    "prompt_text": prompt_text,
                    "stop_reason": result.stop_reason,
                    "final_message": result.message,
                    "final_text": extract_text(result.message),
                    "messages": agent.messages,
                }

                with open(log_path, "w") as f:
                    json.dump(payload, f, indent=2)

                # Validation + provenance (sidecar)
                tool_used, tool_names = detect_tool_use_strands(agent.messages)
                validation = validate_result(prompt_obj, payload["final_text"], canonical_snapshot)
                provenance = classify_provenance(tool_used, validation)

                validation_path = os.path.join(model_results_dir, f"{prompt_name}_{run_id}_validation.json")
                with open(validation_path, "w") as f:
                    json.dump(
                        {
                            "model": model_name,
                            "prompt_name": prompt_name,
                            "prompt_version": prompt_version,
                            "canonical": canonical_snapshot["prompts"].get(prompt_name, {}),
                            "tool_used": tool_used,
                            "tool_names": tool_names,
                            "provenance": provenance,
                            "validation": validation,
                        },
                        f,
                        indent=2,
                    )

                logger.info("    Results saved to %s", log_path)
                logger.info("    Validation saved to %s", validation_path)

            except Exception as e:
                logger.exception(
                    "    Error evaluating prompt '%s' for model %s: %s",
                    prompt_text,
                    model_name,
                    e,
                )


if __name__ == "__main__":
    logger = setup_logging()
    load_dotenv()

    if not os.getenv("FOUNDRY_ENDPOINT") or not os.getenv("FOUNDRY_API_KEY"):
        raise RuntimeError("FOUNDRY_ENDPOINT and FOUNDRY_API_KEY must be set in the environment.")

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--models",
        nargs="+",
        default=["Kimi-K2.5", "Kimi-K2-Thinking", "DeepSeek-V3.2", "gpt-4o"],
        help="List of Foundry model deployment names to evaluate.",
    )
    parser.add_argument("--prompts", type=str, default="prompts.json", help="Path to prompts JSON file.")
    args = parser.parse_args()

    run_evaluation(args.models, args.prompts)

import argparse
import os
import json
import re
import sys
import logging
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from scratch_foundry.httpAgent import create_agent
from evaluation_utils import (
    load_prompts,
    detect_tool_use_scratch,
    validate_result,
    classify_provenance,
    build_canonical_snapshot,
    extract_data_hints_scratch,
)

logger = logging.getLogger(__name__)


def setup_logging() -> logging.Logger:
    repo_root = os.path.dirname(os.path.dirname(__file__))
    log_dir = os.path.join(repo_root, "logs")
    os.makedirs(log_dir, exist_ok=True)
    log_path = os.path.join(log_dir, "scratch_evaluation.log")

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=[logging.FileHandler(log_path), logging.StreamHandler()],
    )
    return logging.getLogger(__name__)

def sanitize_filename(text: str) -> str:
    """Sanitizes a string for use as a filename."""
    s = str(text).strip().replace(' ', '_')
    s = re.sub(r'(?u)[^-\w.]', '', s)
    return s

def run_evaluation(models: list[str], prompt_file: str):
    """
    Runs the evaluation suite against a list of models.
    """
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
    
    results_root = os.path.join("evaluation_results", "scratch")
    if not os.path.exists(results_root):
        os.makedirs(results_root)

    for model_name in models:
        sanitized_model_name = sanitize_filename(model_name)
        model_results_dir = os.path.join(results_root, sanitized_model_name)
        if not os.path.exists(model_results_dir):
            os.makedirs(model_results_dir)

        logger.info("--- Running evaluation for model: %s ---", model_name)
        for prompt_obj in prompts:
            prompt_name = prompt_obj["name"]
            prompt_text = prompt_obj["text"]
            
            logger.info("  - Running prompt: '%s'", prompt_text)
            try:
                # Re-create agent for each prompt to ensure a clean state
                agent = create_agent(model_name)
                response = agent.run(prompt_text)
                
                # Save the conversation log
                log_path = os.path.join(model_results_dir, f"{prompt_name}.json")
                with open(log_path, "w") as f:
                    messages_as_dict = []
                    for message in agent.messages:
                        if hasattr(message, 'dict'):
                            messages_as_dict.append(message.dict())
                        else:
                            messages_as_dict.append(message)
                    json.dump(messages_as_dict, f, indent=2)

                # Validation + provenance (sidecar)
                tool_used, tool_names = detect_tool_use_scratch(messages_as_dict)
                eval_time_unix = int(time.time())
                validation = validate_result(prompt_obj, response, canonical_snapshot, eval_time_unix=eval_time_unix)
                provenance = classify_provenance(tool_used, validation)
                data_hints = extract_data_hints_scratch(messages_as_dict)

                validation_path = os.path.join(model_results_dir, f"{prompt_name}_validation.json")
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
                            "eval_time_unix": eval_time_unix,
                            "data_hints": data_hints,
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
    parser = argparse.ArgumentParser()
    parser.add_argument("--models", nargs="+", default=["DeepSeek-V3.2", "Kimi-K2-Thinking"], help="A list of models to evaluate.")
    parser.add_argument("--prompts", type=str, default="prompts.json", help="Path to prompts JSON file.")
    args = parser.parse_args()
    
    run_evaluation(args.models, args.prompts)

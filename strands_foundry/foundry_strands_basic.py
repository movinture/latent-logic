import argparse
import logging
import os
import sys

from dotenv import load_dotenv

from strands import Agent

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from strands_foundry import FoundryCompletionsModel


def setup_logging() -> logging.Logger:
    repo_root = os.path.dirname(os.path.dirname(__file__))
    log_dir = os.path.join(repo_root, "logs")
    os.makedirs(log_dir, exist_ok=True)
    log_path = os.path.join(log_dir, "strands_basic.log")

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=[logging.FileHandler(log_path), logging.StreamHandler()],
    )
    return logging.getLogger(__name__)


def main() -> None:
    logger = setup_logging()
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", type=str, default="Kimi-K2.5", help="Foundry deployment name")
    parser.add_argument("--prompt", type=str, default="What is the capital of France?", help="Prompt to send")
    parser.add_argument(
        "--system",
        type=str,
        default=(
            "You are a helpful assistant. Respond with the final answer only. "
            "Do not include analysis, reasoning, or scratch work."
        ),
        help="System prompt",
    )
    args = parser.parse_args()

    load_dotenv()

    endpoint = os.getenv("FOUNDRY_ENDPOINT")
    api_key = os.getenv("FOUNDRY_API_KEY")
    if not endpoint or not api_key:
        raise RuntimeError("FOUNDRY_ENDPOINT and FOUNDRY_API_KEY must be set in the environment.")

    model = FoundryCompletionsModel(
        model_id=args.model,
        endpoint=endpoint,
        api_key=api_key,
        params={"temperature": 0.2},
    )

    agent = Agent(model=model, system_prompt=args.system)
    result = agent(args.prompt)

    # Strands returns an AgentResult; the final message text is in result.message
    # The message is in Bedrock-style content blocks.
    text_blocks = [block.get("text", "") for block in result.message.get("content", []) if "text" in block]
    output = "\n".join([t for t in text_blocks if t])
    logger.info(output)


if __name__ == "__main__":
    main()

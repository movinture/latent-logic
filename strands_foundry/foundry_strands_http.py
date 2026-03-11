import argparse
import logging
import os
import sys

from dotenv import load_dotenv
from strands import Agent
from strands_tools import http_request

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from foundry_auth import resolve_foundry_auth_config
from strands_foundry import FoundryCompletionsModel


def setup_logging() -> logging.Logger:
    repo_root = os.path.dirname(os.path.dirname(__file__))
    log_dir = os.path.join(repo_root, "logs")
    os.makedirs(log_dir, exist_ok=True)
    log_path = os.path.join(log_dir, "strands_http.log")

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=[logging.FileHandler(log_path), logging.StreamHandler()],
    )
    return logging.getLogger(__name__)


def extract_text(message: dict) -> str:
    blocks = message.get("content", [])
    parts = [block.get("text", "") for block in blocks if "text" in block]
    return "\n".join([p for p in parts if p])


def main() -> None:
    logger = setup_logging()
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", type=str, default="Kimi-K2.5", help="Foundry deployment name")
    parser.add_argument(
        "--prompt",
        type=str,
        default="Use http_request to fetch https://api.ipify.org?format=json and return just the IP address.",
        help="Prompt to send",
    )
    parser.add_argument(
        "--system",
        type=str,
        default=(
            "You are a helpful assistant. Use tools when needed. "
            "Respond with the final answer only. Do not include analysis or scratch work."
        ),
        help="System prompt",
    )
    args = parser.parse_args()

    load_dotenv()

    auth_config = resolve_foundry_auth_config()
    logger.info(
        "Auth config: endpoint_family=%s scope=%s auth_mode=%s base_url=%s",
        auth_config.endpoint_family,
        auth_config.scope,
        auth_config.auth_mode,
        auth_config.base_url,
    )

    model = FoundryCompletionsModel(
        model_id=args.model,
        params={"temperature": 0.2},
    )

    agent = Agent(model=model, tools=[http_request], system_prompt=args.system)
    result = agent(args.prompt)

    logger.info(extract_text(result.message))


if __name__ == "__main__":
    main()

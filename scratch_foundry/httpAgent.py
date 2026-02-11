import argparse
import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from scratch_foundry.foundryAgent import FoundryAgent
from scratch_foundry.fileTools import file_tools
from scratch_foundry.http_tool import http_tool


def setup_logging() -> logging.Logger:
    repo_root = os.path.dirname(os.path.dirname(__file__))
    log_dir = os.path.join(repo_root, "logs")
    os.makedirs(log_dir, exist_ok=True)
    log_path = os.path.join(log_dir, "scratch_http_agent.log")

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=[logging.FileHandler(log_path), logging.StreamHandler()],
    )
    return logging.getLogger(__name__)

def create_agent(model: str) -> FoundryAgent:
    all_tools = {**file_tools, **http_tool}
    return FoundryAgent(
        model=model, 
        tools=all_tools, 
        system_instruction="You are a helpful assistant that can make HTTP requests to APIs. You have access to an http_request tool. When you need to call a tool, you must respond with a JSON object with 'tool_name' and 'tool_arguments' keys."
    )

def main():
    logger = setup_logging()
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", type=str, default="DeepSeek-V3.2", help="The deployment name of the model to use.")
    args = parser.parse_args()

    agent = create_agent(args.model)
    
    logger.info("Agent ready. Using model: %s", args.model)
    while True:
        user_input = input("You: ")
        if user_input.lower() in ['exit', 'quit']:
            break
    
        response = agent.run(user_input)
        logger.info("Agent: %s", response)

if __name__ == "__main__":
    main()

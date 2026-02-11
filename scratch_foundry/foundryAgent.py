import os
import json
import argparse
import logging
import sys
from openai import OpenAI
from dotenv import load_dotenv
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from scratch_foundry.fileTools import file_tools


def setup_logging() -> logging.Logger:
    repo_root = os.path.dirname(os.path.dirname(__file__))
    log_dir = os.path.join(repo_root, "logs")
    os.makedirs(log_dir, exist_ok=True)
    log_path = os.path.join(log_dir, "scratch_foundry_agent.log")

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=[logging.FileHandler(log_path), logging.StreamHandler()],
    )
    return logging.getLogger(__name__)

load_dotenv()

class FoundryAgent:
    def __init__(self, model: str, tools: list[dict], system_instruction: str = "You are a helpful assistant."):
        self.model = model
        self.client = OpenAI(
            base_url=os.getenv("FOUNDRY_ENDPOINT"),
            api_key=os.getenv("FOUNDRY_API_KEY")
        )
        self.messages = [{"role": "system", "content": system_instruction}]
        self.tools = tools
        self.tool_definitions = [{"type": "function", "function": tool["definition"]} for tool in self.tools.values()]

    def _is_deepseek_custom_tool_call(self, content: str) -> dict | None:
        """
        Checks if the content is a DeepSeek custom JSON tool call and returns it if so.
        """
        try:
            tool_call_info = json.loads(content)
            if "tool_name" in tool_call_info and "tool_arguments" in tool_call_info:
                return tool_call_info
        except (json.JSONDecodeError, KeyError):
            pass
        return None

    def _get_agent_response(self):
        """
        Recursive helper to get the model's response, execute tools, and continue until
        a final text response is received.
        """
        completion = self.client.chat.completions.create(
            model=self.model,
            messages=self.messages,
            tools=self.tool_definitions,
            tool_choice="auto",
        )
        
        response_message = completion.choices[0].message
        self.messages.append(response_message) # Append the model's response

        # Check for standard OpenAI tool calls
        if response_message.tool_calls:
            for tool_call in response_message.tool_calls:
                function_name = tool_call.function.name
                if function_name in self.tools:
                    function_to_call = self.tools[function_name]["function"]
                    function_args = json.loads(tool_call.function.arguments)
                    function_response = function_to_call(**function_args)
                    
                    self.messages.append(
                        {
                            "tool_call_id": tool_call.id,
                            "role": "tool",
                            "name": function_name,
                            "content": str(function_response),
                        }
                    )
                else:
                    self.messages.append(
                        {
                            "tool_call_id": tool_call.id,
                            "role": "tool",
                            "name": function_name,
                            "content": f"Tool '{function_name}' not found.",
                        }
                    )
            # Recursively call to get the model's next response after tool execution
            return self._get_agent_response()

        # Check for DeepSeek custom JSON tool calls if no standard tool calls
        elif response_message.content:
            tool_call_info = self._is_deepseek_custom_tool_call(response_message.content)
            if tool_call_info:
                function_name = tool_call_info["tool_name"]
                function_args = tool_call_info["tool_arguments"]
                if function_name in self.tools:
                    function_to_call = self.tools[function_name]["function"]
                    function_response = function_to_call(**function_args)
                    self.messages.append(
                        {
                            # DeepSeek custom calls don't have tool_call_id, generate a dummy one if needed for consistency
                            "role": "tool",
                            "name": function_name,
                            "content": str(function_response),
                        }
                    )
                else:
                    self.messages.append(
                        {
                            "role": "tool",
                            "name": function_name,
                            "content": f"Tool '{function_name}' not found.",
                        }
                    )
                # Recursively call to get the model's next response after tool execution
                return self._get_agent_response()

        # Base case: no more tool calls, return final text content
        return response_message.content


    def run(self, user_input: str):
        """
        Starts the conversation with a user input and returns the final text response.
        """
        self.messages.append({"role": "user", "content": user_input})
        return self._get_agent_response()

if __name__ == "__main__":
    logger = setup_logging()
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", type=str, default="DeepSeek-V3.2", help="The deployment name of the model to use.")
    args = parser.parse_args()

    agent = FoundryAgent( # Use FoundryAgent here
        model=args.model, 
        tools=file_tools, 
        system_instruction="You are a helpful coding assistant. When you need to call a tool, you must respond with a JSON object with 'tool_name' and 'tool_arguments' keys."
    )
    
    logger.info("Agent ready. Using model: %s", args.model)
    while True:
        user_input = input("You: ")
        if user_input.lower() in ['exit', 'quit']:
            break
    
        response = agent.run(user_input)
        logger.info("Agent: %s", response)

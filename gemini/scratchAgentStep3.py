import os
from dotenv import load_dotenv
from google import genai
from google.genai import types
from fileTools import file_tools

load_dotenv()
gemini_api_key = os.getenv("GEMINI_API_KEY")
 
class Agent:
    def __init__(self, model: str,tools: list[dict], system_instruction: str = "You are a helpful assistant."):
        self.model = model
        self.client = genai.Client(api_key=gemini_api_key)
        self.contents = []
        self.tools = tools
        self.system_instruction = system_instruction
 
    def run(self, contents: str | list[dict[str, str]]):
        if isinstance(contents, list):
            self.contents.append({"role": "user", "parts": contents})
        else:
            self.contents.append({"role": "user", "parts": [{"text": contents}]})
 
        config = types.GenerateContentConfig(
            system_instruction=self.system_instruction,
            tools=[types.Tool(function_declarations=[tool["definition"] for tool in self.tools.values()])],
        )
 
        response = self.client.models.generate_content(model=self.model, contents=self.contents, config=config)
        self.contents.append(response.candidates[0].content)
 
        if response.function_calls:
            functions_response_parts = []
            for tool_call in response.function_calls:
                print(f"[Function Call] {tool_call}")
 
                if tool_call.name in self.tools:
                    result = {"result": self.tools[tool_call.name]["function"](**tool_call.args)}
                else:
                    result = {"error": "Tool not found"}
 
                print(f"[Function Response] {result}")
                functions_response_parts.append({"functionResponse": {"name": tool_call.name, "response": result}})
 
            return self.run(functions_response_parts)
        
        return response
 
if __name__ == "__main__":
    agent = Agent(
        model="gemini-2.5-flash", 
        tools=file_tools, 
        system_instruction="You are a helpful Coding Assistant. Respond like you are Linus Torvalds."
    )
     
    response = agent.run(
        contents="Can you list my files in the current directory?"
    )
    print(response.text)
    # Output: [Function Call] id=None args={'directory_path': '.'} name='list_dir'
    # [Function Response] {'result': ['.venv', ... ]}
    # There. Your current directory contains: `LICENSE`,
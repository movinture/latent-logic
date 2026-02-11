import os
from dotenv import load_dotenv
from google import genai
from google.genai import types
from fileTools import file_tools

load_dotenv()
gemini_api_key = os.getenv("GEMINI_API_KEY")


 
class Agent:
    def __init__(self, model: str,tools: list[dict]):
        self.model = model
        self.client = genai.Client(api_key=gemini_api_key)
        self.contents = []
        self.tools = tools
 
    def run(self, contents: str):
        self.contents.append({"role": "user", "parts": [{"text": contents}]})
 
        config = types.GenerateContentConfig(
            tools=[types.Tool(function_declarations=[tool["definition"] for tool in self.tools.values()])],
        )
 
        response = self.client.models.generate_content(model=self.model, contents=self.contents, config=config)
        self.contents.append(response.candidates[0].content)
 
        return response
 
agent = Agent(model="gemini-2.5-flash", tools=file_tools)
 
response = agent.run(
    contents="Can you list my files in the current directory?"
)
print(response.function_calls)
# Output: [FunctionCall(name='list_dir', arguments={'directory_path': '.'})]
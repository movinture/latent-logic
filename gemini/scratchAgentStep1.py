import os
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()
gemini_api_key = os.getenv("GEMINI_API_KEY")


class Agent:
    def __init__(self, model: str):
        self.model = model
        self.client = genai.Client(api_key=gemini_api_key)
        self.contents = []
 
    def run(self, contents: str):
        self.contents.append({"role": "user", "parts": [{"text": contents}]})
 
        response = self.client.models.generate_content(model=self.model, contents=self.contents)
        self.contents.append(response.candidates[0].content)
 
        return response
 
# agent = Agent(model="gemini-pro")
# agent = Agent("gemini-3-pro-preview")
# agent = Agent("gemini-2.5-pro")
# agent = Agent("gemini-2.5-flash-lite")
agent = Agent("gemini-2.5-flash")
response1 = agent.run(
    contents="Hello, What are top 3 cities in Germany to visit? Only return the names of the cities."
)
 
print(f"Model: {response1.text}")
# Output: Berlin, Munich, Cologne 
response2 = agent.run(
    contents="Tell me something about the second city."
)
 
print(f"Model: {response2.text}")
# Output: Munich is the capital of Bavaria and is known for its Oktoberfest.
# import os
# from dotenv import load_dotenv
# from google import genai
# from google.genai import types
from fileTools import file_tools


from scratchAgentStep3 import Agent

agent = Agent(
    model="gemini-2.5-flash", 
    tools=file_tools, 
    system_instruction="You are a helpful Coding Assistant. Respond like you are Linus Torvalds."
)
 
print("Agent ready. Ask it to check files in this directory.")
while True:
    user_input = input("You: ")
    if user_input.lower() in ['exit', 'quit']:
        break
 
    response = agent.run(user_input)
    print(f"Linus: {response.text}\n")
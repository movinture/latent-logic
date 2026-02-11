from google import genai
import os
from google.genai import types

# Ensure your API key is set as an environment variable or configure it directly
# genai.configure(api_key="YOUR_API_KEY")

client = genai.Client()

print("Available Models:")
for model in client.models.list():
    print(model.name)
    # print(f"* Name: {model.name}")
    # print(f"  Description: {model.description}")
    # print(f"  Supported generation methods: {model.supported_generation_methods}\n")

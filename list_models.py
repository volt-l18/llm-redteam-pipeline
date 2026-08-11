import os
import google.generativeai as genai
from dotenv import load_dotenv

# Load the API key from your .env file
load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")

if not api_key:
    print("Error: GEMINI_API_KEY not found in .env file.")
    exit()

genai.configure(api_key=api_key)

print("Fetching available models for your API key...\n")
try:
    for m in genai.list_models():
        # We only want models that support text generation
        if "generateContent" in m.supported_generation_methods:
            print(f"- {m.name}")
except Exception as e:
    print(f"Failed to fetch models: {e}")

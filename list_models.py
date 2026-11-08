import os
import sys

from dotenv import load_dotenv
import google.generativeai as genai

# Load the API key from your .env file
load_dotenv()

if "--orcarouter" in sys.argv:
    # OrcaRouter Cyber Inference catalog (GET https://api.orcarouter.ai/v1/models)
    from src.orcarouter_cli import main as orca_main

    raise SystemExit(orca_main(["models", *sys.argv[2:]]))

api_key = os.getenv("GEMINI_API_KEY")

if not api_key:
    print("Error: GEMINI_API_KEY not found in .env file.")
    print("For OrcaRouter models run: python list_models.py --orcarouter")
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

# src/config.py
import os
from dotenv import load_dotenv

# Load environment variables from the .env file
load_dotenv()

# Pull exact model strings from .env, falling back to safe defaults if missing.
# OrcaRouter models use the "orcarouter/" provider prefix registered by
# src.orcarouter, e.g. "orcarouter/orcarouter/auto".
TARGET_MODEL = os.getenv("TARGET_MODEL", "ollama/llama3.2")
ATTACKER_MODEL = os.getenv("ATTACKER_MODEL", "gemini/gemini-3.6-flash")
EVALUATOR_MODEL = os.getenv("EVALUATOR_MODEL", "gemini/gemini-3.6-flash")

# OrcaRouter Cyber Inference provider settings
ORCAROUTER_API_BASE = os.getenv("ORCAROUTER_API_BASE_URL", "").strip() or None
ORCAROUTER_KEY_PRESENT = bool(os.getenv("ORCAROUTER_API_KEY", "").strip())

# Pipeline Settings
MAX_TURNS = 5

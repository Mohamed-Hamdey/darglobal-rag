# app/config.py
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent
INDEX_PATH = BASE_DIR / "index" / "rag.sqlite"

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
# Fallback chain of free models
LLM_MODELS = [
    "nvidia/nemotron-3.5-super-vl:free",
    "nvidia/nemotron-3.5-lightning:free",
    "nvidia/nemotron-3-ultra-550b-a55b:free"
]

DAILY_BUDGET = int(os.getenv("DAILY_LLM_BUDGET", "40"))
PER_IP_LIMIT = int(os.getenv("PER_IP_LIMIT", "8"))
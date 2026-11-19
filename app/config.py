# app/config.py
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent
INDEX_PATH = BASE_DIR / "index" / "rag.sqlite"
GAZETTEER_PATH = BASE_DIR / "data" / "gazetteer.json"
STARTER_CACHE_PATH = BASE_DIR / "data" / "starter_answers.json"

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
LLM_MODELS = [m.strip() for m in os.getenv(
    "LLM_MODELS",
    "nvidia/nemotron-3.5-super-vl:free,nvidia/nemotron-3.5-lightning:free,nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free"
).split(",") if m.strip()]

DAILY_LLM_BUDGET = int(os.getenv("DAILY_LLM_BUDGET", "40"))
PER_IP_LIMIT = int(os.getenv("PER_IP_LIMIT", "8"))
PER_IP_WINDOW_S = int(os.getenv("PER_IP_WINDOW_S", "600"))
DATA_DATE = os.getenv("DATA_DATE", "2026-11-19")
ENABLE_DENSE = os.getenv("ENABLE_DENSE", "0") == "1"
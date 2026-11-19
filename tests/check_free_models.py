import httpx
from app.config import LLM_MODELS
ids = {m["id"] for m in httpx.get("https://openrouter.ai/api/v1/models", timeout=15).json()["data"]}
for m in LLM_MODELS:
    print(("✅" if m in ids else "❌"), m)
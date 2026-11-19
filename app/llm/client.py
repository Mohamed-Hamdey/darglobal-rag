import httpx, json
from app.config import OPENROUTER_API_KEY, LLM_MODELS

HEADERS = lambda: {"Authorization": f"Bearer {OPENROUTER_API_KEY}",
                   "HTTP-Referer": "https://darglobal-assessment.onrender.com",
                   "X-Title": "DarGlobal x Wasalt RAG", "Content-Type": "application/json"}

def verify_models() -> list[str]:
    """Keep only :free models currently available. Never hard-code a dead ID."""
    try:
        r = httpx.get("https://openrouter.ai/api/v1/models", timeout=15)
        ids = {m["id"] for m in r.json().get("data", [])}
        chain = [m for m in LLM_MODELS if m in ids]
        return chain or LLM_MODELS
    except Exception:
        return LLM_MODELS

async def stream(chain: list[str], system: str, user: str):
    """Yield tokens. On 429/5xx/timeout → next model. All fail → raise."""
    last_err = None
    for model in chain:
        try:
            async with httpx.AsyncClient(timeout=45) as c:
                async with c.stream("POST", "https://openrouter.ai/api/v1/chat/completions",
                                    headers=HEADERS(),
                                    json={"model": model, "temperature": 0.1, "stream": True,
                                          "messages": [{"role": "system", "content": system},
                                                       {"role": "user", "content": user}]}) as resp:
                    if resp.status_code != 200:
                        last_err = f"{model}: HTTP {resp.status_code}"; continue
                    async for line in resp.aiter_lines():
                        if not line.startswith("data: "): 
                            continue
                        d = line[6:]
                        if d.strip() == "[DONE]": 
                            return
                        try:
                            chunk_data = json.loads(d)
                            content = chunk_data["choices"][0]["delta"].get("content")
                            if content:  # ONLY yield if content is a valid string
                                yield (model, content)
                        except Exception: 
                            pass
                    return
        except Exception as e:
            last_err = f"{model}: {e}"
    raise RuntimeError(f"All models failed. Last: {last_err}")
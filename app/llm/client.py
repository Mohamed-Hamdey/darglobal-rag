# app/llm/client.py
import httpx
import json
from typing import AsyncGenerator
from app.config import OPENROUTER_API_KEY, LLM_MODELS

async def stream_llm_response(system_prompt: str, user_message: str, context_str: str) -> AsyncGenerator[str, None]:
    if not OPENROUTER_API_KEY:
        yield "⚠️ OpenRouter API key is missing. Showing sources only."
        return

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"CONTEXT:\n{context_str}\n\nQUESTION:\n{user_message}"}
    ]
    
    # Try models in order
    for model in LLM_MODELS:
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                async with client.stream(
                    "POST",
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                        "HTTP-Referer": "https://darglobal.co.uk",
                        "X-Title": "DarGlobal RAG Demo",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": model,
                        "messages": messages,
                        "temperature": 0.1,
                        "stream": True
                    }
                ) as response:
                    if response.status_code != 200:
                        error_text = await response.aread()
                        print(f"Model {model} failed: {response.status_code} - {error_text}")
                        continue # Try next model
                        
                    async for line in response.aiter_lines():
                        if line.startswith("data: "):
                            data = line[6:]
                            if data.strip() == "[DONE]":
                                return
                            try:
                                chunk = json.loads(data)
                                content = chunk["choices"][0]["delta"].get("content", "")
                                if content:
                                    yield content
                            except json.JSONDecodeError:
                                pass
                    return # Success, exit loop
        except Exception as e:
            print(f"Exception with model {model}: {e}")
            continue
            
    yield "\n\n⚠️ All AI models are currently busy or rate-limited. Please rely on the cited sources below."
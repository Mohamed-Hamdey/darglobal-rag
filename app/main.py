# app/main.py
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path
import sqlite3
import json
from datetime import datetime

from app.config import INDEX_PATH, LLM_MODELS
from app.retrieval.store import retrieve_context
from app.llm.client import stream_llm_response

app = FastAPI(title="DarGlobal x Wasalt RAG API")

# 1. Mount static UI files
UI_DIR = Path(__file__).parent / "ui"
app.mount("/ui", StaticFiles(directory=str(UI_DIR)), name="ui")

# 2. Serve index.html at root
@app.get("/")
def read_root():
    return FileResponse(str(UI_DIR / "index.html"))

# 3. CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

SYSTEM_PROMPT = """You are a helpful, factual research assistant for DarGlobal and Wasalt real estate data.
RULES:
1. Answer ONLY using the provided CONTEXT. If the context doesn't have the answer, say "I couldn't find this in the collected data."
2. NEVER calculate, estimate, or convert prices. Quote figures exactly as they appear in the context with their currency.
3. Always cite your sources using [1], [2], etc., corresponding to the chunk numbers in the context.
4. Keep answers concise, professional, and in the same language as the user's question (English or Arabic).
5. Add a brief disclaimer: "Figures are indicative and subject to change."
"""

@app.get("/api/health")
def health():
    return {"status": "ok", "timestamp": datetime.now().isoformat()}

@app.get("/api/meta")
def meta():
    conn = sqlite3.connect(INDEX_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM chunks_fts")
    total_chunks = cursor.fetchone()[0]
    conn.close()
    return {
        "models": LLM_MODELS,
        "data_date": "2026-11-19",
        "counts": {"total_chunks": total_chunks}
    }

@app.post("/api/chat")
async def chat(request: Request):
    body = await request.json()
    message = body.get("message", "").strip()
    source_filter = body.get("source", "both")
    
    if not message:
        return JSONResponse({"error": "Message is required"}, status_code=400)

    # 1. Retrieve
    retrieval_result = retrieve_context(message, source_filter=source_filter, k=5)
    chunks = retrieval_result["chunks"]
    facts = retrieval_result["facts"]
    
    # 2. Format Context (may be empty)
    context_parts = []
    if facts:
        context_parts.append("### PRECOMPUTED FACTS:")
        for i, f in enumerate(facts):
            context_parts.append(f"[F{i+1}] {f.get('category')} in {f.get('city')}: "
                                 f"Count={f.get('count')}, Avg Price={f.get('avg_price')} {f.get('currency')}")
    if chunks:
        context_parts.append("### PASSAGES:")
        for i, c in enumerate(chunks):
            context_parts.append(f"[{i+1}] {c['company']} | {c['title']} | {c.get('city','N/A')}\n"
                                 f"URL: {c['url']}\nText: {c['text_display'][:800]}...")
    context_str = "\n\n".join(context_parts)

    # 3. Stream (works even with empty context → model will refuse per system prompt)
    async def event_generator():
        yield f"data: {json.dumps({'type': 'meta', 'model': LLM_MODELS[0]})}\n\n"
        if not context_str:
            # Skip the LLM entirely: save quota, guarantee instant graceful refusal
            msg = ("I couldn't find this in the collected data. Try asking about "
                   "DarGlobal projects (e.g. Trump Tower Jeddah, AIDA, Aston Martin) "
                   "or Wasalt listings by city. "
                   "Figures are indicative and subject to change.")
            yield f"data: {json.dumps({'type': 'token', 'content': msg})}\n\n"
            yield f"data: {json.dumps({'type': 'citations', 'data': []})}\n\n"
            yield f"data: {json.dumps({'type': 'done'})}\n\n"
            return
        full_answer = []
        async for token in stream_llm_response(SYSTEM_PROMPT, message, context_str):
            full_answer.append(token)
            yield f"data: {json.dumps({'type': 'token', 'content': token})}\n\n"
        citations = [{"id": i+1, "title": c["title"], "company": c["company"],
                      "url": c["url"], "scraped_at": c["scraped_at"]} for i, c in enumerate(chunks)]
        yield f"data: {json.dumps({'type': 'citations', 'data': citations})}\n\n"
        yield f"data: {json.dumps({'type': 'done'})}\n\n"

    # 2. Format Context
    context_parts = []
    if facts:
        context_parts.append("### PRECOMPUTED FACTS:")
        for i, f in enumerate(facts):
            context_parts.append(f"[F{i+1}] {f.get('category')} in {f.get('city')}: Count={f.get('count')}, Avg Price={f.get('avg_price')} {f.get('currency')}")
            
    context_parts.append("### PASSAGES:")
    for i, c in enumerate(chunks):
        context_parts.append(f"[{i+1}] {c['company']} | {c['title']} | {c.get('city', 'N/A')}\nURL: {c['url']}\nText: {c['text_display'][:800]}...")
        
    context_str = "\n\n".join(context_parts)
    
    # 3. Stream LLM
    async def event_generator():
        # Send metadata first
        yield f"data: {json.dumps({'type': 'meta', 'model': LLM_MODELS[0]})}\n\n"
        
        full_answer = []
        async for token in stream_llm_response(SYSTEM_PROMPT, message, context_str):
            full_answer.append(token)
            yield f"data: {json.dumps({'type': 'token', 'content': token})}\n\n"
            
        # Build citations
        citations = []
        for i, c in enumerate(chunks):
            citations.append({
                "id": i + 1,
                "title": c["title"],
                "company": c["company"],
                "url": c["url"],
                "scraped_at": c["scraped_at"]
            })
            
        yield f"data: {json.dumps({'type': 'citations', 'data': citations})}\n\n"
        yield f"data: {json.dumps({'type': 'done'})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")
# app/main.py
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path
import json
from app.config import INDEX_PATH, DATA_DATE
from app.retrieval.store import retrieve, get_chunk, counts
from app.retrieval.router import route
from app.retrieval.facts import listing_facts, facts_to_text
from app.llm.prompts import SYSTEM, build_context, citations_from
from app.llm.client import stream, verify_models
from app.llm.guard import check
from app.llm.fallback import sources_only
from app.api import cache, ratelimit

app = FastAPI(title="DarGlobal × Wasalt RAG")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

UI_DIR = Path(__file__).parent / "ui"
app.mount("/ui", StaticFiles(directory=str(UI_DIR)), name="ui")

CHAIN: list[str] = []

@app.on_event("startup")
def _boot():
    global CHAIN
    cache.load()
    CHAIN = verify_models()
    print(f"[startup] model chain: {CHAIN}")

def ev(obj): 
    return f"data: {json.dumps(obj, ensure_ascii=False)}\n\n"

@app.get("/")
def root(): 
    return FileResponse(str(UI_DIR / "index.html"))

@app.get("/api/health")
def health(): 
    return {"ok": True}

@app.get("/api/meta")
def meta():
    c = counts()
    return {
        "model": CHAIN[0] if CHAIN else None, 
        "models": CHAIN, 
        "data_date": DATA_DATE,
        "pages_indexed": c["darglobal"], 
        "wasalt_listings": c["wasalt"],
        "sources": 2, 
        "chunks": c["chunks"], 
        "budget_remaining": ratelimit.remaining()
    }

@app.get("/api/source/{chunk_id}")
def source(cid: str):
    c = get_chunk(cid)
    if not c: 
        return JSONResponse({"error": "not found"}, 404)
    return {k: c.get(k) for k in ("title", "company", "url", "scraped_at", "page_type", "city", "country", "language")} | {"text_display": c["text_display"]}

@app.post("/api/chat")
async def chat(req: Request):
    body = await req.json()
    msg = (body.get("message") or "").strip()
    source_f = body.get("source", "both")
    lang = body.get("lang", "auto")
    
    if not msg: 
        return JSONResponse({"error": "message required"}, 400)

    ip = req.headers.get("x-forwarded-for", req.client.host).split(",")[0]
    # Use "auto" for lang in cache key to match seed_cache.py
    ck = cache.key(msg, source_f, "auto")
    hit = cache.get(ck)

    # Router + retrieval
    r = route(msg)
    facts = listing_facts(**{k: v for k, v in r["entities"].items() if k in ("city", "purpose", "property_type")}) if r["intent"] == "numeric_stats" else []
    # Fetch more chunks if the user is asking for a list or statistics
    k_val = 10 if r["intent"] in ("listing_search", "numeric_stats") else 5
    chunks = retrieve(msg, source_f, k=k_val)
    ctx = build_context(facts_to_text(facts), chunks)

    async def gen():
        try:
            if hit:
                yield ev({"type": "meta", "model": hit.get("model", "cache"), "cached": True})
                yield ev({"type": "token", "content": hit["answer"]})
                yield ev({"type": "citations", "data": hit["citations"]})
                yield ev({"type": "done"})
                return

            # GUARANTEED SSE FALLBACK (No JSONResponse!)
            if not chunks and not facts:
                yield ev({"type": "meta", "model": None, "cached": False})
                yield ev({"type": "token", "content": sources_only([])})
                yield ev({"type": "citations", "data": []})
                yield ev({"type": "done"})
                return

            if not ratelimit.per_ip_ok(ip):
                yield ev({"type": "warning", "content": "Rate limit reached — showing sources only."})
                yield ev({"type": "token", "content": sources_only(chunks)})
                yield ev({"type": "citations", "data": citations_from(chunks)})
                yield ev({"type": "done"})
                return

            if not ratelimit.budget_ok() or not CHAIN:
                yield ev({"type": "warning", "content": "Live answers limited — showing sources only."})
                yield ev({"type": "token", "content": sources_only(chunks)})
                yield ev({"type": "citations", "data": citations_from(chunks)})
                yield ev({"type": "done"})
                return

            ratelimit.spend()
            user_msg = ctx + "\n\nQUESTION:\n" + msg
            full, used_model = [], None
            
            try:
                async for model, tok in stream(CHAIN, SYSTEM, user_msg):
                    if not tok: continue
                    used_model = model
                    if not full:
                        yield ev({"type": "meta", "model": model, "cached": False})
                    full.append(tok)
                    yield ev({"type": "token", "content": tok})
            except Exception as e:
                yield ev({"type": "warning", "content": f"Model unavailable: {e}"})
                yield ev({"type": "token", "content": sources_only(chunks)})

            answer = "".join(full)
            bad = check(answer, ctx)
            if bad:
                yield ev({"type": "warning", "content": "⚠ Some figures couldn't be verified."})
                
            cits = citations_from(chunks)
            yield ev({"type": "citations", "data": cits})
            
            if answer:
                cache.set(ck, {"answer": answer, "citations": cits, "model": used_model})
                
            yield ev({"type": "done"})
            
        except Exception as fatal:
            import traceback
            traceback.print_exc()
            yield ev({"type": "error", "content": f"{type(fatal).__name__}: {fatal}"})

    return StreamingResponse(gen(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
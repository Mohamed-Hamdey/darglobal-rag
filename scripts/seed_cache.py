import asyncio, json
from pathlib import Path
from app.llm.client import stream, verify_models
from app.llm.prompts import SYSTEM, build_context, citations_from
from app.retrieval.store import retrieve
from app.retrieval.facts import listing_facts, facts_to_text
from app.api import cache

STARTERS = [
    ("What branded residences does DarGlobal partner with?", "both"),
    ("Typical apartment prices in Riyadh?", "wasalt"),
    ("Tell me about Trump Tower Jeddah", "darglobal"),
    ("ما هي مشاريع دار جلوبال في السعودية؟", "both"),
    ("How do Wasalt listings break down by city?", "wasalt"),
    ("What is DarGlobal's investment focus?", "darglobal"),
]

async def main():
    chain = verify_models()
    cache.load()
    for q, src in STARTERS:
        chunks = retrieve(q, src, 5)
        facts = listing_facts(**{}) if "price" in q.lower() else []
        ctx = build_context(facts_to_text(facts), chunks)
        full = []
        async for m, tok in stream(chain, SYSTEM, ctx + "\n\nQUESTION:\n" + q):
            full.append(tok)
        cache.set(cache.key(q, src, "auto"), {"answer": "".join(full),
                                              "citations": citations_from(chunks), "model": m})
        print("seeded:", q[:40])
    Path("data/starter_answers.json").write_text(
        json.dumps(cache._cache, ensure_ascii=False, indent=1), encoding="utf-8")
    print("saved data/starter_answers.json")

asyncio.run(main())
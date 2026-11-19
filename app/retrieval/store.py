# app/retrieval/store.py
import sqlite3, json, re
from pathlib import Path
from app.config import INDEX_PATH

GAZ_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "gazetteer.json"
_gaz = None

def load_gazetteer():
    global _gaz
    if _gaz is None:
        try:
            _gaz = json.loads(GAZ_PATH.read_text(encoding="utf-8"))
        except Exception:
            _gaz = {"ar_to_en": {}, "en_to_ar": {}}
    return _gaz

def sanitize_fts_query(query: str) -> str:
    return re.sub(r'[^a-zA-Z0-9\u0600-\u06FF\s]', ' ', query).strip()

def expand_tokens(query: str) -> str:
    """Return an FTS5 MATCH string: original tokens OR'd with gazetteer expansions."""
    g = load_gazetteer()
    toks = [t for t in sanitize_fts_query(query).split() if t]
    out = set(toks)
    for t in toks:
        out.update(g["ar_to_en"].get(t, []))
        out.update(g["en_to_ar"].get(t, []))
    # multi-word brand alias
    if "دار جلوبال" in query or "darglobal" in query.lower():
        out.update(["darglobal", "dar", "global"])
    return " OR ".join(sorted(out))

def retrieve_context(query: str, source_filter: str = "both", k: int = 5) -> dict:
    conn = sqlite3.connect(INDEX_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    match_str = expand_tokens(query)
    cols = ("chunk_id, doc_id, title, text_display, source, company, url, "
            "scraped_at, city, property_type, price_value, currency")
    where_src = ""
    if source_filter == "darglobal":
        where_src = " AND source='darglobal'"
    elif source_filter == "wasalt":
        where_src = " AND source='wasalt'"

    chunks = []
    if match_str:
        try:
            cur.execute(f"SELECT {cols} FROM chunks_fts WHERE chunks_fts MATCH ?{where_src} "
                        f"ORDER BY rank LIMIT ?", (match_str, k))
            chunks = [dict(r) for r in cur.fetchall()]
        except sqlite3.OperationalError:
            chunks = []

    # LIKE fallback (handles morphological Arabic FTS misses)
    if not chunks:
        like = f"%{sanitize_fts_query(query)[:40]}%"
        cur.execute(f"SELECT {cols} FROM chunks_fts WHERE text_search LIKE ?{where_src} LIMIT ?", (like, k))
        chunks = [dict(r) for r in cur.fetchall()]

    # If still nothing and filter is 'both', drop the filter (graceful degradation)
    if not chunks and source_filter != "both":
        cur.execute(f"SELECT {cols} FROM chunks_fts WHERE chunks_fts MATCH ? ORDER BY rank LIMIT ?",
                    (match_str, k))
        chunks = [dict(r) for r in cur.fetchall()]

    facts = []
    if any(kw in query.lower() for kw in ["price", "median", "average", "cost", "how much", "سعر", "متوسط", "أسعار"]):
        cur.execute("SELECT * FROM aggregates LIMIT 3")
        facts = [dict(r) for r in cur.fetchall()]

    conn.close()
    return {"chunks": chunks, "facts": facts}
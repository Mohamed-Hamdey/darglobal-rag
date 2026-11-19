# app/retrieval/store.py
import sqlite3, json, re
from app.config import INDEX_PATH, GAZETTEER_PATH
from app.core.text_ar import normalize_ar

_gaz = None
def gaz():
    global _gaz
    if _gaz is None:
        try: 
            _gaz = json.loads(GAZETTEER_PATH.read_text(encoding="utf-8"))
        except Exception: 
            _gaz = {"ar_to_en": {}, "en_to_ar": {}}
    return _gaz

def sanitize(q: str) -> str:
    return re.sub(r'[^a-zA-Z0-9\u0600-\u06FF\s]', ' ', q).strip()

def strip_ar_prefixes(word: str) -> str:
    """Strip common Arabic prefixes (ب, ل, ك, و, ف, وال) for better dictionary matching."""
    word = word.strip()
    if word.startswith(("ب", "ل", "ك", "و", "ف")) and len(word) > 2:
        word = word[1:]
    if word.startswith("وال") and len(word) > 3:
        word = word[2:]
    return word

def expand(query: str) -> str:
    g = gaz()
    norm_q = normalize_ar(query.lower())
    toks = set()
    for t in sanitize(query).split():
        tl = t.lower()
        toks.add(tl)
        
        # Strip prefixes before looking up in the gazetteer
        clean_t = strip_ar_prefixes(tl)
        clean_norm = strip_ar_prefixes(normalize_ar(t))
        
        toks.update(x.lower() for x in g["ar_to_en"].get(clean_t, []))
        toks.update(x.lower() for x in g["ar_to_en"].get(clean_norm, []))
        toks.update(x.lower() for x in g["en_to_ar"].get(clean_t, []))
        
    if "دار جلوبال" in norm_q or "darglobal" in norm_q or "dar global" in norm_q:
        toks.update({"darglobal", "dar", "global"})
        
    toks = {t for t in toks if len(t) > 1}
    parts = [f'"{t}"' if " " in t else t for t in sorted(toks)]
    return " OR ".join(parts) if parts else ""

COLS = ("chunk_id, doc_id, title, text_display, source, company, url, scraped_at, "
        "city, property_type, purpose, price_value, currency, page_type, language")

def _src_clause(f):
    return {"darglobal": " AND source='darglobal'", "wasalt": " AND source='wasalt'"}.get(f, "")

def retrieve(query: str, source_filter: str = "both", k: int = 5) -> list[dict]:
    conn = sqlite3.connect(f"file:{INDEX_PATH}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    match = expand(query)
    src = _src_clause(source_filter)
    rows = []

    # 1. Try strict FTS5 MATCH first
    if match:
        try:
            cur.execute(f"SELECT {COLS} FROM chunks_fts WHERE chunks_fts MATCH ?{src} "
                        f"ORDER BY rank LIMIT ?", (match, k))
            rows = [dict(r) for r in cur.fetchall()]
        except sqlite3.OperationalError:
            rows = []

    # 2. LIKE fallback against the EXPANSIONS (bridges AR→EN corpus), not the raw query
    if not rows and match:
        toks = [t.strip('"') for t in match.split(" OR ") if t.strip('"')]
        # Limit to 8 tokens to prevent massive SQL strings
        conds = " OR ".join(["text_search LIKE ?"] * min(len(toks), 8))
        params = [f"%{t}%" for t in toks[:8]]
        cur.execute(f"SELECT {COLS} FROM chunks_fts WHERE ({conds}){src} LIMIT ?", (*params, k))
        rows = [dict(r) for r in cur.fetchall()]

    # 3. Graceful degradation: if still no rows and filter is specific, drop the filter
    if not rows and source_filter != "both" and match:
        toks = [t.strip('"') for t in match.split(" OR ") if t.strip('"')]
        conds = " OR ".join(["text_search LIKE ?"] * min(len(toks), 8))
        params = [f"%{t}%" for t in toks[:8]]
        cur.execute(f"SELECT {COLS} FROM chunks_fts WHERE ({conds}) LIMIT ?", (*params, k))
        rows = [dict(r) for r in cur.fetchall()]

    conn.close()
    return rows

def get_chunk(chunk_id: str) -> dict | None:
    conn = sqlite3.connect(f"file:{INDEX_PATH}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute(f"SELECT {COLS} FROM chunks_fts WHERE chunk_id = ?", (chunk_id,))
    r = cur.fetchone()
    conn.close()
    return dict(r) if r else None

def counts() -> dict:
    conn = sqlite3.connect(f"file:{INDEX_PATH}?mode=ro", uri=True)
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM chunks_fts")
    total = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM chunks_fts WHERE source='darglobal'")
    dg = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM chunks_fts WHERE source='wasalt'")
    wa = cur.fetchone()[0]
    conn.close()
    return {"chunks": total, "darglobal": dg, "wasalt": wa}
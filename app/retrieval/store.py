# app/retrieval/store.py
import sqlite3
import re
from typing import List, Dict, Any
from app.config import INDEX_PATH

def sanitize_fts_query(query: str) -> str:
    # Prevent FTS5 syntax errors/injection
    return re.sub(r'[^a-zA-Z0-9\u0600-\u06FF\s]', ' ', query).strip()

def retrieve_context(query: str, source_filter: str = "both", k: int = 5) -> Dict[str, Any]:
    conn = sqlite3.connect(INDEX_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    clean_query = sanitize_fts_query(query)
    
    # Base FTS5 query
    sql = """
        SELECT chunk_id, doc_id, title, text_display, source, company, url, scraped_at, city, property_type, price_value, currency
        FROM chunks_fts
        WHERE text_search MATCH ?
    """
    params = [clean_query]
    
    if source_filter == "darglobal":
        sql += " AND source = 'darglobal'"
    elif source_filter == "wasalt":
        sql += " AND source = 'wasalt'"
        
    sql += " ORDER BY rank LIMIT ?"
    params.append(k)
    
    cursor.execute(sql, params)
    chunks = [dict(row) for row in cursor.fetchall()]
    
    # Simple heuristic for numeric intent to fetch aggregates
    numeric_keywords = ["price", "median", "average", "cost", "how much", "سعر", "متوسط"]
    facts = []
    if any(kw in query.lower() for kw in numeric_keywords):
        cursor.execute("SELECT * FROM aggregates LIMIT 3")
        facts = [dict(row) for row in cursor.fetchall()]
        
    conn.close()
    return {"chunks": chunks, "facts": facts}
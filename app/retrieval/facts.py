import sqlite3
from app.config import INDEX_PATH

def listing_facts(city=None, purpose=None, property_type=None, limit=3) -> list[dict]:
    conn = sqlite3.connect(f"file:{INDEX_PATH}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    sql, params = "SELECT * FROM aggregates WHERE 1=1", []
    
    if city:
        sql += " AND city = ?"
        params.append(city)
    if purpose:
        sql += " AND purpose = ?"
        params.append(purpose)
    if property_type:
        sql += " AND property_type = ?"
        params.append(property_type)
        
    sql += " ORDER BY count DESC LIMIT ?"
    params.append(limit)
    
    cur.execute(sql, params)
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows

def facts_to_text(facts: list[dict]) -> str:
    out = []
    for i, f in enumerate(facts, 1):
        out.append(f"[F{i}] Wasalt {f['property_type']} for {f['purpose']} in {f['city']}: "
                   f"{f['count']} listings, median price {f['median_price']:,.0f} {f['currency']}, "
                   f"average {f['avg_price']:,.0f} {f['currency']}. Computed {f['as_of']}.")
    return "\n".join(out)
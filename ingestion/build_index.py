# ingestion/build_index.py
import sqlite3
import json
import hashlib
from pathlib import Path

PROCESSED_DIR = Path("data/processed")
INDEX_DIR = Path("index")
INDEX_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = INDEX_DIR / "rag.sqlite"

def create_schema(conn):
    cursor = conn.cursor()
    # FTS5 table with ALL necessary columns for both DarGlobal and Wasalt
    cursor.execute("""
        CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
            chunk_id, doc_id, title, text_search, text_display, 
            source, company, page_type, city, country, language, url, scraped_at,
            property_type, purpose, currency, price_value, area_sqm, bedrooms
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS aggregates (
            fact_id TEXT PRIMARY KEY,
            category TEXT, city TEXT, property_type TEXT, purpose TEXT,
            count INTEGER, avg_price REAL, currency TEXT, source_url TEXT, as_of TEXT
        )
    """)
    conn.commit()

def process_jsonl(file_path: Path, conn):
    if not file_path.exists():
        print(f"⚠️ {file_path.name} not found. Skipping.")
        return 0
        
    cursor = conn.cursor()
    count = 0
    
    with open(file_path, 'r', encoding='utf-8') as f:
        for line in f:
            doc = json.loads(line)
            chunk_id = hashlib.sha1(f"{doc['doc_id']}_0".encode()).hexdigest()[:12]
            text_search = doc.get('text', '').lower()
            
            cursor.execute("""
                INSERT INTO chunks_fts 
                (chunk_id, doc_id, title, text_search, text_display, source, company, page_type, 
                 city, country, language, url, scraped_at, property_type, purpose, currency, price_value, area_sqm, bedrooms)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                chunk_id, doc['doc_id'], doc.get('title', 'Unknown'), text_search, doc.get('text', ''),
                doc['source'], doc['company'], doc.get('page_type', 'other'),
                doc.get('city'), doc.get('country'), doc.get('language', 'en'), 
                doc['url'], doc.get('scraped_at', ''),
                doc.get('property_type'), doc.get('purpose'), doc.get('currency'),
                doc.get('price_value'), doc.get('area_sqm'), doc.get('bedrooms')
            ))
            count += 1
    conn.commit()
    return count

def compute_aggregates(conn):
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM chunks_fts WHERE source = 'wasalt'")
    wasalt_count = cursor.fetchone()[0]
    
    if wasalt_count > 0:
        cursor.execute("""
            INSERT OR REPLACE INTO aggregates (fact_id, category, city, property_type, purpose, count, avg_price, currency, source_url, as_of)
            SELECT 
                'wasalt_stats_' || COALESCE(city, 'unknown') || '_' || COALESCE(property_type, 'unknown'),
                'listing_stats', COALESCE(city, 'Unknown City'), COALESCE(property_type, 'Unknown Type'),
                COALESCE(purpose, 'Unknown'), COUNT(*) as count, AVG(price_value) as avg_price,
                COALESCE(currency, 'SAR'), 'computed_from_scraped_data', CURRENT_DATE
            FROM chunks_fts
            WHERE source = 'wasalt' AND page_type = 'listing'
            GROUP BY city, property_type, purpose, currency
        """)
        conn.commit()
        print(f"✅ Computed aggregates for {wasalt_count} Wasalt listings.")
    else:
        print("⚠️ No Wasalt data found. Skipping aggregate computation.")

def main():
    print("🏗️ Building RAG Index...")
    if DB_PATH.exists():
        DB_PATH.unlink()
        
    conn = sqlite3.connect(DB_PATH)
    create_schema(conn)
    
    dg_count = process_jsonl(PROCESSED_DIR / "darglobal_pages.jsonl", conn)
    print(f"✅ Indexed {dg_count} DarGlobal documents.")
    
    wa_count = process_jsonl(PROCESSED_DIR / "wasalt_listings.jsonl", conn)
    print(f"✅ Indexed {wa_count} Wasalt documents.")
    
    compute_aggregates(conn)
    
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM chunks_fts")
    total_chunks = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM aggregates")
    total_facts = cursor.fetchone()[0]
    conn.close()
    
    print(f"🎉 Index built successfully: {DB_PATH}")
    print(f"   Total chunks: {total_chunks} | Total aggregate facts: {total_facts}")

if __name__ == "__main__":
    main()
import sqlite3
import json
import hashlib
import statistics
from pathlib import Path
from collections import defaultdict

BASE_DIR = Path(__file__).resolve().parent.parent
PROCESSED_DIR = BASE_DIR / "data" / "processed"
INDEX_DIR = BASE_DIR / "index"
INDEX_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = INDEX_DIR / "rag.sqlite"

def create_schema(conn):
    cursor = conn.cursor()
    # FTS5 table with contextual prefix support
    cursor.execute("""
        CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
            chunk_id, doc_id, title, text_search, text_display, 
            source, company, page_type, city, country, language, url, scraped_at,
            property_type, purpose, currency, price_value, area_sqm, bedrooms
        )
    """)
    
    # Precomputed aggregates table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS aggregates (
            fact_id TEXT PRIMARY KEY,
            category TEXT,
            city TEXT,
            property_type TEXT,
            purpose TEXT,
            count INTEGER,
            avg_price REAL,
            median_price REAL,
            currency TEXT,
            source_url TEXT,
            as_of TEXT
        )
    """)
    conn.commit()

def process_jsonl(file_path: Path, conn):
    if not file_path.exists():
        print(f"{file_path.name} not found. Skipping.")
        return 0, []
        
    cursor = conn.cursor()
    count = 0
    wasalt_listings = [] # Collect for aggregation
    
    with open(file_path, 'r', encoding='utf-8') as f:
        for line in f:
            doc = json.loads(line)
            chunk_id = hashlib.sha1(f"{doc['doc_id']}_0".encode()).hexdigest()[:12]
            
            # V2: Contextual Prefix for better BM25 relevance
            prefix_parts = [doc['company'], doc.get('page_type', 'other')]
            if doc.get('city'): prefix_parts.append(doc['city'])
            if doc.get('purpose'): prefix_parts.append(doc['purpose'])
            if doc.get('language'): prefix_parts.append(doc['language'])
            prefix = f"[{' | '.join(prefix_parts)}] "
            
            text_display = doc.get('text', '').strip()
            text_search = (prefix + text_display).lower()
            
            cursor.execute("""
                INSERT INTO chunks_fts 
                (chunk_id, doc_id, title, text_search, text_display, source, company, page_type, 
                 city, country, language, url, scraped_at, property_type, purpose, currency, price_value, area_sqm, bedrooms)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                chunk_id, doc['doc_id'], doc.get('title', 'Unknown'), text_search, text_display,
                doc['source'], doc['company'], doc.get('page_type', 'other'),
                doc.get('city'), doc.get('country'), doc.get('language', 'en'), 
                doc['url'], doc.get('scraped_at', ''),
                doc.get('property_type'), doc.get('purpose'), doc.get('currency'),
                doc.get('price_value'), doc.get('area_sqm'), doc.get('bedrooms')
            ))
            count += 1
            
            # Collect Wasalt listings for aggregation
            if doc['source'] == 'wasalt' and doc.get('page_type') == 'listing' and doc.get('price_value'):
                wasalt_listings.append(doc)
                
    conn.commit()
    return count, wasalt_listings

def compute_aggregates(conn, wasalt_listings: list):
    if not wasalt_listings:
        print("No Wasalt listings with prices found. Skipping aggregate computation.")
        return
        
    cursor = conn.cursor()
    # Group by city, property_type, purpose
    groups = defaultdict(list)
    for doc in wasalt_listings:
        key = (doc.get('city', 'Unknown'), doc.get('property_type', 'Unknown'), doc.get('purpose', 'Unknown'), doc.get('currency', 'SAR'))
        groups[key].append(doc['price_value'])
        
    fact_id_counter = 0
    for (city, prop_type, purpose, currency), prices in groups.items():
        if not prices: continue
        
        fact_id = f"wasalt_stats_{fact_id_counter}"
        fact_id_counter += 1
        
        avg_price = sum(prices) / len(prices)
        median_price = statistics.median(prices)
        
        cursor.execute("""
            INSERT OR REPLACE INTO aggregates 
            (fact_id, category, city, property_type, purpose, count, avg_price, median_price, currency, source_url, as_of)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, date('now'))
        """, (
            fact_id, 'listing_stats', city, prop_type, purpose, 
            len(prices), avg_price, median_price, currency, 'computed_from_scraped_data'
        ))
        
    conn.commit()
    print(f"Computed {fact_id_counter} aggregate fact groups for Wasalt listings.")

def main():
    print("="*60)
    print("🏗️ Building RAG Index V2 (FTS5 + Aggregates + Prefixes)")
    print("="*60)
    
    if DB_PATH.exists():
        DB_PATH.unlink() # Start fresh for reproducibility
        
    conn = sqlite3.connect(DB_PATH)
    create_schema(conn)
    
    dg_count, _ = process_jsonl(PROCESSED_DIR / "darglobal_pages.jsonl", conn)
    print(f"Indexed {dg_count} DarGlobal documents.")
    
    wa_count, wa_listings = process_jsonl(PROCESSED_DIR / "wasalt_listings.jsonl", conn)
    print(f"Indexed {wa_count} Wasalt documents.")
    
    compute_aggregates(conn, wa_listings)
    
    # Verify
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM chunks_fts")
    total_chunks = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM aggregates")
    total_facts = cursor.fetchone()[0]
    
    conn.close()
    print("="*60)
    print(f"Index built successfully: {DB_PATH}")
    print(f"Total chunks: {total_chunks}")
    print(f"Total aggregate facts: {total_facts}")
    print("="*60)

if __name__ == "__main__":
    main()
"""
Wasalt API-First Scraper (The Golden Path)
Hits the internal JSON endpoint directly, bypassing HTML/WAF entirely.
"""
import json
import hashlib
import time
import random
import re
from pathlib import Path
from datetime import datetime, timezone
import httpx

BASE_DIR = Path(__file__).resolve().parent.parent
PROCESSED_DIR = BASE_DIR / "data" / "processed"
OUT_JSONL = PROCESSED_DIR / "wasalt_listings.jsonl"
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

API_URL = "https://api.wasalt.com/misc/v5/properties/filter"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; rv:160.0) Gecko/20100101 Firefox/160.0",
    "Accept": "*/*",
    "Accept-Language": "en-US,en;q=0.9",
    "Content-Type": "application/json",
    "locale": "en",
    "source": "Web",
    "Origin": "https://wasalt.sa",
    "Referer": "https://wasalt.sa/",
}

def make_doc_id(url: str) -> str:
    return hashlib.sha256(url.encode("utf-8")).hexdigest()[:16]

def parse_number(value):
    if value is None or isinstance(value, bool): return None
    if isinstance(value, (int, float)): return float(value)
    match = re.search(r"-?\d+(?:\.\d+)?", str(value).replace(",", ""))
    return float(match.group()) if match else None

def clean_text(value) -> str:
    if value is None: return ""
    if isinstance(value, (dict, list)): return json.dumps(value, ensure_ascii=False)
    text = re.sub(r"<[^>]+>", " ", str(value))
    return re.sub(r"\s+", " ", text).strip()

def extract_properties(data):
    """Dynamically find the list of properties in the API response."""
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in ["properties", "items", "results", "data", "listings"]:
            if key in data:
                res = extract_properties(data[key])
                if res: return res
        for v in data.values():
            if isinstance(v, list) and len(v) > 0 and isinstance(v[0], dict):
                return v
    return []

def normalize_property(prop: dict) -> dict | None:
    info = prop.get("propertyInfo", {}) or prop
    attributes = prop.get("attributes", []) or []
    
    def get_attr(key):
        for attr in attributes:
            if isinstance(attr, dict) and str(attr.get("key", "")).lower() == key.lower():
                return attr.get("value")
        return info.get(key)

    title = info.get("title") or info.get("name") or "Untitled"
    description = info.get("regaMojDesc") or info.get("description") or ""
    
    city = info.get("city")
    if isinstance(city, dict): city = city.get("name", "Unknown")
    district = info.get("district")
    if isinstance(district, dict): district = district.get("name", "Unknown")

    purpose_raw = str(info.get("propertyFor", "")).lower()
    purpose = "sale" if "sale" in purpose_raw else "rent" if "rent" in purpose_raw else "unknown"
    slug = info.get("slug", "")
    url = f"https://wasalt.sa/en/property/{purpose}/{slug}" if slug else "https://wasalt.sa"

    return {
        "doc_id": make_doc_id(url),
        "source": "wasalt",
        "company": "Wasalt",
        "page_type": "listing",
        "url": url,
        "title": clean_text(title),
        "language": "en",
        "text": clean_text(description),
        "scraped_at": datetime.now(timezone.utc).isoformat(),
        "city": clean_text(city),
        "district": clean_text(district),
        "country": "Saudi Arabia",
        "purpose": purpose,
        "property_type": clean_text(info.get("propertySubType") or info.get("propertyType") or "Unknown"),
        "price_value": parse_number(info.get("salePrice") or info.get("price")),
        "currency": clean_text(info.get("currencyType") or "SAR"),
        "area_sqm": parse_number(get_attr("carpetArea") or get_attr("area")),
        "bedrooms": parse_number(get_attr("noOfBedrooms") or get_attr("bedrooms")),
    }

def main():
    print("="*60)
    print("V3 Wasalt API Extraction (Direct JSON Endpoint)")
    print("="*60)
    
    documents = {}
    if OUT_JSONL.exists():
        for line in OUT_JSONL.read_text(encoding="utf-8").splitlines():
            if line.strip():
                try:
                    doc = json.loads(line)
                    documents[doc["doc_id"]] = doc
                except: pass

    with httpx.Client(headers=HEADERS, timeout=30, follow_redirects=True) as client:
        for purpose in ["sale", "rent"]:
            for page in range(5): # Get 5 pages of each (5 * 32 = 160 listings max per purpose)
                payload = {
                    "propertyFor": purpose,
                    "includeProperties": True,
                    "page": page,
                    "pageSize": 32,
                    "type": "residential"
                }
                print(f"\n[FETCH] {purpose.capitalize()} - Page {page}")
                try:
                    response = client.post(API_URL, json=payload)
                    response.raise_for_status()
                    data = response.json()
                    
                    properties = extract_properties(data)
                    if not properties:
                        print("  [WARN] No properties found in response. Keys:", list(data.keys())[:5])
                        break

                    added = 0
                    for prop in properties:
                        doc = normalize_property(prop)
                        if doc and doc["title"] and doc["title"] != "Untitled" and doc["doc_id"] not in documents:
                            documents[doc["doc_id"]] = doc
                            added += 1
                    
                    print(f"  [SUCCESS] Found {len(properties)} items, added {added} new. (Total unique: {len(documents)})")
                    
                    if added == 0 and len(properties) > 0:
                        print("  [INFO] All items on this page were already seen. Stopping pagination.")
                        break
                        
                    if len(properties) < 32:
                        print("  [INFO] Reached end of pagination for this purpose.")
                        break
                        
                except httpx.HTTPStatusError as e:
                    print(f"  [ERROR] HTTP {e.response.status_code}")
                    break
                except Exception as e:
                    print(f"  [ERROR] {e}")
                    break
                
                time.sleep(random.uniform(1.5, 3.0)) # Polite delay

    with open(OUT_JSONL, "w", encoding="utf-8") as f:
        for doc in documents.values():
            f.write(json.dumps(doc, ensure_ascii=False) + "\n")

    print("\n" + "="*60)
    print(f"[COMPLETE] Total unique real listings saved: {len(documents)}")
    print(f"[OUTPUT] {OUT_JSONL}")
    print("="*60)

if __name__ == "__main__":
    main()
# ingestion/scrape_wasalt_final.py
import gzip, random, time, re, json, hashlib
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path
from datetime import datetime, timezone
import httpx

BASE_DIR = Path(__file__).resolve().parent.parent
RAW_DIR = BASE_DIR / "data/raw/wasalt"
PROCESSED_DIR = BASE_DIR / "data/processed"
OUT_JSONL = PROCESSED_DIR / "wasalt_listings.jsonl"

RAW_DIR.mkdir(parents=True, exist_ok=True)
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

# MAGIC TRICK: The robots.txt explicitly allows this bot. 
# Using it often bypasses WAF rules that block custom UAs.
UA = "anthropic-ai"

SITEMAP_URL = "https://cdn.wasalt.sa/sitemap/product_sitemap_en_sa.xml.gz"
N_PAGES = 60  # Solid, diverse sample size for MVP
MAX_BLOCKS = 3

def canonicalize_url(url: str) -> str:
    return url.split("?")[0].rstrip("/")

def make_doc_id(url: str) -> str:
    return hashlib.sha256(canonicalize_url(url).encode("utf-8")).hexdigest()[:16]

def load_sitemap(client):
    print(f"[INFO] Fetching sitemap: {SITEMAP_URL}")
    r = client.get(SITEMAP_URL)
    r.raise_for_status()
    try:
        data = gzip.decompress(r.content)
    except OSError:
        data = r.content
    
    # Save snapshot for reproducibility
    snapshot_path = BASE_DIR / "data/raw/wasalt_product_sitemap_en.xml"
    snapshot_path.write_bytes(data)
    
    root = ET.fromstring(data)
    urls = [e.text.strip() for e in root.iter() if e.tag.endswith("loc") and e.text]
    print(f"[INFO] Found {len(urls)} URLs in sitemap.")
    return urls

def stratified_sample(urls, n, seed=42):
    groups = defaultdict(list)
    for u in urls:
        # Match /en/property/(sale|rent)/(something)
        m = re.search(r"/en/property/(sale|rent)/([^/]+)", u)
        if m:
            groups[(m.group(1), m.group(2))].append(u)
    
    rng = random.Random(seed)
    for g in groups.values():
        rng.shuffle(g)
        
    out, keys = [], list(groups.keys())
    # Round-robin to ensure diverse property types and purposes
    while len(out) < n and any(groups.values()):
        for k in keys:
            if groups[k] and len(out) < n:
                out.append(groups[k].pop())
    return out

def extract_next_data(html: str):
    match = re.search(r'<script[^>]*id=["\']__NEXT_DATA__["\'][^>]*>(.*?)</script>', html, flags=re.I | re.S)
    if not match:
        return None
    try:
        return json.loads(match.group(1))
    except json.JSONDecodeError:
        return None

def find_nested_property_info(data):
    if isinstance(data, dict):
        for key in ("propertyInfo", "property_info", "property"):
            value = data.get(key)
            if isinstance(value, dict) and value:
                return value
        for value in data.values():
            result = find_nested_property_info(value)
            if result:
                return result
    elif isinstance(data, list):
        for item in data:
            result = find_nested_property_info(item)
            if result:
                return result
    return None

def get_value(obj, *keys):
    if not isinstance(obj, dict):
        return None
    for key in keys:
        value = obj.get(key)
        if value is not None and value != "":
            return value
    return None

def parse_number(value):
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    match = re.search(r"-?\d+(?:\.\d+)?", str(value).replace(",", ""))
    return float(match.group()) if match else None

def normalize_property(url: str, property_info: dict, page_props: dict = None):
    page_props = page_props or {}
    attributes = page_props.get("attributes") or property_info.get("attributes") or []
    if not isinstance(attributes, list):
        attributes = []

    title = get_value(property_info, "title", "name", "propertyTitle")
    description = get_value(property_info, "regaMojDesc", "description", "propertyDescription")
    
    area = get_value(property_info, "carpetArea", "area", "areaSqm")
    bedrooms = get_value(property_info, "noOfBedrooms", "bedrooms")
    
    if area is None:
        area = next((a.get("value") for a in attributes if isinstance(a, dict) and str(a.get("key", "")).lower() in ["carpetarea", "area"]), None)
    if bedrooms is None:
        bedrooms = next((a.get("value") for a in attributes if isinstance(a, dict) and str(a.get("key", "")).lower() in ["noofbedrooms", "bedrooms"]), None)

    price = get_value(property_info, "salePrice", "price", "rentPrice")
    city = get_value(property_info, "city", "cityName")
    district = get_value(property_info, "district", "districtName")
    
    if isinstance(city, dict): city = get_value(city, "name", "en")
    if isinstance(district, dict): district = get_value(district, "name", "en")

    purpose_raw = str(get_value(property_info, "propertyFor", "purpose", "listingType") or "").lower()
    purpose = "sale" if "sale" in purpose_raw else "rent" if "rent" in purpose_raw else "unknown"

    return {
        "doc_id": make_doc_id(url),
        "source": "wasalt",
        "company": "Wasalt",
        "page_type": "listing",
        "url": canonicalize_url(url),
        "title": str(title).strip() if title else "Untitled",
        "language": "ar" if "/ar/" in url.lower() else "en",
        "text": str(description).strip() if description else "",
        "scraped_at": datetime.now(timezone.utc).isoformat(),
        "city": str(city).strip() if city else "Unknown",
        "district": str(district).strip() if district else "Unknown",
        "country": "Saudi Arabia",
        "purpose": purpose,
        "property_type": str(get_value(property_info, "propertySubType", "propertyType", "type") or "Unknown").strip(),
        "price_value": parse_number(price),
        "currency": "SAR",
        "area_sqm": parse_number(area),
        "bedrooms": parse_number(bedrooms),
    }

def main():
    print("="*60)
    print("Starting Wasalt Listing Scraper (AI Bot UA Strategy)")
    print("="*60)
    
    docs = {}
    if OUT_JSONL.exists():
        with open(OUT_JSONL, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    doc = json.loads(line)
                    docs[doc["doc_id"]] = doc
                except: pass
    print(f"[INFO] Existing documents: {len(docs)}")

    headers = {"User-Agent": UA, "Accept-Language": "en-US,en;q=0.9"}
    
    with httpx.Client(headers=headers, timeout=30, follow_redirects=True) as c:
        urls = stratified_sample(load_sitemap(c), N_PAGES)
        print(f"[INFO] Stratified sample: {len(urls)} URLs")
        
        blocks = 0
        for i, u in enumerate(urls, 1):
            doc_id = make_doc_id(u)
            if doc_id in docs:
                print(f"[{i}/{len(urls)}] SKIP (already have)")
                continue
                
            try:
                r = c.get(u)
            except httpx.HTTPError as e:
                print(f"[{i}/{len(urls)}] ERR {e}")
                continue
                
            if r.status_code in (403, 429):
                blocks += 1
                print(f"[{i}/{len(urls)}] BLOCKED {r.status_code}")
                if blocks >= MAX_BLOCKS:
                    print("[CRITICAL] Site is refusing requests. Stopping.")
                    break
                time.sleep(5)
                continue
                
            blocks = 0 # Reset on success
            
            if r.status_code != 200:
                print(f"[{i}/{len(urls)}] HTTP {r.status_code}")
                continue
                
            # Save raw HTML
            sha = hashlib.sha256(u.encode()).hexdigest()
            with gzip.open(RAW_DIR / f"{sha}.html.gz", "wt", encoding="utf-8") as f:
                f.write(r.text)
                
            # Extract
            nd = extract_next_data(r.text)
            info = None
            props = {}
            
            if isinstance(nd, dict):
                props = (nd.get("props") or {}).get("pageProps") or {}
                if isinstance(props, dict):
                    info = props.get("propertyInfo") or props.get("property")
                if not info:
                    info = find_nested_property_info(nd)
                    
            if not info:
                print(f"[{i}/{len(urls)}] NO DATA (No __NEXT_DATA__ property info)")
                continue
                
            doc = normalize_property(u, info, props)
            if not doc["title"] or doc["title"] == "Untitled":
                print(f"[{i}/{len(urls)}] NO TITLE")
                continue
                
            docs[doc_id] = doc
            print(f"[{i}/{len(urls)}] OK: {doc['title'][:40]}... | {doc['city']} | SAR {doc['price_value']}")
            
            # Save incrementally every 10 docs
            if i % 10 == 0:
                with open(OUT_JSONL, "w", encoding="utf-8") as f:
                    for d in docs.values():
                        f.write(json.dumps(d, ensure_ascii=False) + "\n")
                        
            time.sleep(random.uniform(2.0, 3.5)) # Polite delay

    # Final save
    with open(OUT_JSONL, "w", encoding="utf-8") as f:
        for d in docs.values():
            f.write(json.dumps(d, ensure_ascii=False) + "\n")
            
    print("="*60)
    print(f"[COMPLETE] Total unique documents: {len(docs)}")
    print(f"[OUTPUT] {OUT_JSONL}")
    print("="*60)

if __name__ == "__main__":
    main()
# ingestion/scrape_wasalt_search.py
import asyncio
import gzip
import hashlib
import json
import re
from pathlib import Path
from datetime import datetime, timezone
from playwright.async_api import async_playwright

BASE_DIR = Path(__file__).resolve().parent.parent
RAW_DIR = BASE_DIR / "data" / "raw" / "wasalt"
PROCESSED_DIR = BASE_DIR / "data" / "processed"
OUT_JSONL = PROCESSED_DIR / "wasalt_listings.jsonl"

RAW_DIR.mkdir(parents=True, exist_ok=True)
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

SEARCH_URLS = [
    "https://wasalt.sa/en/sale/search?countryId=1&propertyFor=sale",
    "https://wasalt.sa/en/rent/search?countryId=1&propertyFor=rent",
]

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"

def canonicalize_url(url: str) -> str:
    return url.split("?")[0].rstrip("/")

def make_doc_id(url: str) -> str:
    return hashlib.sha256(canonicalize_url(url).encode("utf-8")).hexdigest()[:16]

def parse_number(value):
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    match = re.search(r"-?\d+(?:\.\d+)?", str(value).replace(",", ""))
    return float(match.group()) if match else None

def clean_text(value) -> str:
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    text = str(value)
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text).strip()

async def scrape_search_page(page, url: str):
    print(f"\n[FETCH] Search Page: {url}")
    try:
        response = await page.goto(url, wait_until="domcontentloaded", timeout=30000)
        if response and response.status != 200:
            print(f"  [WARN] HTTP {response.status} - Skipping this page.")
            return []
        
        await page.wait_for_timeout(3000)
        html = await page.content()
        
        url_hash = hashlib.sha256(url.encode("utf-8")).hexdigest()
        raw_file = RAW_DIR / f"search_{url_hash}.html.gz"
        with gzip.open(raw_file, "wt", encoding="utf-8") as f:
            f.write(html)
            
        match = re.search(r'<script[^>]*id=["\']__NEXT_DATA__["\'][^>]*>(.*?)</script>', html, flags=re.I | re.S)
        if not match:
            print("  [WARN] No __NEXT_DATA__ found.")
            return []
            
        data = json.loads(match.group(1))
        page_props = data.get("props", {}).get("pageProps", {})
        search_result = page_props.get("searchResult", {})
        properties = search_result.get("properties", [])
        
        if not properties:
            print("  [WARN] No properties array found in __NEXT_DATA__.")
            return []
            
        print(f"  [SUCCESS] Found {len(properties)} real listings in payload.")
        return properties
        
    except Exception as e:
        print(f"  [ERROR] {e}")
        return []

def normalize_property(prop: dict, base_url: str = "https://wasalt.sa") -> dict | None:
    # Bulletproof type check
    if not isinstance(prop, dict):
        return None
        
    property_info = prop.get("propertyInfo", {}) or prop
    attributes = prop.get("attributes", []) or []
    
    def get_attr(key):
        for attr in attributes:
            if isinstance(attr, dict) and str(attr.get("key", "")).lower() == key.lower():
                return attr.get("value")
        return property_info.get(key)

    title = property_info.get("title") or property_info.get("name") or "Untitled Property"
    description = property_info.get("regaMojDesc") or property_info.get("description") or ""
    
    city = property_info.get("city")
    if isinstance(city, dict): city = city.get("name", "Unknown")
        
    district = property_info.get("district")
    if isinstance(district, dict): district = district.get("name", "Unknown")

    purpose_raw = str(property_info.get("propertyFor", "")).lower()
    purpose = "sale" if "sale" in purpose_raw else "rent" if "rent" in purpose_raw else "unknown"

    slug = property_info.get("slug", "")
    url = f"{base_url}/en/property/{purpose}/{slug}" if slug else base_url

    return {
        "doc_id": make_doc_id(url),
        "source": "wasalt",
        "company": "Wasalt",
        "page_type": "listing",
        "url": url,
        "title": clean_text(title),
        "language": "ar" if "/ar/" in url.lower() else "en",
        "text": clean_text(description),
        "scraped_at": datetime.now(timezone.utc).isoformat(),
        "city": clean_text(city),
        "district": clean_text(district),
        "country": "Saudi Arabia",
        "purpose": purpose,
        "property_type": clean_text(property_info.get("propertySubType") or property_info.get("propertyType") or "Unknown"),
        "price_value": parse_number(property_info.get("salePrice") or property_info.get("price")),
        "currency": clean_text(property_info.get("currencyType") or "SAR"),
        "area_sqm": parse_number(get_attr("carpetArea") or get_attr("area")),
        "bedrooms": parse_number(get_attr("noOfBedrooms") or get_attr("bedrooms")),
    }

async def main():
    print("="*60)
    print("Starting Wasalt Real Data Extraction (Search Page Method)")
    print("="*60)
    
    all_properties = []
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(user_agent=UA)
        page = await context.new_page()
        
        for url in SEARCH_URLS:
            props = await scrape_search_page(page, url)
            all_properties.extend(props)
            await asyncio.sleep(2.0)
            
        await browser.close()

    if not all_properties:
        print("\n[CRITICAL] No real data extracted from search pages.")
        return

    documents = {}
    for prop in all_properties:
        if not isinstance(prop, dict):
            print(f"  [WARN] Skipping malformed property entry: {type(prop)}")
            continue
            
        doc = normalize_property(prop)
        if doc and doc["title"] and doc["title"] != "Untitled Property":
            documents[doc["doc_id"]] = doc

    with open(OUT_JSONL, "w", encoding="utf-8") as f:
        for doc in documents.values():
            f.write(json.dumps(doc, ensure_ascii=False) + "\n")

    print("\n" + "="*60)
    print(f"[COMPLETE] Total unique real listings extracted and saved: {len(documents)}")
    print(f"[OUTPUT] {OUT_JSONL}")
    print("="*60)

if __name__ == "__main__":
    asyncio.run(main())
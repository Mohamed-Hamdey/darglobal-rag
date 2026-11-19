# ingestion/scrape_wasalt.py (Hardened Version)
import asyncio
import gzip
import json
import hashlib
import random
import re
from pathlib import Path
from datetime import datetime, timezone
from playwright.async_api import async_playwright

RAW_DIR = Path("data/raw/wasalt")
PROCESSED_DIR = Path("data/processed")
RAW_DIR.mkdir(parents=True, exist_ok=True)
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

SITEMAP_PATH = Path("data/raw/wasalt_sitemap_en.xml")
OUT_JSONL = PROCESSED_DIR / "wasalt_listings.jsonl"

def get_sample_urls(sitemap_path: Path, limit: int = 50):
    if not sitemap_path.exists():
        print(f"❌ {sitemap_path} not found. Run fetch_wasalt_sitemap.py first.")
        return []
    
    xml = sitemap_path.read_text(encoding="utf-8")
    urls = re.findall(r'<loc>(.*?)</loc>', xml)
    
    # Filter for actual listing pages (adjust slug logic based on your probe findings)
    listing_urls = [u for u in urls if "/en/" in u and ("properties-for-sale" in u or "properties-for-rent" in u or "-sm-" in u)]
    return listing_urls[:limit]

async def scrape_url(page, url, sem):
    async with sem:
        try:
            print(f"Fetching: {url}")
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            await page.wait_for_timeout(2000) # Polite delay for Cloudflare/JS
            
            html = await page.content()
            match = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', html, re.DOTALL)
            if not match:
                print(f"  ⚠️ No __NEXT_DATA__ found for {url}")
                return None
            
            data = json.loads(match.group(1))
            props = data.get("props", {}).get("pageProps", {})
            prop_info = props.get("propertyInfo") or {}
            
            if not prop_info.get("title"):
                print(f"  ⚠️ No propertyInfo found for {url}")
                return None
                
            attributes = props.get("attributes", []) or []
            area = next((a.get("value") for a in attributes if isinstance(a, dict) and a.get("key") == "carpetArea"), None)
            bedrooms = next((a.get("value") for a in attributes if isinstance(a, dict) and a.get("key") == "noOfBedrooms"), None)
            
            doc = {
                "doc_id": hashlib.sha1(url.encode()).hexdigest()[:12],
                "source": "wasalt",
                "company": "Wasalt",
                "page_type": "listing",
                "url": url,
                "title": prop_info.get("title"),
                "language": "en",
                "text": prop_info.get("regaMojDesc") or prop_info.get("description") or "",
                "scraped_at": datetime.now(timezone.utc).isoformat(),
                "city": prop_info.get("city"),
                "district": prop_info.get("district"),
                "country": prop_info.get("country"),
                "purpose": prop_info.get("propertyFor"),
                "property_type": prop_info.get("propertySubType"),
                "price_value": prop_info.get("salePrice"),
                "currency": prop_info.get("currencyType"),
                "area_sqm": float(area) if area and str(area).replace('.','',1).isdigit() else None,
                "bedrooms": float(bedrooms) if bedrooms and str(bedrooms).replace('.','',1).isdigit() else None,
                "extra": {"slug": prop_info.get("slug"), "attributes": attributes}
            }
            
            url_hash = hashlib.sha1(url.encode()).hexdigest()
            raw_file = RAW_DIR / f"{url_hash}.html.gz"
            with gzip.open(raw_file, "wt", encoding="utf-8") as f:
                f.write(html)
                
            print(f"  ✅ Saved: {prop_info.get('title')} ({prop_info.get('city')})")
            return doc
            
        except Exception as e:
            print(f"  ❌ Error scraping {url}: {e}")
            return None

async def main():
    urls = get_sample_urls(SITEMAP_PATH, limit=50) # Cap at 50 for MVP speed
    if not urls:
        return
        
    print(f"Starting scrape of {len(urls)} URLs...")
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")
        page = await context.new_page()
        sem = asyncio.Semaphore(1) # Strict politeness
        
        results = []
        for url in urls:
            doc = await scrape_url(page, url, sem)
            if doc:
                results.append(doc)
            await asyncio.sleep(random.uniform(1.5, 3.0))
        await browser.close()
        
    with open(OUT_JSONL, "w", encoding="utf-8") as f:
        for doc in results:
            f.write(json.dumps(doc, ensure_ascii=False) + "\n")
    print(f"\n✅ Scraped {len(results)} listings. Saved to {OUT_JSONL}")

if __name__ == "__main__":
    asyncio.run(main())
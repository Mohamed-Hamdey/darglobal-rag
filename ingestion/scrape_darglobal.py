# ingestion/scrape_darglobal.py (V2: Curated High-Value Targets)
import asyncio
import gzip
import hashlib
import json
import re
from pathlib import Path
from datetime import datetime, timezone
from selectolax.lexbor import LexborHTMLParser
from playwright.async_api import async_playwright

BASE_URL = "https://darglobal.co.uk"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
RAW_DIR = Path("data/raw/darglobal")
PROCESSED_DIR = Path("data/processed")
RAW_DIR.mkdir(parents=True, exist_ok=True)
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

# Curated high-value URLs (Projects, Brands, Investor, Press)
TARGET_URLS = [
    "https://darglobal.co.uk",
    "https://darglobal.co.uk/about",
    "https://darglobal.co.uk/investor",
    "https://darglobal.co.uk/press",
    "https://darglobal.co.uk/partners/aston-martin",
    "https://darglobal.co.uk/aida-trump-international-apartments",
    "https://darglobal.co.uk/trump-tower-jeddah",
    "https://darglobal.co.uk/aida-coastal-investment-villas",
    "https://darglobal.co.uk/aida-trump-international-hotel",
    "https://darglobal.co.uk/aida-trump-international-cliff-villas",
    "https://darglobal.co.uk/aida-trump-villas",
    "https://darglobal.co.uk/trump-international-hotel-and-tower-dubai",
    "https://darglobal.co.uk/landing-page/aida",
    "https://darglobal.co.uk/one-of-one/trump-penthouse",
    "https://darglobal.co.uk/rayana/trump-mansions",
    "https://darglobal.co.uk/rayana/trump-international-qatar",
    "https://darglobal.co.uk/trump-plaza/executive-residences",
    "https://darglobal.co.uk/trump-plaza/park-residences",
    "https://darglobal.co.uk/insights/trump-international-hotel-dubai",
    "https://darglobal.co.uk/development-management",
    "https://darglobal.co.uk/hospitality",
    "https://darglobal.co.uk/luxury-golf-communities",
    "https://darglobal.co.uk/exclusive-membership",
    "https://darglobal.co.uk/careers",
    "https://darglobal.co.uk/get-in-touch",
    "https://darglobal.co.uk/privacy-policy",
    "https://darglobal.co.uk/terms-conditions",
    "https://darglobal.co.uk/why-invest",
    "https://darglobal.co.uk/tokenization",
    "https://darglobal.co.uk/sohar-islamic"
]

async def fetch_and_parse(page, url: str, sem: asyncio.Semaphore):
    async with sem:
        try:
            print(f"Fetching: {url}")
            
            # Stealth: Override automation fingerprints
            await page.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
                Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3] });
                Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
            """)
            
            await page.goto(url, wait_until="networkidle", timeout=30000)
            await page.wait_for_timeout(1500) 
            
            html = await page.content()
            
            if "_Incapsula_Resource" in html or "Checking your browser" in html or len(html) < 1000:
                print(f"  ⚠️ Blocked by WAF or empty: {url}")
                return None
                
            parser = LexborHTMLParser(html)
            title_node = parser.css_first("title")
            title = title_node.text(strip=True) if title_node else "Unknown"
            
            for tag in parser.css("script, style, nav, footer, header, form, iframe"):
                tag.decompose()
                
            text = parser.body.text(separator="\n", strip=True)
            text = re.sub(r"\n{3,}", "\n\n", text).strip()
            
            if len(text) < 150:
                return None
                
            doc_id = hashlib.sha1(url.encode()).hexdigest()[:12]
            raw_file = RAW_DIR / f"{doc_id}.html.gz"
            with gzip.open(raw_file, "wt", encoding="utf-8") as f:
                f.write(html)
                
            return {
                "doc_id": doc_id, "source": "darglobal", "company": "DarGlobal",
                "page_type": "marketing", "url": url, "title": title,
                "language": "en", "text": text,
                "scraped_at": datetime.now(timezone.utc).isoformat(),
                "city": None, "country": None, "property_type": None, 
                "purpose": None, "currency": None, "price_value": None, 
                "area_sqm": None, "bedrooms": None, "brand_partner": None
            }
        except Exception as e:
            print(f"  ❌ Error fetching {url}: {e}")
            return None

async def main():
    print(f"Starting Stealth Playwright scrape of {len(TARGET_URLS)} DarGlobal URLs...")
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=['--disable-blink-features=AutomationControlled', '--no-sandbox', '--disable-setuid-sandbox']
        )
        context = await browser.new_context(user_agent=USER_AGENT, viewport={'width': 1920, 'height': 1080})
        page = await context.new_page()
        sem = asyncio.Semaphore(1) # Strictly 1 at a time to avoid rate limiting
        
        tasks = [fetch_and_parse(page, url, sem) for url in TARGET_URLS]
        results = await asyncio.gather(*tasks)
        await browser.close()
        
    valid_docs = [doc for doc in results if doc is not None]
    out_jsonl = PROCESSED_DIR / "darglobal_pages.jsonl"
    
    with open(out_jsonl, "w", encoding="utf-8") as f:
        for doc in valid_docs:
            f.write(json.dumps(doc, ensure_ascii=False) + "\n")
    print(f"\n✅ Scraped {len(valid_docs)} pages. Saved to {out_jsonl}")

if __name__ == "__main__":
    asyncio.run(main())
# ingestion/scrape_darglobal.py (Maximum Stealth)
import asyncio
import gzip
import hashlib
import json
import re
from pathlib import Path
from datetime import datetime, timezone
import httpx
from selectolax.lexbor import LexborHTMLParser
from playwright.async_api import async_playwright

BASE_URL = "https://darglobal.co.uk"
SITEMAP_URL = f"{BASE_URL}/sitemap.xml"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
RAW_DIR = Path("data/raw/darglobal")
PROCESSED_DIR = Path("data/processed")
RAW_DIR.mkdir(parents=True, exist_ok=True)
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

async def get_sitemap_urls() -> list[str]:
    try:
        async with httpx.AsyncClient(headers={"User-Agent": USER_AGENT}, follow_redirects=True, timeout=15.0) as client:
            res = await client.get(SITEMAP_URL)
            res.raise_for_status()
            content = res.content
            if content.startswith(b'\x1f\x8b'):
                content = gzip.decompress(content)
            
            text = content.decode('utf-8')
            urls = re.findall(r'<loc>(.*?)</loc>', text)
            
            # Target high-value pages only to minimize requests and WAF triggers
            keywords = ['/projects/', '/about', '/investor', '/press', '/trump', '/aida', '/aston']
            high_value = [u for u in urls if any(k in u for k in keywords)]
            
            if not high_value:
                high_value = [u for u in urls if "darglobal.co.uk" in u and not u.endswith(('.xml', '.pdf', '.png', '.jpg', '.svg'))]
            
            print(f"Found {len(high_value)} target URLs. Capping at 20 for MVP.")
            return high_value[:20]
    except Exception as e:
        print(f"❌ Failed to fetch sitemap: {e}")
        return []

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
            
            # Use 'networkidle' to ensure JS challenges complete
            await page.goto(url, wait_until="networkidle", timeout=30000)
            await page.wait_for_timeout(2000) 
            
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
            }
        except Exception as e:
            print(f"  ❌ Error fetching {url}: {e}")
            return None

async def main():
    urls = await get_sitemap_urls()
    if not urls: return
        
    print(f"Starting Stealth Playwright scrape of {len(urls)} DarGlobal URLs...")
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--no-sandbox',
                '--disable-setuid-sandbox'
            ]
        )
        context = await browser.new_context(
            user_agent=USER_AGENT,
            viewport={'width': 1920, 'height': 1080}
        )
        page = await context.new_page()
        sem = asyncio.Semaphore(1) # Strictly 1 at a time to avoid rate limiting
        
        tasks = [fetch_and_parse(page, url, sem) for url in urls]
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
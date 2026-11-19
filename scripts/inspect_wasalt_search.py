import asyncio, gzip, json, re
from pathlib import Path
from playwright.async_api import async_playwright

URL = "https://wasalt.sa/en/sale/search?countryId=1&propertyFor=sale"
UA = "DarGlobalAssignmentBot/1.0 (job assignment; contact: YOUR_EMAIL)"
OUT = Path("data/raw/wasalt_search_sale_p1.html.gz")

def listing_lists(o, path="$"):
    hits = []
    if isinstance(o, list) and len(o) >= 5 and all(isinstance(x, dict) for x in o[:5]):
        keys = set().union(*[set(x) for x in o[:5]])
        score = sum(any(w in k.lower() for k in keys) for w in ("price", "slug", "area", "bed", "title", "city"))
        if score >= 3:
            hits.append((path, len(o), sorted(keys)[:40]))
    if isinstance(o, dict):
        for k, v in o.items():
            hits += listing_lists(v, f"{path}.{k}")
    elif isinstance(o, list):
        for i, v in enumerate(o[:50]):
            hits += listing_lists(v, f"{path}[{i}]")
    return hits

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(headless=True)
        page = await (await b.new_context(user_agent=UA)).new_page()
        r = await page.goto(URL, wait_until="domcontentloaded", timeout=30000)
        print("HTTP", r.status if r else None)
        if r and r.status != 200:
            await b.close(); return                      # blocked = stop, don't retry
        await page.wait_for_timeout(3000)
        html = await page.content()
        OUT.parent.mkdir(parents=True, exist_ok=True)
        with gzip.open(OUT, "wt", encoding="utf-8") as f: f.write(html)
        m = re.search(r'<script[^>]*id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.S)
        print("__NEXT_DATA__ present:", bool(m))
        if m:
            data = json.loads(m.group(1))
            print("pageProps keys:", list((data.get("props", {}).get("pageProps") or {}).keys())[:30])
            for path, n, keys in listing_lists(data)[:5]:
                print("\nLIST", path, "items:", n, "\nkeys:", keys)
        cards = page.locator('a[href*="/en/property/"]')
        print("\ncard links:", await cards.count())
        for i in range(min(2, await cards.count())):
            print(f"--- card {i} text ---\n", (await cards.nth(i).inner_text())[:300])
        await b.close()

asyncio.run(main())
# ingestion/scrape_wasalt_search.py
import asyncio
import hashlib
import json
import random
import re
from datetime import datetime, timezone
from pathlib import Path
from playwright.async_api import async_playwright

BASE_DIR = Path(__file__).resolve().parent.parent
PROCESSED_DIR = BASE_DIR / "data" / "processed"
OUT_JSONL = PROCESSED_DIR / "wasalt_listings.jsonl"

PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

# Set to False locally if you want to visually inspect pagination or test WAF behavior
HEADLESS = True
MAX_PAGES_PER_SEED = 5

# Shard across purposes and sort orders to surface different listings on Page 1.
# Tip: Open wasalt.sa in a browser, apply specific city/district/propertyType filters,
# and paste those exact search URLs here for much broader coverage.
SEED_URLS = [
    "https://wasalt.sa/en/sale/search?countryId=1&propertyFor=sale&page=1",
    "https://wasalt.sa/en/sale/search?countryId=1&propertyFor=sale&page=1&sort=newest",
    "https://wasalt.sa/en/sale/search?countryId=1&propertyFor=sale&page=1&sort=priceAsc",
    "https://wasalt.sa/en/sale/search?countryId=1&propertyFor=sale&page=1&sort=priceDesc",
    "https://wasalt.sa/en/rent/search?countryId=1&propertyFor=rent&page=1",
    "https://wasalt.sa/en/rent/search?countryId=1&propertyFor=rent&page=1&sort=newest",
    "https://wasalt.sa/en/rent/search?countryId=1&propertyFor=rent&page=1&sort=priceAsc",
    "https://wasalt.sa/en/rent/search?countryId=1&propertyFor=rent&page=1&sort=priceDesc",
]

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.0.0 Safari/537.36"
)

NEXT_TEXT_RE = re.compile(r"^(>|»|next)$", re.I)


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
    text = re.sub(r"<[^>]+>", " ", str(value))
    return re.sub(r"\s+", " ", text).strip()


def is_listing_dict(item) -> bool:
    """Return True only when item is a dictionary representing a property listing."""
    if not isinstance(item, dict):
        return False
    info = item.get("propertyInfo") if isinstance(item.get("propertyInfo"), dict) else item
    if not isinstance(info, dict):
        return False
    return any(
        k in info
        for k in ("slug", "title", "salePrice", "price", "propertyType", "propertySubType")
    )


def extract_from_next_data(html: str) -> list[dict]:
    match = re.search(
        r'<script[^>]*id=["\']__NEXT_DATA__["\'][^>]*>(.*?)</script>',
        html,
        flags=re.I | re.S,
    )
    if not match:
        return []
    try:
        payload = json.loads(match.group(1))
    except json.JSONDecodeError:
        return []
    props = payload.get("props", {}).get("pageProps", {})
    raw_props = props.get("searchResult", {}).get("properties", []) or []
    return [x for x in raw_props if is_listing_dict(x)]


def find_properties_in_json(obj) -> list[dict]:
    """Recursively locate a list containing valid property listing dicts."""
    if isinstance(obj, dict):
        for key in ("properties", "items", "results", "listings"):
            val = obj.get(key)
            if isinstance(val, list):
                valid = [x for x in val if is_listing_dict(x)]
                if valid:
                    return valid
        for v in obj.values():
            found = find_properties_in_json(v)
            if found:
                return found
    elif isinstance(obj, list):
        valid = [x for x in obj if is_listing_dict(x)]
        if len(valid) >= 3:
            return valid
        for item in obj:
            found = find_properties_in_json(item)
            if found:
                return found
    return []


def get_listing_key(raw: dict) -> str:
    info = raw.get("propertyInfo") if isinstance(raw.get("propertyInfo"), dict) else raw
    slug = info.get("slug") or info.get("id") or json.dumps(info, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(str(slug).encode("utf-8")).hexdigest()[:16]


def build_record(raw: dict, uid: str, seed_url: str) -> dict:
    info = raw.get("propertyInfo") if isinstance(raw.get("propertyInfo"), dict) else raw
    attributes = raw.get("attributes", []) if isinstance(raw.get("attributes"), list) else []

    def get_attr(key: str):
        for attr in attributes:
            if isinstance(attr, dict) and str(attr.get("key", "")).lower() == key.lower():
                return attr.get("value")
        return info.get(key)

    city = info.get("city")
    if isinstance(city, dict):
        city = city.get("name", "")
    district = info.get("district")
    if isinstance(district, dict):
        district = district.get("name", "")

    purpose_raw = str(info.get("propertyFor") or seed_url).lower()
    purpose = "sale" if "sale" in purpose_raw else "rent" if "rent" in purpose_raw else "unknown"
    slug = info.get("slug", "")
    url = f"https://wasalt.sa/en/property/{purpose}/{slug}" if slug else ""

    record = dict(raw)
    record["_uid"] = uid
    record["_scraped_at"] = datetime.now(timezone.utc).isoformat()
    record["_seed_url"] = seed_url
    record["_url"] = url
    record["_title"] = clean_text(info.get("title") or info.get("name") or "")
    record["_city"] = clean_text(city)
    record["_district"] = clean_text(district)
    record["_purpose"] = purpose
    record["_property_type"] = clean_text(
        info.get("propertySubType") or info.get("propertyType") or ""
    )
    record["_price"] = parse_number(info.get("salePrice") or info.get("price"))
    record["_currency"] = clean_text(info.get("currencyType") or "SAR")
    record["_area_sqm"] = parse_number(get_attr("carpetArea") or get_attr("area"))
    record["_bedrooms"] = parse_number(get_attr("noOfBedrooms") or get_attr("bedrooms"))
    return record


def load_seen_ids(path: Path) -> set[str]:
    seen = set()
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    row = json.loads(line)
                    if isinstance(row, dict) and "_uid" in row:
                        seen.add(row["_uid"])
                except json.JSONDecodeError:
                    continue
    return seen


async def _pick_first_enabled(locator):
    count = await locator.count()
    for i in range(count):
        item = locator.nth(i)
        try:
            if await item.is_visible() and await item.is_enabled():
                return item
        except Exception:
            continue
    return None


async def find_pagination_control(page, target_page: int):
    """Find a real pagination control (not a Swiper/carousel button) for target_page."""
    css_candidates = [
        f'nav a[href*="page={target_page}"]:not([disabled])',
        f'[class*="pagination" i] a[href*="page={target_page}"]:not([disabled])',
        f'[class*="pagination" i] button:has-text("{target_page}"):not([disabled])',
        f'a[href*="page={target_page}"]:not([class*="swiper" i]):not([disabled])',
        f'button:has-text("{target_page}"):not([class*="swiper" i]):not([disabled])',
    ]
    for selector in css_candidates:
        picked = await _pick_first_enabled(page.locator(selector))
        if picked is not None:
            return picked

    regex_candidates = [
        page.locator("nav button, nav a").filter(has_text=NEXT_TEXT_RE),
        page.locator('[class*="pagination" i] button, [class*="pagination" i] a').filter(
            has_text=NEXT_TEXT_RE
        ),
    ]
    for loc in regex_candidates:
        picked = await _pick_first_enabled(loc)
        if picked is not None:
            return picked

    return None


async def scrape_seed(browser, seed_url: str, seen_ids: set[str], out_file):
    context = await browser.new_context(
        user_agent=UA,
        viewport={"width": 1366, "height": 768},
        locale="en-US",
        timezone_id="Asia/Riyadh",
    )
    page = await context.new_page()
    xhr_buffer: list[dict] = []
    seen_json_endpoints: list[str] = []

    async def on_response(response):
        ct = response.headers.get("content-type", "")
        if "application/json" in ct and response.status == 200:
            seen_json_endpoints.append(response.url)
            try:
                data = await response.json()
                props = find_properties_in_json(data)
                if props:
                    xhr_buffer.extend(props)
            except Exception:
                pass

    page.on("response", on_response)

    def flush_items(items: list) -> int:
        added = 0
        for item in items:
            if not is_listing_dict(item):
                continue
            uid = get_listing_key(item)
            if uid not in seen_ids:
                seen_ids.add(uid)
                record = build_record(item, uid, seed_url)
                out_file.write(json.dumps(record, ensure_ascii=False) + "\n")
                added += 1
        out_file.flush()
        return added

    try:
        print(f"\n[SEED] {seed_url}")
        resp = await page.goto(seed_url, wait_until="domcontentloaded", timeout=30000)
        status = resp.status if resp else None
        if status == 403:
            print("  [WARN] Initial load got HTTP 403 (rate/WAF limit hit).")
            return
        if status != 200:
            print(f"  [WARN] Initial load failed with HTTP {status}")
            return

        await page.wait_for_timeout(random.randint(2500, 4000))
        initial_items = extract_from_next_data(await page.content()) or xhr_buffer[:]
        xhr_buffer.clear()
        added = flush_items(initial_items)
        print(f"  [Page 1] +{added} new listings (total unique: {len(seen_ids)})")

        for page_num in range(2, MAX_PAGES_PER_SEED + 1):
            xhr_buffer.clear()
            seen_json_endpoints.clear()

            await page.evaluate("window.scrollTo(0, document.body.scrollHeight * 0.85)")
            await asyncio.sleep(random.uniform(1.5, 3.0))

            next_btn = await find_pagination_control(page, page_num)
            if next_btn is None:
                print(f"  [STOP] No enabled pagination control found for page {page_num}.")
                break

            try:
                await next_btn.scroll_into_view_if_needed(timeout=5000)
                await next_btn.click(timeout=6000)
            except Exception as click_err:
                print(f"  [STOP] Could not click pagination for page {page_num}: {click_err}")
                break

            await page.wait_for_timeout(random.randint(3500, 6000))

            new_batch = xhr_buffer[:] if xhr_buffer else extract_from_next_data(await page.content())
            new_batch = [x for x in new_batch if is_listing_dict(x)]

            if not new_batch:
                print(
                    f"  [Page {page_num}] +0 valid listings. JSON URLs seen: {seen_json_endpoints[-5:]}"
                )
                break

            added = flush_items(new_batch)
            print(f"  [Page {page_num}] +{added} new listings (total unique: {len(seen_ids)})")
            if added == 0:
                print(f"  [INFO] All {len(new_batch)} items on page {page_num} were already seen.")

            await asyncio.sleep(random.uniform(4.0, 8.0))

    finally:
        await context.close()


async def main():
    seen_ids = load_seen_ids(OUT_JSONL)
    print(f"Starting with {len(seen_ids)} existing listings in {OUT_JSONL}")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=HEADLESS)
        with open(OUT_JSONL, "a", encoding="utf-8") as out_file:
            for seed in SEED_URLS:
                await scrape_seed(browser, seed, seen_ids, out_file)
                await asyncio.sleep(random.uniform(9.0, 16.0))
        await browser.close()

    print(f"\nDone. Total unique listings stored: {len(seen_ids)}")


if __name__ == "__main__":
    asyncio.run(main())
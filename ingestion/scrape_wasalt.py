
"""
Wasalt Property Scraper
-----------------------
Scrapes English property listings from Wasalt's sitemap.

Output:
    data/raw/wasalt/<url_hash>.html.gz
    data/processed/wasalt_listings.jsonl

Features:
    - Sitemap XML parsing
    - Listing URL filtering
    - Next.js __NEXT_DATA__ extraction
    - JSON-LD fallback
    - Safe field normalization
    - Retry handling
    - Incremental JSONL updates
    - URL-based deduplication
    - Compressed raw HTML storage
"""

import asyncio
import gzip
import hashlib
import json
import random
import re
import xml.etree.ElementTree as ET

from pathlib import Path
from datetime import datetime, timezone
from urllib.parse import urlsplit, urlunsplit

from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError


# ============================================================
# CONFIGURATION
# ============================================================

BASE_DIR = Path(__file__).resolve().parent.parent

RAW_DIR = BASE_DIR / "data" / "raw" / "wasalt"
PROCESSED_DIR = BASE_DIR / "data" / "processed"

SITEMAP_PATH = BASE_DIR / "data" / "raw" / "wasalt_sitemap_en.xml"
OUT_JSONL = PROCESSED_DIR / "wasalt_listings.jsonl"

MAX_LISTINGS = 50
MAX_RETRIES = 2
REQUEST_TIMEOUT = 30000

MIN_DELAY = 2.0
MAX_DELAY = 4.0

HEADLESS = True

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)

RAW_DIR.mkdir(parents=True, exist_ok=True)
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)


# ============================================================
# HELPERS
# ============================================================

def canonicalize_url(url: str) -> str:
    """Remove fragments and tracking query parameters."""

    parts = urlsplit(url.strip())

    return urlunsplit((
        parts.scheme,
        parts.netloc.lower(),
        parts.path.rstrip("/"),
        "",
        ""
    ))


def make_doc_id(url: str) -> str:
    return hashlib.sha256(
        canonicalize_url(url).encode("utf-8")
    ).hexdigest()[:16]


def clean_text(value) -> str:
    """Convert HTML or arbitrary values into clean text."""

    if value is None:
        return ""

    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)

    text = str(value)

    text = re.sub(r"<script[^>]*>.*?</script>", "", text,
                  flags=re.I | re.S)
    text = re.sub(r"<style[^>]*>.*?</style>", "", text,
                  flags=re.I | re.S)
    text = re.sub(r"<[^>]+>", " ", text)

    text = re.sub(r"\s+", " ", text)

    return text.strip()


def parse_number(value):
    """Safely extract a numeric value from strings."""

    if value is None:
        return None

    if isinstance(value, (int, float)):
        return float(value)

    text = str(value).replace(",", "").strip()

    match = re.search(r"-?\d+(?:\.\d+)?", text)

    if not match:
        return None

    try:
        return float(match.group())
    except ValueError:
        return None


def get_value(obj, *keys):
    """Get the first non-empty value from a dictionary."""

    if not isinstance(obj, dict):
        return None

    for key in keys:
        value = obj.get(key)

        if value is not None and value != "":
            return value

    return None


def find_attribute(attributes, *keys):
    """Find a property attribute by its key."""

    if not isinstance(attributes, list):
        return None

    wanted = {key.lower() for key in keys}

    for attribute in attributes:

        if not isinstance(attribute, dict):
            continue

        key = str(attribute.get("key", "")).lower()

        if key in wanted:
            return attribute.get("value")

    return None


# ============================================================
# SITEMAP
# ============================================================

def is_listing_url(url: str) -> bool:
    """
    Identify likely Wasalt listing URLs.

    Adjust these patterns if your sitemap probe reveals
    a different URL structure.
    """

    parsed = urlsplit(url)

    if "wasalt.sa" not in parsed.netloc.lower() and "wasalt.com" not in parsed.netloc.lower():
        return False

    path = parsed.path.lower()

    if not path.startswith("/en/"):
        return False

    listing_markers = (
        "properties-for-sale",
        "properties-for-rent",
        "property-for-sale",
        "property-for-rent",
        "property",
        "listing",
        "-sm-",
    )

    return any(marker in path for marker in listing_markers)


def get_sample_urls(
    sitemap_path: Path,
    limit: int = MAX_LISTINGS
):
    """Extract unique listing URLs from the sitemap."""

    if not sitemap_path.exists():
        print(f"[ERROR] Sitemap not found: {sitemap_path}")
        return []

    try:
        tree = ET.parse(sitemap_path)
        root = tree.getroot()

    except ET.ParseError as exc:
        print(f"[ERROR] Invalid sitemap XML: {exc}")
        return []

    urls = []

    for element in root.iter():

        if not element.tag.endswith("loc"):
            continue

        url = (element.text or "").strip()

        if url and is_listing_url(url):
            urls.append(canonicalize_url(url))

    # Preserve order while removing duplicates.
    urls = list(dict.fromkeys(urls))

    print(f"[INFO] Total listing URLs discovered: {len(urls)}")

    return urls[:limit]


# ============================================================
# NEXT.JS EXTRACTION
# ============================================================

def find_nested_property_info(data):
    """
    Search nested Next.js payloads for propertyInfo.

    This provides a fallback if the pageProps structure changes.
    """

    if isinstance(data, dict):

        for key in ("propertyInfo", "property_info"):

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


def extract_next_data(html: str):
    """Extract and decode the Next.js data payload."""

    match = re.search(
        r'<script[^>]*id=["\']__NEXT_DATA__["\'][^>]*>'
        r"(.*?)</script>",
        html,
        re.DOTALL | re.IGNORECASE
    )

    if not match:
        return None

    try:
        return json.loads(match.group(1))

    except json.JSONDecodeError:
        return None


def extract_json_ld(html: str):
    """Extract structured JSON-LD data as a fallback."""

    scripts = re.findall(
        r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>'
        r"(.*?)</script>",
        html,
        re.DOTALL | re.IGNORECASE
    )

    results = []

    for script in scripts:

        try:
            data = json.loads(script)
            results.append(data)

        except json.JSONDecodeError:
            continue

    return results


def find_json_ld_property(data):
    """Find a likely real-estate listing in JSON-LD."""

    if isinstance(data, list):

        for item in data:
            result = find_json_ld_property(item)

            if result:
                return result

    elif isinstance(data, dict):

        item_type = data.get("@type", "")

        if isinstance(item_type, list):
            item_type = " ".join(item_type)

        if any(
            marker in str(item_type).lower()
            for marker in ("product", "house", "apartment", "residence")
        ):
            return data

        graph = data.get("@graph")

        if graph:
            result = find_json_ld_property(graph)

            if result:
                return result

        for value in data.values():

            if isinstance(value, (dict, list)):
                result = find_json_ld_property(value)

                if result:
                    return result

    return None


# ============================================================
# PROPERTY NORMALIZATION
# ============================================================

def normalize_property(
    url: str,
    property_info: dict,
    page_props: dict = None
):
    """Convert Wasalt data into the RAG document schema."""

    page_props = page_props or {}

    raw_purpose = str(get_value(property_info, "propertyFor", "purpose", "listingType") or "").lower()
    normalized_purpose = "sale" if "sale" in raw_purpose else "rent" if "rent" in raw_purpose else raw_purpose

    attributes = (
        page_props.get("attributes")
        or property_info.get("attributes")
        or []
    )

    if not isinstance(attributes, list):
        attributes = []

    title = get_value(
        property_info,
        "title",
        "name",
        "propertyTitle"
    )

    description = get_value(
        property_info,
        "regaMojDesc",
        "description",
        "propertyDescription"
    )

    area = get_value(
        property_info,
        "carpetArea",
        "area",
        "areaSqm"
    )

    bedrooms = get_value(
        property_info,
        "noOfBedrooms",
        "bedrooms"
    )

    if area is None:
        area = find_attribute(
            attributes,
            "carpetArea",
            "area",
            "areaSqm"
        )

    if bedrooms is None:
        bedrooms = find_attribute(
            attributes,
            "noOfBedrooms",
            "bedrooms"
        )

    price = get_value(
        property_info,
        "salePrice",
        "price",
        "rentPrice"
    )

    city = get_value(property_info, "city", "cityName")
    district = get_value(property_info, "district", "districtName")

    country = get_value(property_info, "country", "countryName")

    if isinstance(city, dict):
        city = get_value(city, "name", "en")

    if isinstance(district, dict):
        district = get_value(district, "name", "en")

    if isinstance(country, dict):
        country = get_value(country, "name", "en")

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
        "country": clean_text(country),

        "purpose": normalized_purpose,

        "property_type": get_value(
            property_info,
            "propertySubType",
            "propertyType",
            "type"
        ),

        "price_value": parse_number(price),

        "currency": get_value(
            property_info,
            "currencyType",
            "currency"
        ),

        "area_sqm": parse_number(area),
        "bedrooms": parse_number(bedrooms),

        "extra": {
            "slug": get_value(property_info, "slug"),
            "attributes": attributes,
            "raw_price": price,
        }
    }


# ============================================================
# RAW HTML STORAGE
# ============================================================

def save_raw_html(url: str, html: str):

    url_hash = hashlib.sha256(
        canonicalize_url(url).encode("utf-8")
    ).hexdigest()

    raw_file = RAW_DIR / f"{url_hash}.html.gz"

    with gzip.open(raw_file, "wt", encoding="utf-8") as file:
        file.write(html)


# ============================================================
# SCRAPER
# ============================================================

async def scrape_url(page, url: str):

    for attempt in range(1, MAX_RETRIES + 2):

        try:

            print(f"\n[FETCH] {url} | Attempt {attempt}")

            response = await page.goto(
                url,
                wait_until="domcontentloaded",
                timeout=REQUEST_TIMEOUT
            )

            if response:

                status = response.status

                if status in (404, 410):
                    print(f"[SKIP] HTTP {status}")
                    return None

                if status in (403, 429):
                    print(f"[WARN] HTTP {status}; access restricted")
                    return None

                if status >= 500:
                    raise RuntimeError(f"Server returned HTTP {status}")

            # Allow client-side data initialization.
            await page.wait_for_timeout(1500)

            html = await page.content()

            if not html:
                raise ValueError("Empty HTML response")

            # 1. Try Next.js payload.
            next_data = extract_next_data(html)

            property_info = None
            page_props = {}

            if next_data:

                page_props = (
                    next_data.get("props", {})
                    .get("pageProps", {})
                )

                if isinstance(page_props, dict):

                    property_info = (
                        page_props.get("propertyInfo")
                        or page_props.get("property")
                    )

                if not property_info:
                    property_info = find_nested_property_info(
                        next_data
                    )

            # 2. JSON-LD fallback.
            if not property_info:

                json_ld_data = extract_json_ld(html)

                for data in json_ld_data:

                    property_info = find_json_ld_property(data)

                    if property_info:
                        break

            if not property_info:

                print("[WARN] No property data found")

                return None

            if not isinstance(property_info, dict):
                return None

            # Avoid saving category/search pages as listings.
            title = get_value(
                property_info,
                "title",
                "name",
                "propertyTitle"
            )

            if not title:
                print("[WARN] Property title missing")
                return None

            doc = normalize_property(
                url,
                property_info,
                page_props
            )

            if not doc["text"]:
                print("[WARN] Description is empty")

            save_raw_html(url, html)

            print(
                f"[SUCCESS] {doc['title']} | "
                f"{doc['city'] or 'Unknown city'}"
            )

            return doc

        except PlaywrightTimeoutError:
            print(f"[TIMEOUT] {url}")

        except Exception as exc:
            print(f"[ERROR] {url}: {exc}")

        if attempt <= MAX_RETRIES:
            delay = attempt * random.uniform(2, 4)

            print(f"[RETRY] Waiting {delay:.1f} seconds")

            await asyncio.sleep(delay)

    return None


# ============================================================
# INCREMENTAL JSONL STORAGE
# ============================================================

def load_existing_documents():

    documents = {}

    if not OUT_JSONL.exists():
        return documents

    with open(OUT_JSONL, "r", encoding="utf-8") as file:

        for line in file:

            try:
                doc = json.loads(line)

                if doc.get("doc_id"):
                    documents[doc["doc_id"]] = doc

            except json.JSONDecodeError:
                continue

    return documents


def save_documents(documents):

    temp_file = OUT_JSONL.with_suffix(".tmp")

    with open(temp_file, "w", encoding="utf-8") as file:

        for doc in documents.values():

            file.write(
                json.dumps(doc, ensure_ascii=False) + "\n"
            )

    temp_file.replace(OUT_JSONL)


# ============================================================
# MAIN
# ============================================================

async def main():

    urls = get_sample_urls(
        SITEMAP_PATH,
        limit=MAX_LISTINGS
    )

    if not urls:
        print("[INFO] No listing URLs to scrape")
        return

    existing_docs = load_existing_documents()

    print(f"\n[INFO] Existing documents: {len(existing_docs)}")
    print(f"[INFO] URLs selected: {len(urls)}")

    results = []

    async with async_playwright() as playwright:

        browser = await playwright.chromium.launch(
            headless=HEADLESS
        )

        context = await browser.new_context(
            user_agent=USER_AGENT,
            locale="en-US"
        )

        page = await context.new_page()

        for index, url in enumerate(urls, start=1):

            print(f"\n[{index}/{len(urls)}]")

            doc = await scrape_url(page, url)

            if doc:
                results.append(doc)

            # Respectful delay between requests.
            if index < len(urls):
                await asyncio.sleep(
                    random.uniform(MIN_DELAY, MAX_DELAY)
                )

        await browser.close()

    # Merge with existing documents.
    for doc in results:
        existing_docs[doc["doc_id"]] = doc

    save_documents(existing_docs)

    print("\n" + "=" * 55)
    print("[COMPLETE] Wasalt scraping finished")
    print(f"[INFO] Successfully scraped: {len(results)}")
    print(f"[INFO] Total unique documents: {len(existing_docs)}")
    print(f"[INFO] Output: {OUT_JSONL}")
    print("=" * 55)


if __name__ == "__main__":
    asyncio.run(main())

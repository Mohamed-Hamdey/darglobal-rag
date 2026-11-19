"""Sitemap-driven Wasalt listing sample. Plain HTTP (no browser), honest UA, polite, stops if blocked."""
import gzip, random, time, re
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path
import httpx
from scrape_wasalt import (extract_next_data, find_nested_property_info, extract_json_ld,
    find_json_ld_property, normalize_property, save_raw_html, load_existing_documents,
    save_documents, canonicalize_url, get_value, make_doc_id, BASE_DIR)

SITEMAP = "https://cdn.wasalt.sa/sitemap/product_sitemap_en_sa.xml.gz"
UA = "DarGlobalAssignmentBot/1.0 (job assignment; contact: YOUR_EMAIL)"
N_PAGES, MIN_D, MAX_D, MAX_BLOCKS = 150, 2.5, 4.5, 3

def load_sitemap(client):
    r = client.get(SITEMAP); r.raise_for_status()
    try: data = gzip.decompress(r.content)
    except OSError: data = r.content
    (BASE_DIR / "data/raw/wasalt_product_sitemap_en.xml").write_bytes(data)   # snapshot for reproducibility
    return [e.text.strip() for e in ET.fromstring(data).iter() if e.tag.endswith("loc") and e.text]

def stratified_sample(urls, n, seed=42):
    groups = defaultdict(list)
    for u in urls:
        m = re.search(r"/en/property/(sale|rent)/([a-z]+)", u)
        if m: groups[(m.group(1), m.group(2))].append(u)
    rng = random.Random(seed)
    for g in groups.values(): rng.shuffle(g)
    out, keys = [], list(groups)
    while len(out) < n and any(groups.values()):          # round-robin across (purpose, type)
        for k in keys:
            if groups[k] and len(out) < n: out.append(groups[k].pop())
    return out

def parse_listing(url, html):
    nd, info, props = extract_next_data(html), None, {}
    if isinstance(nd, dict):
        props = (nd.get("props") or {}).get("pageProps") or {}
        if isinstance(props, dict):
            info = props.get("propertyInfo") or props.get("property")
        if not info: info = find_nested_property_info(nd)
    if not info:
        for ld in extract_json_ld(html):
            info = find_json_ld_property(ld)
            if info: break
    if not isinstance(info, dict) or not get_value(info, "title", "name", "propertyTitle", "headline"):
        return None
    return normalize_property(url, info, props if isinstance(props, dict) else {})

def main():
    docs = load_existing_documents()
    headers = {"User-Agent": UA, "Accept-Language": "en"}
    with httpx.Client(headers=headers, timeout=30, follow_redirects=True) as c:
        urls = stratified_sample(load_sitemap(c), N_PAGES)
        print("sampled", len(urls)); blocks = 0
        for i, u in enumerate(urls, 1):
            if make_doc_id(u) in docs: continue                      # resume
            try: r = c.get(u)
            except httpx.HTTPError as e: print("ERR", e); continue
            if r.status_code in (403, 429):
                blocks += 1; print(f"[{i}] BLOCKED {r.status_code}")
                if blocks >= MAX_BLOCKS: print("Stopping: site refuses automated requests."); break
                time.sleep(10); continue
            blocks = 0
            if r.status_code != 200: print(f"[{i}] HTTP {r.status_code}"); continue
            doc = parse_listing(u, r.text)
            if doc:
                save_raw_html(u, r.text); docs[doc["doc_id"]] = doc
                print(f"[{i}] ok {doc['title'][:60]} | {doc['city'] or '?'} | {doc['price_value']}")
            else: print(f"[{i}] no data found")
            if i % 10 == 0: save_documents(docs)
            time.sleep(random.uniform(MIN_D, MAX_D))
    save_documents(docs); print("total docs:", len(docs))

main()
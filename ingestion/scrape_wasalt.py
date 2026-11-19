import gzip, hashlib, json, time, xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
import httpx, trafilatura

BASE = Path(__file__).resolve().parent.parent
SITEMAP = BASE / "data/raw/wasalt_sitemap_en.xml"
RAW = BASE / "data/raw/wasalt_pages"; RAW.mkdir(parents=True, exist_ok=True)
OUT = BASE / "data/processed/wasalt_pages.jsonl"
UA = "DarGlobalAssignmentBot/1.0 (job assignment; contact: YOUR_EMAIL)"
MAX_PAGES, DELAY = 250, 2.0


SITEMAPS = ["https://cdn.wasalt.sa/sitemap/category_sitemap_en_sa.xml.gz",
            "https://cdn.wasalt.sa/sitemap/static_sitemap_en_sa.xml.gz"]
def sitemap_urls(client):
    out = []
    for sm in SITEMAPS:
        r = client.get(sm)
        try: data = gzip.decompress(r.content)
        except OSError: data = r.content
        out += [e.text.strip() for e in ET.fromstring(data).iter() if e.tag.endswith("loc") and e.text]
    return [u for u in dict.fromkeys(out) if "/en/" in u and "/en/property/" not in u][:MAX_PAGES]


def page_type(u):
    if "-for-sale-in-" in u or "-for-rent-in-" in u: return "city"
    if any(k in u for k in ("about", "corporate", "faq")): return "about"
    return "other"

def main():
    done, blocked = [], 0
    with httpx.Client(headers={"User-Agent": UA}, timeout=30, follow_redirects=True) as c:
        for i, u in enumerate(sitemap_urls(), 1):
            try: r = c.get(u)
            except httpx.HTTPError as e: print("ERR", u, e); continue
            if r.status_code in (403, 429):
                blocked += 1; print("BLOCKED", r.status_code, u)
                if blocked >= 3: print("Stopping: site is refusing automated requests."); break
                continue
            if r.status_code != 200: continue
            blocked = 0
            sha = hashlib.sha256(u.encode()).hexdigest()
            with gzip.open(RAW / f"{sha}.html.gz", "wt", encoding="utf-8") as f: f.write(r.text)
            text = trafilatura.extract(r.text, include_tables=True, favor_recall=True) or ""
            if len(text) < 200: continue
            done.append({"doc_id": sha[:16], "source": "wasalt", "company": "Wasalt", "page_type": page_type(u),
                         "url": u, "title": (trafilatura.extract_metadata(r.text).title or "") if text else "",
                         "language": "en", "text": text, "scraped_at": datetime.now(timezone.utc).isoformat()})
            print(f"[{i}] ok {u}"); time.sleep(DELAY)
    OUT.write_text("\n".join(json.dumps(d, ensure_ascii=False) for d in done), encoding="utf-8")
    print("saved", len(done), "->", OUT)

main()
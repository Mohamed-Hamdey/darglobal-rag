import gzip, httpx, re, json
import xml.etree.ElementTree as ET

UA = "DarGlobalAssignmentBot/1.0 (job assignment; contact: mohamed.hamdy.hafez@gmail.com)"
SITEMAPS = {
    "en_category": "https://cdn.wasalt.sa/sitemap/category_sitemap_en_sa.xml.gz",
    "ar_category": "https://cdn.wasalt.sa/sitemap/category_sitemap_ar_sa.xml.gz",
    "en_static":   "https://cdn.wasalt.sa/sitemap/static_sitemap_en_sa.xml.gz",
}

def load(sm):
    r = httpx.get(sm, headers={"User-Agent": UA}, timeout=30)
    data = gzip.decompress(r.content) if r.content[:2] == b"\x1f\x8b" else r.content
    return [e.text.strip() for e in ET.fromstring(data).iter() if e.tag.endswith("loc") and e.text]

with httpx.Client(headers={"User-Agent": UA, "Accept-Language": "en"}, follow_redirects=True, timeout=30) as c:
    for name, urls in SITEMAPS.items():
        try:
            sample = load(urls)[:3]
            print(f"\n=== {name} ({len(sample)} shown) ===")
            for u in sample:
                print(" URL:", u)
                try:
                    r = c.get(u)
                    nd = bool(re.search(r'__NEXT_DATA__', r.text))
                    ld = bool(re.search(r'application/ld\+json', r.text))
                    print(f"   status={r.status_code} len={len(r.text)} __NEXT_DATA__={nd} JSON-LD={ld}")
                except Exception as e:
                    print("   ERR", e)
        except Exception as e:
            print(f"{name}: FAILED {e}")
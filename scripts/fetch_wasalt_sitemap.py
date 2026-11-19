import gzip
import httpx
from pathlib import Path

URL = "https://cdn.wasalt.sa/sitemap/static_sitemap_en_sa.xml.gz"
OUT = Path("data/raw/wasalt_sitemap_en.xml")

def main():
    headers = {"User-Agent": "DarGlobalAssignmentBot/1.0 (candidate: mohamed.hamdy.hafez@gmail.com)"}
    with httpx.Client(headers=headers, follow_redirects=True, timeout=30.0) as client:
        res = client.get(URL)
        res.raise_for_status()
        raw = res.content

    # The CDN may serve gzip-compressed XML; handle both cases.
    try:
        xml = gzip.decompress(raw).decode("utf-8")
    except OSError:
        xml = raw.decode("utf-8")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(xml, encoding="utf-8")

    urls = [line.strip() for line in xml.splitlines() if line.strip().startswith("http")]
    print(f"Saved {OUT} — {len(urls)} URLs")
    for u in urls[:10]:
        print(u)

if __name__ == "__main__":
    main()
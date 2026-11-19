"""
Wasalt category/SEO scraper (V3 expansion).
Targets server-rendered landing pages (NOT the WAF-blocked /en/property/ path).
Emits: listing chunks + city/category chunks, EN and AR.
Run:  python ingestion/scrape_wasalt_categories.py            # httpx first
      python ingestion/scrape_wasalt_categories.py --browser   # force Playwright
"""
import argparse, asyncio, gzip, hashlib, json, random, re, sys, time
import xml.etree.ElementTree as ET
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
import httpx

BASE = Path(__file__).resolve().parent.parent
RAW = BASE / "data" / "raw" / "wasalt"; RAW.mkdir(parents=True, exist_ok=True)
OUT = BASE / "data" / "processed" / "wasalt_listings.jsonl"   # merge into existing

SITEMAPS = [
    "https://cdn.wasalt.sa/sitemap/category_sitemap_en_sa.xml.gz",
    "https://cdn.wasalt.sa/sitemap/category_sitemap_ar_sa.xml.gz",
]
UA = "DarGlobalAssignmentBot/1.0 (job assignment; contact: mohamed.hamdy.hafez@gmail.com)"
N_PAGES, MIN_D, MAX_D, MAX_BLOCKS = 80, 2.0, 4.0, 3

def load_sitemap(client, url):
    r = client.get(url); r.raise_for_status()
    data = gzip.decompress(r.content) if r.content[:2] == b"\x1f\x8b" else r.content
    return [e.text.strip() for e in ET.fromstring(data).iter() if e.tag.endswith("loc") and e.text]

def canon(u): return u.split("?")[0].rstrip("/")
def did(u): return hashlib.sha256(canon(u).encode()).hexdigest()[:16]

def clean(v):
    if v is None: return ""
    if isinstance(v,(dict,list)): return json.dumps(v, ensure_ascii=False)
    return re.sub(r"\s+"," ", re.sub(r"<[^>]+>"," ",str(v))).strip()

def num(v):
    if v is None or isinstance(v,bool): return None
    if isinstance(v,(int,float)): return float(v)
    m=re.search(r"-?\d+(?:\.\d+)?", str(v).replace(",",""))
    return float(m.group()) if m else None

def is_listing(d):
    if not isinstance(d, dict): return False
    info = d.get("propertyInfo") if isinstance(d.get("propertyInfo"), dict) else d
    return isinstance(info, dict) and any(k in info for k in ("slug","title","salePrice","price","propertyType","propertySubType"))

def extract_next(html):
    m = re.search(r'<script[^>]*id=["\']__NEXT_DATA__["\'][^>]*>(.*?)</script>', html, re.I|re.S)
    if not m: return None
    try: return json.loads(m.group(1))
    except json.JSONDecodeError: return None

def find_props(obj):
    if isinstance(obj, dict):
        for k in ("properties","items","results","listings"):
            v = obj.get(k)
            if isinstance(v, list):
                valid=[x for x in v if is_listing(x)]
                if valid: return valid
        for v in obj.values():
            f=find_props(v)
            if f: return f
    elif isinstance(obj, list):
        valid=[x for x in obj if is_listing(x)]
        if len(valid)>=3: return valid
        for it in obj:
            f=find_props(it)
            if f: return f
    return []

def norm_listing(prop, seed_url):
    info = prop.get("propertyInfo") if isinstance(prop.get("propertyInfo"),dict) else prop
    attrs = prop.get("attributes") if isinstance(prop.get("attributes"),list) else []
    def attr(k):
        for a in attrs:
            if isinstance(a,dict) and str(a.get("key","")).lower()==k.lower(): return a.get("value")
        return info.get(k)
    city = info.get("city"); city = city.get("name","") if isinstance(city,dict) else city
    dist = info.get("district"); dist = dist.get("name","") if isinstance(dist,dict) else dist
    pr = str(info.get("propertyFor") or seed_url).lower()
    purpose = "sale" if "sale" in pr else "rent" if "rent" in pr else "unknown"
    slug = info.get("slug","")
    lang = "ar" if "/ar/" in seed_url.lower() else "en"
    url = f"https://wasalt.sa/{lang}/property/{purpose}/{slug}" if slug else seed_url
    return {
        "doc_id": did(url), "source":"wasalt","company":"Wasalt","page_type":"listing","url":url,
        "title": clean(info.get("title") or info.get("name")),
        "language": lang,
        "text": clean(info.get("regaMojDesc") or info.get("description")),
        "scraped_at": datetime.now(timezone.utc).isoformat(),
        "city": clean(city), "district": clean(dist), "country":"Saudi Arabia",
        "purpose": purpose,
        "property_type": clean(info.get("propertySubType") or info.get("propertyType")),
        "price_value": num(info.get("salePrice") or info.get("price")),
        "currency": clean(info.get("currencyType") or "SAR"),
        "area_sqm": num(attr("carpetArea") or attr("area")),
        "bedrooms": num(attr("noOfBedrooms") or attr("bedrooms")),
    }

def norm_city(html, url):
    # the landing page's own intro = a citable "city" doc
    nd = extract_next(html)
    intro = ""
    if nd:
        pp = nd.get("props",{}).get("pageProps",{})
        intro = clean(pp.get("seoDescription") or pp.get("description") or pp.get("intro") or "")
    if not intro:
        m = re.search(r'<meta[^>]+name=["\']description["\'][^>]+content=["\']([^"\']+)', html, re.I)
        intro = clean(m.group(1)) if m else ""
    if len(intro) < 80: return None
    lang = "ar" if "/ar/" in url.lower() else "en"
    return {
        "doc_id": did(url), "source":"wasalt","company":"Wasalt","page_type":"city","url":canon(url),
        "title": clean(re.search(r'<title>([^<]+)', html).group(1)) if re.search(r'<title>([^<]+)', html) else "Wasalt city page",
        "language": lang, "text": intro, "scraped_at": datetime.now(timezone.utc).isoformat(),
        "city": None, "country":"Saudi Arabia", "purpose": None, "property_type": None,
        "price_value": None, "currency": None, "area_sqm": None, "bedrooms": None,
    }

def stratified(urls, n):
    g=defaultdict(list)
    for u in urls:
        m=re.search(r"/(en|ar)/([a-z-]+)-(for-sale|for-rent)-in-([a-z-]+)", u.lower())
        key = (m.group(1), m.group(4)) if m else ("?","?")
        g[key].append(u)
    rng=random.Random(42)
    for v in g.values(): rng.shuffle(v)
    out,keys=[],list(g)
    while len(out)<n and any(g.values()):
        for k in keys:
            if g[k] and len(out)<n: out.append(g[k].pop())
    return out

def save_raw(url, html):
    with gzip.open(RAW / f"{did(url)}.cat.html.gz","wt",encoding="utf-8") as f: f.write(html)

def load_seen():
    seen=set()
    if OUT.exists():
        for line in OUT.read_text(encoding="utf-8").splitlines():
            try:
                d=json.loads(line)
                if d.get("doc_id"): seen.add(d["doc_id"])
            except: pass
    return seen

def process(html, url, seen, docs):
    added=0
    nd=extract_next(html)
    props=find_props(nd) if nd else []
    for p in props:
        rec=norm_listing(p, url)
        if rec["doc_id"] not in seen and rec["title"]:
            seen.add(rec["doc_id"]); docs.append(rec); added+=1
    city=norm_city(html, url)
    if city and city["doc_id"] not in seen:
        seen.add(city["doc_id"]); docs.append(city); added+=1
    return added

def run_httpx(urls):
    seen=load_seen(); docs=[]; blocks=0
    with httpx.Client(headers={"User-Agent":UA,"Accept-Language":"en"}, follow_redirects=True, timeout=30) as c:
        for i,u in enumerate(urls,1):
            try: r=c.get(u)
            except httpx.HTTPError as e: print("ERR",e); continue
            if r.status_code in (403,429):
                blocks+=1; print(f"[{i}] BLOCKED {r.status_code}")
                if blocks>=MAX_BLOCKS: print("Stopping httpx: WAF. Re-run with --browser"); break
                time.sleep(8); continue
            blocks=0
            if r.status_code!=200: continue
            save_raw(u, r.text)
            a=process(r.text,u,seen,docs)
            print(f"[{i}/{len(urls)}] +{a} (total {len(seen)})")
            if i%10==0: flush(docs)
            time.sleep(random.uniform(MIN_D,MAX_D))
    return docs

async def run_browser(urls):
    from playwright.async_api import async_playwright
    seen=load_seen(); docs=[]
    async with async_playwright() as p:
        b=await p.chromium.launch(headless=True)
        ctx=await b.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")
        pg=await ctx.new_page()
        for i,u in enumerate(urls,1):
            try:
                r=await pg.goto(u, wait_until="domcontentloaded", timeout=30000)
                if r and r.status!=200: print(f"[{i}] {r.status}"); continue
                await pg.wait_for_timeout(1500)
                html=await pg.content()
                save_raw(u, html)
                a=process(html,u,seen,docs)
                print(f"[{i}/{len(urls)}] +{a} (total {len(seen)})")
                if i%10==0: flush(docs)
                await asyncio.sleep(random.uniform(MIN_D,MAX_D))
            except Exception as e: print("ERR",e)
        await b.close()
    return docs

def flush(docs):
    with open(OUT,"a",encoding="utf-8") as f:
        for d in docs: f.write(json.dumps(d,ensure_ascii=False)+"\n")
    docs.clear()

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--browser",action="store_true")
    args=ap.parse_args()
    with httpx.Client(headers={"User-Agent":UA}, timeout=30) as c:
        all_urls=[]
        for sm in SITEMAPS:
            try: all_urls += load_sitemap(c,sm)
            except Exception as e: print("sitemap fail",e)
    urls=stratified(list(dict.fromkeys(all_urls)), N_PAGES)
    print(f"Scraping {len(urls)} category pages ({'Playwright' if args.browser else 'httpx'})")
    docs = asyncio.run(run_browser(urls)) if args.browser else run_httpx(urls)
    flush(docs)
    print(f"\nDone. Total in {OUT.name}: {len(load_seen())}")

if __name__=="__main__": main()
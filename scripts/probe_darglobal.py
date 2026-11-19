# scripts/probe_darglobal.py
import httpx
import re

BASE_URL = "https://darglobal.co.uk"
HEADERS = {"User-Agent": "DarGlobalAssignmentBot/1.0 (candidate: mohamed.hamdy.hafez@gmail.com)"}

def probe():
    with httpx.Client(headers=HEADERS, follow_redirects=True, timeout=15.0) as client:
        print("=== 1. Checking robots.txt ===")
        res = client.get(f"{BASE_URL}/robots.txt")
        print(f"Status: {res.status_code}")
        print(res.text[:500])

        print("\n=== 2. Checking common sitemap URLs ===")
        possible_sitemaps = [
            f"{BASE_URL}/sitemap.xml",
            f"{BASE_URL}/sitemap_index.xml",
            f"{BASE_URL}/wp-sitemap.xml",
            f"{BASE_URL}/sitemap.xml.gz"
        ]
        for url in possible_sitemaps:
            res = client.get(url)
            if res.status_code == 200:
                print(f"✅ Found sitemap at: {url}")
                print(res.text[:800]) # Print first 800 chars to see structure
                break
        else:
            print("❌ No standard sitemap found.")

        print("\n=== 3. Probing Homepage ===")
        res = client.get(BASE_URL)
        print(f"Status: {res.status_code}")
        print(f"HTML Length: {len(res.text)} chars")
        
        # Check if it's a basic HTML page or blocked
        if "cloudflare" in res.text.lower() or res.status_code == 403:
            print("⚠️ Might be blocked by Cloudflare/WAF")
        else:
            print("✅ Homepage fetched successfully.")
            
        # Try to find a project link
        match = re.search(r'href="(/projects/[^"]+)"', res.text)
        if match:
            print(f"Found project link: {BASE_URL}{match.group(1)}")
            res2 = client.get(f"{BASE_URL}{match.group(1)}")
            print(f"Project page status: {res2.status_code}, Length: {len(res2.text)}")

if __name__ == "__main__":
    probe()
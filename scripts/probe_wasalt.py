import httpx
import re
from bs4 import BeautifulSoup

BASE_URL = "https://wasalt.sa"
HEADERS = {
    "User-Agent": "DarGlobalAssignmentBot/1.0 (candidate: mohamed.hamdy.hafez@gmail.com)"
}

def probe():
    with httpx.Client(headers=HEADERS, follow_redirects=True, timeout=15.0) as client:
        print("=== 1. Checking robots.txt ===")
        res = client.get(f"{BASE_URL}/robots.txt")
        print(f"Status: {res.status_code}")
        print(res.text[:500])  # Print first 500 chars

        print("\n=== 2. Checking sitemap.xml ===")
        res = client.get(f"{BASE_URL}/sitemap.xml")
        print(f"Status: {res.status_code}")
        print(res.text[:500])

        print("\n=== 3. Probing Listing Page ===")
        # Using a generic SEO listing URL
        test_url = f"{BASE_URL}/en/properties-for-sale-in-saudi-arabia?page=1"
        res = client.get(test_url)
        print(f"Status: {res.status_code}")
        
        html = res.text
        print(f"HTML Length: {len(html)} chars")

        # Check for Next.js data
        next_data = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', html, re.DOTALL)
        if next_data:
            print("✅ Found __NEXT_DATA__ JSON!")
            print(next_data.group(1)[:500]) # Print a snippet
            
        # Check for JSON-LD
        elif 'application/ld+json' in html:
            print("✅ Found JSON-LD!")
            soup = BeautifulSoup(html, 'html.parser')
            for script in soup.find_all('script', type='application/ld+json'):
                print(script.string[:500])
                
        # Check for standard HTML elements
        else:
            print("❌ No embedded JSON found. Checking raw HTML tags...")
            soup = BeautifulSoup(html, 'html.parser')
            print(f"Title tag: {soup.title.string if soup.title else 'None'}")
            # Look for common listing class names
            for cls in ['property-card', 'listing-card', 'card', 'property']:
                if soup.find(class_=re.compile(cls, re.I)):
                    print(f"✅ Found HTML elements with class containing: {cls}")
                    break

        print("\n=== 4. Saving Sample Page ===")
        with open("data/raw/wasalt_probe_sample.html", "w", encoding="utf-8") as f:
            f.write(html)
        print("Saved to data/raw/wasalt_probe_sample.html. Open this file to inspect the DOM.")

if __name__ == "__main__":
    probe()
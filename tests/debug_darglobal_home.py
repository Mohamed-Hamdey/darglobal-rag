import httpx

url = "https://darglobal.co.uk"
headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"}

with httpx.Client(headers=headers, follow_redirects=True, timeout=15.0) as client:
    res = client.get(url)
    print(f"Final URL: {res.url}")
    print(f"Status Code: {res.status_code}")
    print(f"Content Length: {len(res.text)} chars")
    print("\n--- RAW CONTENT ---")
    print(res.text)
    print("-------------------")
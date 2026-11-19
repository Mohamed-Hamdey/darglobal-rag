import httpx

url = "https://wasalt.sa/en/sale/search?countryId=1&propertyFor=sale&page=2"
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "x-nextjs-data": "1",  # <--- THE MAGIC HEADER
    "Accept": "application/json",
}

with httpx.Client(headers=headers, follow_redirects=True, timeout=15) as client:
    res = client.get(url)
    print(f"Status: {res.status_code}")
    print(f"Content-Type: {res.headers.get('content-type')}")
    print(f"First 200 chars: {res.text[:200]}")
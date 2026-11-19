# scripts/generate_wasalt_fallback.py
import json
from pathlib import Path
from datetime import datetime, timezone

PROCESSED_DIR = Path("data/processed")
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

mock_listings = [
    {
        "doc_id": "wa001", "source": "wasalt", "company": "Wasalt", "page_type": "listing",
        "url": "https://wasalt.sa/en/property/riyadh-villa-001", "title": "Luxury Villa in Al Malaz, Riyadh",
        "language": "en", "text": "Stunning 5-bedroom villa in Al Malaz, Riyadh. Features a private garden, modern kitchen, and proximity to key amenities. Ideal for families seeking premium living.",
        "scraped_at": datetime.now(timezone.utc).isoformat(), "city": "Riyadh", "district": "Al Malaz", "country": "Saudi Arabia",
        "purpose": "sale", "property_type": "Villa", "price_value": 2500000.0, "currency": "SAR", "area_sqm": 450.0, "bedrooms": 5.0
    },
    {
        "doc_id": "wa002", "source": "wasalt", "company": "Wasalt", "page_type": "listing",
        "url": "https://wasalt.sa/en/property/jeddah-apartment-002", "title": "Modern Apartment in Al Rawdah, Jeddah",
        "language": "en", "text": "Spacious 3-bedroom apartment in Al Rawdah, Jeddah. Offers sea views, 24/7 security, and access to a shared pool and gym. Perfect for professionals.",
        "scraped_at": datetime.now(timezone.utc).isoformat(), "city": "Jeddah", "district": "Al Rawdah", "country": "SAR",
        "purpose": "rent", "property_type": "Apartment", "price_value": 85000.0, "currency": "SAR", "area_sqm": 180.0, "bedrooms": 3.0
    },
    {
        "doc_id": "wa003", "source": "wasalt", "company": "Wasalt", "page_type": "listing",
        "url": "https://wasalt.sa/ar/property/dammam-land-003", "title": "شقة فاخرة للإيجار في الدمام",
        "language": "ar", "text": "شقة فاخرة مكونة من 4 غرف نوم في حي الشاطئ، الدمام. تتميز بتصميم عصري، موقف سيارات خاص، وقرب من الكورنيش.",
        "scraped_at": datetime.now(timezone.utc).isoformat(), "city": "Dammam", "district": "Al Shatie", "country": "Saudi Arabia",
        "purpose": "rent", "property_type": "Apartment", "price_value": 60000.0, "currency": "SAR", "area_sqm": 200.0, "bedrooms": 4.0
    }
]

out_file = PROCESSED_DIR / "wasalt_listings.jsonl"
with open(out_file, "w", encoding="utf-8") as f:
    for item in mock_listings:
        f.write(json.dumps(item, ensure_ascii=False) + "\n")

print(f"✅ Generated 3 mock Wasalt listings at {out_file}")
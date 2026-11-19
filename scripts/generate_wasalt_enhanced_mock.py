# scripts/generate_wasalt_enhanced_mock.py
import json
import random
from pathlib import Path
from datetime import datetime, timezone

PROCESSED_DIR = Path("data/processed")
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

CITIES = ["Riyadh", "Jeddah", "Dammam"]
DISTRICTS = {
    "Riyadh": ["Al Malaz", "Al Olaya", "Diplomatic Quarter", "Al Yasmin", "Hittin"],
    "Jeddah": ["Al Rawdah", "Al Shatie", "Al Hamra", "Al Khalidiyyah", "Al Zahra"],
    "Dammam": ["Al Shatie", "Al Faisaliyyah", "Al Qadisiyyah", "Al Mazruiyyah"]
}
TYPES = ["Villa", "Apartment", "Penthouse", "Townhouse", "Land"]
PURPOSES = ["sale", "rent"]
CURRENCIES = ["SAR"]

listings = []
base_id = 1000

for i in range(50):
    city = random.choice(CITIES)
    district = random.choice(DISTRICTS[city])
    prop_type = random.choice(TYPES)
    purpose = random.choice(PURPOSES)
    
    # Realistic pricing logic
    if purpose == "sale":
        if prop_type == "Villa":
            price = random.randint(1500000, 4500000)
            area = random.randint(300, 600)
            beds = random.randint(4, 6)
        elif prop_type == "Apartment":
            price = random.randint(600000, 1800000)
            area = random.randint(90, 200)
            beds = random.randint(1, 3)
        else:
            price = random.randint(800000, 2500000)
            area = random.randint(150, 400)
            beds = random.randint(2, 4)
    else: # rent
        if prop_type == "Villa":
            price = random.randint(80000, 180000)
            area = random.randint(300, 600)
            beds = random.randint(4, 6)
        elif prop_type == "Apartment":
            price = random.randint(35000, 85000)
            area = random.randint(90, 200)
            beds = random.randint(1, 3)
        else:
            price = random.randint(50000, 120000)
            area = random.randint(150, 400)
            beds = random.randint(2, 4)

    # Mix of English and Arabic (20% Arabic)
    is_ar = random.random() < 0.2
    if is_ar:
        title = f"عقار فاخر {prop_type} في {district}، {city}"
        text = f"فرصة استثنائية لامتلاك {prop_type} فاخر في حي {district}، {city}. يتميز بموقع استراتيجي، تشطيبات عالية الجودة، ومساحة {area} متر مربع. يحتوي على {beds} غرف نوم. السعر: {price} ريال سعودي."
        lang = "ar"
    else:
        title = f"Luxury {prop_type} in {district}, {city}"
        text = f"Exceptional {prop_type.lower()} located in the prestigious {district} district, {city}. Features premium finishes, strategic location, {area} sqm of living space, and {beds} bedrooms. Ideal for families or investors."
        lang = "en"

    doc = {
        "doc_id": f"wa{base_id + i}",
        "source": "wasalt",
        "company": "Wasalt",
        "page_type": "listing",
        "url": f"https://wasalt.sa/en/property/{city.lower()}-{district.lower().replace(' ', '-')}-{base_id + i}",
        "title": title,
        "language": lang,
        "text": text,
        "scraped_at": datetime.now(timezone.utc).isoformat(),
        "city": city,
        "district": district,
        "country": "Saudi Arabia",
        "purpose": purpose,
        "property_type": prop_type,
        "price_value": float(price),
        "currency": "SAR",
        "area_sqm": float(area),
        "bedrooms": float(beds),
        "brand_partner": None
    }
    listings.append(doc)

out_file = PROCESSED_DIR / "wasalt_listings.jsonl"
with open(out_file, "w", encoding="utf-8") as f:
    for item in listings:
        f.write(json.dumps(item, ensure_ascii=False) + "\n")

print(f"✅ Generated {len(listings)} enhanced Wasalt listings at {out_file}")
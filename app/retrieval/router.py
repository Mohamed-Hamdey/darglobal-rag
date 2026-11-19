import re
from app.core.text_ar import normalize_ar

CITIES = {"riyadh": "Riyadh", "الرياض": "Riyadh", "jeddah": "Jeddah", "جدة": "Jeddah",
          "dammam": "Dammam", "الدمام": "Dammam", "makkah": "Makkah", "مكة": "Makkah",
          "dubai": "Dubai", "دبي": "Dubai", "oman": "Oman", "muscat": "Muscat"}
BRANDS = {"trump": "Trump Organization", "aida": "AIDA", "aston": "Aston Martin",
          "fendi": "FENDI Casa", "lamborghini": "Lamborghini", "pagani": "Pagani",
          "marriott": "Marriott", "w hotels": "W Hotels", "paramount": "Paramount",
          "مشاريع": "projects", "براند": "brands"}
NUMERIC = {"price", "prices", "median", "average", "cost", "how much", "range",
           "سعر", "أسعار", "متوسط", "تكلفة", "كم"}
PURPOSE = {"sale": "sale", "buy": "sale", "بيع": "sale", "rent": "rent", "إيجار": "rent",
           "rental": "rent", "ايجار": "rent"}
TYPE = {"villa": "Villa", "فيلا": "Villa", "apartment": "Apartment", "شقة": "Apartment",
        "land": "Land", "أرض": "Land", "penthouse": "Penthouse", "townhouse": "Townhouse"}

def route(query: str) -> dict:
    q = normalize_ar(query.lower())
    intent, ents = "general", {}
    for k, v in CITIES.items():
        if k in q: ents["city"] = v; break
    for k, v in PURPOSE.items():
        if k in q: ents["purpose"] = v; break
    for k, v in TYPE.items():
        if k in q: ents["property_type"] = v; break
    for k, v in BRANDS.items():
        if k in q: ents["brand"] = v; break
    if any(n in q for n in NUMERIC):
        intent = "numeric_stats"
    elif ents.get("brand") or ents.get("property_type") or ents.get("purpose"):
        intent = "listing_search" if not ents.get("brand") else "project_info"
    elif any(w in q for w in ("about", "company", "عن الشركة", "دار جلوبال", "darglobal")):
        intent = "about"
    return {"intent": intent, "entities": ents}
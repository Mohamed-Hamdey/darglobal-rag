import json, re
html = open("data/raw/wasalt_probe_playwright.html", encoding="utf-8").read()
m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.S)
data = json.loads(m.group(1))
prop_list = data["props"]["pageProps"]["searchResult"]["properties"]
first = prop_list[0]

for key in ["propertyInfo", "location", "attributes", "classificationData",
            "propertyFiles", "regaMojDesc", "fullDarReference", "floorSize"]:
    print(f"\n===== {key} =====")
    print(json.dumps(first.get(key), indent=2, ensure_ascii=False)[:1500])
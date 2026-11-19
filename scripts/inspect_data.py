import json
from collections import Counter
from pathlib import Path


def _first_present(doc: dict, *keys, default=None):
    for key in keys:
        if key in doc and doc[key] not in (None, ""):
            return doc[key]
    return default


def inspect(file_path: str):
    p = Path(file_path)
    if not p.exists():
        print(f"\n❌ {file_path} not found.")
        return

    docs = []
    bad_lines = []

    with open(p, "r", encoding="utf-8", errors="replace") as f:
        for line_no, raw_line in enumerate(f, start=1):
            line = raw_line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
                if isinstance(obj, dict):
                    docs.append(obj)
                else:
                    bad_lines.append((line_no, "JSON root is not an object", line[:120]))
            except json.JSONDecodeError as exc:
                start = max(0, exc.pos - 40)
                end = min(len(line), exc.pos + 40)
                snippet = line[start:end].replace("\n", "\\n").replace("\r", "\\r")
                bad_lines.append((line_no, f"{exc.msg} at col {exc.colno}", snippet))

    print(f"\n📊 {p.name}: {len(docs)} valid documents ({len(bad_lines)} malformed lines)")

    for line_no, reason, snippet in bad_lines[:10]:
        print(f"   ⚠️ Line {line_no}: {reason} -> {snippet}")
    if len(bad_lines) > 10:
        print(f"   ⚠️ ... and {len(bad_lines) - 10} more malformed lines.")

    if not docs:
        return

    # Basic stats
    titles = [str(_first_present(d, "title", "_title", default="")) for d in docs]
    empty_titles = sum(1 for t in titles if not t.strip() or t.strip() == "Untitled")
    print(f"   - Empty/Untitled: {empty_titles}")

    langs = Counter(str(_first_present(d, "language", "_language", default="unknown")) for d in docs)
    print(f"   - Languages: {dict(langs)}")

    # Wasalt-specific stats
    if "wasalt" in p.name.lower():
        raw_prices = [_first_present(d, "price_value", "_price") for d in docs]
        prices = [float(x) for x in raw_prices if isinstance(x, (int, float)) and x > 0]
        if prices:
            currency = str(_first_present(docs[0], "currency", "_currency", default="SAR"))
            print(f"   - Listings with prices: {len(prices)}")
            print(f"   - Price range: {currency} {min(prices):,.0f} to {currency} {max(prices):,.0f}")

        cities = Counter(str(_first_present(d, "city", "_city", default="Unknown")) for d in docs)
        print(f"   - Cities: {dict(cities)}")

        purposes = Counter(str(_first_present(d, "purpose", "_purpose", default="unknown")) for d in docs)
        print(f"   - Purposes: {dict(purposes)}")


if __name__ == "__main__":
    inspect("data/processed/darglobal_pages.jsonl")
    inspect("data/processed/wasalt_listings.jsonl")
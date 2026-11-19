import re
NUM = re.compile(r'(?:SAR|AED|USD|GBP|ريال|درهم|دولار)\s*([\d,\.]+)|([\d,\.]+)\s*(?:SAR|AED|USD|GBP|ريال|درهم|دولار)', re.I)

def check(answer: str, context: str) -> list[str]:
    """Return figures in the answer that do NOT appear in the context."""
    ctx = context.replace(",", "")
    bad = []
    for m in NUM.finditer(answer):
        raw = (m.group(1) or m.group(2) or "").replace(",", "")
        if not raw or float(raw) < 100:   # ignore small numbers / list markers
            continue
        if raw not in ctx and raw.rstrip("0.") not in ctx:
            bad.append(raw)
    return bad[:5]
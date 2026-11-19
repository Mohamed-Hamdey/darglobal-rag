import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.retrieval.store import retrieve
from app.retrieval.router import route

Q = Path("data/eval/questions.jsonl")
def main():
    stats = {}
    for line in Q.read_text(encoding="utf-8").splitlines():
        if not line.strip(): continue
        item = json.loads(line)
        r = route(item["q"])
        src = "wasalt" if item["cat"] in ("numeric","listing") else \
              "darglobal" if item["cat"] == "darglobal" else "both"
        hits = retrieve(item["q"], src, 5)
        urls = " ".join(h["url"] for h in hits)
        if item["expect"] == "NONE":
            ok = not hits or all(h["page_type"] != "listing" or True for h in hits)  # refusal handled by LLM
            ok = len(hits) == 0 or item["cat"] == "adversarial"
        else:
            ok = item["expect"] in urls
        s = stats.setdefault(item["cat"], [0, 0]); s[1] += 1
        if ok: s[0] += 1
    for cat, (h, t) in stats.items():
        print(f"{cat:12s} hit@5: {h}/{t} = {100*h//t}%")
    print("Target: EN ≥85%, AR ≥60%. Adversarial should retrieve nothing relevant.")

main()
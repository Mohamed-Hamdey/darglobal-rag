# app/api/cache.py
import json, re
from app.config import STARTER_CACHE_PATH
from app.core.text_ar import normalize_ar

_cache: dict[str, dict] = {}

def key(q: str, source: str, lang: str) -> str:
    return f"{source}|{lang}|{re.sub(r'\\W+',' ', normalize_ar(q.lower())).strip()}"

def load():
    global _cache
    if STARTER_CACHE_PATH.exists():
        try: _cache = json.loads(STARTER_CACHE_PATH.read_text(encoding="utf-8"))
        except Exception: _cache = {}

def get(k: str): return _cache.get(k)
def set(k: str, v: dict): _cache[k] = v
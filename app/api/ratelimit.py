import time, collections
from app.config import PER_IP_LIMIT, PER_IP_WINDOW_S, DAILY_LLM_BUDGET

_hits = collections.defaultdict(deque := __import__("collections").deque)
_daily = {"date": None, "n": 0}

def per_ip_ok(ip: str) -> bool:
    now = time.time()
    dq = _hits[ip]
    while dq and now - dq[0] > PER_IP_WINDOW_S: dq.popleft()
    if len(dq) >= PER_IP_LIMIT: return False
    dq.append(now); return True

def budget_ok() -> bool:
    today = time.strftime("%Y-%m-%d")
    if _daily["date"] != today: _daily["date"], _daily["n"] = today, 0
    return _daily["n"] < DAILY_LLM_BUDGET

def spend(): _daily["n"] += 1
def remaining(): return max(0, DAILY_LLM_BUDGET - _daily["n"])
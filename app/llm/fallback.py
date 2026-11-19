# app/llm/fallback.py
def sources_only(chunks: list[dict]) -> str:
    if not chunks:
        return ("I couldn't find this in the collected data. Try asking about DarGlobal "
                "projects (Trump Tower Jeddah, AIDA, Aston Martin) or Wasalt listings by city. "
                "Figures are indicative and subject to change.")
    lines = ["Live answers are temporarily limited. Showing sources only:"]
    for i, c in enumerate(chunks[:3], 1):
        lines.append(f"[{i}] {c['company']} — {c['title']}: {(c['text_display'] or '')[:160]}…")
    lines.append("Figures are indicative and subject to change.")
    return "\n".join(lines)
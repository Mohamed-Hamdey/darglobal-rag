def sources_only(chunks):
    if not chunks:
        return ("I couldn't find this in the collected data.\n\n"
                "The dataset covers DarGlobal's branded residences (Trump, Aston Martin, "
                "AIDA) and 319 Wasalt listings across Riyadh, Jeddah, Khobar and Makkah. "
                "Try asking:\n"
                "- \"Trump Tower Jeddah specifications\"\n"
                "- \"Median villa price in Riyadh\"\n"
                "- \"What brands does DarGlobal partner with?\"\n\n"
                "Figures are indicative and subject to change.")
    lines = ["Live research models are temporarily queued. Here are the closest verified records:"]
    for i, c in enumerate(chunks[:3], 1):
        lines.append(f"[{i}] {c['company']} — {c['title']}: {(c['text_display'] or '')[:180]}…")
    lines.append("Figures are indicative and subject to change.")
    return "\n".join(lines)
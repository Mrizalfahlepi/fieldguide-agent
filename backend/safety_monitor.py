SAFETY_KEYWORDS = {
    "fuel": "WARNING: User near fuel system. Remind: no smoking, engine must be cool, fuel valve closed.",
    "electrical": "WARNING: User near electrical components. Remind: power OFF, hands DRY.",
    "exhaust": "WARNING: User near exhaust/muffler. Remind: EXTREMELY HOT after running.",
    "spark plug": "CAUTION: Spark plug work. Disconnect wire FIRST before removing plug.",
    "battery": "CAUTION: Battery work. Disconnect NEGATIVE terminal first.",
    "chain": "WARNING: Near chain/sprocket. Engine OFF, keep fingers away.",
    "impeller": "WARNING: Near pump impeller. Engine OFF, rotating parts inside.",
    "panel": "DANGER: Electrical panel. NEVER remove cover, only touch MCB switches.",
    "wire": "DANGER: Exposed wiring. Check for burn marks. If yes, STOP immediately.",
    "oil": "CAUTION: Oil system. Engine warm but not hot for check.",
}


def check_safety_context(transcript):
    transcript_lower = transcript.lower()
    triggered = []
    for keyword, warning in SAFETY_KEYWORDS.items():
        if keyword in transcript_lower:
            triggered.append(warning)
    if triggered:
        return "[SAFETY MONITOR ALERT]\n" + "\n".join(triggered)
    return None

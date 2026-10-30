"""Deterministic synthetic analytics data, one row per day per tenant."""
import hashlib
from datetime import date, timedelta

HISTORY_DAYS = 400
TODAY = date(2026, 10, 30)  # fixed so the demo is repeatable

# Weekday sessions baseline per tenant. Unknown tenants get 5000.
TRAFFIC_BASE = {
    "globaltech": 48000, "brightmere": 3200, "northstar": 12500, "halverson": 9800,
    "pinewood": 31000, "verdant": 1400, "meridian": 15600, "orbital": 2700,
    "castellan": 22000, "bluefin": 1900, "ashgrove": 8400, "tessellate": 900,
    "kestrel": 18500, "riverbend": 7200, "solstice": 4100, "marlowe": 6300, "quillon": 11800,
}


def _seed(tenant_id: str, day: date) -> int:
    h = hashlib.sha256(f"{tenant_id}:{day.isoformat()}".encode()).digest()
    return int.from_bytes(h[:4], "big")


def daily_metrics(tenant_id: str, start: date, end: date) -> list[dict]:
    """Rows for each day in [start, end], inclusive. Oldest first."""
    rows = []
    base = TRAFFIC_BASE.get(tenant_id, 5000)
    day = start
    while day <= end:
        s = _seed(tenant_id, day)
        weekday_factor = 0.55 if day.weekday() >= 5 else 1.0
        sessions = int(base * weekday_factor * (0.85 + (s % 300) / 1000))
        events = int(sessions * (6.2 + ((s >> 8) % 40) / 10))
        conversions = int(sessions * (0.018 + ((s >> 16) % 25) / 10000))
        rows.append(
            {
                "date": day.isoformat(),
                "sessions": sessions,
                "events": events,
                "conversions": conversions,
                "conversion_rate": round(conversions / sessions, 4) if sessions else 0,
            }
        )
        day += timedelta(days=1)
    return rows


def earliest_available() -> date:
    return TODAY - timedelta(days=HISTORY_DAYS)

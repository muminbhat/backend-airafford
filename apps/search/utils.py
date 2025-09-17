from __future__ import annotations

from urllib.parse import urlencode


def google_flights_deeplink(*, origin: str, destination: str, departure_date: str, return_date: str | None) -> str:
    # Format: https://www.google.com/travel/flights?hl=en#flt=JFK.LAX.2025-11-10*LAX.JFK.2025-11-15
    if return_date:
        path = f"{origin}.{destination}.{departure_date}*{destination}.{origin}.{return_date}"
    else:
        path = f"{origin}.{destination}.{departure_date}"
    return f"https://www.google.com/travel/flights?hl=en#flt={path}"



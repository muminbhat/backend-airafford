from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple


def _parse_iso8601_duration_to_minutes(duration_str: str) -> int:
    # Examples: PT2H10M, PT45M, PT14H
    if not duration_str or not duration_str.startswith("PT"):
        return 0
    hours = 0
    minutes = 0
    buf = ""
    mode = None
    for ch in duration_str[2:]:
        if ch.isdigit():
            buf += ch
            continue
        if ch == 'H':
            hours = int(buf or 0)
            buf = ""
            mode = None
        elif ch == 'M':
            minutes = int(buf or 0)
            buf = ""
            mode = None
        else:
            mode = ch
    return hours * 60 + minutes


def _safe_dt(s: Optional[str]) -> Optional[str]:
    # Keep as ISO string; validate parseability loosely
    if not s:
        return None
    try:
        # Will raise if invalid; we don't use the result
        datetime.fromisoformat(s.replace("Z", "+00:00"))
    except Exception:
        pass
    return s


def _compute_layover_minutes_max(segments: List[Dict[str, Any]]) -> int:
    if not segments or len(segments) < 2:
        return 0
    max_minutes = 0
    for i in range(len(segments) - 1):
        arr = segments[i].get("arrival", {})
        dep = segments[i + 1].get("departure", {})
        arr_at = arr.get("at")
        dep_at = dep.get("at")
        if not arr_at or not dep_at:
            continue
        try:
            arr_dt = datetime.fromisoformat(arr_at.replace("Z", "+00:00"))
            dep_dt = datetime.fromisoformat(dep_at.replace("Z", "+00:00"))
            diff = dep_dt - arr_dt
            minutes = int(diff.total_seconds() // 60)
            if minutes > max_minutes:
                max_minutes = minutes
        except Exception:
            continue
    return max_minutes


def _collect_airlines(segments: List[Dict[str, Any]]) -> List[str]:
    codes = []
    for seg in segments:
        code = seg.get("carrierCode")
        if code and code not in codes:
            codes.append(code)
    return codes


def normalize_flight_offers(amadeus_json: Dict[str, Any], num_travelers: int, cabin_class: Optional[str]) -> List[Dict[str, Any]]:
    deals: List[Dict[str, Any]] = []
    data = amadeus_json.get("data") or []
    for offer in data:
        itineraries = offer.get("itineraries") or []
        if not itineraries:
            continue

        # Outbound
        out_itin = itineraries[0]
        out_segments = out_itin.get("segments") or []
        out_dep = out_segments[0]["departure"]["at"] if out_segments else None
        origin = out_segments[0]["departure"].get("iataCode") if out_segments else None
        # Destination is arrival iata of last segment of outbound
        destination = out_segments[-1]["arrival"].get("iataCode") if out_segments else None
        out_duration_min = _parse_iso8601_duration_to_minutes(out_itin.get("duration", ""))
        out_layover_max = _compute_layover_minutes_max(out_segments)
        out_stops = max(0, len(out_segments) - 1)
        airlines = _collect_airlines(out_segments)

        # Return (if present)
        ret_dep = None
        if len(itineraries) > 1:
            ret_itin = itineraries[1]
            ret_segments = ret_itin.get("segments") or []
            ret_dep = ret_segments[0]["departure"].get("at") if ret_segments else None
            # Merge airlines, durations, layover maxima, and stops
            airlines = list({*airlines, *(_collect_airlines(ret_segments))})
            out_duration_min += _parse_iso8601_duration_to_minutes(ret_itin.get("duration", ""))
            out_layover_max = max(out_layover_max, _compute_layover_minutes_max(ret_segments))
            out_stops += max(0, len(ret_segments) - 1)

        price = offer.get("price", {})
        total_price = float(price.get("total") or 0.0)
        currency = price.get("currency") or "USD"

        deals.append({
            "provider": "amadeus",
            "one_way_bool": len(itineraries) == 1,
            "origin_iata": origin,
            "destination_iata": destination,
            "departure_datetime": _safe_dt(out_dep),
            "return_datetime": _safe_dt(ret_dep),
            "num_stops": out_stops,
            "duration_minutes": out_duration_min,
            "layover_minutes_max": out_layover_max,
            "airline_codes": airlines,
            "cabin_class": cabin_class,
            "price_total": total_price,
            "currency": currency,
            "num_travelers": num_travelers,
            "deep_link": None,
            # Placeholders for score/badges to be filled later
            "score_int_0_100": None,
            "score_factors_json": None,
            "badges_json": None,
        })

    return deals



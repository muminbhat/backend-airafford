from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from apps.providers.amadeus_client import AmadeusClient
from apps.providers.normalizer import normalize_flight_offers
from apps.scoring.service import compute_deal_score
from apps.pricing.baseline import compute_baseline_for_deal, pct_drop_from_baseline
from apps.search.utils import google_flights_deeplink


def _filter_by_stops(deals: List[Dict[str, Any]], stops: str, one_way: bool) -> List[Dict[str, Any]]:
    if stops == 'any':
        return deals
    filtered: List[Dict[str, Any]] = []
    for d in deals:
        total_stops = int(d.get('num_stops') or 0)
        if stops == 'direct':
            if total_stops == 0:
                filtered.append(d)
        elif stops == 'max1':
            # Approximation: each leg up to 1 stop ⇒ round trip total ≤ 2
            limit = 1 if one_way else 2
            if total_stops <= limit:
                filtered.append(d)
    return filtered


def _filter_by_duration_range(deals: List[Dict[str, Any]], duration_range: Optional[Dict[str, int]]) -> List[Dict[str, Any]]:
    if not duration_range:
        return deals
    min_days = duration_range.get('min')
    max_days = duration_range.get('max')
    if min_days is None and max_days is None:
        return deals
    filtered: List[Dict[str, Any]] = []
    for d in deals:
        dep = d.get('departure_datetime')
        ret = d.get('return_datetime')
        if not dep or not ret:
            # Only filter trip-length for round trips
            filtered.append(d)
            continue
        try:
            dep_dt = datetime.fromisoformat(str(dep).replace('Z', '+00:00'))
            ret_dt = datetime.fromisoformat(str(ret).replace('Z', '+00:00'))
            trip_days = (ret_dt.date() - dep_dt.date()).days
        except Exception:
            filtered.append(d)
            continue
        if (min_days is None or trip_days >= min_days) and (max_days is None or trip_days <= max_days):
            filtered.append(d)
    return filtered


def search_deals(
    *,
    one_way: bool,
    origin: str,
    destination: Optional[str],
    departure_date: str,
    return_date: Optional[str],
    travelers: int,
    cabin: Optional[str],
    stops: str,
    duration_range: Optional[Dict[str, int]],
    limit: int = 50,
) -> List[Dict[str, Any]]:
    client = AmadeusClient()
    params: Dict[str, Any] = {
        'originLocationCode': origin,
        'departureDate': departure_date,
        'adults': travelers,
        'max': min(limit, 250),
    }
    if destination:
        params['destinationLocationCode'] = destination
    if cabin:
        params['travelClass'] = cabin
    if not one_way and return_date:
        params['returnDate'] = return_date
    if stops == 'direct':
        params['nonStop'] = 'true'

    # If destination is provided → search offers directly
    if destination:
        raw = client.search_flight_offers(**params)
    else:
        # Anywhere: use inspiration to get top destinations then fetch offers for each
        insp = client.flight_destinations(origin=origin, oneWay=str(one_way).lower())
        candidates = [d.get('destination') for d in (insp.get('data') or []) if d.get('destination')]
        offers = []
        for dst in candidates[:10]:
            p = dict(params)
            p['destinationLocationCode'] = dst
            try:
                res = client.search_flight_offers(**p)
                if res and res.get('data'):
                    offers.extend(res.get('data'))
            except Exception:
                continue
        raw = { 'data': offers }
    normalized = normalize_flight_offers(raw, num_travelers=travelers, cabin_class=cabin)

    # Post-filters
    normalized = _filter_by_stops(normalized, stops=stops, one_way=one_way)
    normalized = _filter_by_duration_range(normalized, duration_range=duration_range)

    # Scoring (basic for now)
    for d in normalized:
        # Baseline & pct drop
        baseline, _ = compute_baseline_for_deal(
            origin=d.get('origin_iata'), destination=d.get('destination_iata'), departure_iso=d.get('departure_datetime')
        )
        d['price_baseline'] = baseline
        d['price_pct_drop'] = pct_drop_from_baseline(float(d.get('price_total') or 0.0), baseline)
        # bookUrl fallback
        try:
            dep_date = str(d.get('departure_datetime'))[:10]
            ret_date = str(d.get('return_datetime'))[:10] if d.get('return_datetime') else None
            d['deep_link'] = d.get('deep_link') or google_flights_deeplink(
                origin=str(d.get('origin_iata') or ''),
                destination=str(d.get('destination_iata') or ''),
                departure_date=dep_date,
                return_date=ret_date,
            )
        except Exception:
            pass
        score, reasons, badges = compute_deal_score(d)
        d['score_int_0_100'] = score
        d['score_factors_json'] = reasons
        d['badges_json'] = badges

    # Order by price asc, then score desc
    normalized.sort(key=lambda x: (
        -float(x.get('price_pct_drop') or 0.0),
        float(x.get('price_total') or 0.0),
        -int(x.get('score_int_0_100') or 0),
    ))
    return normalized[:limit]



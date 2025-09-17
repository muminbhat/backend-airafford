from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional

from django.db import transaction

from apps.deals.models import FlightDeal, SearchRequest


def _parse_iso_dt(dt_str: Optional[str]) -> Optional[datetime]:
    if not dt_str:
        return None
    try:
        # Support 'Z' suffix
        if dt_str.endswith('Z'):
            dt_str = dt_str.replace('Z', '+00:00')
        dt = datetime.fromisoformat(dt_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None


def _compute_search_hash(params: Dict[str, Any]) -> str:
    key_parts = [
        str(params.get('origin') or ''),
        str(params.get('destination') or ''),
        str(params.get('departure_date') or ''),
        str(params.get('return_date') or ''),
        str(params.get('travelers') or ''),
        str(params.get('cabin') or ''),
        str(params.get('stops') or ''),
    ]
    digest = hashlib.sha256('|'.join(key_parts).encode('utf-8')).hexdigest()
    return digest


def record_search_request(params: Dict[str, Any], user_agent: Optional[str], ip_hash: Optional[str]) -> SearchRequest:
    return SearchRequest.objects.create(params_json=params, user_agent=user_agent or '', ip_hash=ip_hash or '')


@transaction.atomic
def persist_deals(normalized_deals: Iterable[Dict[str, Any]], search_params: Dict[str, Any], limit: int = 50) -> List[FlightDeal]:
    search_hash = _compute_search_hash(search_params)
    saved: List[FlightDeal] = []
    for d in list(normalized_deals)[:limit]:
        obj, _ = FlightDeal.objects.update_or_create(
            search_hash=search_hash,
            origin_iata=d.get('origin_iata'),
            destination_iata=d.get('destination_iata'),
            departure_datetime=_parse_iso_dt(d.get('departure_datetime')),
            defaults={
                'provider': d.get('provider') or 'amadeus',
                'deep_link': d.get('deep_link'),
                'one_way_bool': bool(d.get('one_way_bool')),
                'return_datetime': _parse_iso_dt(d.get('return_datetime')),
                'num_stops': int(d.get('num_stops') or 0),
                'duration_minutes': int(d.get('duration_minutes') or 0),
                'layover_minutes_max': int(d.get('layover_minutes_max') or 0),
                'airline_codes': list(d.get('airline_codes') or []),
                'cabin_class': d.get('cabin_class'),
                'price_total': float(d.get('price_total') or 0.0),
                'currency': d.get('currency') or 'USD',
                'num_travelers': int(d.get('num_travelers') or 1),
                'score_int_0_100': d.get('score_int_0_100'),
                'score_factors_json': d.get('score_factors_json'),
                'badges_json': d.get('badges_json'),
            }
        )
        saved.append(obj)
    return saved


def fetch_top_deals(*, origin: Optional[str] = None, destination: Optional[str] = None, limit: int = 50) -> List[FlightDeal]:
    qs = FlightDeal.objects.all().order_by('-score_int_0_100', '-created_at')
    if origin:
        qs = qs.filter(origin_iata=origin)
    if destination:
        qs = qs.filter(destination_iata=destination)
    return list(qs[:limit])



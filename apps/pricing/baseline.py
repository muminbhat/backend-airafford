from __future__ import annotations

from datetime import datetime, timedelta
from statistics import median
from typing import Optional, Tuple

from django.db.models import Q

from apps.deals.models import FlightDeal


def _safe_date(dt_iso: Optional[str]) -> Optional[datetime]:
    if not dt_iso:
        return None
    try:
        return datetime.fromisoformat(str(dt_iso).replace('Z', '+00:00'))
    except Exception:
        return None


def compute_baseline_for_deal(
    *, origin: str, destination: str, departure_iso: Optional[str], currency_hint: Optional[str] = None
) -> Tuple[Optional[float], Optional[float]]:
    """Compute a simple median baseline and % drop using historical FlightDeal rows.

    Returns: (baseline_price, pct_drop) where pct_drop is in [0,1] or None.
    """
    dep_dt = _safe_date(departure_iso)
    if not dep_dt:
        # Use last 90 days deals for route
        window_start = datetime.utcnow() - timedelta(days=90)
        qs = (
            FlightDeal.objects.filter(origin_iata=origin, destination_iata=destination, created_at__gte=window_start)
            .order_by('-created_at')
            .values_list('price_total', flat=True)[:500]
        )
    else:
        # Use deals within +/- 30 days around the departure date for the same route
        start = dep_dt - timedelta(days=30)
        end = dep_dt + timedelta(days=30)
        qs = (
            FlightDeal.objects.filter(
                origin_iata=origin,
                destination_iata=destination,
                departure_datetime__gte=start,
                departure_datetime__lte=end,
            )
            .order_by('-created_at')
            .values_list('price_total', flat=True)[:500]
        )

    prices = [float(p) for p in qs if p is not None]
    if not prices:
        return None, None
    base = float(median(prices))
    return base, None


def pct_drop_from_baseline(current_price: float, baseline: Optional[float]) -> Optional[float]:
    if baseline is None or baseline <= 0:
        return None
    drop = (baseline - current_price) / baseline
    return max(0.0, round(drop, 4))



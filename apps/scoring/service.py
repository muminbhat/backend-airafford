from __future__ import annotations

from typing import Any, Dict, List, Tuple
from datetime import datetime
from django.conf import settings
from apps.scoring.ai_client import ai_score_deal, AIScoringError
from apps.deals.models import AirlineQuality


def compute_deal_score(deal: Dict[str, Any]) -> Tuple[int, List[str], List[str]]:
    """Compute AI-driven score [0,100] with fallback heuristics and badges."""
    # Try AI
    try:
        ai_score, ai_reasons, ai_badges = ai_score_deal(deal)
        # Merge AI badges with heuristic-only safety badges without changing AI score
        merged_badges: List[str] = list(ai_badges)
        # Heuristic safety badges
        stops = int(deal.get('num_stops') or 0)
        layover_max = int(deal.get('layover_minutes_max') or 0)
        departure_iso = deal.get('departure_datetime')
        try:
            if layover_max >= 180 and '⏱️ Long layover' not in merged_badges:
                merged_badges.append('⏱️ Long layover')
        except Exception:
            pass
        try:
            if departure_iso:
                from datetime import datetime
                dep_dt = datetime.fromisoformat(str(departure_iso).replace('Z', '+00:00'))
                if 0 <= dep_dt.hour <= 5 and '🌙 Red-eye' not in merged_badges:
                    merged_badges.append('🌙 Red-eye')
        except Exception:
            pass
        return ai_score, ai_reasons, merged_badges[:3]
    except AIScoringError:
        pass

    # Fallback heuristic
    score = 50.0
    reasons: List[str] = []
    badges: List[str] = []

    stops = int(deal.get('num_stops') or 0)
    layover_max = int(deal.get('layover_minutes_max') or 0)
    duration_min = int(deal.get('duration_minutes') or 0)
    departure_iso = deal.get('departure_datetime')

    if stops == 0:
        score += 20
        reasons.append('Direct flight bonus')
    elif stops == 1:
        score += 10
        reasons.append('One-stop acceptable')
    else:
        reasons.append('Multiple stops reduce comfort')

    if layover_max >= 180:
        penalty = min(10.0, (layover_max / 60.0) * 2.0)
        score -= penalty
        reasons.append(f'Layover penalty (-{int(penalty)})')
        badges.append('⏱️ Long layover')

    if duration_min >= 1200:
        score -= 10
        reasons.append('Very long total duration')
    elif duration_min >= 900:
        score -= 5
        reasons.append('Long total duration')

    # Airline quality penalty
    try:
        airline_codes = list(deal.get('airline_codes') or [])
        if airline_codes:
            low_quality = AirlineQuality.objects.filter(carrier_code__in=airline_codes, score_float_0_1__lt=0.4)
            if low_quality.exists():
                score -= 8
                reasons.append('Low-rated operating carrier')
                badges.append('⚠️ Bad airline')
    except Exception:
        pass

    # Time-of-day preferences: red-eye penalty
    try:
        if departure_iso:
            dep_dt = datetime.fromisoformat(str(departure_iso).replace('Z', '+00:00'))
            if 0 <= dep_dt.hour <= 5:
                score -= 4
                reasons.append('Red-eye departure')
                badges.append('🌙 Red-eye')
    except Exception:
        pass

    score = max(0, min(100, int(round(score))))
    if score >= 85 and stops == 0:
        badges.append('🔥 Amazing deal')

    return score, reasons, badges



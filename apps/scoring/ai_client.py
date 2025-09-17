from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple
import requests
from django.conf import settings


class AIScoringError(Exception):
    pass


def _build_prompt(deal: Dict[str, Any]) -> str:
    # Instruction for consistent structured outputs
    allowed_badges = [
        "⚠️ Bad airline",
        "⏱️ Long layover",
        "🌙 Red-eye",
        "🔥 Amazing deal",
        "🌅 Morning departure",
        "🛌 Weekend-friendly",
        "🍂 Shoulder season",
        "⏱️ Tight connection",
    ]
    return (
        "You are Flight Scanner AI. Score a flight deal from 0-100. "
        "Optimize for value and traveler experience. Consider: stops, maximum layover, total duration (minutes), cabin, airline quality (if implied by codes), and price. "
        "If price baselines are absent, prioritize comfort (direct, shorter duration, reasonable layovers) and keep scores conservative.\n\n"
        "Return STRICT JSON with keys: \n"
        "- score: integer 0-100 (no decimals)\n"
        "- reasons: array of up to 5 short strings (human-friendly)\n"
        "- badges: array of up to 3 strings chosen from this set only: " + str(allowed_badges) + "\n\n"
        "Guidelines: Direct gets higher scores. Layovers over 180 minutes are bad. Red-eye departures (00:00-05:59 local) are bad.\n"
        "Award '🔥 Amazing deal' only if overall score >= 85 and the itinerary is direct.\n\n"
        f"deal: {deal}"
    )


def ai_score_deal(deal: Dict[str, Any]) -> Tuple[int, List[str], List[str]]:
    base_url = settings.AI_BASE_URL.rstrip('/')
    api_key = settings.AI_API_KEY
    model = getattr(settings, 'AI_MODEL', 'llama-3')
    headers = {
        'Content-Type': 'application/json',
    }
    if api_key:
        headers['Authorization'] = f'Bearer {api_key}'
    body = {
        'model': model,
        'messages': [
            { 'role': 'system', 'content': 'You are a precise flight deal grader that returns strict JSON only.' },
            { 'role': 'user', 'content': _build_prompt(deal) },
        ],
        'temperature': 0.2,
        'response_format': { 'type': 'json_object' },
    }
    resp = requests.post(f"{base_url}/chat/completions", headers=headers, json=body, timeout=30)
    if resp.status_code >= 400:
        raise AIScoringError(f"AI scoring failed: {resp.status_code} {resp.text}")
    data = resp.json()
    content = data.get('choices', [{}])[0].get('message', {}).get('content', '{}')
    try:
        import json
        obj = json.loads(content)
        score = int(obj.get('score', 0))
        reasons = [str(x) for x in obj.get('reasons', [])][:5]
        badges = [str(x) for x in obj.get('badges', [])][:3]
        score = max(0, min(100, score))
        return score, reasons, badges
    except Exception as e:
        raise AIScoringError(f"Malformed AI response: {content}")



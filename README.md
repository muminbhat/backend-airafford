# AirAfford AI
This helps you spot unusually cheap flights from your home airport. It uses Amadeus for live data and an AI Deal Score to quickly judge which options are worth booking.

## Start
Backend (Django):
1. Open a terminal in `backend/`
2. Create venv and install deps
   ```bash
   python -m venv .venv
   .venv/Scripts/pip install -r requirements.txt
   ```
3. Copy `.env.example` to `.env` and fill values (Amadeus test keys are fine). For AI I am using an OpenAI style endpoint (no key needed):
   
   ```env
   AI_BASE_URL=https://digillm.digiboxx.com/v1
   AI_MODEL=llama-3
   ```
4. Run DB migrations and start server
   
   ```bash
   .venv/Scripts/python manage.py migrate
   .venv/Scripts/python manage.py runserver 127.0.0.1:8000
   ```

Frontend (Next.js):
1. From `frontend/`, run:
   
   ```bash
   npm run dev
   ```
2. Open `http://localhost:3000`

Tip: If you don’t enter dates on the search form, backend will default to tomorrow (and return +5 days for round trip). There's validation also implemented that prevents it. 

## Endpoints (backend)
- POST ` /api/deals/search `
  - Body:
    ```json
    {
      "oneWay": true,
      "origin": "JFK",
      "destination": "LAX", // optional; if omitted we do "Anywhere"
      "dateRange": { "start": "2025-11-10", "end": "2025-11-15" },
      "stops": "any|direct|max1",
      "travelers": 1,
      "cabin": "ECONOMY|PREMIUM_ECONOMY|BUSINESS|FIRST",
      "limit": 25
    }
    ```
  - Returns normalised deals with fields like `price_total`, `price_baseline`, `price_pct_drop`, `score_int_0_100`, `score_factors_json`, `badges_json`, `deep_link`.

- GET ` /api/deals/top?origin=JFK&limit=20 `
- GET ` /api/metadata/airports?query=del ` (for IATA autocomplete)
- GET ` /api/health `

## What powers the data
- Amadeus Flight Offers Search for live fares.
- Amadeus Flight Inspiration Search for “Anywhere” suggestions.
- We store recent results to compute a simple route baseline (median) so that “% drop” feels meaningful.

## AI Deal Score (how we score)
We use an AI‑first approach with a fallback heuristic.
- The AI (Llama 3, OpenAI‑compatible endpoint) sees a compact JSON‑friendly prompt with these signals:
  - Stops (direct vs 1+), maximum layover minutes
  - Total duration in minutes
  - Cabin class
  - Airline codes (to imply quality if known)
  - Current price, baseline price (median), computed % drop
  - Dates (to catch red‑eye)
- It must respond in strict JSON:
  ```json
  { "score": 0-100, "reasons": ["..."], "badges": ["..."] }
  ```
- We whitelist badges to keep UX clean: ⚠️ Bad airline, ⏱️ Long layover, 🌙 Red‑eye, 🔥 Amazing deal, 🌅 Morning departure, 🛌 Weekend‑friendly, 🍂 Shoulder season, ⏱️ Tight connection.
- If AI fails or is unavailable, we fall back to a sensible heuristic:
  - Start at 50; +20 direct, +10 one stop
  - Penalty for very long layover (≥ 180 mins)
  - Penalty for very long total duration (≥ 15h strong, ≥ 10h mild)
  - Penalty for red‑eye (00:00–05:59)
  - Optional “bad airline” penalty if we have a low rating on file
  - “🔥 Amazing deal” if score ≥ 85 and direct

### Baseline and % drop
- Baseline is the median of prices for the same route within ±30 days of departure (fallback to last 90 days of stored results).
- % drop = max(0, (baseline − current)/baseline)
- Sorting prefers bigger % drop, then lower price, then higher score.

## System design
- Web: Django + DRF (serves API)
- DB: Postgres (deals, baselines), nightly backup
- Cache: Redis (search caching/coalescing, airport lookups)
- Celery + Beat (daily baseline rebuilds, pre‑warm top deals)
- LLM: external OpenAI‑style endpoint
- Reverse proxy: Nginx
- Monitoring: Sentry for errors, simple request timing logs

High level flow:
1) Frontend calls Search → Web checks cache → calls Amadeus → normalises → computes baseline & % drop → AI scores → persists snapshot → returns JSON.
2) Anywhere: Web asks Inspiration API for destinations → fetches offers per top route → same pipeline as above.
3) Airports: Locations API with small TTL cache to keep type‑ahead snappy.

<img width="3840" height="1643" alt="SysDes" src="https://github.com/user-attachments/assets/5c5f264d-87bf-429a-af92-789076fbce28" />

## Notes
- CORS is enabled for local development.
- Dates are optional; we pick tomorrow (and +5 days for round trip) if you don’t provide them. (Recently i added validation in frontend)
- Google Flights link is provided as a simple fallback deep link for booking.

import time
from dataclasses import dataclass
from typing import Any, Dict, Optional

import requests
from django.conf import settings


class AmadeusAuthError(Exception):
    pass


class AmadeusApiError(Exception):
    def __init__(self, status_code: int, payload: Any):
        super().__init__(f"Amadeus API error {status_code}: {payload}")
        self.status_code = status_code
        self.payload = payload


@dataclass
class OAuthToken:
    access_token: str
    token_type: str
    expires_at_epoch: float

    @property
    def is_expired(self) -> bool:
        # Refresh 60s before expiry as a buffer
        return time.time() >= (self.expires_at_epoch - 60)


class AmadeusClient:
    """Lightweight Amadeus client with token caching in-memory.

    For multi-process deployments, consider Redis-backed token caching.
    """

    def __init__(self, base_url: Optional[str] = None, api_key: Optional[str] = None, api_secret: Optional[str] = None):
        self.base_url = base_url or settings.AMADEUS_BASE_URL.rstrip('/')
        self.api_key = api_key or settings.AMADEUS_API_KEY
        self.api_secret = api_secret or settings.AMADEUS_API_SECRET
        self._token: Optional[OAuthToken] = None
        self._session = requests.Session()

    # ---------- OAuth ----------
    def _fetch_token(self) -> OAuthToken:
        url = f"{self.base_url}/v1/security/oauth2/token"
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        data = {
            "grant_type": "client_credentials",
            "client_id": self.api_key,
            "client_secret": self.api_secret,
        }
        resp = self._session.post(url, headers=headers, data=data, timeout=15)
        if resp.status_code != 200:
            raise AmadeusAuthError(f"Failed to obtain token: {resp.status_code} {resp.text}")
        payload = resp.json()
        expires_in = payload.get("expires_in", 0)
        token = OAuthToken(
            access_token=payload["access_token"],
            token_type=payload.get("token_type", "Bearer"),
            expires_at_epoch=time.time() + float(expires_in),
        )
        return token

    def _get_token(self) -> OAuthToken:
        if self._token is None or self._token.is_expired:
            self._token = self._fetch_token()
        return self._token

    # ---------- HTTP ----------
    def _headers(self) -> Dict[str, str]:
        token = self._get_token()
        return {
            "Authorization": f"Bearer {token.access_token}",
            "Accept": "application/json",
        }

    def get(self, path: str, params: Optional[Dict[str, Any]] = None, timeout: int = 20) -> Any:
        url = f"{self.base_url}{path}"
        resp = self._session.get(url, headers=self._headers(), params=params or {}, timeout=timeout)
        if resp.status_code >= 400:
            raise AmadeusApiError(resp.status_code, resp.text)
        if resp.status_code == 204:
            return None
        return resp.json()

    def post(self, path: str, json: Optional[Dict[str, Any]] = None, timeout: int = 25) -> Any:
        url = f"{self.base_url}{path}"
        resp = self._session.post(url, headers={**self._headers(), "Content-Type": "application/json"}, json=json or {}, timeout=timeout)
        if resp.status_code >= 400:
            raise AmadeusApiError(resp.status_code, resp.text)
        if resp.status_code == 204:
            return None
        return resp.json()

    # ---------- Flight Offers Search ----------
    def search_flight_offers(self, **kwargs: Any) -> Any:
        """Wrapper for Amadeus Flight Offers Search API (v2).

        Common parameters:
        - originLocationCode: IATA
        - destinationLocationCode: IATA
        - departureDate: YYYY-MM-DD
        - returnDate: YYYY-MM-DD (optional for round-trip)
        - adults: int
        - travelClass: ECONOMY|PREMIUM_ECONOMY|BUSINESS|FIRST
        - nonStop: true|false
        - max: int (limit results)
        """
        params = {k: v for k, v in kwargs.items() if v is not None}
        return self.get("/v2/shopping/flight-offers", params=params)

    # ---------- Inspiration (Anywhere) ----------
    def flight_destinations(self, **kwargs: Any) -> Any:
        """Amadeus Flight Inspiration Search.

        Common params:
        - origin: IATA code
        - departureDate: YYYY-MM (month) or YYYY-MM-DD
        - oneWay: true|false
        """
        params = {k: v for k, v in kwargs.items() if v is not None}
        return self.get("/v1/shopping/flight-destinations", params=params)

    # ---------- Locations (Airports) ----------
    def search_locations(self, *, keyword: str, subType: str = "AIRPORT", limit: int = 10) -> Any:
        params = {"keyword": keyword, "subType": subType, "page[limit]": min(limit, 20)}
        return self.get("/v1/reference-data/locations", params=params)



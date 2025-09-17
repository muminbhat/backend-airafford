from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from apps.api.serializers import DealsSearchRequestSerializer, DealSerializer
from apps.search.service import search_deals
from apps.providers.amadeus_client import AmadeusApiError, AmadeusAuthError
from apps.deals.repository import record_search_request, persist_deals, fetch_top_deals
from apps.providers.amadeus_client import AmadeusClient


class DealsSearchView(APIView):
    def post(self, request):
        serializer = DealsSearchRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        from datetime import datetime, timedelta

        date_range = data.get("dateRange") or {}
        dep = (date_range.get("start") or "").strip()
        ret = (date_range.get("end") or "").strip() if not data["oneWay"] else None
        if not dep:
            dep = (datetime.utcnow() + timedelta(days=1)).date().isoformat()
        if not data["oneWay"] and not ret:
            try:
                dep_dt = datetime.fromisoformat(dep)
            except Exception:
                dep_dt = (datetime.utcnow() + timedelta(days=1))
            ret = (dep_dt + timedelta(days=5)).date().isoformat()

        try:
            deals = search_deals(
                one_way=data["oneWay"],
                origin=data["origin"].upper(),
            destination=(data.get("destination") or None)
                and (data.get("destination") or '').upper(),
                departure_date=dep,
                return_date=ret,
                travelers=data["travelers"],
                cabin=data.get("cabin"),
                stops=data.get("stops", "any"),
                duration_range=data.get("durationRange"),
                limit=data.get("limit", 50),
            )
            # Persist async in future; synchronous for MVP
            record_search_request(
                params={
                    'one_way': data["oneWay"],
                    'origin': data["origin"].upper(),
                    'destination': data["destination"].upper(),
                    'departure_date': dep,
                    'return_date': ret,
                    'travelers': data["travelers"],
                    'cabin': data.get("cabin"),
                    'stops': data.get("stops", "any"),
                },
                user_agent=request.META.get('HTTP_USER_AGENT'),
                ip_hash=request.META.get('REMOTE_ADDR'),
            )
            persist_deals(deals, search_params={
                'origin': data["origin"].upper(),
                'destination': data["destination"].upper(),
                'departure_date': dep,
                'return_date': ret,
                'travelers': data["travelers"],
                'cabin': data.get("cabin"),
                'stops': data.get("stops", "any"),
            }, limit=data.get("limit", 50))
        except (AmadeusAuthError, AmadeusApiError) as e:
            return Response({"detail": str(e)}, status=status.HTTP_502_BAD_GATEWAY)

        return Response({"deals": DealSerializer(deals, many=True).data}, status=status.HTTP_200_OK)


class TopDealsView(APIView):
    def get(self, request):
        origin = request.query_params.get('origin')
        destination = request.query_params.get('destination')
        try:
            limit = int(request.query_params.get('limit', '50'))
        except Exception:
            limit = 50
        items = fetch_top_deals(origin=origin, destination=destination, limit=limit)
        # Convert model instances to API shape via DealSerializer
        payload = []
        for it in items:
            payload.append({
                'provider': it.provider,
                'one_way_bool': it.one_way_bool,
                'origin_iata': it.origin_iata,
                'destination_iata': it.destination_iata,
                'departure_datetime': it.departure_datetime.isoformat() if it.departure_datetime else None,
                'return_datetime': it.return_datetime.isoformat() if it.return_datetime else None,
                'num_stops': it.num_stops,
                'duration_minutes': it.duration_minutes,
                'layover_minutes_max': it.layover_minutes_max,
                'airline_codes': it.airline_codes,
                'cabin_class': it.cabin_class,
                'price_total': it.price_total,
                'currency': it.currency,
                'num_travelers': it.num_travelers,
                'deep_link': it.deep_link,
                'score_int_0_100': it.score_int_0_100,
                'score_factors_json': it.score_factors_json,
                'badges_json': it.badges_json,
            })
        return Response({'deals': DealSerializer(payload, many=True).data}, status=status.HTTP_200_OK)


class HealthView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request):
        return Response({'status': 'ok'}, status=status.HTTP_200_OK)


class AirportsAutocompleteView(APIView):
    def get(self, request):
        q = request.query_params.get('query') or ''
        if not q or len(q) < 2:
            return Response({'airports': []}, status=status.HTTP_200_OK)
        client = AmadeusClient()
        res = client.search_locations(keyword=q, subType='AIRPORT', limit=10)
        airports = []
        for item in res.get('data', []):
            code = item.get('iataCode')
            name = item.get('name')
            city = (item.get('address') or {}).get('cityName')
            country = (item.get('address') or {}).get('countryName')
            if code and name:
                airports.append({'iata': code, 'name': name, 'city': city, 'country': country})
        return Response({'airports': airports}, status=status.HTTP_200_OK)



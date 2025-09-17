from __future__ import annotations

from django.db import models


class Airport(models.Model):
    iata = models.CharField(primary_key=True, max_length=3)
    name = models.CharField(max_length=128)
    city = models.CharField(max_length=128)
    country = models.CharField(max_length=64)
    lat = models.FloatField(null=True, blank=True)
    lon = models.FloatField(null=True, blank=True)

    def __str__(self) -> str:  # pragma: no cover
        return f"{self.iata} - {self.city}"


class AirlineQuality(models.Model):
    carrier_code = models.CharField(primary_key=True, max_length=3)
    score_float_0_1 = models.FloatField(default=0.5)
    updated_at = models.DateTimeField(auto_now=True)


class FareHistoryBucket(models.Model):
    origin_iata = models.CharField(max_length=3)
    destination_iata = models.CharField(max_length=3)
    one_way_bool = models.BooleanField(default=True)
    month_bucket = models.CharField(max_length=7)  # YYYY-MM
    days_to_departure_bucket = models.CharField(max_length=16)  # e.g., 0-7
    median_price = models.FloatField(null=True, blank=True)
    mean_price = models.FloatField(null=True, blank=True)
    std_price = models.FloatField(null=True, blank=True)
    currency = models.CharField(max_length=8, default='USD')
    sample_size = models.IntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["origin_iata", "destination_iata", "month_bucket", "days_to_departure_bucket"]),
        ]


class FlightDeal(models.Model):
    provider = models.CharField(max_length=32)
    search_hash = models.CharField(max_length=64, db_index=True)
    deep_link = models.URLField(null=True, blank=True)

    origin_iata = models.CharField(max_length=3)
    destination_iata = models.CharField(max_length=3)
    one_way_bool = models.BooleanField(default=True)

    departure_datetime = models.DateTimeField(null=True, blank=True)
    return_datetime = models.DateTimeField(null=True, blank=True)

    num_stops = models.IntegerField(default=0)
    duration_minutes = models.IntegerField(default=0)
    layover_minutes_max = models.IntegerField(default=0)

    airline_codes = models.JSONField(default=list)
    cabin_class = models.CharField(max_length=32, null=True, blank=True)

    price_total = models.FloatField(default=0)
    currency = models.CharField(max_length=8, default='USD')
    num_travelers = models.IntegerField(default=1)

    score_int_0_100 = models.IntegerField(null=True, blank=True)
    score_factors_json = models.JSONField(null=True, blank=True)
    badges_json = models.JSONField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    valid_until = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["origin_iata", "destination_iata", "departure_datetime", "price_total"]),
        ]


class SearchRequest(models.Model):
    params_json = models.JSONField()
    user_agent = models.CharField(max_length=256, null=True, blank=True)
    ip_hash = models.CharField(max_length=64, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)



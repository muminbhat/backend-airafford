from rest_framework import serializers


class DealsSearchRequestSerializer(serializers.Serializer):
    oneWay = serializers.BooleanField()
    origin = serializers.CharField(min_length=3, max_length=3)
    destination = serializers.CharField(min_length=3, max_length=3, required=False, allow_null=True)
    dateRange = serializers.DictField(child=serializers.CharField(allow_blank=True), required=False)
    durationRange = serializers.DictField(child=serializers.IntegerField(), required=False)
    stops = serializers.ChoiceField(choices=["direct", "max1", "any"], default="any")
    travelers = serializers.IntegerField(min_value=1, max_value=9)
    cabin = serializers.ChoiceField(choices=["ECONOMY", "PREMIUM_ECONOMY", "BUSINESS", "FIRST"], required=False, allow_null=True)
    limit = serializers.IntegerField(min_value=1, max_value=100, required=False, default=50)


class DealSerializer(serializers.Serializer):
    provider = serializers.CharField()
    one_way_bool = serializers.BooleanField()
    origin_iata = serializers.CharField()
    destination_iata = serializers.CharField()
    departure_datetime = serializers.CharField(allow_null=True)
    return_datetime = serializers.CharField(allow_null=True)
    num_stops = serializers.IntegerField()
    duration_minutes = serializers.IntegerField()
    layover_minutes_max = serializers.IntegerField()
    airline_codes = serializers.ListField(child=serializers.CharField())
    cabin_class = serializers.CharField(allow_null=True)
    price_total = serializers.FloatField()
    currency = serializers.CharField()
    num_travelers = serializers.IntegerField()
    deep_link = serializers.CharField(allow_null=True)
    # Insights
    price_baseline = serializers.FloatField(allow_null=True, required=False)
    price_pct_drop = serializers.FloatField(allow_null=True, required=False)
    score_int_0_100 = serializers.IntegerField(allow_null=True)
    score_factors_json = serializers.ListField(child=serializers.CharField(), allow_null=True)
    badges_json = serializers.ListField(child=serializers.CharField(), allow_null=True)


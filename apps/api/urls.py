from django.urls import path
from apps.api.views import DealsSearchView, TopDealsView, HealthView, AirportsAutocompleteView

urlpatterns = [
    path('deals/search', DealsSearchView.as_view(), name='deals-search'),
    path('deals/top', TopDealsView.as_view(), name='deals-top'),
    path('health', HealthView.as_view(), name='health'),
    path('metadata/airports', AirportsAutocompleteView.as_view(), name='airports-autocomplete'),
]



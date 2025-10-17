from django.urls import path
from .views import PingView, SecurePingView

urlpatterns = [
    path('secure-ping/', SecurePingView.as_view(), name='api-secure-ping'),
    path("ping/", PingView.as_view(), name="api-ping"),
]

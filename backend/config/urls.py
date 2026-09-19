from django.contrib import admin
from django.urls import path
from drf_spectacular.views import SpectacularAPIView

from health.views import LiveView, ReadyView

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/health/live/", LiveView.as_view(), name="health-live"),
    path("api/health/ready/", ReadyView.as_view(), name="health-ready"),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
]

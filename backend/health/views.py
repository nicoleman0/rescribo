from django.conf import settings
from django.db import DatabaseError, connection
from drf_spectacular.utils import extend_schema
from redis import Redis, RedisError
from rest_framework import serializers
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from health.version import VERSION


class HealthSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=["ok", "unavailable"])


class LiveView(APIView):
    authentication_classes: list = []
    permission_classes = [AllowAny]

    @extend_schema(responses=HealthSerializer, auth=[])
    def get(self, request: Request) -> Response:
        return Response({"status": "ok"})


class ReadyView(APIView):
    authentication_classes: list = []
    permission_classes = [AllowAny]

    @extend_schema(responses={200: HealthSerializer, 503: HealthSerializer}, auth=[])
    def get(self, request: Request) -> Response:
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
            with Redis.from_url(
                settings.REDIS_URL, socket_connect_timeout=2, socket_timeout=2
            ) as redis:
                redis.ping()
        except DatabaseError, RedisError:
            return Response({"status": "unavailable"}, status=503)
        return Response({"status": "ok"})


class VersionSerializer(serializers.Serializer):
    # connections.views also generates a "Version" component; name this one after the app.
    version = serializers.CharField()

    class Meta:
        ref_name = "AppVersion"


class VersionView(APIView):
    @extend_schema(responses=VersionSerializer)
    def get(self, request: Request) -> Response:
        return Response({"version": VERSION})

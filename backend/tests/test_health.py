from unittest.mock import patch

import pytest
from django.db import OperationalError
from django.test import Client
from redis import ConnectionError as RedisConnectionError


def test_liveness_does_not_need_dependencies(client: Client) -> None:
    response = client.get("/api/health/live/")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.django_db
def test_readiness_checks_real_database_and_redis(client: Client) -> None:
    assert client.get("/api/health/ready/").status_code == 200


def test_database_failure_does_not_expose_details(client: Client) -> None:
    with patch("health.views.connection.cursor", side_effect=OperationalError("private detail")):
        response = client.get("/api/health/ready/")
    assert response.status_code == 503
    assert response.json() == {"status": "unavailable"}


@pytest.mark.django_db
def test_redis_failure_reports_unavailable(client: Client) -> None:
    with patch("health.views.Redis.from_url", side_effect=RedisConnectionError("private detail")):
        assert client.get("/api/health/ready/").status_code == 503

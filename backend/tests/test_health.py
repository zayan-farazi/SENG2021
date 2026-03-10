from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client():
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client


def test_health_returns_200(client):
    response = client.get("/v1/health")
    assert response.status_code == 200


def test_health_returns_correct_fields(client):
    response = client.get("/v1/health")
    data = response.json()

    assert "status" in data
    assert "uptimeSeconds" in data
    assert "version" in data
    assert "requestCount" in data


def test_health_returns_correct_values(client):
    response = client.get("/v1/health")
    data = response.json()

    assert data["status"] == "healthy"
    assert isinstance(data["uptimeSeconds"], float)
    assert data["version"] == "0.1.0"
    assert isinstance(data["requestCount"], int)


def test_health_request_count_increments(client):
    response1 = client.get("/v1/health")
    count1 = response1.json()["requestCount"]

    response2 = client.get("/v1/health")
    count2 = response2.json()["requestCount"]

    assert count2 == count1 + 1


def test_health_uptime_is_positive(client):
    response = client.get("/v1/health")
    assert response.json()["uptimeSeconds"] >= 0


def test_health_request_count_is_non_negative(client):
    response = client.get("/v1/health")
    assert response.json()["requestCount"] >= 0
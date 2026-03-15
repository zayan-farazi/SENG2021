from __future__ import annotations

import importlib

from fastapi.testclient import TestClient

import app.main as app_main
from app.main import DEFAULT_ALLOWED_ORIGINS, _parse_allowed_origins


def test_parse_allowed_origins_defaults_to_localhost_values():
    assert _parse_allowed_origins(None) == list(DEFAULT_ALLOWED_ORIGINS)


def test_parse_allowed_origins_strips_whitespace_and_empties():
    assert _parse_allowed_origins(" https://a.example , ,https://b.example  ") == [
        "https://a.example",
        "https://b.example",
    ]


def test_health_preflight_allows_default_localhost_origin():
    with TestClient(app_main.app, raise_server_exceptions=False) as client:
        response = client.options(
            "/v1/health",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "GET",
            },
        )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"


def test_health_preflight_allows_configured_render_origin(monkeypatch):
    monkeypatch.setenv("ALLOWED_ORIGINS", "https://frontend-example.onrender.com")
    reloaded = importlib.reload(app_main)

    with TestClient(reloaded.app, raise_server_exceptions=False) as client:
        response = client.options(
            "/v1/health",
            headers={
                "Origin": "https://frontend-example.onrender.com",
                "Access-Control-Request-Method": "GET",
            },
        )

    assert response.status_code == 200
    assert (
        response.headers["access-control-allow-origin"] == "https://frontend-example.onrender.com"
    )

    importlib.reload(app_main)

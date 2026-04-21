from __future__ import annotations

from fastapi.testclient import TestClient

from app.api.routes import inventory
from app.main import app
from app.models.schemas import ProductListResponse
from app.services.app_key_auth import get_current_party_email


def build_product_list_response() -> ProductListResponse:
    return ProductListResponse.model_validate(
        {
            "items": [
                {
                    "prod_id": 101,
                    "party_id": "seller@example.com",
                    "name": "Handmade ceramic mug",
                    "price": 34,
                    "unit": "EA",
                    "description": "Handmade ceramic mug",
                    "category": "Homeware",
                    "release_date": "2026-04-20",
                    "available_units": 9,
                    "is_visible": True,
                    "show_soldout": True,
                    "image_url": "https://example.test/mug.webp",
                }
            ],
            "page": {"limit": 100, "offset": 0, "hasMore": False, "total": 1},
        }
    )


def test_get_marketplace_catalogue_route_is_registered(monkeypatch):
    monkeypatch.setattr(
        inventory,
        "get_public_marketplace_products",
        lambda limit, offset: build_product_list_response(),
    )

    with TestClient(app) as client:
        response = client.get("/v2/catalogue?limit=100&offset=0")

    assert response.status_code == 200
    body = response.json()
    assert body["items"][0]["name"] == "Handmade ceramic mug"


def test_get_private_inventory_route_is_registered(monkeypatch):
    monkeypatch.setattr(
        inventory,
        "get_user_inventory",
        lambda party_id, limit, offset: build_product_list_response(),
    )
    app.dependency_overrides[get_current_party_email] = lambda: "seller@example.com"

    try:
        with TestClient(app) as client:
            response = client.get("/v2/inventory?limit=100&offset=0")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["items"][0]["party_id"] == "seller@example.com"

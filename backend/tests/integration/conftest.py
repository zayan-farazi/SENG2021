from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import suppress

import pytest
from fastapi.testclient import TestClient

import app.other as other
from app.main import app
from app.services import order_store


def _ensure_supabase_env() -> None:
    if not (os.getenv("SUPABASE_URL") and os.getenv("SUPABASE_KEY")):
        other._load_local_env_files()
    if not (os.getenv("SUPABASE_URL") and os.getenv("SUPABASE_KEY")):
        pytest.skip("SUPABASE_URL and SUPABASE_KEY must be configured to run integration tests.")


@pytest.fixture
def integration_client() -> Iterator[TestClient]:
    _ensure_supabase_env()
    other._SUPABASE_CLIENT = None
    order_store.ORDERS.clear()

    with TestClient(app, raise_server_exceptions=False) as client:
        yield client

    order_store.ORDERS.clear()
    app.dependency_overrides.clear()
    other._SUPABASE_CLIENT = None


@pytest.fixture
def tracked_supabase_records() -> Iterator[dict[str, list[str]]]:
    _ensure_supabase_env()
    tracked = {"party_ids": [], "order_ids": []}
    yield tracked

    with suppress(RuntimeError):
        client = other.get_supabase_client()
        for external_order_id in tracked["order_ids"]:
            for row in other.findOrders(externalOrderId=external_order_id):
                client.table("orderdetails").delete().eq("orderid", row["id"]).execute()
                client.table("orders").delete().eq("id", row["id"]).execute()
        for party_id in tracked["party_ids"]:
            client.table("app_keys").delete().eq("party_id", party_id).execute()
            client.table("parties").delete().eq("party_id", party_id).execute()

    order_store.ORDERS.clear()
    other._SUPABASE_CLIENT = None

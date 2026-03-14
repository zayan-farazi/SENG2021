from __future__ import annotations

from time import monotonic

import pytest

from app.api.routes.orders import ORDERS
from app.main import app
from app.services import order_store
from app.services.app_key_auth import get_current_party_email


@pytest.fixture(autouse=True)
def reset_order_state(request, monkeypatch):
    node_path = str(request.node.path)
    is_integration_test = (
        "/tests/integration/" in node_path or "\\tests\\integration\\" in node_path
    )

    ORDERS.clear()
    app.dependency_overrides.clear()
    if not is_integration_test:
        app.dependency_overrides[get_current_party_email] = lambda: "buyer@example.com"
    if not is_integration_test and request.node.name not in {
        "test_persist_order_to_database_with_real_supabase",
        "test_get_order_record_loads_and_caches_database_order",
        "test_update_order_record_loads_database_order_when_cache_is_empty",
        "test_delete_order_record_deletes_database_order_when_cache_is_empty",
        "test_delete_order_record_returns_false_when_order_is_missing",
    }:
        monkeypatch.setattr(order_store, "persist_order_to_database", lambda _req: 1)
    app.state.start_time = monotonic()
    app.state.request_count = 0

    yield

    ORDERS.clear()
    app.dependency_overrides.clear()
    app.state.start_time = monotonic()
    app.state.request_count = 0

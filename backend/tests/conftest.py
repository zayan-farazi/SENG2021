from __future__ import annotations

from time import monotonic

import pytest

from app.api.routes.orders import ORDERS
from app.main import app
from app.services import order_store
from app.services.app_key_auth import get_current_party_id


@pytest.fixture(autouse=True)
def reset_order_state(request, monkeypatch):
    ORDERS.clear()
    app.dependency_overrides.clear()
    app.dependency_overrides[get_current_party_id] = lambda: "buyer-123"
    if request.node.module.__name__ != "test_order_store":
        monkeypatch.setattr(order_store, "persist_order_to_database", lambda _req: 1)
    app.state.start_time = monotonic()
    app.state.request_count = 0

    yield

    ORDERS.clear()
    app.dependency_overrides.clear()
    app.state.start_time = monotonic()
    app.state.request_count = 0

from __future__ import annotations

import pytest

from app.api.routes.orders import ORDERS
from app.main import app
from app.services import order_store


@pytest.fixture(autouse=True)
def reset_order_state(request, monkeypatch):
    ORDERS.clear()
    if request.node.module.__name__ != "test_order_store":
        monkeypatch.setattr(order_store, "persist_order_to_database", lambda _req: 1)
    for attr in ("request_count", "start_time", "version"):
        if hasattr(app.state, attr):
            delattr(app.state, attr)

    yield

    ORDERS.clear()
    for attr in ("request_count", "start_time", "version"):
        if hasattr(app.state, attr):
            delattr(app.state, attr)

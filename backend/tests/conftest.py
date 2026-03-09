from __future__ import annotations

import pytest

from app.api.routes.orders import ORDERS
from app.main import app


@pytest.fixture(autouse=True)
def reset_order_state():
    ORDERS.clear()
    for attr in ("request_count", "start_time", "version"):
        if hasattr(app.state, attr):
            delattr(app.state, attr)

    yield

    ORDERS.clear()
    for attr in ("request_count", "start_time", "version"):
        if hasattr(app.state, attr):
            delattr(app.state, attr)

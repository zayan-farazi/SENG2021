from __future__ import annotations

import importlib.util


def test_websocket_transport_dependency_is_installed():
    assert importlib.util.find_spec("websockets") is not None

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app
from app.services import inventory_assistant


def test_inventory_assistant_websocket_connects_and_returns_ready_state():
    with TestClient(app) as client:
        with client.websocket_connect("/v1/inventory/assistant/ws") as websocket:
            message = websocket.receive_json()

    assert message == {"type": "session.ready", "payload": {"currentPartial": ""}}


def test_inventory_assistant_websocket_echoes_partial_transcripts():
    with TestClient(app) as client:
        with client.websocket_connect("/v1/inventory/assistant/ws") as websocket:
            websocket.receive_json()
            websocket.send_json({"type": "transcript.partial", "payload": {"text": "create a new"}})

            echo = websocket.receive_json()

    assert echo == {
        "type": "transcript.echo",
        "payload": {"kind": "partial", "text": "create a new"},
    }


def test_inventory_assistant_websocket_returns_interpreted_command(monkeypatch):
    async def fake_interpret_inventory_command(**kwargs):  # noqa: ARG001
        return inventory_assistant.InventoryAssistantInterpretation(
            command=inventory_assistant.InventoryAssistantCommandPatch(
                kind="create_product",
                query=None,
                value=None,
                productId=None,
                productName=None,
                name="Linen tote",
                price=31.0,
                stock=8,
                category="Fashion",
                unitCode="EA",
                isVisible=True,
                unresolvedReason=None,
            )
        )

    monkeypatch.setattr(
        inventory_assistant,
        "interpret_inventory_command",
        fake_interpret_inventory_command,
    )
    monkeypatch.setattr(
        "app.api.routes.orders.interpret_inventory_command", fake_interpret_inventory_command
    )

    with TestClient(app) as client:
        with client.websocket_connect("/v1/inventory/assistant/ws") as websocket:
            websocket.receive_json()
            websocket.send_json(
                {
                    "type": "session.start",
                    "payload": {
                        "products": [
                            {
                                "id": "1",
                                "name": "Ceramic mug",
                                "category": "Handcrafted",
                                "stock": 12,
                            }
                        ],
                        "categories": ["Fashion", "Handcrafted", "Others"],
                        "filters": {"query": "", "inStockOnly": False},
                    },
                }
            )
            websocket.receive_json()
            websocket.send_json(
                {
                    "type": "transcript.final",
                    "payload": {"text": "create a new linen tote for 31 dollars with 8 in stock"},
                }
            )

            echo = websocket.receive_json()
            command = websocket.receive_json()

    assert echo == {
        "type": "transcript.echo",
        "payload": {
            "kind": "final",
            "text": "create a new linen tote for 31 dollars with 8 in stock",
        },
    }
    assert command == {
        "type": "assistant.command",
        "payload": {
            "command": {
                "kind": "create_product",
                "query": None,
                "value": None,
                "productId": None,
                "productName": None,
                "name": "Linen tote",
                "price": 31.0,
                "stock": 8,
                "category": "Fashion",
                "unitCode": "EA",
                "isVisible": True,
                "unresolvedReason": None,
            },
            "message": None,
        },
    }

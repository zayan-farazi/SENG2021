from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app
from app.services import documents_assistant


def test_documents_assistant_websocket_connects_and_returns_ready_state():
    with TestClient(app) as client:
        with client.websocket_connect("/v1/order/documents/assistant/ws") as websocket:
            message = websocket.receive_json()

    assert message == {"type": "session.ready", "payload": {"currentPartial": ""}}


def test_documents_assistant_websocket_echoes_partial_transcripts():
    with TestClient(app) as client:
        with client.websocket_connect("/v1/order/documents/assistant/ws") as websocket:
            websocket.receive_json()
            websocket.send_json({"type": "transcript.partial", "payload": {"text": "mark invoice"}})

            echo = websocket.receive_json()

    assert echo == {
        "type": "transcript.echo",
        "payload": {"kind": "partial", "text": "mark invoice"},
    }


def test_documents_assistant_websocket_returns_interpreted_command(monkeypatch):
    async def fake_interpret_documents_command(**kwargs):  # noqa: ARG001
        return documents_assistant.DocumentsAssistantInterpretation(
            command=documents_assistant.DocumentsAssistantCommandPatch(
                kind="set_invoice_status",
                status="paid",
                paymentDate="2026-04-22",
                unresolvedReason=None,
            )
        )

    monkeypatch.setattr(
        documents_assistant,
        "interpret_documents_command",
        fake_interpret_documents_command,
    )
    monkeypatch.setattr(
        "app.api.routes.orders.interpret_documents_command", fake_interpret_documents_command
    )

    with TestClient(app) as client:
        with client.websocket_connect("/v1/order/documents/assistant/ws") as websocket:
            websocket.receive_json()
            websocket.send_json(
                {
                    "type": "session.start",
                    "payload": {
                        "orderId": "ord_123",
                        "hasDespatch": False,
                        "hasInvoice": True,
                        "invoiceStatus": "sent",
                        "viewerIsSeller": True,
                    },
                }
            )
            websocket.receive_json()
            websocket.send_json(
                {
                    "type": "transcript.final",
                    "payload": {"text": "mark the invoice as paid today"},
                }
            )

            echo = websocket.receive_json()
            command = websocket.receive_json()

    assert echo == {
        "type": "transcript.echo",
        "payload": {
            "kind": "final",
            "text": "mark the invoice as paid today",
        },
    }
    assert command == {
        "type": "assistant.command",
        "payload": {
            "command": {
                "kind": "set_invoice_status",
                "status": "paid",
                "paymentDate": "2026-04-22",
                "unresolvedReason": None,
            },
            "message": None,
        },
    }


def test_documents_assistant_websocket_supports_copy_invoice_xml_command(monkeypatch):
    async def fake_interpret_documents_command(**kwargs):  # noqa: ARG001
        return documents_assistant.DocumentsAssistantInterpretation(
            command=documents_assistant.DocumentsAssistantCommandPatch(
                kind="copy_invoice_xml",
                status=None,
                paymentDate=None,
                unresolvedReason=None,
            )
        )

    monkeypatch.setattr(
        documents_assistant,
        "interpret_documents_command",
        fake_interpret_documents_command,
    )
    monkeypatch.setattr(
        "app.api.routes.orders.interpret_documents_command", fake_interpret_documents_command
    )

    with TestClient(app) as client:
        with client.websocket_connect("/v1/order/documents/assistant/ws") as websocket:
            websocket.receive_json()
            websocket.send_json(
                {
                    "type": "transcript.final",
                    "payload": {"text": "copy the invoice xml"},
                }
            )

            echo = websocket.receive_json()
            command = websocket.receive_json()

    assert echo == {
        "type": "transcript.echo",
        "payload": {
            "kind": "final",
            "text": "copy the invoice xml",
        },
    }
    assert command == {
        "type": "assistant.command",
        "payload": {
            "command": {
                "kind": "copy_invoice_xml",
                "status": None,
                "paymentDate": None,
                "unresolvedReason": None,
            },
            "message": None,
        },
    }

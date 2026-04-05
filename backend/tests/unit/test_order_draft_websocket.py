from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.api.routes import orders
from app.main import app
from app.services import groq_order_extractor, order_store
from app.services.order_draft import (
    HostedDeliveryFieldUpdates,
    HostedFieldUpdates,
    HostedLineAction,
    HostedTranscriptInterpretation,
    HostedTranscriptPatch,
)


def build_patch(
    *,
    buyer_email: str | None = None,
    buyer_name: str | None = None,
    seller_email: str | None = None,
    seller_name: str | None = None,
    currency: str | None = None,
    issue_date: str | None = None,
    line_actions: list[HostedLineAction] | None = None,
    unresolved_reason: str | None = None,
) -> HostedTranscriptPatch:
    return HostedTranscriptPatch(
        fieldUpdates=HostedFieldUpdates(
            buyerEmail=buyer_email,
            buyerName=buyer_name,
            sellerEmail=seller_email,
            sellerName=seller_name,
            currency=currency,
            issueDate=issue_date,
            notes=None,
            delivery=HostedDeliveryFieldUpdates(
                street=None,
                city=None,
                state=None,
                postcode=None,
                country=None,
                requestedDate=None,
            ),
        ),
        lineActions=line_actions or [],
        warnings=[],
        unresolvedReason=unresolved_reason,
    )


@pytest.fixture(autouse=True)
def stub_order_persistence(monkeypatch):
    monkeypatch.setattr(order_store, "persist_order_to_database", lambda req: 123)
    monkeypatch.setattr(
        order_store,
        "persist_order_runtime_metadata_to_database",
        lambda *args, **kwargs: None,
    )


def test_websocket_connects_and_returns_initial_session_state():
    with TestClient(app) as client:
        with client.websocket_connect("/v1/order/draft/ws") as websocket:
            message = websocket.receive_json()

    assert message["type"] == "session.ready"
    assert message["payload"]["draft"]["lines"] == []
    assert message["payload"]["connectionStatus"] == "connected"


def test_partial_transcript_echoes_without_mutating_the_draft():
    with TestClient(app) as client:
        with client.websocket_connect("/v1/order/draft/ws") as websocket:
            websocket.receive_json()
            websocket.send_json({"type": "transcript.partial", "payload": {"text": "i want 2"}})

            echo = websocket.receive_json()

    assert echo == {
        "type": "transcript.echo",
        "payload": {"kind": "partial", "text": "i want 2"},
    }


def test_final_transcript_updates_draft_state_from_hosted_parser(monkeypatch):
    async def fake_extract(draft, transcript_log, transcript):  # noqa: ARG001
        return HostedTranscriptInterpretation(
            patch=build_patch(
                buyer_name="James",
                seller_name="Grocery Store",
                line_actions=[
                    HostedLineAction(
                        action="upsert",
                        productName="oranges",
                        quantity=4,
                        unitCode="EA",
                        unitPrice="4.00",
                    )
                ],
            )
        )

    monkeypatch.setattr(groq_order_extractor, "extract_transcript_patch", fake_extract)

    with TestClient(app) as client:
        with client.websocket_connect("/v1/order/draft/ws") as websocket:
            websocket.receive_json()
            websocket.send_json(
                {"type": "transcript.final", "payload": {"text": "James wants four oranges"}}
            )

            echo = websocket.receive_json()
            update = websocket.receive_json()

    assert echo == {
        "type": "transcript.echo",
        "payload": {"kind": "final", "text": "James wants four oranges"},
    }
    assert update["type"] == "draft.updated"
    assert update["payload"]["state"]["draft"]["buyerName"] == "James"
    assert update["payload"]["state"]["draft"]["sellerName"] == "Grocery Store"
    assert update["payload"]["state"]["draft"]["lines"] == [
        {"productName": "oranges", "quantity": 4, "unitCode": "EA", "unitPrice": "4.00"}
    ]


def test_final_transcript_preserves_draft_when_hosted_parser_fails(monkeypatch):
    async def fake_extract(draft, transcript_log, transcript):  # noqa: ARG001
        return HostedTranscriptInterpretation(
            warning_message="Transcript could not be interpreted by the hosted parser.",
            unresolved_reason="Transcript could not be interpreted by the hosted parser.",
        )

    monkeypatch.setattr(groq_order_extractor, "extract_transcript_patch", fake_extract)

    with TestClient(app) as client:
        with client.websocket_connect("/v1/order/draft/ws") as websocket:
            websocket.receive_json()
            websocket.send_json(
                {
                    "type": "transcript.final",
                    "payload": {"text": "today's date is the eighth of march 2026"},
                }
            )

            websocket.receive_json()
            update = websocket.receive_json()

    assert update["payload"]["state"]["draft"]["buyerName"] is None
    assert update["payload"]["state"]["warnings"] == [
        {
            "transcript": "today's date is the eighth of march 2026",
            "message": "Transcript could not be interpreted by the hosted parser.",
        }
    ]
    assert update["payload"]["state"]["unresolved"] == [
        {
            "transcript": "today's date is the eighth of march 2026",
            "message": "Transcript could not be interpreted by the hosted parser.",
        }
    ]


def test_manual_draft_patch_merges_and_returns_updated_state():
    with TestClient(app) as client:
        with client.websocket_connect("/v1/order/draft/ws") as websocket:
            websocket.receive_json()
            websocket.send_json(
                {
                    "type": "draft.patch",
                    "payload": {
                        "draft": {
                            "buyerName": "Acme Books",
                            "delivery": {"city": "Sydney"},
                        }
                    },
                }
            )

            update = websocket.receive_json()

    assert update["type"] == "draft.updated"
    assert update["payload"]["state"]["draft"]["buyerName"] == "Acme Books"
    assert update["payload"]["state"]["draft"]["delivery"]["city"] == "Sydney"


def test_commit_is_blocked_when_required_fields_are_missing():
    with TestClient(app) as client:
        with client.websocket_connect("/v1/order/draft/ws") as websocket:
            websocket.receive_json()
            websocket.send_json({"type": "session.commit", "payload": {}})

            blocked = websocket.receive_json()

    assert blocked["type"] == "commit.blocked"
    assert [error["loc"] for error in blocked["payload"]["errors"]] == [
        ["buyerEmail"],
        ["buyerName"],
        ["sellerEmail"],
        ["sellerName"],
        ["lines"],
    ]


def test_commit_succeeds_when_draft_is_valid(monkeypatch):
    print("HELLOO")

    def mock_get_email(raw_key):
        print(f"Mock get_current_party_email called with: {raw_key}")
        return "buyer@example.com"

    monkeypatch.setattr(orders, "get_current_party_email", mock_get_email)

    monkeypatch.setattr(
        orders, "resolve_party_from_app_key", lambda raw_key: ["buyer@example.com", "Buyer Company"]
    )

    with TestClient(app) as client:
        with client.websocket_connect("/v1/order/draft/ws") as websocket:
            websocket.receive_json()  # session.ready
            websocket.send_json(
                {
                    "type": "session.start",
                    "payload": {
                        "draft": {
                            "buyerEmail": "buyer@example.com",
                            "buyerName": "Acme Books",
                            "sellerEmail": "seller@example.com",
                            "sellerName": "Digital Book Supply",
                            "lines": [{"productName": "oranges", "quantity": 4, "unitCode": "EA"}],
                        }
                    },
                }
            )
            websocket.receive_json()  # draft.updated
            websocket.send_json(
                {"type": "session.commit", "payload": {"appKey": "appkey_test_value"}}
            )
            created = websocket.receive_json()

    assert created["type"] == "order.created"
    assert created["payload"]["order"]["status"] == "DRAFT"
    assert created["payload"]["order"]["orderId"].startswith("ord_")


def test_commit_requires_app_key_when_draft_is_valid():
    with TestClient(app) as client:
        with client.websocket_connect("/v1/order/draft/ws") as websocket:
            websocket.receive_json()
            websocket.send_json(
                {
                    "type": "session.start",
                    "payload": {
                        "draft": {
                            "buyerEmail": "buyer@example.com",
                            "buyerName": "Acme Books",
                            "sellerEmail": "seller@example.com",
                            "sellerName": "Digital Book Supply",
                            "lines": [{"productName": "oranges", "quantity": 4, "unitCode": "EA"}],
                        }
                    },
                }
            )
            websocket.receive_json()
            websocket.send_json({"type": "session.commit", "payload": {}})

            error = websocket.receive_json()

    assert error == {
        "type": "error",
        "payload": {
            "code": "unauthorized",
            "message": "session.commit requires a valid appKey.",
        },
    }


def test_reset_clears_session_state():
    with TestClient(app) as client:
        with client.websocket_connect("/v1/order/draft/ws") as websocket:
            websocket.receive_json()
            websocket.send_json(
                {
                    "type": "draft.patch",
                    "payload": {
                        "draft": {
                            "buyerName": "Acme Books",
                            "lines": [{"productName": "oranges", "quantity": 2, "unitCode": "EA"}],
                        }
                    },
                }
            )
            websocket.receive_json()
            websocket.send_json({"type": "session.reset", "payload": {}})

            update = websocket.receive_json()

    assert update["type"] == "draft.updated"
    assert update["payload"]["state"]["draft"]["lines"] == []
    assert update["payload"]["state"]["transcriptLog"] == []
    assert update["payload"]["state"]["warnings"] == []
    assert update["payload"]["state"]["unresolved"] == []

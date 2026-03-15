from __future__ import annotations

from time import time_ns

import pytest

from app.services import groq_order_extractor, order_store
from app.services.order_draft import (
    HostedDeliveryFieldUpdates,
    HostedFieldUpdates,
    HostedLineAction,
    HostedTranscriptInterpretation,
    HostedTranscriptPatch,
)

pytestmark = pytest.mark.integration


def _tag() -> str:
    return str(time_ns())


def _auth_headers(app_key: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {app_key}"}


def _register_party(client, tracked, *, name_prefix: str, email_prefix: str, tag: str) -> dict:
    payload = {
        "partyName": f"{name_prefix} {tag}",
        "contactEmail": f"{email_prefix}-{tag}@example.com",
    }
    response = client.post("/v1/parties/register", json=payload)
    assert response.status_code == 201
    body = response.json()
    tracked["party_ids"].append(body["partyId"])
    return {
        "partyName": payload["partyName"],
        "contactEmail": payload["contactEmail"].lower(),
        "appKey": body["appKey"],
    }


def test_transcript_conversion_payload_can_drive_create_and_update(
    integration_client, tracked_supabase_records, monkeypatch
):
    tag = _tag()
    buyer = _register_party(
        integration_client,
        tracked_supabase_records,
        name_prefix="Transcript Buyer",
        email_prefix="transcript-buyer",
        tag=tag,
    )
    seller = _register_party(
        integration_client,
        tracked_supabase_records,
        name_prefix="Transcript Seller",
        email_prefix="transcript-seller",
        tag=tag,
    )

    async def fake_extract(draft, transcript_log, transcript):  # noqa: ARG001
        if "update" in transcript.lower():
            patch = HostedTranscriptPatch(
                fieldUpdates=HostedFieldUpdates(
                    buyerEmail=buyer["contactEmail"],
                    buyerName=buyer["partyName"],
                    sellerEmail=seller["contactEmail"],
                    sellerName=seller["partyName"],
                    currency="AUD",
                    issueDate="2026-03-14",
                    notes=f"Transcript order updated {tag}",
                    delivery=HostedDeliveryFieldUpdates(
                        street="2 Transcript Lane",
                        city="Sydney",
                        state="NSW",
                        postcode="2000",
                        country="AU",
                        requestedDate="2026-03-21",
                    ),
                ),
                lineActions=[
                    HostedLineAction(
                        action="upsert",
                        productName="Oranges",
                        quantity=5,
                        unitCode="EA",
                        unitPrice="4.75",
                    )
                ],
                warnings=[],
                unresolvedReason=None,
            )
        else:
            patch = HostedTranscriptPatch(
                fieldUpdates=HostedFieldUpdates(
                    buyerEmail=buyer["contactEmail"],
                    buyerName=buyer["partyName"],
                    sellerEmail=seller["contactEmail"],
                    sellerName=seller["partyName"],
                    currency="AUD",
                    issueDate="2026-03-14",
                    notes=f"Transcript order {tag}",
                    delivery=HostedDeliveryFieldUpdates(
                        street="1 Transcript Lane",
                        city="Sydney",
                        state="NSW",
                        postcode="2000",
                        country="AU",
                        requestedDate="2026-03-20",
                    ),
                ),
                lineActions=[
                    HostedLineAction(
                        action="upsert",
                        productName="Oranges",
                        quantity=3,
                        unitCode="EA",
                        unitPrice="4.25",
                    )
                ],
                warnings=[],
                unresolvedReason=None,
            )
        return HostedTranscriptInterpretation(patch=patch)

    monkeypatch.setattr(groq_order_extractor, "extract_transcript_patch", fake_extract)

    convert_create = integration_client.post(
        "/v1/orders/convert/transcript",
        json={"transcript": "buyer wants oranges from seller"},
        headers=_auth_headers(buyer["appKey"]),
    )
    assert convert_create.status_code == 200
    payload = convert_create.json()["payload"]
    assert payload["buyerEmail"] == buyer["contactEmail"]

    create_response = integration_client.post(
        "/v1/order/create",
        json=payload,
        headers=_auth_headers(buyer["appKey"]),
    )
    assert create_response.status_code == 201
    order_id = create_response.json()["orderId"]
    tracked_supabase_records["order_ids"].append(order_id)

    order_store.ORDERS.clear()

    convert_update = integration_client.post(
        "/v1/orders/convert/transcript",
        json={"transcript": "update the order to five oranges", "currentPayload": payload},
        headers=_auth_headers(seller["appKey"]),
    )
    assert convert_update.status_code == 200

    update_response = integration_client.put(
        f"/v1/order/{order_id}",
        json=convert_update.json()["payload"],
        headers=_auth_headers(seller["appKey"]),
    )
    assert update_response.status_code == 200
    assert sorted(update_response.json()) == ["orderId", "status", "updatedAt"]

    get_ubl_response = integration_client.get(
        f"/v1/order/{order_id}/ubl",
        headers=_auth_headers(seller["appKey"]),
    )
    assert get_ubl_response.status_code == 200
    assert "updated" in get_ubl_response.text

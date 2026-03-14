from __future__ import annotations

import asyncio
from datetime import date
from decimal import Decimal

from app.models.schemas import Delivery, LineItem, OrderDraft, OrderRequest
from app.services import order_conversion
from app.services.order_draft import (
    HostedDeliveryFieldUpdates,
    HostedFieldUpdates,
    HostedTranscriptInterpretation,
    HostedTranscriptPatch,
)


def build_request() -> OrderRequest:
    return OrderRequest(
        buyerEmail="buyer@example.com",
        buyerName="Buyer Co",
        sellerEmail="seller@example.com",
        sellerName="Seller Co",
        currency="AUD",
        issueDate=date(2026, 3, 14),
        notes="Original notes",
        delivery=Delivery(
            street="1 Main St",
            city="Sydney",
            state="NSW",
            postcode="2000",
            country="AU",
            requestedDate=date(2026, 3, 20),
        ),
        lines=[
            LineItem(
                productName="Apples",
                quantity=2,
                unitCode="EA",
                unitPrice=Decimal("4.00"),
            )
        ],
    )


def test_convert_transcript_to_draft_merges_current_payload(monkeypatch):
    async def fake_extract(draft, transcript_log, transcript):  # noqa: ARG001
        return HostedTranscriptInterpretation(
            patch=HostedTranscriptPatch(
                fieldUpdates=HostedFieldUpdates(
                    buyerEmail=None,
                    buyerName="Updated Buyer",
                    sellerEmail=None,
                    sellerName=None,
                    currency=None,
                    issueDate=None,
                    notes="Updated notes",
                    delivery=HostedDeliveryFieldUpdates(
                        street=None,
                        city=None,
                        state=None,
                        postcode=None,
                        country=None,
                        requestedDate=None,
                    ),
                ),
                lineActions=[],
                warnings=[],
                unresolvedReason=None,
            )
        )

    monkeypatch.setattr(
        order_conversion.groq_order_extractor, "extract_transcript_patch", fake_extract
    )

    result = asyncio.run(
        order_conversion.convert_transcript_to_draft("update buyer", build_request())
    )

    assert result.draft.buyerName == "Updated Buyer"
    assert result.draft.sellerEmail == "seller@example.com"
    assert result.draft.notes == "Updated notes"


def test_convert_csv_to_draft_parses_canonical_template():
    csv_text = """buyerEmail,buyerName,sellerEmail,sellerName,currency,issueDate,notes,deliveryStreet,deliveryCity,deliveryState,deliveryPostcode,deliveryCountry,deliveryRequestedDate,productName,quantity,unitCode,unitPrice
buyer@example.com,Buyer Co,seller@example.com,Seller Co,AUD,2026-03-14,CSV notes,1 Main St,Sydney,NSW,2000,AU,2026-03-20,Oranges,3,EA,4.25
buyer@example.com,Buyer Co,seller@example.com,Seller Co,AUD,2026-03-14,CSV notes,1 Main St,Sydney,NSW,2000,AU,2026-03-20,Apples,2,EA,5.50
"""

    result = order_conversion.convert_csv_to_draft(csv_text, None)

    assert result.issues == []
    assert result.draft.buyerEmail == "buyer@example.com"
    assert result.draft.sellerEmail == "seller@example.com"
    assert result.draft.delivery is not None
    assert len(result.draft.lines) == 2
    assert result.draft.lines[0].productName == "Oranges"


def test_convert_csv_to_draft_reports_conflicting_order_values():
    csv_text = """buyerEmail,buyerName,sellerEmail,sellerName,currency,issueDate,notes,deliveryStreet,deliveryCity,deliveryState,deliveryPostcode,deliveryCountry,deliveryRequestedDate,productName,quantity,unitCode,unitPrice
buyer@example.com,Buyer Co,seller@example.com,Seller Co,AUD,2026-03-14,CSV notes,1 Main St,Sydney,NSW,2000,AU,2026-03-20,Oranges,3,EA,4.25
other@example.com,Buyer Co,seller@example.com,Seller Co,AUD,2026-03-14,CSV notes,1 Main St,Sydney,NSW,2000,AU,2026-03-20,Apples,2,EA,5.50
"""

    result = order_conversion.convert_csv_to_draft(csv_text, None)

    assert any(issue.path == "buyerEmail" for issue in result.issues)


def test_prefill_caller_email_only_fills_single_missing_party():
    draft = OrderDraft(sellerEmail="seller@example.com")

    result = order_conversion.prefill_caller_email(draft, "buyer@example.com")

    assert result.buyerEmail == "buyer@example.com"
    assert result.sellerEmail == "seller@example.com"


def test_prefill_caller_email_does_not_guess_when_both_missing():
    draft = OrderDraft()

    result = order_conversion.prefill_caller_email(draft, "buyer@example.com")

    assert result.buyerEmail is None
    assert result.sellerEmail is None


def test_parse_current_payload_json_accepts_serialized_order_request():
    payload = build_request().model_dump_json()

    parsed = order_conversion.parse_current_payload_json(payload)

    assert parsed is not None
    assert parsed.buyerEmail == "buyer@example.com"

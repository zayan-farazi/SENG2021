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

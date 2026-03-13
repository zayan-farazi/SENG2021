from __future__ import annotations

from datetime import date

from app.models.schemas import DraftLineItem, OrderDraft
from app.services.order_draft import (
    DraftSessionState,
    HostedDeliveryFieldUpdates,
    HostedFieldUpdates,
    HostedLineAction,
    HostedTranscriptInterpretation,
    HostedTranscriptPatch,
    apply_draft_patch,
    apply_transcript_interpretation,
    normalize_product_name,
    validate_draft_for_commit,
)


def build_patch(
    *,
    buyer_name: str | None = None,
    seller_name: str | None = None,
    currency: str | None = None,
    issue_date: str | None = None,
    notes: str | None = None,
    delivery_requested_date: str | None = None,
    delivery_street: str | None = None,
    line_actions: list[HostedLineAction] | None = None,
    warnings: list[str] | None = None,
    unresolved_reason: str | None = None,
) -> HostedTranscriptPatch:
    return HostedTranscriptPatch(
        fieldUpdates=HostedFieldUpdates(
            buyerName=buyer_name,
            sellerName=seller_name,
            currency=currency,
            issueDate=issue_date,
            notes=notes,
            delivery=HostedDeliveryFieldUpdates(
                street=delivery_street,
                city=None,
                state=None,
                postcode=None,
                country=None,
                requestedDate=delivery_requested_date,
            ),
        ),
        lineActions=line_actions or [],
        warnings=warnings or [],
        unresolvedReason=unresolved_reason,
    )


def test_apply_transcript_interpretation_updates_full_order_fields():
    state = DraftSessionState()
    interpretation = HostedTranscriptInterpretation(
        patch=build_patch(
            buyer_name="James",
            seller_name="Grocery Store",
            currency="AUD",
            issue_date="2026-03-08",
            notes="Deliver to the front counter",
            delivery_requested_date="2026-04-04",
            delivery_street="123 Test St",
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

    result = apply_transcript_interpretation(
        state,
        "James would like four oranges from the grocery store",
        interpretation,
    )

    assert result.applied_changes == [
        "Updated buyer name.",
        "Updated seller name.",
        "Set currency to AUD.",
        "Set issue date to 2026-03-08.",
        "Updated order notes.",
        "Updated delivery street.",
        "Updated requested delivery date to 2026-04-04.",
        "Added oranges with quantity 4.",
    ]
    assert state.draft.buyerName == "James"
    assert state.draft.sellerName == "Grocery Store"
    assert state.draft.currency == "AUD"
    assert state.draft.issueDate == date(2026, 3, 8)
    assert state.draft.notes == "Deliver to the front counter"
    assert state.draft.delivery.street == "123 Test St"
    assert state.draft.delivery.requestedDate == date(2026, 4, 4)
    assert state.draft.lines == [
        DraftLineItem(productName="oranges", quantity=4, unitCode="EA", unitPrice="4.00")
    ]


def test_apply_transcript_interpretation_updates_existing_line_item():
    state = DraftSessionState(
        draft=OrderDraft(lines=[DraftLineItem(productName="oranges", quantity=2, unitCode="EA")])
    )
    interpretation = HostedTranscriptInterpretation(
        patch=build_patch(
            line_actions=[
                HostedLineAction(
                    action="upsert",
                    productName="Oranges",
                    quantity=5,
                    unitCode=None,
                    unitPrice="4.50",
                )
            ]
        )
    )

    result = apply_transcript_interpretation(state, "make that five oranges", interpretation)

    assert result.applied_changes == ["Updated Oranges quantity to 5."]
    assert state.draft.lines[0].quantity == 5
    assert str(state.draft.lines[0].unitPrice) == "4.50"


def test_apply_transcript_interpretation_deletes_existing_line_item():
    state = DraftSessionState(
        draft=OrderDraft(lines=[DraftLineItem(productName="oranges", quantity=4, unitCode="EA")])
    )
    interpretation = HostedTranscriptInterpretation(
        patch=build_patch(
            line_actions=[
                HostedLineAction(
                    action="delete",
                    productName="oranges",
                    quantity=None,
                    unitCode=None,
                    unitPrice=None,
                )
            ]
        )
    )

    result = apply_transcript_interpretation(state, "I do not want oranges", interpretation)

    assert result.applied_changes == ["Removed oranges from the draft."]
    assert state.draft.lines == []


def test_apply_transcript_interpretation_warns_when_delete_target_is_missing():
    state = DraftSessionState()
    interpretation = HostedTranscriptInterpretation(
        patch=build_patch(
            line_actions=[
                HostedLineAction(
                    action="delete",
                    productName="oranges",
                    quantity=None,
                    unitCode=None,
                    unitPrice=None,
                )
            ]
        )
    )

    result = apply_transcript_interpretation(state, "I do not want oranges", interpretation)

    assert result.applied_changes == []
    assert result.warnings == [
        {
            "transcript": "I do not want oranges",
            "message": "Could not find an existing line item for oranges.",
        }
    ]


def test_apply_transcript_interpretation_preserves_draft_on_hosted_parser_failure():
    state = DraftSessionState(
        draft=OrderDraft(lines=[DraftLineItem(productName="oranges", quantity=4, unitCode="EA")])
    )
    interpretation = HostedTranscriptInterpretation(
        warning_message="Transcript could not be interpreted by the hosted parser.",
        unresolved_reason="Transcript could not be interpreted by the hosted parser.",
    )

    result = apply_transcript_interpretation(
        state,
        "today's date is the eighth of March 2026",
        interpretation,
    )

    assert result.applied_changes == []
    assert result.warnings == [
        {
            "transcript": "today's date is the eighth of March 2026",
            "message": "Transcript could not be interpreted by the hosted parser.",
        }
    ]
    assert result.unresolved == [
        {
            "transcript": "today's date is the eighth of March 2026",
            "message": "Transcript could not be interpreted by the hosted parser.",
        }
    ]
    assert state.draft.lines == [DraftLineItem(productName="oranges", quantity=4, unitCode="EA")]


def test_normalize_product_name_handles_case_punctuation_and_pluralization():
    assert normalize_product_name("Oranges!!!") == "orange"
    assert normalize_product_name(" APPLES ") == "apple"
    assert normalize_product_name("books") == "book"


def test_apply_draft_patch_merges_nested_fields_and_replaces_lines():
    state = DraftSessionState(
        draft=OrderDraft(
            buyerName="Existing Buyer",
            delivery={"city": "Sydney"},
            lines=[DraftLineItem(productName="oranges", quantity=2, unitCode="EA")],
        )
    )

    apply_draft_patch(
        state,
        {
            "sellerName": "New Seller",
            "delivery": {"street": "123 Test St"},
            "lines": [{"productName": "apples", "quantity": 3, "unitCode": "EA"}],
        },
    )

    assert state.draft.buyerName == "Existing Buyer"
    assert state.draft.sellerName == "New Seller"
    assert state.draft.delivery.city == "Sydney"
    assert state.draft.delivery.street == "123 Test St"
    assert [line.productName for line in state.draft.lines] == ["apples"]


def test_validate_draft_for_commit_reports_missing_required_fields():
    draft = OrderDraft(lines=[DraftLineItem(productName="oranges", unitCode="EA")])

    req, errors = validate_draft_for_commit(draft)

    assert req is None
    assert [error["loc"] for error in errors] == [
        ("buyerId",),
        ("buyerName",),
        ("sellerId",),
        ("sellerName",),
        ("lines", 0, "quantity"),
    ]

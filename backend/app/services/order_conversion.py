from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.models.schemas import OrderDraft, OrderRequest
from app.services import groq_order_extractor
from app.services.order_draft import (
    DraftSessionState,
    apply_transcript_interpretation,
    validate_draft_for_commit,
)


@dataclass
class ConversionIssue:
    path: str
    issue: str
    hint: str


@dataclass
class ConversionResult:
    draft: OrderDraft
    warnings: list[str]
    issues: list[ConversionIssue]


def order_request_to_draft(payload: OrderRequest | None) -> OrderDraft:
    if payload is None:
        return OrderDraft()
    return OrderDraft.model_validate(payload.model_dump(mode="json"))


async def convert_transcript_to_draft(
    transcript: str,
    current_payload: OrderRequest | None,
) -> ConversionResult:
    draft = order_request_to_draft(current_payload)
    state = DraftSessionState(draft=draft)
    interpretation = await groq_order_extractor.extract_transcript_patch(
        state.draft,
        state.transcript_log,
        transcript.strip(),
    )
    mutation = apply_transcript_interpretation(state, transcript, interpretation)

    warnings = [warning["message"] for warning in mutation.warnings]
    issues = [
        ConversionIssue(
            path="transcript",
            issue=unresolved["message"],
            hint="Adjust the transcript or provide currentPayload context.",
        )
        for unresolved in mutation.unresolved
    ]
    return ConversionResult(draft=state.draft, warnings=warnings, issues=issues)


def prefill_caller_email(draft: OrderDraft, current_party_email: str) -> OrderDraft:
    buyer_email = draft.buyerEmail
    seller_email = draft.sellerEmail
    if bool(buyer_email) == bool(seller_email):
        return draft

    if buyer_email is None:
        return draft.model_copy(update={"buyerEmail": current_party_email})
    return draft.model_copy(update={"sellerEmail": current_party_email})


def finalize_payload(draft: OrderDraft) -> tuple[OrderRequest | None, list[dict[str, Any]]]:
    return validate_draft_for_commit(draft)

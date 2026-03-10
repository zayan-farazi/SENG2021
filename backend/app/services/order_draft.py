from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, ValidationError

from app.models.schemas import DraftDelivery, DraftLineItem, OrderDraft, OrderRequest

PUNCTUATION_RE = re.compile(r"[^\w\s]")
WHITESPACE_RE = re.compile(r"\s+")


class HostedDeliveryFieldUpdates(BaseModel):
    model_config = ConfigDict(extra="forbid")

    street: str | None
    city: str | None
    state: str | None
    postcode: str | None
    country: str | None
    requestedDate: str | None


class HostedFieldUpdates(BaseModel):
    model_config = ConfigDict(extra="forbid")

    buyerName: str | None
    sellerName: str | None
    currency: str | None
    issueDate: str | None
    notes: str | None
    delivery: HostedDeliveryFieldUpdates


class HostedLineAction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: Literal["upsert", "delete"]
    productName: str
    quantity: int | None
    unitCode: str | None
    unitPrice: str | None


class HostedTranscriptPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    fieldUpdates: HostedFieldUpdates
    lineActions: list[HostedLineAction]
    warnings: list[str]
    unresolvedReason: str | None


@dataclass
class HostedTranscriptInterpretation:
    patch: HostedTranscriptPatch | None = None
    warning_message: str | None = None
    unresolved_reason: str | None = None


@dataclass
class DraftSessionState:
    draft: OrderDraft = field(default_factory=OrderDraft)
    transcript_log: list[dict[str, str]] = field(default_factory=list)
    warnings: list[dict[str, str]] = field(default_factory=list)
    unresolved: list[dict[str, str]] = field(default_factory=list)
    current_partial: str = ""
    connection_status: str = "connected"


@dataclass
class DraftMutationResult:
    applied_changes: list[str] = field(default_factory=list)
    warnings: list[dict[str, str]] = field(default_factory=list)
    unresolved: list[dict[str, str]] = field(default_factory=list)


def serialize_state(state: DraftSessionState) -> dict[str, Any]:
    return {
        "draft": state.draft.model_dump(mode="json"),
        "transcriptLog": state.transcript_log,
        "warnings": state.warnings,
        "unresolved": state.unresolved,
        "currentPartial": state.current_partial,
        "connectionStatus": state.connection_status,
    }


def reset_state(state: DraftSessionState) -> None:
    state.draft = OrderDraft()
    state.transcript_log.clear()
    state.warnings.clear()
    state.unresolved.clear()
    state.current_partial = ""
    state.connection_status = "connected"


def append_partial_transcript(state: DraftSessionState, text: str) -> None:
    state.current_partial = text.strip()


def apply_draft_patch(state: DraftSessionState, patch: dict[str, Any]) -> list[str]:
    validated_patch = OrderDraft.model_validate(patch)
    merged = _deep_merge(
        state.draft.model_dump(mode="json"),
        validated_patch.model_dump(mode="json", exclude_unset=True),
    )
    state.draft = OrderDraft.model_validate(merged)
    return ["Draft updated from form."]


def apply_transcript_interpretation(
    state: DraftSessionState,
    transcript: str,
    interpretation: HostedTranscriptInterpretation,
) -> DraftMutationResult:
    cleaned = transcript.strip()
    state.current_partial = ""
    state.transcript_log.append({"kind": "final", "text": cleaned})

    warnings: list[dict[str, str]] = []
    unresolved: list[dict[str, str]] = []
    applied_changes: list[str] = []

    if interpretation.warning_message:
        warnings.append(_warning_item(cleaned, interpretation.warning_message))

    if interpretation.patch is None:
        unresolved_reason = (
            interpretation.unresolved_reason
            or "Transcript could not be interpreted by the hosted parser."
        )
        unresolved.append(_unresolved_item(cleaned, unresolved_reason))
        state.warnings.extend(warnings)
        state.unresolved.extend(unresolved)
        return DraftMutationResult(
            applied_changes=applied_changes,
            warnings=warnings,
            unresolved=unresolved,
        )

    for warning in interpretation.patch.warnings:
        warnings.append(_warning_item(cleaned, warning))

    try:
        working_draft = state.draft.model_copy(deep=True)
        field_updates = interpretation.patch.fieldUpdates
        working_draft, field_changes = _apply_field_updates(working_draft, field_updates)
        applied_changes.extend(field_changes)

        working_draft, line_changes, line_warnings = _apply_line_actions(
            working_draft,
            interpretation.patch.lineActions,
            cleaned,
        )
        applied_changes.extend(line_changes)
        warnings.extend(line_warnings)
    except (ValidationError, ValueError):
        warning_message = "Transcript could not be interpreted by the hosted parser."
        warnings.append(_warning_item(cleaned, warning_message))
        unresolved.append(_unresolved_item(cleaned, warning_message))
        state.warnings.extend(warnings)
        state.unresolved.extend(unresolved)
        return DraftMutationResult(
            applied_changes=[],
            warnings=warnings,
            unresolved=unresolved,
        )

    if interpretation.patch.unresolvedReason:
        unresolved.append(_unresolved_item(cleaned, interpretation.patch.unresolvedReason))

    state.draft = working_draft
    state.warnings.extend(warnings)
    state.unresolved.extend(unresolved)
    return DraftMutationResult(
        applied_changes=applied_changes,
        warnings=warnings,
        unresolved=unresolved,
    )


def validate_draft_for_commit(
    draft: OrderDraft,
) -> tuple[OrderRequest | None, list[dict[str, Any]]]:
    try:
        payload = draft.model_dump(mode="python", exclude_none=True)
        return OrderRequest.model_validate(payload), []
    except ValidationError as exc:
        return None, exc.errors()


def normalize_product_name(product_name: str) -> str:
    sanitized = PUNCTUATION_RE.sub(" ", product_name.lower())
    collapsed = WHITESPACE_RE.sub(" ", sanitized).strip()
    parts = [_singularize(part) for part in collapsed.split(" ") if part]
    return " ".join(parts)


def _apply_field_updates(
    draft: OrderDraft,
    field_updates: HostedFieldUpdates,
) -> tuple[OrderDraft, list[str]]:
    applied_changes: list[str] = []
    working_draft = draft

    if field_updates.buyerName:
        working_draft = working_draft.model_copy(
            update={"buyerName": field_updates.buyerName.strip()}
        )
        applied_changes.append("Updated buyer name.")

    if field_updates.sellerName:
        working_draft = working_draft.model_copy(
            update={"sellerName": field_updates.sellerName.strip()}
        )
        applied_changes.append("Updated seller name.")

    if field_updates.currency:
        currency = field_updates.currency.strip().upper()
        working_draft = working_draft.model_copy(update={"currency": currency})
        applied_changes.append(f"Set currency to {currency}.")

    if field_updates.issueDate:
        parsed_issue_date = date.fromisoformat(field_updates.issueDate)
        working_draft = working_draft.model_copy(update={"issueDate": parsed_issue_date})
        applied_changes.append(f"Set issue date to {parsed_issue_date.isoformat()}.")

    if field_updates.notes:
        working_draft = working_draft.model_copy(update={"notes": field_updates.notes.strip()})
        applied_changes.append("Updated order notes.")

    delivery = (
        working_draft.delivery.model_copy(deep=True) if working_draft.delivery else DraftDelivery()
    )
    delivery_changes: list[str] = []
    delivery_updates = field_updates.delivery

    for field_name in ("street", "city", "state", "postcode", "country"):
        value = getattr(delivery_updates, field_name)
        if value:
            delivery = delivery.model_copy(update={field_name: value.strip()})
            delivery_changes.append(f"Updated delivery {field_name}.")

    if delivery_updates.requestedDate:
        parsed_requested_date = date.fromisoformat(delivery_updates.requestedDate)
        delivery = delivery.model_copy(update={"requestedDate": parsed_requested_date})
        delivery_changes.append(
            f"Updated requested delivery date to {parsed_requested_date.isoformat()}."
        )

    if delivery_changes:
        working_draft = working_draft.model_copy(update={"delivery": delivery})
        applied_changes.extend(delivery_changes)

    return working_draft, applied_changes


def _apply_line_actions(
    draft: OrderDraft,
    line_actions: list[HostedLineAction],
    transcript: str,
) -> tuple[OrderDraft, list[str], list[dict[str, str]]]:
    lines = [line.model_copy(deep=True) for line in draft.lines]
    applied_changes: list[str] = []
    warnings: list[dict[str, str]] = []

    for action in line_actions:
        product_name = action.productName.strip()
        normalized_product = normalize_product_name(product_name)

        if action.action == "delete":
            retained_lines = [
                line
                for line in lines
                if not line.productName
                or normalize_product_name(line.productName) != normalized_product
            ]
            if len(retained_lines) == len(lines):
                warnings.append(
                    _warning_item(
                        transcript,
                        f"Could not find an existing line item for {product_name}.",
                    )
                )
                continue

            lines = retained_lines
            applied_changes.append(f"Removed {product_name} from the draft.")
            continue

        patch: dict[str, Any] = {}
        if action.quantity is not None:
            patch["quantity"] = action.quantity
        if action.unitCode is not None:
            patch["unitCode"] = action.unitCode.strip()
        if action.unitPrice is not None:
            patch["unitPrice"] = action.unitPrice.strip()

        line_index = next(
            (
                index
                for index, existing_line in enumerate(lines)
                if existing_line.productName
                and normalize_product_name(existing_line.productName) == normalized_product
            ),
            None,
        )

        if line_index is None:
            if action.quantity is None:
                warnings.append(
                    _warning_item(
                        transcript,
                        f"Could not add {product_name} without a quantity.",
                    )
                )
                continue

            new_line = DraftLineItem(
                productName=product_name,
                quantity=action.quantity,
                unitCode=patch.get("unitCode", "EA"),
                unitPrice=patch.get("unitPrice"),
            )
            lines.append(new_line)
            applied_changes.append(f"Added {product_name} with quantity {action.quantity}.")
            continue

        updated_line = lines[line_index].model_copy(update=patch)
        lines[line_index] = updated_line

        if action.quantity is not None:
            applied_changes.append(f"Updated {product_name} quantity to {action.quantity}.")
        else:
            applied_changes.append(f"Updated {product_name}.")

    return draft.model_copy(update={"lines": lines}), applied_changes, warnings


def _singularize(token: str) -> str:
    if token.endswith("ies") and len(token) > 3:
        return token[:-3] + "y"
    if token.endswith("es") and len(token) > 3:
        singular_candidate = token[:-2]
        if singular_candidate.endswith(("s", "x", "z")) or singular_candidate.endswith(
            ("ch", "sh")
        ):
            return singular_candidate
    if token.endswith("s") and len(token) > 2 and not token.endswith("ss"):
        return token[:-1]
    return token


def _warning_item(transcript: str, message: str) -> dict[str, str]:
    return {"transcript": transcript, "message": message}


def _unresolved_item(transcript: str, message: str) -> dict[str, str]:
    return {"transcript": transcript, "message": message}


def _deep_merge(base: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in patch.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged

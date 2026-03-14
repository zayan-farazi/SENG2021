from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from typing import Any

from pydantic import ValidationError

from app.models.schemas import OrderDraft, OrderRequest
from app.services import groq_order_extractor
from app.services.order_draft import (
    DraftSessionState,
    apply_transcript_interpretation,
    validate_draft_for_commit,
)

CANONICAL_CSV_HEADERS = [
    "buyerEmail",
    "buyerName",
    "sellerEmail",
    "sellerName",
    "currency",
    "issueDate",
    "notes",
    "deliveryStreet",
    "deliveryCity",
    "deliveryState",
    "deliveryPostcode",
    "deliveryCountry",
    "deliveryRequestedDate",
    "productName",
    "quantity",
    "unitCode",
    "unitPrice",
]

_ORDER_FIELD_COLUMN_MAP = {
    "buyerEmail": "buyerEmail",
    "buyerName": "buyerName",
    "sellerEmail": "sellerEmail",
    "sellerName": "sellerName",
    "currency": "currency",
    "issueDate": "issueDate",
    "notes": "notes",
}

_DELIVERY_COLUMN_MAP = {
    "deliveryStreet": "street",
    "deliveryCity": "city",
    "deliveryState": "state",
    "deliveryPostcode": "postcode",
    "deliveryCountry": "country",
    "deliveryRequestedDate": "requestedDate",
}


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


def convert_csv_to_draft(csv_text: str, current_payload: OrderRequest | None) -> ConversionResult:
    draft_data = order_request_to_draft(current_payload).model_dump(mode="json", exclude_none=True)
    issues: list[ConversionIssue] = []
    warnings: list[str] = []

    reader = csv.DictReader(io.StringIO(csv_text))
    actual_headers = reader.fieldnames or []
    missing_headers = [header for header in CANONICAL_CSV_HEADERS if header not in actual_headers]
    if missing_headers:
        return ConversionResult(
            draft=OrderDraft.model_validate(draft_data),
            warnings=[],
            issues=[
                ConversionIssue(
                    path="file",
                    issue=f"CSV is missing required headers: {', '.join(missing_headers)}",
                    hint="Use the documented canonical CSV template.",
                )
            ],
        )

    rows = list(reader)
    if not rows:
        return ConversionResult(
            draft=OrderDraft.model_validate(draft_data),
            warnings=[],
            issues=[
                ConversionIssue(
                    path="file",
                    issue="CSV must contain at least one data row.",
                    hint="Add one row per line item.",
                )
            ],
        )

    for csv_column, order_field in _ORDER_FIELD_COLUMN_MAP.items():
        values = _unique_non_empty(row.get(csv_column) for row in rows)
        if len(values) > 1:
            issues.append(
                ConversionIssue(
                    path=csv_column,
                    issue=f"{csv_column} has conflicting values across rows.",
                    hint="Keep order-level columns identical on every row.",
                )
            )
            continue
        if values:
            draft_data[order_field] = values[0]

    delivery_data = dict(draft_data.get("delivery") or {})
    for csv_column, delivery_field in _DELIVERY_COLUMN_MAP.items():
        values = _unique_non_empty(row.get(csv_column) for row in rows)
        if len(values) > 1:
            issues.append(
                ConversionIssue(
                    path=csv_column,
                    issue=f"{csv_column} has conflicting values across rows.",
                    hint="Keep delivery-level columns identical on every row.",
                )
            )
            continue
        if values:
            delivery_data[delivery_field] = values[0]
    if delivery_data:
        draft_data["delivery"] = delivery_data

    lines = []
    for index, row in enumerate(rows):
        line_payload = {
            "productName": _blank_to_none(row.get("productName")),
            "quantity": _blank_to_none(row.get("quantity")),
            "unitCode": _blank_to_none(row.get("unitCode")),
            "unitPrice": _blank_to_none(row.get("unitPrice")),
        }
        try:
            normalized_line = {
                key: value for key, value in line_payload.items() if value is not None
            }
            lines.append(normalized_line)
            if line_payload["unitPrice"] is None:
                warnings.append(f"lines[{index}].unitPrice is missing")
        except ValidationError:
            issues.append(
                ConversionIssue(
                    path=f"lines[{index}]",
                    issue="CSV row could not be parsed into a line item.",
                    hint="Check productName, quantity, unitCode, and unitPrice values.",
                )
            )
    if lines:
        draft_data["lines"] = lines

    try:
        draft = OrderDraft.model_validate(draft_data)
    except ValidationError as exc:
        issues.extend(_validation_errors_to_conversion_issues(exc.errors()))
        draft = OrderDraft()

    return ConversionResult(draft=draft, warnings=warnings, issues=issues)


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


def parse_current_payload_json(raw_payload: str | None) -> OrderRequest | None:
    if raw_payload is None or not raw_payload.strip():
        return None
    return OrderRequest.model_validate_json(raw_payload)


def _unique_non_empty(values: Any) -> list[str]:
    seen: list[str] = []
    for value in values:
        normalized = _blank_to_none(value)
        if normalized is not None and normalized not in seen:
            seen.append(normalized)
    return seen


def _blank_to_none(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def _validation_errors_to_conversion_issues(errors: list[dict[str, Any]]) -> list[ConversionIssue]:
    issues: list[ConversionIssue] = []
    for error in errors:
        location = error.get("loc", ())
        path = ".".join(str(part) for part in location) if location else "payload"
        issues.append(
            ConversionIssue(
                path=path,
                issue=error.get("msg", "Invalid payload."),
                hint="Provide values that match the order payload schema.",
            )
        )
    return issues

from __future__ import annotations

import json
import os
from typing import Any, Literal

import httpx
from pydantic import BaseModel, ConfigDict

from app.env import load_local_env_files

DEFAULT_GROQ_BASE_URL = "https://api.groq.com/openai/v1"
DEFAULT_GROQ_MODEL = "openai/gpt-oss-20b"
DEFAULT_GROQ_TIMEOUT_SECONDS = 20.0
RECENT_TRANSCRIPT_LIMIT = 3


class DocumentsAssistantCommandPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal[
        "fetch_despatch",
        "generate_despatch",
        "generate_invoice",
        "refresh_invoice",
        "fetch_invoice_xml",
        "download_invoice_pdf",
        "set_invoice_status",
        "delete_invoice",
        "none",
    ]
    status: str | None
    paymentDate: str | None
    unresolvedReason: str | None


class DocumentsAssistantInterpretation(BaseModel):
    command: DocumentsAssistantCommandPatch | None = None
    unresolved_reason: str | None = None
    warning_message: str | None = None


async def interpret_documents_command(
    *,
    transcript: str,
    order_id: str | None,
    has_despatch: bool,
    has_invoice: bool,
    invoice_status: str | None,
    viewer_is_seller: bool,
    transcript_log: list[str],
) -> DocumentsAssistantInterpretation:
    load_local_env_files()
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        return DocumentsAssistantInterpretation(
            unresolved_reason="Hosted documents parsing is not configured.",
            warning_message="Set GROQ_API_KEY to enable natural-language document voice commands.",
        )

    base_url = os.getenv("GROQ_BASE_URL", DEFAULT_GROQ_BASE_URL).rstrip("/")
    model = os.getenv("GROQ_MODEL", DEFAULT_GROQ_MODEL)
    timeout_seconds = _parse_timeout_seconds(os.getenv("GROQ_TIMEOUT_SECONDS"))
    request_body = _build_request_body(
        transcript=transcript,
        order_id=order_id,
        has_despatch=has_despatch,
        has_invoice=has_invoice,
        invoice_status=invoice_status,
        viewer_is_seller=viewer_is_seller,
        transcript_log=transcript_log,
        model=model,
    )

    try:
        async with httpx.AsyncClient(timeout=timeout_seconds) as client:
            response = await client.post(
                f"{base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json=request_body,
            )
    except httpx.HTTPError:
        return DocumentsAssistantInterpretation(
            unresolved_reason="Documents voice interpretation failed.",
            warning_message="Documents voice interpretation failed.",
        )

    if response.status_code >= 400:
        return DocumentsAssistantInterpretation(
            unresolved_reason="Documents voice interpretation failed.",
            warning_message="Documents voice interpretation failed.",
        )

    try:
        payload = response.json()
        message = payload["choices"][0]["message"]["content"]
        parsed_command = DocumentsAssistantCommandPatch.model_validate(json.loads(message))
    except (KeyError, IndexError, TypeError, ValueError):
        return DocumentsAssistantInterpretation(
            unresolved_reason="Documents voice interpretation failed.",
            warning_message="Documents voice interpretation failed.",
        )

    if parsed_command.kind == "none":
        return DocumentsAssistantInterpretation(
            unresolved_reason=parsed_command.unresolvedReason
            or "I could not map that to a document action.",
        )

    if parsed_command.status is not None:
        cleaned_status = parsed_command.status.strip().lower()
        parsed_command.status = cleaned_status or None

    if parsed_command.paymentDate is not None:
        cleaned_payment_date = parsed_command.paymentDate.strip()
        parsed_command.paymentDate = cleaned_payment_date or None

    if parsed_command.kind == "set_invoice_status" and not parsed_command.status:
        return DocumentsAssistantInterpretation(
            unresolved_reason=parsed_command.unresolvedReason
            or "I could not determine the invoice status update.",
        )

    return DocumentsAssistantInterpretation(command=parsed_command)


def _build_request_body(
    *,
    transcript: str,
    order_id: str | None,
    has_despatch: bool,
    has_invoice: bool,
    invoice_status: str | None,
    viewer_is_seller: bool,
    transcript_log: list[str],
    model: str,
) -> dict[str, Any]:
    return {
        "model": model,
        "messages": [
            {"role": "system", "content": _system_prompt()},
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "orderId": order_id,
                        "hasDespatch": has_despatch,
                        "hasInvoice": has_invoice,
                        "invoiceStatus": invoice_status,
                        "viewerIsSeller": viewer_is_seller,
                        "recentFinalTranscripts": transcript_log[-RECENT_TRANSCRIPT_LIMIT:],
                        "latestTranscript": transcript,
                    }
                ),
            },
        ],
        "temperature": 0,
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": "documents_command",
                "strict": True,
                "schema": DocumentsAssistantCommandPatch.model_json_schema(),
            },
        },
    }


def _system_prompt() -> str:
    return """
Convert a locked-order documents transcript into exactly one command.

Rules:
- Return only one command.
- Include every schema field in the response. Use null for fields that do not apply to the chosen command.
- Use `fetch_despatch` when the user wants to load or fetch despatch XML.
- Use `generate_despatch` when the user wants to create or generate a despatch advice.
- Use `generate_invoice` when the user wants to create or generate an invoice.
- Use `refresh_invoice` when the user wants invoice details refreshed or reloaded.
- Use `fetch_invoice_xml` when the user wants invoice XML loaded.
- Use `download_invoice_pdf` when the user wants the invoice PDF downloaded.
- Use `set_invoice_status` when the user wants the invoice marked as sent, paid, overdue, cancelled, or otherwise updated.
- Use `delete_invoice` when the user wants the invoice removed.
- Natural phrases like "mark the invoice as paid", "can you create the invoice now", and "load the despatch advice xml" should map to the matching command.
- If the user mentions a payment date, place it in `paymentDate` using the transcript value when possible.
- Do not invent extra actions.
- If the request is ambiguous or cannot be mapped safely, return kind `none` and set `unresolvedReason`.
""".strip()


def _parse_timeout_seconds(value: str | None) -> float:
    if value is None:
        return DEFAULT_GROQ_TIMEOUT_SECONDS
    try:
        parsed = float(value)
    except ValueError:
        return DEFAULT_GROQ_TIMEOUT_SECONDS
    return parsed if parsed > 0 else DEFAULT_GROQ_TIMEOUT_SECONDS

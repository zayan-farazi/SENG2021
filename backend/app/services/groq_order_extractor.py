from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import httpx

from app.models.schemas import OrderDraft
from app.services.order_draft import HostedTranscriptInterpretation, HostedTranscriptPatch

DEFAULT_GROQ_BASE_URL = "https://api.groq.com/openai/v1"
DEFAULT_GROQ_MODEL = "openai/gpt-oss-20b"
DEFAULT_GROQ_TIMEOUT_SECONDS = 20.0
RECENT_TRANSCRIPT_LIMIT = 2


async def extract_transcript_patch(
    draft: OrderDraft,
    transcript_log: list[dict[str, str]],
    transcript: str,
) -> HostedTranscriptInterpretation:
    _load_local_env_files()
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        return HostedTranscriptInterpretation(
            warning_message="Hosted parser is not configured. Set GROQ_API_KEY to enable transcript parsing.",
            unresolved_reason="Transcript could not be interpreted by the hosted parser.",
        )

    base_url = os.getenv("GROQ_BASE_URL", DEFAULT_GROQ_BASE_URL).rstrip("/")
    model = os.getenv("GROQ_MODEL", DEFAULT_GROQ_MODEL)
    timeout_seconds = float(os.getenv("GROQ_TIMEOUT_SECONDS", DEFAULT_GROQ_TIMEOUT_SECONDS))
    request_body = build_request_body(draft, transcript_log, transcript, model=model)

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
        return HostedTranscriptInterpretation(
            warning_message="Transcript could not be interpreted by the hosted parser.",
            unresolved_reason="Transcript could not be interpreted by the hosted parser.",
        )

    if response.status_code >= 400:
        return HostedTranscriptInterpretation(
            warning_message="Transcript could not be interpreted by the hosted parser.",
            unresolved_reason="Transcript could not be interpreted by the hosted parser.",
        )

    try:
        payload = response.json()
        message = payload["choices"][0]["message"]["content"]
        parsed_patch = HostedTranscriptPatch.model_validate(json.loads(message))
    except (KeyError, IndexError, TypeError, ValueError):
        return HostedTranscriptInterpretation(
            warning_message="Transcript could not be interpreted by the hosted parser.",
            unresolved_reason="Transcript could not be interpreted by the hosted parser.",
        )

    return HostedTranscriptInterpretation(
        patch=parsed_patch,
        unresolved_reason=parsed_patch.unresolvedReason,
    )


def build_request_body(
    draft: OrderDraft,
    transcript_log: list[dict[str, str]],
    transcript: str,
    *,
    model: str,
) -> dict[str, Any]:
    context_payload = build_compact_context_payload(draft, transcript_log, transcript)
    return {
        "model": model,
        "messages": [
            {"role": "system", "content": _system_prompt()},
            {"role": "user", "content": json.dumps(context_payload)},
        ],
        "temperature": 0,
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": "order_patch",
                "strict": True,
                "schema": HostedTranscriptPatch.model_json_schema(),
            },
        },
    }


def build_compact_context_payload(
    draft: OrderDraft,
    transcript_log: list[dict[str, str]],
    transcript: str,
) -> dict[str, Any]:
    return {
        "currentDraft": compact_draft_context(draft),
        "recentFinalTranscripts": select_recent_transcripts(transcript_log),
        "latestTranscript": transcript,
    }


def compact_draft_context(draft: OrderDraft) -> dict[str, Any]:
    compact: dict[str, Any] = {}

    for field_name in ("buyerName", "sellerName", "currency", "issueDate", "notes"):
        value = getattr(draft, field_name)
        if value is not None:
            compact[field_name] = value.isoformat() if hasattr(value, "isoformat") else value

    if draft.delivery:
        compact_delivery = {
            field_name: (value.isoformat() if hasattr(value, "isoformat") else value)
            for field_name in ("street", "city", "state", "postcode", "country", "requestedDate")
            if (value := getattr(draft.delivery, field_name)) is not None
        }
        if compact_delivery:
            compact["delivery"] = compact_delivery

    compact_lines = []
    for line in draft.lines:
        compact_line = {
            field_name: (str(value) if field_name == "unitPrice" else value)
            for field_name in ("productName", "quantity", "unitCode", "unitPrice")
            if (value := getattr(line, field_name)) is not None
        }
        if compact_line:
            compact_lines.append(compact_line)
    if compact_lines:
        compact["lines"] = compact_lines

    return compact


def select_recent_transcripts(transcript_log: list[dict[str, str]]) -> list[dict[str, str]]:
    finals = [entry for entry in transcript_log if entry.get("kind") == "final"]
    return finals[-RECENT_TRANSCRIPT_LIMIT:]


def measure_context_payload_sizes(
    draft: OrderDraft,
    transcript_log: list[dict[str, str]],
    transcript: str,
) -> dict[str, int]:
    full_payload = {
        "currentDraft": draft.model_dump(mode="json"),
        "recentFinalTranscripts": transcript_log[-6:],
        "latestTranscript": transcript,
    }
    compact_payload = build_compact_context_payload(draft, transcript_log, transcript)
    return {
        "full": len(json.dumps(full_payload)),
        "compact": len(json.dumps(compact_payload)),
    }


def _system_prompt() -> str:
    return """
Convert ordering transcripts into a JSON patch for the current order draft.

Rules:
- Return only changes to apply to the current draft.
- Use null for untouched scalar fields.
- delivery must include all keys, using null for untouched values.
- lineActions may add, update, or delete items in order.
- Use ISO dates for issueDate and requestedDate.
- Use uppercase 3-letter currency codes.
- Use plain numeric strings for unitPrice such as "4.00".
- If the user says they do not want an item, emit a delete action.
- If nothing can be safely applied, leave updates empty and set unresolvedReason.
- Put ambiguity in warnings.
""".strip()


def _load_local_env_files() -> None:
    for env_file in _candidate_env_files():
        if not env_file.is_file():
            continue
        for line in env_file.read_text(encoding="utf-8").splitlines():
            key, value = _parse_env_line(line)
            if key and value is not None:
                os.environ.setdefault(key, value)


def _candidate_env_files() -> list[Path]:
    backend_dir = Path(__file__).resolve().parents[2]
    repo_root = backend_dir.parent
    return [
        backend_dir / ".env",
        backend_dir / ".env.local",
        repo_root / ".env",
        repo_root / ".env.local",
    ]


def _parse_env_line(line: str) -> tuple[str | None, str | None]:
    stripped = line.strip()
    if not stripped or stripped.startswith("#"):
        return None, None

    if stripped.startswith("export "):
        stripped = stripped.removeprefix("export ").strip()

    if "=" not in stripped:
        return None, None

    key, raw_value = stripped.split("=", 1)
    key = key.strip()
    value = raw_value.strip()
    if not key:
        return None, None

    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        value = value[1:-1]

    return key, value

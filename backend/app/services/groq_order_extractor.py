from __future__ import annotations

import json
import os
from pathlib import Path

import httpx

from app.models.schemas import OrderDraft
from app.services.order_draft import HostedTranscriptInterpretation, HostedTranscriptPatch

DEFAULT_GROQ_BASE_URL = "https://api.groq.com/openai/v1"
DEFAULT_GROQ_MODEL = "openai/gpt-oss-20b"
DEFAULT_GROQ_TIMEOUT_SECONDS = 20.0


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

    request_body = {
        "model": model,
        "messages": [
            {"role": "system", "content": _system_prompt()},
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "currentDraft": draft.model_dump(mode="json"),
                        "recentFinalTranscripts": transcript_log[-6:],
                        "latestTranscript": transcript,
                    }
                ),
            },
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


def _system_prompt() -> str:
    return """
You convert conversational ordering transcripts into structured JSON patches for an order draft.

Rules:
- Return only data that should change in the current draft.
- Use null for untouched scalar fields.
- delivery must always be present with all keys, using null for untouched values.
- lineActions must contain ordered upsert/delete actions.
- Use ISO dates (YYYY-MM-DD) for issueDate and requestedDate.
- Use uppercase 3-letter currency codes when present.
- Use plain numeric strings for unitPrice, for example "4.00".
- If the transcript expresses deletion such as "I don't want oranges", emit a delete action.
- If nothing can be safely applied, leave field updates null/empty and set unresolvedReason.
- warnings should contain any ambiguity the UI should surface.
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

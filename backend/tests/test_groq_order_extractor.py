from __future__ import annotations

import asyncio
import json

import httpx

from app.models.schemas import OrderDraft
from app.services import groq_order_extractor


def test_extract_transcript_patch_returns_warning_when_api_key_is_missing(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.setattr(groq_order_extractor, "_candidate_env_files", lambda: [])

    result = asyncio.run(
        groq_order_extractor.extract_transcript_patch(OrderDraft(), [], "hello world")
    )

    assert result.patch is None
    assert (
        result.warning_message
        == "Hosted parser is not configured. Set GROQ_API_KEY to enable transcript parsing."
    )
    assert result.unresolved_reason == "Transcript could not be interpreted by the hosted parser."


def test_extract_transcript_patch_parses_valid_structured_response(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "test-key")

    async def fake_post(self, url, *, headers, json):  # noqa: ARG001
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": """
                            {
                              "fieldUpdates": {
                                "buyerName": "James",
                                "sellerName": "Grocery Store",
                                "currency": "AUD",
                                "issueDate": "2026-03-08",
                                "notes": null,
                                "delivery": {
                                  "street": null,
                                  "city": null,
                                  "state": null,
                                  "postcode": null,
                                  "country": null,
                                  "requestedDate": null
                                }
                              },
                              "lineActions": [
                                {
                                  "action": "upsert",
                                  "productName": "oranges",
                                  "quantity": 4,
                                  "unitCode": "EA",
                                  "unitPrice": "4.00"
                                }
                              ],
                              "warnings": [],
                              "unresolvedReason": null
                            }
                            """
                        }
                    }
                ]
            },
        )

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)

    result = asyncio.run(
        groq_order_extractor.extract_transcript_patch(
            OrderDraft(),
            [{"kind": "final", "text": "hello"}],
            "James would like four oranges from the grocery store",
        )
    )

    assert result.patch is not None
    assert result.patch.fieldUpdates.buyerName == "James"
    assert result.patch.fieldUpdates.currency == "AUD"
    assert result.patch.lineActions[0].productName == "oranges"
    assert result.patch.lineActions[0].unitPrice == "4.00"


def test_extract_transcript_patch_loads_api_key_from_env_file(monkeypatch, tmp_path):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    env_file = tmp_path / ".env"
    env_file.write_text('GROQ_API_KEY="file-key"\n', encoding="utf-8")
    monkeypatch.setattr(groq_order_extractor, "_candidate_env_files", lambda: [env_file])
    seen_headers = {}

    async def fake_post(self, url, *, headers, json):  # noqa: ARG001
        seen_headers.update(headers)
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": json_module.dumps(
                                {
                                    "fieldUpdates": {
                                        "buyerName": "Zion",
                                        "sellerName": None,
                                        "currency": None,
                                        "issueDate": None,
                                        "notes": None,
                                        "delivery": {
                                            "street": None,
                                            "city": None,
                                            "state": None,
                                            "postcode": None,
                                            "country": None,
                                            "requestedDate": None,
                                        },
                                    },
                                    "lineActions": [],
                                    "warnings": [],
                                    "unresolvedReason": None,
                                }
                            )
                        }
                    }
                ]
            },
        )

    json_module = json
    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)

    result = asyncio.run(
        groq_order_extractor.extract_transcript_patch(OrderDraft(), [], "my name is Zion")
    )

    assert result.patch is not None
    assert seen_headers["Authorization"] == "Bearer file-key"


def test_extract_transcript_patch_returns_warning_when_response_is_malformed(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "test-key")

    async def fake_post(self, url, *, headers, json):  # noqa: ARG001
        return httpx.Response(200, json={"choices": [{"message": {"content": "{not-json}"}}]})

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)

    result = asyncio.run(
        groq_order_extractor.extract_transcript_patch(OrderDraft(), [], "hello world")
    )

    assert result.patch is None
    assert result.warning_message == "Transcript could not be interpreted by the hosted parser."


def test_extract_transcript_patch_returns_warning_when_request_fails(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "test-key")

    async def fake_post(self, url, *, headers, json):  # noqa: ARG001
        raise httpx.ConnectError("boom")

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)

    result = asyncio.run(
        groq_order_extractor.extract_transcript_patch(OrderDraft(), [], "hello world")
    )

    assert result.patch is None
    assert result.warning_message == "Transcript could not be interpreted by the hosted parser."

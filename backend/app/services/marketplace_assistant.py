from __future__ import annotations

import json
import os
from typing import Any, Literal

import httpx
from pydantic import BaseModel, ConfigDict, Field

from app.env import load_local_env_files

DEFAULT_GROQ_BASE_URL = "https://api.groq.com/openai/v1"
DEFAULT_GROQ_MODEL = "openai/gpt-oss-20b"
DEFAULT_GROQ_TIMEOUT_SECONDS = 20.0
RECENT_TRANSCRIPT_LIMIT = 3


class MarketplaceAssistantProduct(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    seller: str
    category: str
    stock: int = Field(ge=0)


class MarketplaceAssistantCartLine(BaseModel):
    model_config = ConfigDict(extra="forbid")

    productId: str
    name: str
    quantity: int = Field(ge=0)


class MarketplaceAssistantFilterState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str = ""
    category: str = "All"
    inStockOnly: bool = False


class MarketplaceAssistantCommandPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal[
        "search",
        "clear_search",
        "set_category",
        "set_in_stock",
        "go_to_checkout",
        "change_quantity",
        "remove_product",
        "none",
    ]
    query: str | None
    category: str | None
    value: bool | None
    productId: str | None
    quantityDelta: int | None
    unresolvedReason: str | None


class MarketplaceAssistantInterpretation(BaseModel):
    command: MarketplaceAssistantCommandPatch | None = None
    unresolved_reason: str | None = None
    warning_message: str | None = None


async def interpret_marketplace_command(
    *,
    transcript: str,
    products: list[MarketplaceAssistantProduct],
    categories: list[str],
    filters: MarketplaceAssistantFilterState,
    cart_lines: list[MarketplaceAssistantCartLine],
    transcript_log: list[str],
) -> MarketplaceAssistantInterpretation:
    load_local_env_files()
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        return MarketplaceAssistantInterpretation(
            unresolved_reason="Hosted marketplace parsing is not configured.",
            warning_message="Set GROQ_API_KEY to enable natural-language marketplace voice commands.",
        )

    base_url = os.getenv("GROQ_BASE_URL", DEFAULT_GROQ_BASE_URL).rstrip("/")
    model = os.getenv("GROQ_MODEL", DEFAULT_GROQ_MODEL)
    timeout_seconds = _parse_timeout_seconds(os.getenv("GROQ_TIMEOUT_SECONDS"))
    request_body = _build_request_body(
        transcript=transcript,
        products=products,
        categories=categories,
        filters=filters,
        cart_lines=cart_lines,
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
        return MarketplaceAssistantInterpretation(
            unresolved_reason="Marketplace voice interpretation failed.",
            warning_message="Marketplace voice interpretation failed.",
        )

    if response.status_code >= 400:
        return MarketplaceAssistantInterpretation(
            unresolved_reason="Marketplace voice interpretation failed.",
            warning_message="Marketplace voice interpretation failed.",
        )

    try:
        payload = response.json()
        message = payload["choices"][0]["message"]["content"]
        parsed_command = MarketplaceAssistantCommandPatch.model_validate(json.loads(message))
    except (KeyError, IndexError, TypeError, ValueError):
        return MarketplaceAssistantInterpretation(
            unresolved_reason="Marketplace voice interpretation failed.",
            warning_message="Marketplace voice interpretation failed.",
        )

    if parsed_command.kind == "none":
        return MarketplaceAssistantInterpretation(
            unresolved_reason=parsed_command.unresolvedReason
            or "I could not map that to a marketplace action.",
        )

    valid_product_ids = {product.id for product in products}
    valid_categories = {category for category in categories}

    if parsed_command.kind in {"change_quantity", "remove_product"}:
        if not parsed_command.productId or parsed_command.productId not in valid_product_ids:
            return MarketplaceAssistantInterpretation(
                unresolved_reason=parsed_command.unresolvedReason
                or "I could not map that to a marketplace product.",
            )

    if parsed_command.kind == "change_quantity":
        if parsed_command.quantityDelta is None or parsed_command.quantityDelta == 0:
            return MarketplaceAssistantInterpretation(
                unresolved_reason=parsed_command.unresolvedReason
                or "I could not determine the requested quantity.",
            )

    if parsed_command.kind == "set_category":
        if not parsed_command.category or parsed_command.category not in valid_categories:
            return MarketplaceAssistantInterpretation(
                unresolved_reason=parsed_command.unresolvedReason
                or "I could not map that to a marketplace category.",
            )

    if parsed_command.kind == "search" and not parsed_command.query:
        return MarketplaceAssistantInterpretation(
            unresolved_reason=parsed_command.unresolvedReason
            or "I could not determine what to search for.",
        )

    if parsed_command.kind == "set_in_stock" and parsed_command.value is None:
        return MarketplaceAssistantInterpretation(
            unresolved_reason=parsed_command.unresolvedReason
            or "I could not determine the stock filter state.",
        )

    return MarketplaceAssistantInterpretation(command=parsed_command)


def _build_request_body(
    *,
    transcript: str,
    products: list[MarketplaceAssistantProduct],
    categories: list[str],
    filters: MarketplaceAssistantFilterState,
    cart_lines: list[MarketplaceAssistantCartLine],
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
                        "products": [
                            {
                                "id": product.id,
                                "name": product.name,
                                "seller": product.seller,
                                "category": product.category,
                                "stock": product.stock,
                            }
                            for product in products
                        ],
                        "categories": categories,
                        "currentFilters": filters.model_dump(mode="json"),
                        "currentCart": [line.model_dump(mode="json") for line in cart_lines],
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
                "name": "marketplace_command",
                "strict": True,
                "schema": MarketplaceAssistantCommandPatch.model_json_schema(),
            },
        },
    }


def _system_prompt() -> str:
    return """
Convert a marketplace shopping transcript into exactly one command.

Rules:
- Return only one command.
- Include every schema field in the response. Use null for fields that do not apply to the chosen command.
- Use `search` when the user wants to search listings or sellers.
- Use `set_category` when the user wants a category such as Fashion or Homeware.
- Use `set_in_stock` when the user wants to show only in-stock items or all stock states.
- Use `go_to_checkout` when the user wants to review the cart or move to checkout.
- Use `change_quantity` when the user wants to add or remove a quantity of a specific product.
- Use `remove_product` when the user wants the whole product removed from the cart.
- Natural shopping phrases like "I would like three ceramic mugs" or "can I get two candles" should map to `change_quantity`.
- Use the provided product ids only. Do not invent products or categories.
- `quantityDelta` must be positive for adding and negative for reducing.
- If the request is ambiguous or cannot be mapped safely, return kind `none` and set `unresolvedReason`.
- Keep search queries concise. Keep categories exactly as provided.
""".strip()


def _parse_timeout_seconds(value: str | None) -> float:
    if value is None:
        return DEFAULT_GROQ_TIMEOUT_SECONDS
    try:
        parsed = float(value)
    except ValueError:
        return DEFAULT_GROQ_TIMEOUT_SECONDS
    return parsed if parsed > 0 else DEFAULT_GROQ_TIMEOUT_SECONDS

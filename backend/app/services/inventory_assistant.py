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


class InventoryAssistantProduct(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    category: str
    stock: int = Field(ge=0)


class InventoryAssistantFilterState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str = ""
    inStockOnly: bool = False


class InventoryAssistantCommandPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal[
        "search",
        "clear_search",
        "set_in_stock",
        "create_product",
        "delete_product",
        "none",
    ]
    query: str | None
    value: bool | None
    productId: str | None
    productName: str | None
    name: str | None
    price: float | None
    stock: int | None
    category: str | None
    unitCode: str | None
    isVisible: bool | None
    unresolvedReason: str | None


class InventoryAssistantInterpretation(BaseModel):
    command: InventoryAssistantCommandPatch | None = None
    unresolved_reason: str | None = None
    warning_message: str | None = None


async def interpret_inventory_command(
    *,
    transcript: str,
    products: list[InventoryAssistantProduct],
    categories: list[str],
    filters: InventoryAssistantFilterState,
    transcript_log: list[str],
) -> InventoryAssistantInterpretation:
    load_local_env_files()
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        return InventoryAssistantInterpretation(
            unresolved_reason="Hosted inventory parsing is not configured.",
            warning_message="Set GROQ_API_KEY to enable natural-language inventory voice commands.",
        )

    base_url = os.getenv("GROQ_BASE_URL", DEFAULT_GROQ_BASE_URL).rstrip("/")
    model = os.getenv("GROQ_MODEL", DEFAULT_GROQ_MODEL)
    timeout_seconds = _parse_timeout_seconds(os.getenv("GROQ_TIMEOUT_SECONDS"))
    request_body = _build_request_body(
        transcript=transcript,
        products=products,
        categories=categories,
        filters=filters,
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
        return InventoryAssistantInterpretation(
            unresolved_reason="Inventory voice interpretation failed.",
            warning_message="Inventory voice interpretation failed.",
        )

    if response.status_code >= 400:
        return InventoryAssistantInterpretation(
            unresolved_reason="Inventory voice interpretation failed.",
            warning_message="Inventory voice interpretation failed.",
        )

    try:
        payload = response.json()
        message = payload["choices"][0]["message"]["content"]
        parsed_command = InventoryAssistantCommandPatch.model_validate(json.loads(message))
    except (KeyError, IndexError, TypeError, ValueError):
        return InventoryAssistantInterpretation(
            unresolved_reason="Inventory voice interpretation failed.",
            warning_message="Inventory voice interpretation failed.",
        )

    if parsed_command.kind == "none":
        return InventoryAssistantInterpretation(
            unresolved_reason=parsed_command.unresolvedReason
            or "I could not map that to an inventory action.",
        )

    valid_product_ids = {product.id for product in products}
    valid_categories = {category for category in categories}

    if parsed_command.kind == "delete_product":
        if not parsed_command.productId or parsed_command.productId not in valid_product_ids:
            return InventoryAssistantInterpretation(
                unresolved_reason=parsed_command.unresolvedReason
                or "I could not map that to an inventory item.",
            )
        if not parsed_command.productName:
            matched_product = next(
                (product for product in products if product.id == parsed_command.productId),
                None,
            )
            parsed_command.productName = matched_product.name if matched_product else None

    if parsed_command.kind == "search" and not parsed_command.query:
        return InventoryAssistantInterpretation(
            unresolved_reason=parsed_command.unresolvedReason
            or "I could not determine what to search for.",
        )

    if parsed_command.kind == "set_in_stock" and parsed_command.value is None:
        return InventoryAssistantInterpretation(
            unresolved_reason=parsed_command.unresolvedReason
            or "I could not determine the stock filter state.",
        )

    if parsed_command.kind == "create_product":
        if not parsed_command.name:
            return InventoryAssistantInterpretation(
                unresolved_reason=parsed_command.unresolvedReason
                or "I could not determine the product name.",
            )
        if parsed_command.price is None or parsed_command.price < 0:
            return InventoryAssistantInterpretation(
                unresolved_reason=parsed_command.unresolvedReason
                or "I could not determine the product price.",
            )
        if parsed_command.stock is None or parsed_command.stock < 0:
            return InventoryAssistantInterpretation(
                unresolved_reason=parsed_command.unresolvedReason
                or "I could not determine the available stock.",
            )
        if not parsed_command.category or parsed_command.category not in valid_categories:
            return InventoryAssistantInterpretation(
                unresolved_reason=parsed_command.unresolvedReason
                or "I could not map that to an inventory category.",
            )
        if not parsed_command.unitCode:
            parsed_command.unitCode = "EA"
        if parsed_command.isVisible is None:
            parsed_command.isVisible = True

    return InventoryAssistantInterpretation(command=parsed_command)


def _build_request_body(
    *,
    transcript: str,
    products: list[InventoryAssistantProduct],
    categories: list[str],
    filters: InventoryAssistantFilterState,
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
                        "products": [product.model_dump(mode="json") for product in products],
                        "categories": categories,
                        "currentFilters": filters.model_dump(mode="json"),
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
                "name": "inventory_command",
                "strict": True,
                "schema": InventoryAssistantCommandPatch.model_json_schema(),
            },
        },
    }


def _system_prompt() -> str:
    return """
Convert an inventory-management transcript into exactly one command.

Rules:
- Return only one command.
- Include every schema field in the response. Use null for fields that do not apply to the chosen command.
- Use `search` when the user wants to search inventory items.
- Use `clear_search` when the user wants to clear the search.
- Use `set_in_stock` when the user wants to show only in-stock items or all stock states.
- Use `create_product` when the user wants to create a new inventory listing.
- Use `delete_product` when the user wants to remove an existing inventory item.
- Natural phrases like "create a new linen tote for 31 dollars with 8 in stock" should map to `create_product`.
- Infer `unitCode` as `EA` unless the user says otherwise.
- Infer `isVisible` as true unless the user explicitly asks for a draft, hidden, or private listing.
- Use the provided product ids and categories only. Do not invent categories.
- For create requests, require a usable name, price, stock count, and category. If any are too ambiguous, return kind `none`.
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

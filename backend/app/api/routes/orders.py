from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import ValidationError

from app.models.schemas import Issue, OrderRequest, Severity, ValidationResponse
from app.services import groq_order_extractor, order_store
from app.services.app_key_auth import get_current_party_id
from app.services.order_draft import (
    DraftSessionState,
    append_partial_transcript,
    apply_draft_patch,
    apply_transcript_interpretation,
    reset_state,
    serialize_state,
    validate_draft_for_commit,
)
from app.services.order_store import (
    OrderConflictLockedError,
    OrderNotFoundError,
    OrderPersistenceError,
)
from app.services.ubl_order import OrderGenerationError

# from other import findOrders, saveOrder, saveOrderDetails, DBInfo

router = APIRouter()
logger = logging.getLogger(__name__)
ORDERS = order_store.ORDERS


@router.post("/v1/order/create", status_code=201)
def create_order(req: OrderRequest, current_party_id: str = Depends(get_current_party_id)):
    _assert_party_access(current_party_id, req.buyerId, req.sellerId)

    validation = _validate_order(req)

    if not validation.valid:
        raise HTTPException(
        status_code=400,
        detail=[i.model_dump() for i in validation.issues],
    )

    try:
        record = order_store.create_order_record(req)
    except OrderGenerationError as exc:
        logger.exception("Order creation failed")
        raise HTTPException(status_code=500, detail="Unable to create order.") from exc
    except OrderPersistenceError as exc:
        logger.exception("Order persistence verification failed")
        raise HTTPException(status_code=500, detail="Unable to persist order.") from exc

    record["warnings"] = [w.model_dump() for w in validation.warnings]
    return order_store.build_order_response(record)


@router.delete("/v1/order/{order_id}", status_code=204)
def delete_order(order_id: str, current_party_id: str = Depends(get_current_party_id)):
    existing = ORDERS.get(order_id)
    if existing is None:
        raise HTTPException(status_code=404, detail="Not Found")

    payload = existing.get("payload", {})
    _assert_order_access(current_party_id, payload)

    try:
        deleted = order_store.delete_order_record(order_id)
    except OrderPersistenceError as exc:
        logger.exception("Order delete failed")
        raise HTTPException(status_code=500, detail="Unable to delete order.") from exc

    if not deleted:
        raise HTTPException(status_code=404, detail="Not Found")


@router.websocket("/v1/order/draft/ws")
async def order_draft_session(websocket: WebSocket):
    await websocket.accept()
    state = DraftSessionState()
    await websocket.send_json({"type": "session.ready", "payload": serialize_state(state)})

    try:
        while True:
            message = await websocket.receive_json()
            if not isinstance(message, dict):
                await _send_error(
                    websocket, "invalid_message", "WebSocket messages must be JSON objects."
                )
                continue

            event_type = message.get("type")
            payload = message.get("payload") or {}

            if not isinstance(payload, dict):
                await _send_error(
                    websocket, "invalid_payload", "Event payloads must be JSON objects."
                )
                continue

            if event_type == "session.start":
                await _handle_session_start(websocket, state, payload)
            elif event_type == "transcript.partial":
                await _handle_partial_transcript(websocket, state, payload)
            elif event_type == "transcript.final":
                await _handle_final_transcript(websocket, state, payload)
            elif event_type == "draft.patch":
                await _handle_draft_patch(websocket, state, payload)
            elif event_type == "session.commit":
                await _handle_commit(websocket, state)
            elif event_type == "session.reset":
                reset_state(state)
                await _send_draft_update(websocket, state, ["Draft reset."])
            else:
                await _send_error(
                    websocket, "unknown_event", f"Unsupported event type: {event_type}"
                )
    except WebSocketDisconnect:
        logger.info("Draft session disconnected")


async def _handle_session_start(
    websocket: WebSocket,
    state: DraftSessionState,
    payload: dict[str, Any],
):
    draft_payload = payload.get("draft")
    if draft_payload is None:
        await _send_draft_update(websocket, state, ["Draft session started."])
        return

    if not isinstance(draft_payload, dict):
        await _send_error(websocket, "invalid_draft", "Draft payload must be a JSON object.")
        return

    try:
        applied_changes = apply_draft_patch(state, draft_payload)
    except ValidationError as exc:
        await _send_error(
            websocket, "invalid_draft", "Draft payload failed validation.", exc.errors()
        )
        return

    await _send_draft_update(websocket, state, applied_changes)


async def _handle_partial_transcript(
    websocket: WebSocket,
    state: DraftSessionState,
    payload: dict[str, Any],
):
    text = payload.get("text")
    if not isinstance(text, str):
        await _send_error(
            websocket, "invalid_transcript", "Partial transcript text must be a string."
        )
        return

    append_partial_transcript(state, text)
    await websocket.send_json(
        {
            "type": "transcript.echo",
            "payload": {"kind": "partial", "text": state.current_partial},
        }
    )


async def _handle_final_transcript(
    websocket: WebSocket,
    state: DraftSessionState,
    payload: dict[str, Any],
):
    text = payload.get("text")
    if not isinstance(text, str):
        await _send_error(
            websocket, "invalid_transcript", "Final transcript text must be a string."
        )
        return

    cleaned = text.strip()
    await websocket.send_json(
        {"type": "transcript.echo", "payload": {"kind": "final", "text": cleaned}}
    )
    interpretation = await groq_order_extractor.extract_transcript_patch(
        state.draft,
        state.transcript_log,
        cleaned,
    )
    result = apply_transcript_interpretation(state, cleaned, interpretation)
    await _send_draft_update(websocket, state, result.applied_changes)


async def _handle_draft_patch(
    websocket: WebSocket,
    state: DraftSessionState,
    payload: dict[str, Any],
):
    draft_payload = payload.get("draft")
    if not isinstance(draft_payload, dict):
        await _send_error(websocket, "invalid_draft", "Draft payload must be a JSON object.")
        return

    try:
        applied_changes = apply_draft_patch(state, draft_payload)
    except ValidationError as exc:
        await _send_error(
            websocket, "invalid_draft", "Draft payload failed validation.", exc.errors()
        )
        return

    await _send_draft_update(websocket, state, applied_changes)


async def _handle_commit(websocket: WebSocket, state: DraftSessionState):
    req, errors = validate_draft_for_commit(state.draft)
    if req is None:
        await websocket.send_json(
            {
                "type": "commit.blocked",
                "payload": {"errors": errors, "state": serialize_state(state)},
            }
        )
        return

    try:
        record = order_store.create_order_record(req)
    except OrderGenerationError:
        logger.exception("WebSocket order creation failed")
        await _send_error(websocket, "order_creation_failed", "Unable to create order.")
        return
    except OrderPersistenceError:
        logger.exception("WebSocket order persistence failed")
        await _send_error(websocket, "order_persistence_failed", "Unable to persist order.")
        return

    await websocket.send_json(
        {
            "type": "order.created",
            "payload": {
                "order": order_store.build_order_response(record),
                "state": serialize_state(state),
            },
        }
    )


async def _send_draft_update(
    websocket: WebSocket,
    state: DraftSessionState,
    applied_changes: list[str],
):
    await websocket.send_json(
        {
            "type": "draft.updated",
            "payload": {"state": serialize_state(state), "appliedChanges": applied_changes},
        }
    )


async def _send_error(
    websocket: WebSocket,
    code: str,
    message: str,
    details: Any | None = None,
):
    payload = {"code": code, "message": message}
    if details is not None:
        payload["details"] = details
    await websocket.send_json({"type": "error", "payload": payload})


@router.get("/v1/order/{order_id}")
def get_order(order_id: str, current_party_id: str = Depends(get_current_party_id)):
    order = ORDERS.get(order_id)

    if order is None:
        raise HTTPException(status_code=404, detail="Not Found")

    payload = order.get("payload", {})
    _assert_order_access(current_party_id, payload)

    if not order.get("ublXml"):
        raise HTTPException(status_code=500, detail="Order XML missing.")

    return {
        "orderId": order["orderId"],
        "status": order["status"],
        "createdAt": order["createdAt"],
        "updatedAt": order["updatedAt"],
        "ublXml": order["ublXml"],
        "warnings": order["warnings"],
    }


@router.put("/v1/order/{order_id}")
def update_order(
    order_id: str, req: OrderRequest, current_party_id: str = Depends(get_current_party_id)
):
    existing = ORDERS.get(order_id)
    if existing is None:
        raise HTTPException(status_code=404, detail="Not Found")

    payload = existing.get("payload", {})
    _assert_order_access(current_party_id, payload)
    if req.buyerId != payload.get("buyerId") or req.sellerId != payload.get("sellerId"):
        raise HTTPException(status_code=409, detail="Order parties cannot be changed.")
    
    validation = _validate_order(req)

    if not validation.valid:
        raise HTTPException(
            status_code=400,
            detail=[i.model_dump() for i in validation.issues],
        )

    try:
        record = order_store.update_order_record(order_id, req)

    except OrderNotFoundError as exc:
        # Order could not be found with order_id
        raise HTTPException(status_code=404, detail="Not Found") from exc

    except OrderConflictLockedError as exc:
        # Order is not in an editable status
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    except OrderGenerationError as exc:
        logger.exception("Order update failed")
        raise HTTPException(status_code=500, detail="Unable to update order.") from exc

    except OrderPersistenceError as exc:
        logger.exception("Order update persistence verification failed")
        raise HTTPException(status_code=500, detail="Unable to persist updated order.") from exc

    record["warnings"] = [w.model_dump() for w in validation.warnings]
    return {
        "orderId": record["orderId"],
        "status": record["status"],
        "updatedAt": record["updatedAt"],
        "ublXml": record["ublXml"],
        "warnings": record["warnings"],
    }


def _assert_order_access(current_party_id: str, payload: dict[str, Any]) -> None:
    buyer_id = payload.get("buyerId")
    seller_id = payload.get("sellerId")
    if not isinstance(buyer_id, str) or not isinstance(seller_id, str):
        raise HTTPException(status_code=500, detail="Order party information missing.")

    _assert_party_access(current_party_id, buyer_id, seller_id)


def _assert_party_access(current_party_id: str, buyer_id: str, seller_id: str) -> None:
    if current_party_id not in {buyer_id, seller_id}:
        raise HTTPException(status_code=403, detail="Forbidden")


def _validate_buyer_seller(order: OrderRequest, issues: list[Issue]) -> None:
    if not order.buyerId:
        issues.append(
            Issue(
                path="buyerId",
                issue="buyerId is required",
                severity=Severity.error,
                hint="Provide a valid buyer party ID.",
            )
        )
    if not order.buyerName:
        issues.append(
            Issue(
                path="buyerName",
                issue="buyerName is required",
                severity=Severity.error,
                hint="Provide the full name or company name of the buyer.",
            )
        )
    if not order.sellerId:
        issues.append(
            Issue(
                path="sellerId",
                issue="sellerId is required",
                severity=Severity.error,
                hint="Provide a valid seller party ID.",
            )
        )
    if not order.sellerName:
        issues.append(
            Issue(
                path="sellerName",
                issue="sellerName is required",
                severity=Severity.error,
                hint="Provide the full name or company name of the seller.",
            )
        )


def _validate_lines(order: OrderRequest, issues: list[Issue], warnings: list[Issue]) -> None:
    for i, line in enumerate(order.lines):
        if not line.productName:
            issues.append(
                Issue(
                    path=f"lines[{i}].productName",
                    issue="productName is required",
                    severity=Severity.error,
                    hint="Provide a product or service name for this line.",
                )
            )
        if line.unitPrice is None:
            warnings.append(
                Issue(
                    path=f"lines[{i}].unitPrice",
                    issue="unitPrice is missing",
                    severity=Severity.warning,
                    hint="Provide a unit price so the order total can be calculated.",
                )
            )
        if line.unitCode is None:
            warnings.append(
                Issue(
                    path=f"lines[{i}].unitCode",
                    issue="unitCode is missing",
                    severity=Severity.warning,
                    hint="unitCode defaults to 'EA' (each) if not provided.",
                )
            )


def _validate_delivery(order: OrderRequest, issues: list[Issue], warnings: list[Issue]) -> None:
    if order.delivery is None:
        warnings.append(
            Issue(
                path="delivery",
                issue="delivery is missing",
                severity=Severity.warning,
                hint="Provide a delivery object if physical shipment is required.",
            )
        )
        return

    for field in ("street", "city", "country"):
        if not getattr(order.delivery, field):
            warnings.append(
                Issue(
                    path=f"delivery.{field}",
                    issue=f"delivery.{field} is required",
                    severity=Severity.warning,
                    hint=f"Provide a value for delivery.{field}.",
                )
            )

    if not order.delivery.postcode:
        warnings.append(
            Issue(
                path="delivery.postcode",
                issue="delivery.postcode is missing",
                severity=Severity.warning,
                hint="Postcode improves delivery accuracy and may be required by some carriers.",
            )
        )
    if not order.delivery.state:
        warnings.append(
            Issue(
                path="delivery.state",
                issue="delivery.state is missing",
                severity=Severity.warning,
                hint="State/province may be required for certain countries.",
            )
        )


def _validate_currency(order: OrderRequest, warnings: list[Issue]) -> None:
    if order.currency is None:
        warnings.append(
            Issue(
                path="currency",
                issue="currency is required",
                severity=Severity.warning,
                hint="Use an ISO 4217 currency code, e.g. 'AUD'.",
            )
        )


def _validate_dates(order: OrderRequest, warnings: list[Issue]) -> None:
    if order.issueDate is None:
        warnings.append(
            Issue(
                path="issueDate",
                issue="issueDate is missing",
                severity=Severity.warning,
                hint="Provide an issue date for the order.",
            )
        )
    if order.delivery and order.delivery.requestedDate is None:
        warnings.append(
            Issue(
                path="delivery.requestedDate",
                issue="delivery.requestedDate is missing",
                severity=Severity.warning,
                hint="Provide a requested delivery date.",
            )
        )


def _validate_order(order: OrderRequest) -> ValidationResponse:
    issues: list[Issue] = []
    warnings: list[Issue] = []

    _validate_buyer_seller(order, issues)
    _validate_lines(order, issues, warnings)
    _validate_delivery(order, issues, warnings)
    _validate_currency(order, warnings)
    _validate_dates(order, warnings)

    fields = [
        order.buyerId,
        order.buyerName,
        order.sellerId,
        order.sellerName,
        order.currency,
        order.issueDate,
        order.delivery,
        order.lines,
    ]
    score = round(sum(bool(f) for f in fields) / len(fields), 2)

    return ValidationResponse(
        valid=len(issues) == 0,
        issues=issues,
        warnings=warnings,
        score=score,
    )


@router.post("/v1/orders/validate")
async def validate_order(order: OrderRequest, current_party_id: str = Depends(get_current_party_id)) -> ValidationResponse:
    return _validate_order(order)

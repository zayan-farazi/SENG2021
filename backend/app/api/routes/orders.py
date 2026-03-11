from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import ValidationError

from app.models.schemas import OrderRequest
from app.services import groq_order_extractor, order_store
from app.services.order_draft import (
    DraftSessionState,
    append_partial_transcript,
    apply_draft_patch,
    apply_transcript_interpretation,
    reset_state,
    serialize_state,
    validate_draft_for_commit,
)
from app.services.order_store import OrderPersistenceError
from app.services.ubl_order import OrderGenerationError

# from other import findOrders, saveOrder, saveOrderDetails, DBInfo

router = APIRouter()
logger = logging.getLogger(__name__)
ORDERS = order_store.ORDERS


@router.post("/v1/order/create", status_code=201)
def create_order(req: OrderRequest):
    try:
        record = order_store.create_order_record(req)
    except OrderGenerationError as exc:
        logger.exception("Order creation failed")
        raise HTTPException(status_code=500, detail="Unable to create order.") from exc
    except OrderPersistenceError as exc:
        logger.exception("Order persistence verification failed")
        raise HTTPException(status_code=500, detail="Unable to persist order.") from exc

    return order_store.build_order_response(record)


@router.delete("/v1/order/{order_id}", status_code=204)
def delete_order(order_id: str):
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
def get_order(order_id: str):
    order = ORDERS.get(order_id)

    if order is None:
        raise HTTPException(status_code=404, detail="Not Found")

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

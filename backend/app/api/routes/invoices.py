import logging

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response

from app.integrations import lastminutepush_client
from app.integrations.lastminutepush_client import InvoiceServiceError
from app.services import order_store
from app.services.app_key_auth import get_current_party_email
from app.services.invoice_mapping import order_to_invoice_create_request

router = APIRouter(tags=["Invoices"])
logger = logging.getLogger(__name__)


def _assert_invoice_access(current_party_email: str, payload: dict) -> None:
    """Only allow buyer or seller on the order to generate/fetch invoice artifacts."""
    caller = current_party_email.strip().lower()
    buyer = str(payload.get("buyerEmail", "")).strip().lower()
    seller = str(payload.get("sellerEmail", "")).strip().lower()
    if not buyer or not seller:
        raise HTTPException(status_code=500, detail="Order participant email information missing.")
    if caller not in {buyer, seller}:
        raise HTTPException(status_code=403, detail="Forbidden")


def _invoice_service_detail(reason: str) -> str:
    if reason == "auth":
        return "Invoice service rejected the API key."
    if reason == "payload":
        return "Invoice service rejected the payload."
    if reason == "misconfigured":
        return "Invoice service is not configured."
    if reason == "unavailable":
        return "Invoice service is unavailable."
    return "Invoice service failed."


def _log_invoice_service_failure(operation: str, exc: InvoiceServiceError) -> None:
    details = []
    if exc.status_code is not None:
        details.append(f"status={exc.status_code}")
    if exc.response_body:
        details.append(f"body={exc.response_body}")
    suffix = f" ({', '.join(details)})" if details else ""
    logger.warning(
        "Invoice integration failed during %s: reason=%s%s", operation, exc.reason, suffix
    )


def _raise_invoice_http_error(operation: str, exc: InvoiceServiceError) -> None:
    _log_invoice_service_failure(operation, exc)
    raise HTTPException(status_code=502, detail=_invoice_service_detail(exc.reason)) from exc


@router.post("/v1/order/{order_id}/invoice")
async def generate_invoice_for_order(
    order_id: str,
    current_party_email: str = Depends(get_current_party_email),
):
    order = order_store.get_order_record(order_id)
    if order is None:
        raise HTTPException(status_code=404, detail="Not Found")

    payload = order.get("payload", {})
    _assert_invoice_access(current_party_email, payload)

    for i, line in enumerate(payload.get("lines", [])):
        if line.get("unitPrice") is None:
            raise HTTPException(
                status_code=400,
                detail=[
                    {
                        "path": f"lines[{i}].unitPrice",
                        "issue": "unitPrice is required to generate an invoice.",
                    }
                ],
            )

    invoice_payload = order_to_invoice_create_request(order_id, payload)

    try:
        created = await lastminutepush_client.create_invoice(invoice_payload)
    except InvoiceServiceError as exc:
        _raise_invoice_http_error("create", exc)
    except Exception as exc:
        logger.exception("Unexpected invoice integration failure during create")
        raise HTTPException(status_code=502, detail="Invoice service failed.") from exc

    return {"orderId": order_id, "invoice": created}


@router.get("/v1/invoice/{invoice_id}")
async def fetch_invoice(
    invoice_id: str,
    current_party_email: str = Depends(get_current_party_email),  # noqa: ARG001
):
    try:
        return await lastminutepush_client.get_invoice(invoice_id)
    except InvoiceServiceError as exc:
        _raise_invoice_http_error("fetch", exc)
    except Exception as exc:
        logger.exception("Unexpected invoice integration failure during fetch")
        raise HTTPException(status_code=502, detail="Invoice service failed.") from exc


@router.get("/v1/invoice/{invoice_id}/ubl")
async def fetch_invoice_ubl(
    invoice_id: str,
    current_party_email: str = Depends(get_current_party_email),  # noqa: ARG001
):
    try:
        xml = await lastminutepush_client.get_invoice_ubl_xml(invoice_id)
    except InvoiceServiceError as exc:
        _raise_invoice_http_error("fetch_ubl", exc)
    except Exception as exc:
        logger.exception("Unexpected invoice integration failure during fetch_ubl")
        raise HTTPException(status_code=502, detail="Invoice service failed.") from exc
    return Response(content=xml, media_type="application/xml")


@router.get("/v1/invoice/{invoice_id}/pdf")
async def fetch_invoice_pdf(
    invoice_id: str,
    current_party_email: str = Depends(get_current_party_email),  # noqa: ARG001
):
    try:
        pdf_bytes = await lastminutepush_client.get_invoice_pdf(invoice_id)
    except InvoiceServiceError as exc:
        _raise_invoice_http_error("fetch_pdf", exc)
    except Exception as exc:
        logger.exception("Unexpected invoice integration failure during fetch_pdf")
        raise HTTPException(status_code=502, detail="Invoice service failed.") from exc
    return Response(content=pdf_bytes, media_type="application/pdf")


@router.put("/v1/invoice/{invoice_id}")
async def update_invoice(
    invoice_id: str,
    body: dict,
    current_party_email: str = Depends(get_current_party_email),  # noqa: ARG001
):
    try:
        return await lastminutepush_client.update_invoice(invoice_id, body)
    except InvoiceServiceError as exc:
        _raise_invoice_http_error("update", exc)
    except Exception as exc:
        logger.exception("Unexpected invoice integration failure during update")
        raise HTTPException(status_code=502, detail="Invoice service failed.") from exc


@router.delete("/v1/invoice/{invoice_id}", status_code=204)
async def delete_invoice(
    invoice_id: str,
    current_party_email: str = Depends(get_current_party_email),  # noqa: ARG001
):
    try:
        await lastminutepush_client.delete_invoice(invoice_id)
    except InvoiceServiceError as exc:
        _raise_invoice_http_error("delete", exc)
    except Exception as exc:
        logger.exception("Unexpected invoice integration failure during delete")
        raise HTTPException(status_code=502, detail="Invoice service failed.") from exc
    return Response(status_code=204)


@router.post("/v1/invoice/{invoice_id}/status")
async def transition_invoice_status(
    invoice_id: str,
    body: dict,
    current_party_email: str = Depends(get_current_party_email),  # noqa: ARG001
):
    try:
        return await lastminutepush_client.transition_invoice_status(invoice_id, body)
    except InvoiceServiceError as exc:
        _raise_invoice_http_error("transition_status", exc)
    except Exception as exc:
        logger.exception("Unexpected invoice integration failure during transition_status")
        raise HTTPException(status_code=502, detail="Invoice service failed.") from exc

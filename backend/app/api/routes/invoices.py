from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response

from app.integrations import lastminutepush_client
from app.services import order_store
from app.services.app_key_auth import get_current_party_email
from app.services.invoice_mapping import order_to_invoice_create_request

router = APIRouter(tags=["Invoices"])


def _assert_invoice_access(current_party_email: str, payload: dict) -> None:
    """Only allow buyer or seller on the order to generate/fetch invoice artifacts."""
    caller = current_party_email.strip().lower()
    buyer = str(payload.get("buyerEmail", "")).strip().lower()
    seller = str(payload.get("sellerEmail", "")).strip().lower()
    if not buyer or not seller:
        raise HTTPException(status_code=500, detail="Order participant email information missing.")
    if caller not in {buyer, seller}:
        raise HTTPException(status_code=403, detail="Forbidden")


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
    except Exception as exc:
        raise HTTPException(status_code=502, detail="Invoice service failed.") from exc

    return {"orderId": order_id, "invoice": created}


@router.get("/v1/invoice/{invoice_id}")
async def fetch_invoice(invoice_id: str, _=Depends(get_current_party_email)):
    return await lastminutepush_client.get_invoice(invoice_id)


@router.get("/v1/invoice/{invoice_id}/ubl")
async def fetch_invoice_ubl(invoice_id: str, _=Depends(get_current_party_email)):
    xml = await lastminutepush_client.get_invoice_ubl_xml(invoice_id)
    return Response(content=xml, media_type="application/xml")


@router.get("/v1/invoice/{invoice_id}/pdf")
async def fetch_invoice_pdf(invoice_id: str, _=Depends(get_current_party_email)):
    pdf_bytes = await lastminutepush_client.get_invoice_pdf(invoice_id)
    return Response(content=pdf_bytes, media_type="application/pdf")

@router.put("/v1/invoice/{invoice_id}")
async def update_invoice(invoice_id: str, body: dict, _=Depends(get_current_party_email)):
    """
    Proxy update to LastMinutePush.
    We keep it as dict for MVP so we don't have to replicate their schema in ours.
    """
    try:
        return await lastminutepush_client.update_invoice(invoice_id, body)
    except Exception as exc:
        raise HTTPException(status_code=502, detail="Invoice service failed.") from exc


@router.delete("/v1/invoice/{invoice_id}", status_code=204)
async def delete_invoice(invoice_id: str, _=Depends(get_current_party_email)):
    try:
        await lastminutepush_client.delete_invoice(invoice_id)
    except Exception as exc:
        raise HTTPException(status_code=502, detail="Invoice service failed.") from exc
    return Response(status_code=204)


@router.post("/v1/invoice/{invoice_id}/status")
async def transition_invoice_status(invoice_id: str, body: dict, _=Depends(get_current_party_email)):
    """
    body examples:
      {"status": "sent"}
      {"status": "paid", "payment_date": "2026-03-16"}
    """
    try:
        return await lastminutepush_client.transition_invoice_status(invoice_id, body)
    except Exception as exc:
        raise HTTPException(status_code=502, detail="Invoice service failed.") from exc
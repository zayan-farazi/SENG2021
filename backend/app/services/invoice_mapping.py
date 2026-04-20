from datetime import date
from typing import Any

def order_to_invoice_create_request(order_id: str, order_payload: dict[str, Any]) -> dict[str, Any]:
    issue_date = order_payload.get("issueDate") or date.today().isoformat()
    currency = order_payload.get("currency") or "AUD"

    buyer_name = order_payload.get("buyerName")
    buyer_email = order_payload.get("buyerEmail")
    seller_name = order_payload.get("sellerName")
    seller_email = order_payload.get("sellerEmail")

    items = []
    for line in order_payload.get("lines", []):
        unit_price_raw = line.get("unitPrice")
        unit_price = float(unit_price_raw) if unit_price_raw is not None else 0.0

        items.append({
            "name": line.get("productName"),
            "description": None,
            "quantity": float(line.get("quantity", 1)),
            "unit_price": unit_price,
            "unit_code": line.get("unitCode") or "EA",
        })

    return {
        "order_reference": order_id,
        "status": "draft",
        "issue_date": issue_date,
        "currency": currency,

        "customer_id": buyer_email or buyer_name or f"buyer:{order_id}",
        "customer": {
            "name": buyer_name,
            "identifier": buyer_email,
        },

        "supplier": {
            "name": seller_name,
            "identifier": seller_email,
        },

        "items": items,
    }
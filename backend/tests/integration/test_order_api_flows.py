from __future__ import annotations

from time import time_ns

import pytest

from app.other import findOrders
from app.services import order_store

pytestmark = pytest.mark.integration


def _tag() -> str:
    return str(time_ns())


def _register_party(client, tracked, *, name_prefix: str, email_prefix: str, tag: str) -> dict:
    payload = {
        "partyName": f"{name_prefix} {tag}",
        "contactEmail": f"{email_prefix}-{tag}@example.com",
    }
    response = client.post("/v1/parties/register", json=payload)

    assert response.status_code == 201
    body = response.json()
    tracked["party_ids"].append(body["partyId"])

    return {
        "partyId": body["partyId"],
        "partyName": payload["partyName"],
        "contactEmail": payload["contactEmail"].lower(),
        "appKey": body["appKey"],
    }


def _auth_headers(app_key: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {app_key}"}


def _order_payload(*, buyer: dict, seller: dict, tag: str, notes: str, quantity: int = 3) -> dict:
    return {
        "buyerEmail": buyer["contactEmail"],
        "buyerName": buyer["partyName"],
        "sellerEmail": seller["contactEmail"],
        "sellerName": seller["partyName"],
        "currency": "AUD",
        "issueDate": "2026-03-14",
        "notes": notes,
        "delivery": {
            "street": "1 Integration Lane",
            "city": "Sydney",
            "state": "NSW",
            "postcode": "2000",
            "country": "AU",
            "requestedDate": "2026-03-20",
        },
        "lines": [
            {
                "productName": f"Oranges {tag}",
                "quantity": quantity,
                "unitCode": "EA",
                "unitPrice": "4.25",
            }
        ],
    }


def test_full_order_lifecycle_survives_cache_reset(integration_client, tracked_supabase_records):
    tag = _tag()
    buyer = _register_party(
        integration_client,
        tracked_supabase_records,
        name_prefix="Lifecycle Buyer",
        email_prefix="lifecycle-buyer",
        tag=tag,
    )
    seller = _register_party(
        integration_client,
        tracked_supabase_records,
        name_prefix="Lifecycle Seller",
        email_prefix="lifecycle-seller",
        tag=tag,
    )

    create_response = integration_client.post(
        "/v1/order/create",
        json=_order_payload(
            buyer=buyer,
            seller=seller,
            tag=tag,
            notes=f"Lifecycle test order {tag}",
        ),
        headers=_auth_headers(buyer["appKey"]),
    )
    assert create_response.status_code == 201
    order_id = create_response.json()["orderId"]
    tracked_supabase_records["order_ids"].append(order_id)

    assert findOrders(externalOrderId=order_id)

    order_store.ORDERS.clear()

    get_after_reset = integration_client.get(
        f"/v1/order/{order_id}",
        headers=_auth_headers(buyer["appKey"]),
    )
    assert get_after_reset.status_code == 200

    update_payload = _order_payload(
        buyer=buyer,
        seller=seller,
        tag=tag,
        notes=f"Lifecycle test order updated {tag}",
        quantity=5,
    )
    update_payload["delivery"]["street"] = "2 Integration Lane"
    update_payload["delivery"]["requestedDate"] = "2026-03-21"

    update_after_reset = integration_client.put(
        f"/v1/order/{order_id}",
        json=update_payload,
        headers=_auth_headers(seller["appKey"]),
    )
    assert update_after_reset.status_code == 200

    order_store.ORDERS.clear()

    get_after_update_reset = integration_client.get(
        f"/v1/order/{order_id}",
        headers=_auth_headers(seller["appKey"]),
    )
    assert get_after_update_reset.status_code == 200
    assert "Lifecycle test order updated" in get_after_update_reset.json()["ublXml"]

    persisted = findOrders(externalOrderId=order_id)
    assert persisted
    assert persisted[0]["notes"] == f"Lifecycle test order updated {tag}"
    assert persisted[0]["deliverystreet"] == "2 Integration Lane"

    delete_after_reset = integration_client.delete(
        f"/v1/order/{order_id}",
        headers=_auth_headers(buyer["appKey"]),
    )
    assert delete_after_reset.status_code == 204

    order_store.ORDERS.clear()

    final_get = integration_client.get(
        f"/v1/order/{order_id}",
        headers=_auth_headers(buyer["appKey"]),
    )
    assert final_get.status_code == 404
    assert findOrders(externalOrderId=order_id) == []


def test_async_onboarding_allows_counterparty_access_after_late_registration(
    integration_client, tracked_supabase_records
):
    tag = _tag()
    buyer = _register_party(
        integration_client,
        tracked_supabase_records,
        name_prefix="Async Buyer",
        email_prefix="async-buyer",
        tag=tag,
    )
    seller_contact_email = f"async-seller-{tag}@example.com"
    seller_stub = {
        "partyName": f"Async Seller {tag}",
        "contactEmail": seller_contact_email,
    }

    create_response = integration_client.post(
        "/v1/order/create",
        json=_order_payload(
            buyer=buyer,
            seller=seller_stub,
            tag=tag,
            notes=f"Async onboarding order {tag}",
        ),
        headers=_auth_headers(buyer["appKey"]),
    )
    assert create_response.status_code == 201
    order_id = create_response.json()["orderId"]
    tracked_supabase_records["order_ids"].append(order_id)

    update_before_registration = integration_client.put(
        f"/v1/order/{order_id}",
        json=_order_payload(
            buyer=buyer,
            seller=seller_stub,
            tag=tag,
            notes=f"Async onboarding order {tag}",
            quantity=4,
        ),
        headers=_auth_headers("not-a-real-key"),
    )
    assert update_before_registration.status_code == 401

    delete_before_registration = integration_client.delete(
        f"/v1/order/{order_id}",
        headers=_auth_headers("not-a-real-key"),
    )
    assert delete_before_registration.status_code == 401

    seller = _register_party(
        integration_client,
        tracked_supabase_records,
        name_prefix="Async Seller",
        email_prefix="async-seller",
        tag=tag,
    )

    order_store.ORDERS.clear()

    update_after_registration = integration_client.put(
        f"/v1/order/{order_id}",
        json=_order_payload(
            buyer=buyer,
            seller=seller,
            tag=tag,
            notes=f"Async onboarding order updated {tag}",
            quantity=6,
        ),
        headers=_auth_headers(seller["appKey"]),
    )
    assert update_after_registration.status_code == 200

    get_after_registration = integration_client.get(
        f"/v1/order/{order_id}",
        headers=_auth_headers(seller["appKey"]),
    )
    assert get_after_registration.status_code == 200


def test_unrelated_registered_party_is_forbidden_from_order_crud(
    integration_client, tracked_supabase_records
):
    tag = _tag()
    buyer = _register_party(
        integration_client,
        tracked_supabase_records,
        name_prefix="Auth Buyer",
        email_prefix="auth-buyer",
        tag=tag,
    )
    seller = _register_party(
        integration_client,
        tracked_supabase_records,
        name_prefix="Auth Seller",
        email_prefix="auth-seller",
        tag=tag,
    )
    outsider = _register_party(
        integration_client,
        tracked_supabase_records,
        name_prefix="Auth Outsider",
        email_prefix="auth-outsider",
        tag=tag,
    )

    create_response = integration_client.post(
        "/v1/order/create",
        json=_order_payload(
            buyer=buyer,
            seller=seller,
            tag=tag,
            notes=f"Forbidden access order {tag}",
        ),
        headers=_auth_headers(buyer["appKey"]),
    )
    assert create_response.status_code == 201
    order_id = create_response.json()["orderId"]
    tracked_supabase_records["order_ids"].append(order_id)

    order_store.ORDERS.clear()

    assert (
        integration_client.get(
            f"/v1/order/{order_id}",
            headers=_auth_headers(outsider["appKey"]),
        ).status_code
        == 403
    )
    assert (
        integration_client.put(
            f"/v1/order/{order_id}",
            json=_order_payload(
                buyer=buyer,
                seller=seller,
                tag=tag,
                notes=f"Forbidden access order {tag}",
            ),
            headers=_auth_headers(outsider["appKey"]),
        ).status_code
        == 403
    )
    assert (
        integration_client.delete(
            f"/v1/order/{order_id}",
            headers=_auth_headers(outsider["appKey"]),
        ).status_code
        == 403
    )


def test_registration_conflict_and_validation_authorization(
    integration_client, tracked_supabase_records
):
    tag = _tag()
    buyer = _register_party(
        integration_client,
        tracked_supabase_records,
        name_prefix="Validation Buyer",
        email_prefix="validation-buyer",
        tag=tag,
    )
    seller = _register_party(
        integration_client,
        tracked_supabase_records,
        name_prefix="Validation Seller",
        email_prefix="validation-seller",
        tag=tag,
    )
    outsider = _register_party(
        integration_client,
        tracked_supabase_records,
        name_prefix="Validation Outsider",
        email_prefix="validation-outsider",
        tag=tag,
    )

    duplicate_registration = integration_client.post(
        "/v1/parties/register",
        json={
            "partyName": f"Validation Buyer Duplicate {tag}",
            "contactEmail": buyer["contactEmail"],
        },
    )
    assert duplicate_registration.status_code == 409

    payload = _order_payload(
        buyer=buyer,
        seller=seller,
        tag=tag,
        notes=f"Validation endpoint order {tag}",
    )

    buyer_validation = integration_client.post(
        "/v1/orders/validate",
        json=payload,
        headers=_auth_headers(buyer["appKey"]),
    )
    assert buyer_validation.status_code == 200
    assert buyer_validation.json()["valid"] is True

    seller_validation = integration_client.post(
        "/v1/orders/validate",
        json=payload,
        headers=_auth_headers(seller["appKey"]),
    )
    assert seller_validation.status_code == 200

    outsider_validation = integration_client.post(
        "/v1/orders/validate",
        json=payload,
        headers=_auth_headers(outsider["appKey"]),
    )
    assert outsider_validation.status_code == 403

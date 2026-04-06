from __future__ import annotations

from time import time_ns

import pytest

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


def _order_payload(
    *, buyer: dict, seller: dict, tag: str, notes: str, quantity: int, unit_price: str
) -> dict:
    return {
        "buyerEmail": buyer["contactEmail"],
        "buyerName": buyer["partyName"],
        "sellerEmail": seller["contactEmail"],
        "sellerName": seller["partyName"],
        "currency": "AUD",
        "issueDate": "2026-03-14",
        "notes": notes,
        "delivery": {
            "street": "1 Analytics Lane",
            "city": "Sydney",
            "state": "NSW",
            "postcode": "2000",
            "country": "AU",
            "requestedDate": "2026-03-20",
        },
        "lines": [
            {
                "productName": f"Analytics Product {tag}",
                "quantity": quantity,
                "unitCode": "EA",
                "unitPrice": unit_price,
            }
        ],
    }


def _create_order(
    client,
    tracked,
    *,
    buyer: dict,
    seller: dict,
    tag: str,
    notes: str,
    quantity: int,
    unit_price: str,
):
    response = client.post(
        "/v1/order/create",
        json=_order_payload(
            buyer=buyer,
            seller=seller,
            tag=tag,
            notes=notes,
            quantity=quantity,
            unit_price=unit_price,
        ),
        headers=_auth_headers(buyer["appKey"]),
    )
    assert response.status_code == 201
    order_id = response.json()["orderId"]
    tracked["order_ids"].append(order_id)
    return order_id


def _analytics(client, app_key: str, *, from_date: str, to_date: str):
    return client.get(
        f"/v1/analytics/orders?fromDate={from_date}&toDate={to_date}",
        headers=_auth_headers(app_key),
    )


def test_analytics_endpoint_returns_seller_metrics_from_persisted_orders(
    integration_client, tracked_supabase_records
):
    tag = _tag()
    seller = _register_party(
        integration_client,
        tracked_supabase_records,
        name_prefix="Analytics Seller",
        email_prefix="analytics-seller",
        tag=tag,
    )
    buyer = _register_party(
        integration_client,
        tracked_supabase_records,
        name_prefix="Analytics Buyer",
        email_prefix="analytics-buyer",
        tag=tag,
    )

    _create_order(
        integration_client,
        tracked_supabase_records,
        buyer=buyer,
        seller=seller,
        tag=tag,
        notes=f"Seller analytics order {tag}",
        quantity=3,
        unit_price="4.25",
    )

    order_store.ORDERS.clear()
    response = _analytics(
        integration_client,
        seller["appKey"],
        from_date="2026-03-13T00:00:00",
        to_date="2026-03-15T23:59:59",
    )

    assert response.status_code == 200
    body = response.json()
    assert body["role"] == "seller"
    assert body["analytics"]["totalOrders"] == 1
    assert body["analytics"]["itemsSold"] == 3
    assert body["analytics"]["totalIncome"] == 12.75
    assert body["analytics"]["averageOrderAmount"] == 12.75
    assert body["analytics"]["averageDailyOrders"] == 0.33
    assert body["analytics"]["averageDailyIncome"] == 4.25


def test_analytics_endpoint_returns_buyer_metrics_from_persisted_orders(
    integration_client, tracked_supabase_records
):
    tag = _tag()
    buyer = _register_party(
        integration_client,
        tracked_supabase_records,
        name_prefix="Analytics Buyer",
        email_prefix="analytics-buyer",
        tag=tag,
    )
    seller = _register_party(
        integration_client,
        tracked_supabase_records,
        name_prefix="Analytics Seller",
        email_prefix="analytics-seller",
        tag=tag,
    )

    _create_order(
        integration_client,
        tracked_supabase_records,
        buyer=buyer,
        seller=seller,
        tag=tag,
        notes=f"Buyer analytics order {tag}",
        quantity=2,
        unit_price="7.50",
    )

    order_store.ORDERS.clear()
    response = _analytics(
        integration_client,
        buyer["appKey"],
        from_date="2026-03-13T00:00:00",
        to_date="2026-03-15T23:59:59",
    )

    assert response.status_code == 200
    body = response.json()
    assert body["role"] == "buyer"
    assert body["analytics"]["totalOrders"] == 1
    assert body["analytics"]["itemsBought"] == 2
    assert body["analytics"]["totalSpent"] == 15.0
    assert body["analytics"]["averageOrderAmount"] == 15.0
    assert body["analytics"]["averageDailyOrders"] == 0.33
    assert body["analytics"]["averageDailySpend"] == 5.0


def test_analytics_endpoint_combines_buyer_and_seller_roles(
    integration_client, tracked_supabase_records
):
    tag = _tag()
    dual_party = _register_party(
        integration_client,
        tracked_supabase_records,
        name_prefix="Analytics Dual",
        email_prefix="analytics-dual",
        tag=tag,
    )
    counterparty_a = _register_party(
        integration_client,
        tracked_supabase_records,
        name_prefix="Analytics Counterparty A",
        email_prefix="analytics-counterparty-a",
        tag=tag,
    )
    counterparty_b = _register_party(
        integration_client,
        tracked_supabase_records,
        name_prefix="Analytics Counterparty B",
        email_prefix="analytics-counterparty-b",
        tag=tag,
    )

    _create_order(
        integration_client,
        tracked_supabase_records,
        buyer=counterparty_a,
        seller=dual_party,
        tag=f"{tag}-sell",
        notes=f"Dual role sell order {tag}",
        quantity=4,
        unit_price="5.00",
    )
    _create_order(
        integration_client,
        tracked_supabase_records,
        buyer=dual_party,
        seller=counterparty_b,
        tag=f"{tag}-buy",
        notes=f"Dual role buy order {tag}",
        quantity=1,
        unit_price="9.50",
    )

    order_store.ORDERS.clear()
    response = _analytics(
        integration_client,
        dual_party["appKey"],
        from_date="2026-03-13T00:00:00",
        to_date="2026-03-15T23:59:59",
    )

    assert response.status_code == 200
    body = response.json()
    assert body["role"] == "buyer_and_seller"
    assert body["sellerAnalytics"]["totalIncome"] == 20.0
    assert body["buyerAnalytics"]["totalSpent"] == 9.5
    assert body["netProfit"] == 10.5
    assert body["sellerAnalytics"]["averageDailyOrders"] == 0.33
    assert body["sellerAnalytics"]["averageDailyIncome"] == 6.67
    assert body["buyerAnalytics"]["averageDailyOrders"] == 0.33
    assert body["buyerAnalytics"]["averageDailySpend"] == 3.17


def test_analytics_endpoint_returns_no_orders_message_when_party_has_no_orders(
    integration_client, tracked_supabase_records
):
    tag = _tag()
    party = _register_party(
        integration_client,
        tracked_supabase_records,
        name_prefix="Analytics Empty",
        email_prefix="analytics-empty",
        tag=tag,
    )

    response = _analytics(
        integration_client,
        party["appKey"],
        from_date="2026-03-13T00:00:00",
        to_date="2026-03-15T23:59:59",
    )

    assert response.status_code == 200
    assert response.json() == {"message": "No orders found"}


def test_analytics_endpoint_rejects_missing_or_invalid_date_ranges(
    integration_client, tracked_supabase_records
):
    tag = _tag()
    party = _register_party(
        integration_client,
        tracked_supabase_records,
        name_prefix="Analytics Dates",
        email_prefix="analytics-dates",
        tag=tag,
    )

    missing_dates = integration_client.get(
        "/v1/analytics/orders",
        headers=_auth_headers(party["appKey"]),
    )
    assert missing_dates.status_code == 422
    body = missing_dates.json()
    assert body["message"] == "Request validation failed."
    assert {error["path"] for error in body["errors"]} == {"fromDate", "toDate"}
    assert all(error["source"] == "query" for error in body["errors"])

    invalid_range = _analytics(
        integration_client,
        party["appKey"],
        from_date="2026-03-16T00:00:00",
        to_date="2026-03-15T00:00:00",
    )
    assert invalid_range.status_code == 400
    assert invalid_range.json() == {"detail": "fromDate must be on or before toDate."}


def test_analytics_endpoint_requires_valid_bearer_auth(integration_client):
    missing_auth = integration_client.get(
        "/v1/analytics/orders?fromDate=2026-03-13T00:00:00&toDate=2026-03-15T23:59:59"
    )
    assert missing_auth.status_code == 401
    assert missing_auth.json() == {"detail": "Unauthorized"}

    unknown_key = integration_client.get(
        "/v1/analytics/orders?fromDate=2026-03-13T00:00:00&toDate=2026-03-15T23:59:59",
        headers=_auth_headers("not-a-real-key"),
    )
    assert unknown_key.status_code == 401
    assert unknown_key.json() == {"detail": "Unauthorized"}

from __future__ import annotations

import os
from datetime import date
from decimal import Decimal

import pytest

import app.other as other
from app.models.schemas import Delivery, LineItem, OrderRequest
from app.services import order_store
from app.services.order_store import OrderPersistenceError


def build_request() -> OrderRequest:
    return OrderRequest(
        buyerName="Acme Books",
        sellerName="Digital Book Supply",
        currency="AUD",
        issueDate=date(2026, 3, 10),
        notes="Leave at loading dock",
        delivery=Delivery(
            street="123 Test St",
            city="Sydney",
            postcode="2000",
            country="AU",
        ),
        lines=[
            LineItem(
                productName="Domain-Driven Design",
                quantity=2,
                unitCode="EA",
                unitPrice=Decimal("12.50"),
            ),
            LineItem(
                productName="Clean Architecture",
                quantity=1,
                unitCode="BX",
                unitPrice=None,
            ),
        ],
    )


def test_persist_order_to_database_with_real_supabase(monkeypatch):
    # To run this test, set SUPABASE_URL and SUPABASE_KEY in backend/.env or your shell,
    # then run `cd backend && ./.venv/bin/python -m pytest tests/test_order_store.py -q`.
    # This test verifies that create-order persistence uses other.py to write the order and
    # its line items to Supabase, and that the saved order can be found again via findOrders.
    if not (os.getenv("SUPABASE_URL") and os.getenv("SUPABASE_KEY")):
        other._load_local_env_files()
    if not (os.getenv("SUPABASE_URL") and os.getenv("SUPABASE_KEY")):
        pytest.skip("SUPABASE_URL and SUPABASE_KEY must be configured to run this test.")

    req = build_request()
    created_ids: list[int] = []
    monkeypatch.setattr(order_store, "ORDERS", {})
    monkeypatch.setattr(other, "_SUPABASE_CLIENT", None)

    try:
        db_order_id = order_store.persist_order_to_database(req)
        created_ids.append(db_order_id)

        persisted_orders = other.findOrders(orderId=db_order_id)

        assert persisted_orders
        assert persisted_orders[0]["buyername"] == req.buyerName
        assert persisted_orders[0]["sellername"] == req.sellerName
        assert persisted_orders[0]["currency"] == req.currency
        assert len(persisted_orders[0]["details"]) == len(req.lines)
    finally:
        client = None
        try:
            client = other.get_supabase_client()
        except RuntimeError:
            client = None
        if client:
            for created_id in created_ids:
                client.table("orderdetails").delete().eq("orderid", created_id).execute()
                client.table("orders").delete().eq("id", created_id).execute()
        other._SUPABASE_CLIENT = None


def test_delete_order_record_removes_in_memory_order_when_no_db_order_id():
    order_store.ORDERS["ord_local"] = {
        "orderId": "ord_local",
        "status": "DRAFT",
        "createdAt": "2026-03-11T00:00:00Z",
        "updatedAt": "2026-03-11T00:00:00Z",
        "payload": {"buyerName": "Buyer"},
        "ublXml": "<Order />",
        "warnings": [],
    }

    deleted = order_store.delete_order_record("ord_local")

    assert deleted is True
    assert "ord_local" not in order_store.ORDERS


def test_delete_order_record_removes_db_rows_before_in_memory_order(monkeypatch):
    events: list[tuple[str, str]] = []
    order_store.ORDERS["ord_db"] = {
        "orderId": "ord_db",
        "status": "DRAFT",
        "createdAt": "2026-03-11T00:00:00Z",
        "updatedAt": "2026-03-11T00:00:00Z",
        "payload": {"buyerName": "Buyer"},
        "ublXml": "<Order />",
        "warnings": [],
        "dbOrderId": "42",
    }

    monkeypatch.setattr(
        other, "deleteOrderDetails", lambda order_id: events.append(("details", order_id))
    )
    monkeypatch.setattr(other, "deleteOrder", lambda order_id: events.append(("order", order_id)))

    deleted = order_store.delete_order_record("ord_db")

    assert deleted is True
    assert events == [("details", "42"), ("order", "42")]
    assert "ord_db" not in order_store.ORDERS


def test_delete_order_record_preserves_in_memory_order_when_db_delete_fails(monkeypatch):
    order_store.ORDERS["ord_db_fail"] = {
        "orderId": "ord_db_fail",
        "status": "DRAFT",
        "createdAt": "2026-03-11T00:00:00Z",
        "updatedAt": "2026-03-11T00:00:00Z",
        "payload": {"buyerName": "Buyer"},
        "ublXml": "<Order />",
        "warnings": [],
        "dbOrderId": "99",
    }

    monkeypatch.setattr(
        other, "deleteOrderDetails", lambda order_id: (_ for _ in ()).throw(RuntimeError(order_id))
    )

    with pytest.raises(OrderPersistenceError, match="Order could not be deleted from Supabase."):
        order_store.delete_order_record("ord_db_fail")

    assert "ord_db_fail" in order_store.ORDERS


def test_delete_order_record_returns_false_when_order_is_missing():
    deleted = order_store.delete_order_record("ord_missing")

    assert deleted is False

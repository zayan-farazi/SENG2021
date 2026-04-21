from __future__ import annotations

import app.other as other


class _FakeUpdateQuery:
    def __init__(self):
        self.filtered_order_id = None

    def eq(self, column, value):
        assert column == "id"
        self.filtered_order_id = value
        return self

    def execute(self):
        return type("Resp", (), {"data": [{"id": self.filtered_order_id}]})()


class _FakeTable:
    def update(self, query):
        assert query["order_id"] == "ext-123"
        assert query["ublxml"] == "<Order/>"
        return _FakeUpdateQuery()


class _FakeClient:
    def table(self, name):
        assert name == "orders"
        return _FakeTable()


def test_update_order_runtime_metadata_persists_generated_xml_with_party_ids(monkeypatch):
    captured = {}

    monkeypatch.setattr(other, "get_supabase_client", lambda: _FakeClient())
    monkeypatch.setattr(
        other,
        "findOrders",
        lambda **kwargs: [{"buyer_id": "buyer@example.com", "seller_id": "seller@example.com"}],
    )

    def _capture_save_xml(table_name, order_id, buyer_id, seller_id, xml):
        captured["args"] = (table_name, order_id, buyer_id, seller_id, xml)

    monkeypatch.setattr(other, "saveXml", _capture_save_xml)

    other.updateOrderRuntimeMetadata(
        42,
        externalOrderId="ext-123",
        ublXml="<Order/>",
    )

    assert captured["args"] == (
        "order_gen_xml",
        42,
        "buyer@example.com",
        "seller@example.com",
        "<Order/>",
    )

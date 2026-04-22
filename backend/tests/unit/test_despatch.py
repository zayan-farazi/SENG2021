from __future__ import annotations

from unittest.mock import AsyncMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes.despatch import router
from app.services.app_key_auth import get_current_party_email

app = FastAPI()
app.include_router(router)

SELLER_EMAIL = "seller@example.com"
BUYER_EMAIL = "buyer@example.com"
ORDER_ID = "ORD-2026-001"
DB_ORDER_ID = "db-uuid-001"
DESPATCH_XML = "<DespatchAdvice>test</DespatchAdvice>"
UBL_XML = "<Order>test</Order>"

MOCK_ORDER = {
    "orderId": ORDER_ID,
    "dbOrderId": DB_ORDER_ID,
    "updatedAt": "2026-04-20T12:00:00Z",
    "ublXml": UBL_XML,
    "payload": {
        "buyerEmail": BUYER_EMAIL,
        "sellerEmail": SELLER_EMAIL,
    },
}

MOCK_DESPATCH = {"adviceId": None, "xml": DESPATCH_XML}


def override_auth(email: str):
    app.dependency_overrides[get_current_party_email] = lambda: email


def clear_auth():
    app.dependency_overrides.clear()


client = TestClient(app)


class TestPostDespatch:
    def test_returns_existing_despatch_if_already_stored(self):
        override_auth(SELLER_EMAIL)
        with (
            patch("app.api.routes.despatch.order_store.get_order_record", return_value=MOCK_ORDER),
            patch("app.api.routes.despatch.getXml", return_value=[{"xml": DESPATCH_XML}]),
        ):
            res = client.post(f"/v1/order/{ORDER_ID}/despatch")

        assert res.status_code == 200
        body = res.json()
        assert body["orderId"] == ORDER_ID
        assert body["despatch"]["xml"] == DESPATCH_XML
        clear_auth()

    def test_generates_and_saves_new_despatch(self):
        override_auth(SELLER_EMAIL)
        with (
            patch("app.api.routes.despatch.order_store.get_order_record", return_value=MOCK_ORDER),
            patch("app.api.routes.despatch.getXml", return_value=[]),
            patch(
                "app.api.routes.despatch.create_despatch_from_order_xml",
                new=AsyncMock(return_value=MOCK_DESPATCH),
            ),
            patch("app.api.routes.despatch.saveXml") as mock_save,
        ):
            res = client.post(f"/v1/order/{ORDER_ID}/despatch")

        assert res.status_code == 200
        body = res.json()
        assert body["despatch"]["xml"] == DESPATCH_XML
        mock_save.assert_called_once_with(
            "dispatched_xml", DB_ORDER_ID, BUYER_EMAIL, SELLER_EMAIL, DESPATCH_XML
        )
        clear_auth()

    def test_404_when_order_not_found(self):
        override_auth(SELLER_EMAIL)
        with patch("app.api.routes.despatch.order_store.get_order_record", return_value=None):
            res = client.post(f"/v1/order/{ORDER_ID}/despatch")

        assert res.status_code == 404
        clear_auth()

    def test_403_when_buyer_attempts_despatch(self):
        override_auth(BUYER_EMAIL)
        with patch("app.api.routes.despatch.order_store.get_order_record", return_value=MOCK_ORDER):
            res = client.post(f"/v1/order/{ORDER_ID}/despatch")

        assert res.status_code == 403
        assert "seller" in res.json()["detail"].lower()
        clear_auth()

    def test_403_when_unrelated_party_attempts_despatch(self):
        override_auth("stranger@example.com")
        with patch("app.api.routes.despatch.order_store.get_order_record", return_value=MOCK_ORDER):
            res = client.post(f"/v1/order/{ORDER_ID}/despatch")

        assert res.status_code == 403
        clear_auth()

    def test_500_when_order_missing_db_id(self):
        override_auth(SELLER_EMAIL)
        order = {**MOCK_ORDER, "dbOrderId": None}
        with patch("app.api.routes.despatch.order_store.get_order_record", return_value=order):
            res = client.post(f"/v1/order/{ORDER_ID}/despatch")

        assert res.status_code == 500
        assert "database ID" in res.json()["detail"]
        clear_auth()

    def test_500_when_ubl_xml_missing(self):
        override_auth(SELLER_EMAIL)
        order = {**MOCK_ORDER, "ublXml": None}
        with (
            patch("app.api.routes.despatch.order_store.get_order_record", return_value=order),
            patch("app.api.routes.despatch.getXml", return_value=[]),
        ):
            res = client.post(f"/v1/order/{ORDER_ID}/despatch")

        assert res.status_code == 500
        assert "Order XML missing" in res.json()["detail"]
        clear_auth()

    def test_500_when_despatch_generation_fails(self):
        override_auth(SELLER_EMAIL)
        with (
            patch("app.api.routes.despatch.order_store.get_order_record", return_value=MOCK_ORDER),
            patch("app.api.routes.despatch.getXml", return_value=[]),
            patch(
                "app.api.routes.despatch.create_despatch_from_order_xml",
                new=AsyncMock(side_effect=Exception("generation boom")),
            ),
        ):
            res = client.post(f"/v1/order/{ORDER_ID}/despatch")

        assert res.status_code == 500
        assert "generate despatch" in res.json()["detail"]
        clear_auth()

    def test_500_when_save_fails(self):
        override_auth(SELLER_EMAIL)
        with (
            patch("app.api.routes.despatch.order_store.get_order_record", return_value=MOCK_ORDER),
            patch("app.api.routes.despatch.getXml", return_value=[]),
            patch(
                "app.api.routes.despatch.create_despatch_from_order_xml",
                new=AsyncMock(return_value=MOCK_DESPATCH),
            ),
            patch("app.api.routes.despatch.saveXml", side_effect=Exception("save boom")),
        ):
            res = client.post(f"/v1/order/{ORDER_ID}/despatch")

        assert res.status_code == 500
        assert "persist despatch" in res.json()["detail"]
        clear_auth()

    def test_500_when_getxml_raises(self):
        override_auth(SELLER_EMAIL)
        with (
            patch("app.api.routes.despatch.order_store.get_order_record", return_value=MOCK_ORDER),
            patch("app.api.routes.despatch.getXml", side_effect=Exception("db boom")),
        ):
            res = client.post(f"/v1/order/{ORDER_ID}/despatch")

        assert res.status_code == 500
        assert "fetch despatch XML" in res.json()["detail"]
        clear_auth()


class TestGetDespatch:
    def test_returns_xml_for_seller(self):
        override_auth(SELLER_EMAIL)
        with (
            patch("app.api.routes.despatch.order_store.get_order_record", return_value=MOCK_ORDER),
            patch("app.api.routes.despatch.getXml", return_value=[{"xml": DESPATCH_XML}]),
        ):
            res = client.get(f"/v1/order/{ORDER_ID}/despatch")

        assert res.status_code == 200
        assert res.headers["content-type"] == "application/xml"
        assert res.text == DESPATCH_XML
        clear_auth()

    def test_returns_xml_for_buyer(self):
        override_auth(BUYER_EMAIL)
        with (
            patch("app.api.routes.despatch.order_store.get_order_record", return_value=MOCK_ORDER),
            patch("app.api.routes.despatch.getXml", return_value=[{"xml": DESPATCH_XML}]),
        ):
            res = client.get(f"/v1/order/{ORDER_ID}/despatch")

        assert res.status_code == 200
        assert res.text == DESPATCH_XML
        clear_auth()

    def test_404_when_order_not_found(self):
        override_auth(SELLER_EMAIL)
        with patch("app.api.routes.despatch.order_store.get_order_record", return_value=None):
            res = client.get(f"/v1/order/{ORDER_ID}/despatch")

        assert res.status_code == 404
        clear_auth()

    def test_404_when_no_despatch_stored(self):
        override_auth(SELLER_EMAIL)
        with (
            patch("app.api.routes.despatch.order_store.get_order_record", return_value=MOCK_ORDER),
            patch("app.api.routes.despatch.getXml", return_value=[]),
        ):
            res = client.get(f"/v1/order/{ORDER_ID}/despatch")

        assert res.status_code == 404
        clear_auth()

    def test_403_when_unrelated_party(self):
        override_auth("stranger@example.com")
        with patch("app.api.routes.despatch.order_store.get_order_record", return_value=MOCK_ORDER):
            res = client.get(f"/v1/order/{ORDER_ID}/despatch")

        assert res.status_code == 403
        clear_auth()

    def test_500_when_xml_field_is_empty(self):
        override_auth(SELLER_EMAIL)
        with (
            patch("app.api.routes.despatch.order_store.get_order_record", return_value=MOCK_ORDER),
            patch("app.api.routes.despatch.getXml", return_value=[{"xml": None}]),
        ):
            res = client.get(f"/v1/order/{ORDER_ID}/despatch")

        assert res.status_code == 500
        assert "corrupted" in res.json()["detail"]
        clear_auth()

    def test_500_when_getxml_raises(self):
        override_auth(SELLER_EMAIL)
        with (
            patch("app.api.routes.despatch.order_store.get_order_record", return_value=MOCK_ORDER),
            patch("app.api.routes.despatch.getXml", side_effect=Exception("db boom")),
        ):
            res = client.get(f"/v1/order/{ORDER_ID}/despatch")

        assert res.status_code == 500
        assert "fetch despatch XML" in res.json()["detail"]
        clear_auth()

    def test_500_when_db_order_id_missing(self):
        override_auth(SELLER_EMAIL)
        order = {**MOCK_ORDER, "dbOrderId": None}
        with patch("app.api.routes.despatch.order_store.get_order_record", return_value=order):
            res = client.get(f"/v1/order/{ORDER_ID}/despatch")

        assert res.status_code == 500
        assert "database ID" in res.json()["detail"]
        clear_auth()


class TestDeleteDespatch:
    def test_deletes_existing_despatch(self):
        override_auth(SELLER_EMAIL)
        with (
            patch("app.api.routes.despatch.order_store.get_order_record", return_value=MOCK_ORDER),
            patch("app.api.routes.despatch.getXml", return_value=[{"xml": DESPATCH_XML}]),
            patch("app.api.routes.despatch.deleteXml") as mock_delete,
        ):
            res = client.delete(f"/v1/order/{ORDER_ID}/despatch")

        assert res.status_code == 200
        body = res.json()
        assert body["orderId"] == ORDER_ID
        assert body["detail"] == "Despatch advice deleted."
        mock_delete.assert_called_once_with("dispatched_xml", DB_ORDER_ID)
        clear_auth()

    def test_404_when_order_not_found(self):
        override_auth(SELLER_EMAIL)
        with patch("app.api.routes.despatch.order_store.get_order_record", return_value=None):
            res = client.delete(f"/v1/order/{ORDER_ID}/despatch")

        assert res.status_code == 404
        clear_auth()

    def test_404_when_no_despatch_exists(self):
        override_auth(SELLER_EMAIL)
        with (
            patch("app.api.routes.despatch.order_store.get_order_record", return_value=MOCK_ORDER),
            patch("app.api.routes.despatch.getXml", return_value=[]),
        ):
            res = client.delete(f"/v1/order/{ORDER_ID}/despatch")

        assert res.status_code == 404
        assert "No despatch exists" in res.json()["detail"]
        clear_auth()

    def test_403_when_buyer_attempts_delete(self):
        override_auth(BUYER_EMAIL)
        with patch("app.api.routes.despatch.order_store.get_order_record", return_value=MOCK_ORDER):
            res = client.delete(f"/v1/order/{ORDER_ID}/despatch")

        assert res.status_code == 403
        assert "seller" in res.json()["detail"].lower()
        clear_auth()

    def test_403_when_unrelated_party_attempts_delete(self):
        override_auth("stranger@example.com")
        with patch("app.api.routes.despatch.order_store.get_order_record", return_value=MOCK_ORDER):
            res = client.delete(f"/v1/order/{ORDER_ID}/despatch")

        assert res.status_code == 403
        clear_auth()

    def test_500_when_db_order_id_missing(self):
        override_auth(SELLER_EMAIL)
        order = {**MOCK_ORDER, "dbOrderId": None}
        with patch("app.api.routes.despatch.order_store.get_order_record", return_value=order):
            res = client.delete(f"/v1/order/{ORDER_ID}/despatch")

        assert res.status_code == 500
        assert "database ID" in res.json()["detail"]
        clear_auth()

    def test_500_when_getxml_raises(self):
        override_auth(SELLER_EMAIL)
        with (
            patch("app.api.routes.despatch.order_store.get_order_record", return_value=MOCK_ORDER),
            patch("app.api.routes.despatch.getXml", side_effect=Exception("db boom")),
        ):
            res = client.delete(f"/v1/order/{ORDER_ID}/despatch")

        assert res.status_code == 500
        assert "fetch despatch XML" in res.json()["detail"]
        clear_auth()

    def test_500_when_deletexml_raises(self):
        override_auth(SELLER_EMAIL)
        with (
            patch("app.api.routes.despatch.order_store.get_order_record", return_value=MOCK_ORDER),
            patch("app.api.routes.despatch.getXml", return_value=[{"xml": DESPATCH_XML}]),
            patch("app.api.routes.despatch.deleteXml", side_effect=Exception("delete boom")),
        ):
            res = client.delete(f"/v1/order/{ORDER_ID}/despatch")

        assert res.status_code == 500
        assert "delete despatch" in res.json()["detail"]
        clear_auth()

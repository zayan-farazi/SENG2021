from __future__ import annotations

from xml.etree import ElementTree as ET

import pytest
from fastapi.testclient import TestClient

from app.api.routes import orders
from app.main import app
from app.services import app_key_auth, order_store
from app.services.order_store import OrderPersistenceError
from app.services.party_registration import hash_app_key
from app.services.ubl_order import OrderGenerationError

NS = {
    "cbc": "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2",
    "cac": "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2",
}


def build_payload() -> dict:
    return {
        "buyerEmail": "buyer@example.com",
        "buyerName": "Acme Books",
        "sellerEmail": "seller@example.com",
        "sellerName": "Digital Book Supply",
        "currency": "AUD",
        "issueDate": "2026-03-07",
        "notes": "Leave at loading dock",
        "delivery": {
            "street": "123 Test St",
            "city": "Sydney",
            "state": "NSW",
            "postcode": "2000",
            "country": "AU",
            "requestedDate": "2026-03-10",
        },
        "lines": [
            {
                "productName": "Domain-Driven Design",
                "quantity": 2,
                "unitCode": "EA",
                "unitPrice": "12.50",
            },
            {
                "productName": "Clean Architecture",
                "quantity": 1,
                "unitCode": "BX",
                "unitPrice": "19.99",
            },
        ],
    }


@pytest.fixture
def client():
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client


@pytest.fixture(autouse=True)
def stub_app_key_lookup(monkeypatch):
    app.dependency_overrides.clear()
    key_map = {
        hash_app_key("buyer-key"): {"party_id": "buyer-party"},
        hash_app_key("seller-key"): {"party_id": "seller-party"},
        hash_app_key("other-key"): {"party_id": "other-party"},
    }
    party_map = {
        "buyer-party": {"contact_email": "buyer@example.com"},
        "seller-party": {"contact_email": "seller@example.com"},
        "other-party": {"contact_email": "other@example.com"},
    }
    monkeypatch.setattr(app_key_auth, "findAppKeyByHash", lambda key_hash: key_map.get(key_hash))
    monkeypatch.setattr(
        app_key_auth, "findPartyByPartyId", lambda party_id: party_map.get(party_id)
    )
    yield
    app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
def stub_runtime_metadata_persistence(monkeypatch):
    monkeypatch.setattr(order_store, "persist_order_to_database", lambda req: 123)
    monkeypatch.setattr(
        order_store,
        "persist_order_runtime_metadata_to_database",
        lambda *args, **kwargs: None,
    )


def auth_headers(app_key: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {app_key}"}


def test_create_order_returns_201_and_persists_full_order(client):
    payload = build_payload()

    response = client.post("/v1/order/create", json=payload, headers=auth_headers("buyer-key"))

    assert response.status_code == 201
    body = response.json()

    assert body["orderId"].startswith("ord_")
    assert body["status"] == "DRAFT"
    assert body["createdAt"].endswith("Z")
    assert body == {
        "orderId": body["orderId"],
        "status": "DRAFT",
        "createdAt": body["createdAt"],
    }

    record = orders.ORDERS[body["orderId"]]
    assert record["createdAt"] == body["createdAt"]
    assert record["updatedAt"] == body["createdAt"]
    assert record["payload"]["buyerName"] == payload["buyerName"]
    assert record["payload"]["sellerName"] == payload["sellerName"]
    assert record["payload"]["currency"] == payload["currency"]
    assert record["payload"]["issueDate"] == payload["issueDate"]
    assert record["payload"]["delivery"]["requestedDate"] == payload["delivery"]["requestedDate"]
    assert record["payload"]["lines"][0]["unitPrice"] == payload["lines"][0]["unitPrice"]
    root = ET.fromstring(record["ublXml"])
    assert root.find("cbc:CustomizationID", NS).text
    assert root.find("cbc:ProfileID", NS).text
    assert root.find("cbc:ID", NS).text == body["orderId"]
    assert root.find("cbc:CopyIndicator", NS).text == "false"
    assert root.find("cbc:UUID", NS).text
    assert root.find("cbc:IssueDate", NS).text == payload["issueDate"]
    assert root.find("cbc:DocumentCurrencyCode", NS).text == payload["currency"]
    assert root.find("cac:TransactionConditions/cbc:Description", NS).text == payload["notes"]
    assert (
        root.find(
            "cac:BuyerCustomerParty/cac:Party/cac:PartyName/cbc:Name",
            NS,
        ).text
        == payload["buyerName"]
    )
    assert (
        root.find(
            "cac:BuyerCustomerParty/cac:Party/cac:Contact/cbc:ElectronicMail",
            NS,
        ).text
        == payload["buyerEmail"]
    )
    assert (
        root.find(
            "cac:SellerSupplierParty/cac:Party/cac:PartyName/cbc:Name",
            NS,
        ).text
        == payload["sellerName"]
    )
    assert (
        root.find(
            "cac:SellerSupplierParty/cac:Party/cac:Contact/cbc:ElectronicMail",
            NS,
        ).text
        == payload["sellerEmail"]
    )
    assert root.find("cac:Delivery/cac:DeliveryAddress/cbc:StreetName", NS).text == "123 Test St"
    assert (
        root.find(
            "cac:Delivery/cac:RequestedDeliveryPeriod/cbc:StartDate",
            NS,
        ).text
        == payload["delivery"]["requestedDate"]
    )
    assert root.find("cac:AnticipatedMonetaryTotal/cbc:PayableAmount", NS).text == "44.99"

    price_amount = root.find(".//cac:Price/cbc:PriceAmount", NS)
    assert price_amount.text == payload["lines"][0]["unitPrice"]
    assert price_amount.attrib["currencyID"] == payload["currency"]
    assert root.find(".//cac:Price/cbc:BaseQuantity", NS).text == "2"


def test_create_order_applies_defaults_for_optional_fields(client):
    payload = {
        "buyerEmail": "buyer@example.com",
        "buyerName": "Acme Books",
        "sellerEmail": "seller@example.com",
        "sellerName": "Digital Book Supply",
        "lines": [{"productName": "Working Effectively with Legacy Code", "quantity": 1}],
    }

    response = client.post("/v1/order/create", json=payload, headers=auth_headers("buyer-key"))

    assert response.status_code == 201
    body = response.json()
    record = orders.ORDERS[body["orderId"]]

    assert body == {
        "orderId": body["orderId"],
        "status": "DRAFT",
        "createdAt": body["createdAt"],
    }

    assert record["payload"]["currency"] is None
    assert record["payload"]["issueDate"] is None
    assert record["payload"]["notes"] is None
    assert record["payload"]["delivery"] is None
    assert record["payload"]["lines"][0]["unitCode"] == "EA"
    assert record["payload"]["lines"][0]["unitPrice"] is None

    root = ET.fromstring(record["ublXml"])
    assert root.find("cac:TransactionConditions", NS) is None
    assert root.find("cac:Delivery", NS) is None
    assert root.find("cbc:DocumentCurrencyCode", NS).text == "AUD"
    quantity = root.find(".//cbc:Quantity", NS)
    assert quantity.attrib["unitCode"] == "EA"
    assert root.find(".//cbc:PriceAmount", NS) is None
    assert root.find("cac:AnticipatedMonetaryTotal", NS) is None


@pytest.mark.parametrize(
    ("mutator", "expected_loc"),
    [
        (lambda payload: payload.pop("buyerName"), ["body", "buyerName"]),
        (lambda payload: payload.pop("buyerEmail"), ["body", "buyerEmail"]),
        (lambda payload: payload.update({"lines": []}), ["body", "lines"]),
        (
            lambda payload: payload["lines"][0].update({"quantity": 0}),
            ["body", "lines", 0, "quantity"],
        ),
        (lambda payload: payload.update({"currency": "AU"}), ["body", "currency"]),
        (
            lambda payload: payload["lines"][0].update({"unitPrice": "-1.00"}),
            ["body", "lines", 0, "unitPrice"],
        ),
    ],
)
def test_create_order_rejects_invalid_payloads(client, mutator, expected_loc):
    payload = build_payload()
    mutator(payload)

    response = client.post("/v1/order/create", json=payload, headers=auth_headers("buyer-key"))

    assert response.status_code == 422
    body = response.json()
    assert body["message"] == "Request validation failed."
    source, *path_segments = expected_loc
    expected_path = path_segments[0]
    for segment in path_segments[1:]:
        expected_path = (
            f"{expected_path}[{segment}]"
            if isinstance(segment, int)
            else f"{expected_path}.{segment}"
        )
    assert any(
        error["source"] == source and error["path"] == expected_path for error in body["errors"]
    )
    assert orders.ORDERS == {}


def test_create_order_returns_500_when_id_generation_fails(client, monkeypatch):
    payload = build_payload()

    def fail_generate_order_id():
        raise OrderGenerationError("boom")

    monkeypatch.setattr(order_store, "generate_order_id", fail_generate_order_id)

    response = client.post("/v1/order/create", json=payload, headers=auth_headers("buyer-key"))

    assert response.status_code == 500
    assert response.json() == {"detail": "Unable to create order."}
    assert orders.ORDERS == {}


def test_create_order_returns_500_when_xml_generation_fails(client, monkeypatch):
    payload = build_payload()

    def fail_generate_ubl_order_xml(order_id: str, req):
        raise OrderGenerationError(f"unable to serialize {order_id}")

    monkeypatch.setattr(order_store, "generate_order_id", lambda: "ord_fixedfailure01")
    monkeypatch.setattr(order_store, "generate_ubl_order_xml", fail_generate_ubl_order_xml)

    response = client.post("/v1/order/create", json=payload, headers=auth_headers("buyer-key"))

    assert response.status_code == 500
    assert response.json() == {"detail": "Unable to create order."}
    assert orders.ORDERS == {}


def test_create_order_returns_500_when_database_verification_fails(client, monkeypatch):
    payload = build_payload()

    def fail_persist_order_to_database(req):  # noqa: ARG001
        raise OrderPersistenceError("Supabase verification failed")

    monkeypatch.setattr(order_store, "persist_order_to_database", fail_persist_order_to_database)

    response = client.post("/v1/order/create", json=payload, headers=auth_headers("buyer-key"))

    assert response.status_code == 500
    assert response.json() == {"detail": "Unable to persist order."}
    assert orders.ORDERS == {}


def test_create_order_returns_401_when_auth_header_is_missing(client):
    response = client.post("/v1/order/create", json=build_payload())

    assert response.status_code == 401
    assert response.json() == {"detail": "Unauthorized"}
    assert orders.ORDERS == {}


def test_create_order_returns_401_for_malformed_auth_header(client):
    response = client.post(
        "/v1/order/create",
        json=build_payload(),
        headers={"Authorization": "Basic buyer-key"},
    )

    assert response.status_code == 401
    assert response.json() == {"detail": "Unauthorized"}
    assert orders.ORDERS == {}


def test_create_order_returns_401_for_unknown_app_key(client):
    response = client.post(
        "/v1/order/create", json=build_payload(), headers=auth_headers("unknown-key")
    )

    assert response.status_code == 401
    assert response.json() == {"detail": "Unauthorized"}
    assert orders.ORDERS == {}


def test_create_order_returns_403_for_non_party_caller(client):
    response = client.post(
        "/v1/order/create", json=build_payload(), headers=auth_headers("other-key")
    )

    assert response.status_code == 403
    assert response.json() == {"detail": "Forbidden"}
    assert orders.ORDERS == {}


def test_create_order_allows_seller_party(client):
    response = client.post(
        "/v1/order/create", json=build_payload(), headers=auth_headers("seller-key")
    )

    assert response.status_code == 201

from __future__ import annotations

from datetime import date
from xml.etree import ElementTree as ET

import pytest

from app.models.schemas import Delivery, LineItem, OrderRequest
from app.services import ubl_order
from app.services.ubl_order import OrderGenerationError

NS = {
    "cbc": "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2",
    "cac": "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2",
    "order": "urn:oasis:names:specification:ubl:schema:xsd:Order-2",
}


def test_generate_order_id_returns_prefixed_hex_identifier():
    order_id = ubl_order.generate_order_id()

    assert order_id.startswith("ord_")
    assert len(order_id) == 20
    int(order_id.removeprefix("ord_"), 16)


def test_generate_order_id_wraps_uuid_failures(monkeypatch):
    def fail_uuid4():
        raise RuntimeError("uuid unavailable")

    monkeypatch.setattr(ubl_order, "uuid4", fail_uuid4)

    with pytest.raises(OrderGenerationError, match="Unable to generate order identifier."):
        ubl_order.generate_order_id()


def test_generate_ubl_order_xml_includes_full_structure():
    req = OrderRequest(
        buyerEmail="buyer@example.com",
        buyerName="Acme Books",
        sellerEmail="seller@example.com",
        sellerName="Digital Book Supply",
        currency="AUD",
        issueDate=date(2026, 3, 7),
        notes="Leave at loading dock",
        delivery=Delivery(
            street="123 Test St",
            city="Sydney",
            state="NSW",
            postcode="2000",
            country="AU",
            requestedDate=date(2026, 3, 10),
        ),
        lines=[
            LineItem(
                productName="Domain-Driven Design", quantity=2, unitCode="EA", unitPrice="12.50"
            ),
            LineItem(productName="Clean Architecture", quantity=1, unitCode=None, unitPrice="5.00"),
        ],
    )

    xml_text = ubl_order.generate_ubl_order_xml("ord_1234567890abcdef", req)

    root = ET.fromstring(xml_text)
    assert root.tag == f"{{{NS['order']}}}Order"
    assert root.find("cbc:UBLVersionID", NS).text == "2.1"
    assert (
        root.find("cbc:CustomizationID", NS).text
        == "urn:oasis:names:specification:ubl:xpath:Order-2.1:sbs-1.0"
    )
    assert (
        root.find("cbc:ProfileID", NS).text
        == "bpid:urn:oasis:names:bpss:ubl-2-sbs-order-with-simple-response"
    )
    assert root.find("cbc:ID", NS).text == "ord_1234567890abcdef"
    assert root.find("cbc:CopyIndicator", NS).text == "false"
    assert root.find("cbc:UUID", NS).text
    assert root.find("cbc:IssueDate", NS).text == "2026-03-07"
    assert root.find("cbc:DocumentCurrencyCode", NS).text == "AUD"
    assert (
        root.find("cac:TransactionConditions/cbc:Description", NS).text == "Leave at loading dock"
    )
    assert (
        root.find(
            "cac:BuyerCustomerParty/cac:Party/cac:PartyName/cbc:Name",
            NS,
        ).text
        == "Acme Books"
    )
    assert (
        root.find(
            "cac:BuyerCustomerParty/cac:Party/cac:Contact/cbc:ElectronicMail",
            NS,
        ).text
        == "buyer@example.com"
    )
    assert (
        root.find(
            "cac:SellerSupplierParty/cac:Party/cac:PartyName/cbc:Name",
            NS,
        ).text
        == "Digital Book Supply"
    )
    assert (
        root.find(
            "cac:SellerSupplierParty/cac:Party/cac:Contact/cbc:ElectronicMail",
            NS,
        ).text
        == "seller@example.com"
    )
    assert (
        root.find(
            "cac:BuyerCustomerParty/cac:Party/cac:PostalAddress/cbc:StreetName",
            NS,
        ).text
        == "123 Test St"
    )
    assert root.find("cac:SellerSupplierParty/cac:Party/cac:PostalAddress", NS) is None
    assert root.find("cac:Delivery/cac:DeliveryAddress/cbc:StreetName", NS).text == "123 Test St"
    assert root.find("cac:Delivery/cac:DeliveryAddress/cbc:CityName", NS).text == "Sydney"
    assert root.find("cac:Delivery/cac:DeliveryAddress/cbc:PostalZone", NS).text == "2000"
    assert root.find("cac:Delivery/cac:DeliveryAddress/cbc:CountrySubentity", NS).text == "NSW"
    assert (
        root.find(
            "cac:Delivery/cac:DeliveryAddress/cac:Country/cbc:IdentificationCode",
            NS,
        ).text
        == "AU"
    )
    assert (
        root.find(
            "cac:Delivery/cac:RequestedDeliveryPeriod/cbc:StartDate",
            NS,
        ).text
        == "2026-03-10"
    )

    order_lines = root.findall("cac:OrderLine", NS)
    assert len(order_lines) == 2
    assert order_lines[0].find("cac:LineItem/cbc:ID", NS).text == "1"
    assert order_lines[0].find("cac:LineItem/cbc:LineStatusCode", NS).text == "NoStatus"
    assert order_lines[0].find("cac:LineItem/cbc:Quantity", NS).attrib["unitCode"] == "EA"
    assert order_lines[0].find("cac:LineItem/cbc:LineExtensionAmount", NS).text == "25.00"
    assert (
        order_lines[0].find("cac:LineItem/cac:Price/cbc:PriceAmount", NS).attrib["currencyID"]
        == "AUD"
    )
    assert order_lines[0].find("cac:LineItem/cac:Price/cbc:BaseQuantity", NS).text == "2"
    assert order_lines[1].find("cac:LineItem/cbc:Quantity", NS).attrib["unitCode"] == "EA"
    assert order_lines[1].find("cac:LineItem/cbc:LineExtensionAmount", NS).text == "5.00"
    assert order_lines[1].find("cac:LineItem/cac:Price/cbc:PriceAmount", NS).text == "5.00"
    assert root.find("cac:AnticipatedMonetaryTotal/cbc:LineExtensionAmount", NS).text == "30.00"
    assert root.find("cac:AnticipatedMonetaryTotal/cbc:PayableAmount", NS).text == "30.00"


def test_generate_ubl_order_xml_uses_today_and_omits_absent_optional_elements(monkeypatch):
    class FakeDate:
        @staticmethod
        def today():
            return date(2026, 4, 1)

    monkeypatch.setattr(ubl_order, "date", FakeDate)

    req = OrderRequest(
        buyerEmail="buyer@example.com",
        buyerName="Acme Books",
        sellerEmail="seller@example.com",
        sellerName="Digital Book Supply",
        lines=[LineItem(productName="Refactoring", quantity=3, unitPrice="7.25")],
    )

    xml_text = ubl_order.generate_ubl_order_xml("ord_1234567890abcdef", req)

    root = ET.fromstring(xml_text)
    price_amount = root.find(".//cac:Price/cbc:PriceAmount", NS)

    assert root.find("cbc:IssueDate", NS).text == "2026-04-01"
    assert root.find("cac:TransactionConditions", NS) is None
    assert root.find("cac:Delivery", NS) is None
    assert price_amount.text == "7.25"
    assert price_amount.attrib["currencyID"] == "AUD"
    assert root.find("cbc:DocumentCurrencyCode", NS).text == "AUD"
    assert root.find("cac:AnticipatedMonetaryTotal/cbc:PayableAmount", NS).text == "21.75"


def test_generate_ubl_order_xml_omits_totals_when_no_line_has_price():
    req = OrderRequest(
        buyerEmail="buyer@example.com",
        buyerName="Acme Books",
        sellerEmail="seller@example.com",
        sellerName="Digital Book Supply",
        lines=[LineItem(productName="Refactoring", quantity=3, unitPrice=None)],
    )

    xml_text = ubl_order.generate_ubl_order_xml("ord_1234567890abcdef", req)

    root = ET.fromstring(xml_text)

    assert root.find("cac:AnticipatedMonetaryTotal", NS) is None
    assert root.find(".//cac:Price", NS) is None
    assert root.find(".//cbc:LineExtensionAmount", NS) is None


def test_generate_ubl_order_xml_wraps_serialization_failures(monkeypatch):
    req = OrderRequest(
        buyerEmail="buyer@example.com",
        buyerName="Acme Books",
        sellerEmail="seller@example.com",
        sellerName="Digital Book Supply",
        lines=[LineItem(productName="Refactoring", quantity=1)],
    )

    def fail_tostring(*args, **kwargs):
        raise TypeError("bad xml")

    monkeypatch.setattr(ubl_order, "tostring", fail_tostring)

    with pytest.raises(OrderGenerationError, match="Unable to generate UBL order XML."):
        ubl_order.generate_ubl_order_xml("ord_1234567890abcdef", req)

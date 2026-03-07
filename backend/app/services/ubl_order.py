from __future__ import annotations

from datetime import date
from uuid import uuid4
from xml.dom import minidom
from xml.etree.ElementTree import Element, SubElement, register_namespace, tostring
from xml.parsers.expat import ExpatError

from app.models.schemas import Delivery, LineItem, OrderRequest

NS_ORDER = "urn:oasis:names:specification:ubl:schema:xsd:Order-2"
NS_CBC = "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2"
NS_CAC = "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2"

register_namespace("", NS_ORDER)
register_namespace("cbc", NS_CBC)
register_namespace("cac", NS_CAC)


class OrderGenerationError(RuntimeError):
    pass


def _cbc(parent: Element, tag: str, text: str | None = None, **attrs) -> Element:
    el = SubElement(parent, f"{{{NS_CBC}}}{tag}", attrib={k: str(v) for k, v in attrs.items()})
    if text is not None:
        el.text = str(text)
    return el


def _cac(parent: Element, tag: str) -> Element:
    return SubElement(parent, f"{{{NS_CAC}}}{tag}")


def generate_order_id() -> str:
    try:
        return f"ord_{uuid4().hex[:16]}"
    except Exception as exc:
        raise OrderGenerationError("Unable to generate order identifier.") from exc


def _add_party(order: Element, role_tag: str, party_name: str) -> None:
    party = _cac(order, role_tag)
    party_node = _cac(party, "Party")
    party_name_node = _cac(party_node, "PartyName")
    _cbc(party_name_node, "Name", party_name)


def _add_delivery(order: Element, delivery: Delivery | None) -> None:
    if delivery is None:
        return

    delivery_node = _cac(order, "Delivery")
    address_node = _cac(delivery_node, "DeliveryAddress")

    if delivery.street:
        _cbc(address_node, "StreetName", delivery.street)
    if delivery.city:
        _cbc(address_node, "CityName", delivery.city)
    if delivery.postcode:
        _cbc(address_node, "PostalZone", delivery.postcode)
    if delivery.state:
        _cbc(address_node, "CountrySubentity", delivery.state)
    if delivery.country:
        country_node = _cac(address_node, "Country")
        _cbc(country_node, "IdentificationCode", delivery.country)
    if delivery.requestedDate:
        requested_period = _cac(delivery_node, "RequestedDeliveryPeriod")
        _cbc(requested_period, "StartDate", delivery.requestedDate.isoformat())


def _add_order_lines(order: Element, lines: list[LineItem], currency: str | None) -> None:
    for index, line in enumerate(lines, start=1):
        order_line = _cac(order, "OrderLine")
        line_item = _cac(order_line, "LineItem")
        _cbc(line_item, "ID", str(index))
        _cbc(line_item, "Quantity", str(line.quantity), unitCode=line.unitCode or "EA")

        if line.unitPrice is not None:
            price = _cac(line_item, "Price")
            if currency:
                _cbc(price, "PriceAmount", str(line.unitPrice), currencyID=currency)
            else:
                _cbc(price, "PriceAmount", str(line.unitPrice))

        item = _cac(line_item, "Item")
        _cbc(item, "Name", line.productName)


def generate_ubl_order_xml(order_id: str, req: OrderRequest) -> str:
    try:
        order = Element(f"{{{NS_ORDER}}}Order")

        _cbc(order, "UBLVersionID", "2.1")
        _cbc(order, "ID", order_id)
        _cbc(order, "IssueDate", (req.issueDate or date.today()).isoformat())
        if req.notes:
            _cbc(order, "Note", req.notes)

        _add_party(order, "BuyerCustomerParty", req.buyerName)
        _add_party(order, "SellerSupplierParty", req.sellerName)
        _add_delivery(order, req.delivery)
        _add_order_lines(order, req.lines, req.currency)

        xml_bytes = tostring(order, encoding="utf-8", xml_declaration=True)
        pretty = minidom.parseString(xml_bytes).toprettyxml(indent="  ", encoding="utf-8")
        return pretty.decode("utf-8")
    except (ExpatError, TypeError, ValueError) as exc:
        raise OrderGenerationError("Unable to generate UBL order XML.") from exc

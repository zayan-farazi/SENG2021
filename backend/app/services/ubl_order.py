from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import uuid4
from xml.etree.ElementTree import Element, SubElement, indent, register_namespace, tostring

from app.models.schemas import ORDER_REQUEST_EXAMPLE, Delivery, LineItem, OrderRequest

NS_ORDER = "urn:oasis:names:specification:ubl:schema:xsd:Order-2"
NS_CBC = "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2"
NS_CAC = "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2"
CUSTOMIZATION_ID = "urn:oasis:names:specification:ubl:xpath:Order-2.1:sbs-1.0"
PROFILE_ID = "bpid:urn:oasis:names:bpss:ubl-2-sbs-order-with-simple-response"
DEFAULT_CURRENCY = "AUD"
DOCS_EXAMPLE_ORDER_ID = "ord_abc123def456"
DOCS_EXAMPLE_UUID = "82DC44A7-262C-4A01-BE63-1CB133EAC0FF"

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


def _add_postal_address(parent: Element, delivery: Delivery | None) -> None:
    if delivery is None:
        return

    values = (
        delivery.street,
        delivery.city,
        delivery.postcode,
        delivery.state,
        delivery.country,
    )
    if not any(values):
        return

    address_node = _cac(parent, "PostalAddress")
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


def _add_party(
    order: Element,
    role_tag: str,
    *,
    party_name: str,
    contact_email: str,
    postal_delivery: Delivery | None = None,
) -> None:
    party = _cac(order, role_tag)
    party_node = _cac(party, "Party")
    party_name_node = _cac(party_node, "PartyName")
    _cbc(party_name_node, "Name", party_name)
    _add_postal_address(party_node, postal_delivery)

    contact_node = _cac(party_node, "Contact")
    _cbc(contact_node, "ElectronicMail", contact_email)


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


def _format_decimal(value: Decimal) -> str:
    return f"{value:.2f}"


def _line_extension_amount(line: LineItem) -> Decimal | None:
    if line.unitPrice is None:
        return None
    return line.unitPrice * line.quantity


def _add_order_lines(order: Element, lines: list[LineItem], currency: str) -> None:
    for index, line in enumerate(lines, start=1):
        order_line = _cac(order, "OrderLine")
        line_item = _cac(order_line, "LineItem")
        _cbc(line_item, "ID", str(index))
        _cbc(line_item, "LineStatusCode", "NoStatus")
        _cbc(line_item, "Quantity", str(line.quantity), unitCode=line.unitCode or "EA")

        extension = _line_extension_amount(line)
        if extension is not None:
            _cbc(line_item, "LineExtensionAmount", _format_decimal(extension), currencyID=currency)
            price = _cac(line_item, "Price")
            _cbc(price, "PriceAmount", _format_decimal(line.unitPrice), currencyID=currency)
            _cbc(price, "BaseQuantity", str(line.quantity), unitCode=line.unitCode or "EA")

        item = _cac(line_item, "Item")
        _cbc(item, "Name", line.productName)


def _add_monetary_total(order: Element, lines: list[LineItem], currency: str) -> None:
    extensions = [
        extension for line in lines if (extension := _line_extension_amount(line)) is not None
    ]
    if not extensions:
        return

    total = sum(extensions, start=Decimal("0"))
    total_node = _cac(order, "AnticipatedMonetaryTotal")
    _cbc(total_node, "LineExtensionAmount", _format_decimal(total), currencyID=currency)
    _cbc(total_node, "PayableAmount", _format_decimal(total), currencyID=currency)


def generate_ubl_order_xml(
    order_id: str,
    req: OrderRequest,
    *,
    document_uuid: str | None = None,
) -> str:
    try:
        order = Element(f"{{{NS_ORDER}}}Order")
        currency = req.currency or DEFAULT_CURRENCY

        _cbc(order, "UBLVersionID", "2.1")
        _cbc(order, "CustomizationID", CUSTOMIZATION_ID)
        _cbc(order, "ProfileID", PROFILE_ID)
        _cbc(order, "ID", order_id)
        _cbc(order, "CopyIndicator", "false")
        _cbc(order, "UUID", document_uuid or str(uuid4()).upper())
        _cbc(order, "IssueDate", (req.issueDate or date.today()).isoformat())
        _cbc(order, "DocumentCurrencyCode", currency)
        if req.notes:
            conditions = _cac(order, "TransactionConditions")
            _cbc(conditions, "Description", req.notes)

        _add_party(
            order,
            "BuyerCustomerParty",
            party_name=req.buyerName,
            contact_email=req.buyerEmail,
            postal_delivery=req.delivery,
        )
        _add_party(
            order,
            "SellerSupplierParty",
            party_name=req.sellerName,
            contact_email=req.sellerEmail,
        )
        _add_delivery(order, req.delivery)
        _add_monetary_total(order, req.lines, currency)
        _add_order_lines(order, req.lines, currency)

        indent(order, space="  ")
        xml_bytes = tostring(order, encoding="utf-8", xml_declaration=True)
        xml_text = xml_bytes.decode("utf-8")
        if xml_text.startswith("<?xml version='1.0' encoding='utf-8'?>"):
            xml_text = xml_text.replace(
                "<?xml version='1.0' encoding='utf-8'?>",
                '<?xml version="1.0" encoding="utf-8"?>',
                1,
            )
        return xml_text
    except (TypeError, ValueError) as exc:
        raise OrderGenerationError("Unable to generate UBL order XML.") from exc


def generate_docs_example_ubl_order_xml() -> str:
    req = OrderRequest.model_validate(ORDER_REQUEST_EXAMPLE)
    return generate_ubl_order_xml(
        DOCS_EXAMPLE_ORDER_ID,
        req,
        document_uuid=DOCS_EXAMPLE_UUID,
    )

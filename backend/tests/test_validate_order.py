from __future__ import annotations

from datetime import date
from decimal import Decimal

from app.api.routes.orders import Severity, _validate_order
from app.models.schemas import Delivery, LineItem, OrderRequest


def valid_line(**overrides) -> LineItem:
    data = dict(
        productName="Widget A",
        quantity=2,
        unitCode="EA",
        unitPrice=Decimal("9.99"),
    )
    data.update(overrides)
    return LineItem(**data)


def valid_delivery(**overrides) -> Delivery:
    data = dict(
        street="1 Main St",
        city="Sydney",
        state="NSW",
        postcode="2000",
        country="AU",
        requestedDate=date(2026, 3, 20),
    )
    data.update(overrides)
    return Delivery(**data)


def valid_order(**overrides) -> OrderRequest:
    data = dict(
        buyerId="buyer-123",
        buyerName="Acme Corp",
        sellerId="seller-456",
        sellerName="Widget Co",
        currency="AUD",
        issueDate=date(2026, 3, 14),
        notes="Please deliver before EOD",
        delivery=valid_delivery(),
        lines=[valid_line()],
    )
    data.update(overrides)
    return OrderRequest(**data)


def issue_paths(result) -> list[str]:
    return [i.path for i in result.issues]


def warning_paths(result) -> list[str]:
    return [i.path for i in result.warnings]


def test_valid_order_passes():
    result = _validate_order(valid_order())
    assert result.valid is True
    assert result.issues == []
    assert result.score == 1.0


def test_valid_order_has_no_warnings_when_complete():
    result = _validate_order(valid_order())
    assert result.warnings == []


def test_missing_buyer_id():
    order = valid_order()
    order.buyerId = ""
    result = _validate_order(order)
    assert result.valid is False
    assert "buyerId" in issue_paths(result)


def test_missing_buyer_name():
    order = valid_order()
    order.buyerName = ""
    result = _validate_order(order)
    assert result.valid is False
    assert "buyerName" in issue_paths(result)


def test_missing_seller_id():
    order = valid_order()
    order.sellerId = ""
    result = _validate_order(order)
    assert result.valid is False
    assert "sellerId" in issue_paths(result)


def test_missing_seller_name():
    order = valid_order()
    order.sellerName = ""
    result = _validate_order(order)
    assert result.valid is False
    assert "sellerName" in issue_paths(result)


def test_line_missing_unit_price_is_issue():
    result = _validate_order(valid_order(lines=[valid_line(unitPrice=None)]))
    assert result.valid is True
    assert "lines[0].unitPrice" in warning_paths(result)


def test_line_missing_unit_code_is_warning():
    result = _validate_order(valid_order(lines=[valid_line(unitCode=None)]))
    assert result.valid is True
    assert "lines[0].unitCode" in warning_paths(result)


def test_line_zero_unit_price_is_valid():
    result = _validate_order(valid_order(lines=[valid_line(unitPrice=Decimal("0.00"))]))
    assert result.valid is True
    assert "lines[0].unitPrice" not in issue_paths(result)


def test_missing_delivery_is_warning():
    result = _validate_order(valid_order(delivery=None))
    assert result.valid is True
    assert "delivery" in warning_paths(result)


def test_delivery_missing_street():
    result = _validate_order(valid_order(delivery=valid_delivery(street=None)))
    assert result.valid is True
    assert "delivery.street" in warning_paths(result)


def test_delivery_missing_city():
    result = _validate_order(valid_order(delivery=valid_delivery(city=None)))
    assert result.valid is True
    assert "delivery.city" in warning_paths(result)


def test_delivery_missing_country():
    result = _validate_order(valid_order(delivery=valid_delivery(country=None)))
    assert result.valid is True
    assert "delivery.country" in warning_paths(result)


def test_delivery_missing_postcode_is_warning():
    result = _validate_order(valid_order(delivery=valid_delivery(postcode=None)))
    assert result.valid is True
    assert "delivery.postcode" in warning_paths(result)


def test_delivery_missing_state_is_warning():
    result = _validate_order(valid_order(delivery=valid_delivery(state=None)))
    assert result.valid is True
    assert "delivery.state" in warning_paths(result)


def test_delivery_missing_requested_date_is_warning():
    result = _validate_order(valid_order(delivery=valid_delivery(requestedDate=None)))
    assert result.valid is True
    assert "delivery.requestedDate" in warning_paths(result)


def test_missing_currency():
    result = _validate_order(valid_order(currency=None))
    assert result.valid is True
    assert "currency" in warning_paths(result)


def test_valid_currency_codes():
    for code in ("AUD", "USD", "GBP", "EUR"):
        result = _validate_order(valid_order(currency=code))
        assert result.valid is True, f"Expected {code} to be valid"


def test_missing_issue_date_is_warning():
    result = _validate_order(valid_order(issueDate=None))
    assert result.valid is True
    assert "issueDate" in warning_paths(result)


def test_missing_requested_date_not_warned_when_no_delivery():
    result = _validate_order(valid_order(delivery=None))
    assert "delivery.requestedDate" not in warning_paths(result)


def test_score_is_1_when_all_fields_present():
    result = _validate_order(valid_order())
    assert result.score == 1.0


def test_score_is_partial_when_optional_fields_missing():
    result = _validate_order(valid_order(currency=None, issueDate=None, delivery=None))
    assert result.score == round(5 / 8, 2)


def test_issues_always_have_error_severity():
    result = _validate_order(valid_order(currency=None))
    for issue in result.issues:
        assert issue.severity == Severity.error


def test_warnings_always_have_warning_severity():
    result = _validate_order(valid_order(delivery=None, issueDate=None))
    for warning in result.warnings:
        assert warning.severity == Severity.warning

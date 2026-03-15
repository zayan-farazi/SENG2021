from datetime import datetime

from app.services.analytics_service import get_user_analytics


def test_seller_only_analytics(monkeypatch):

    orders = [
        {"id": 1, "status": "Complete", "issuedate": "2026-03-01"},
        {"id": 2, "status": "Pending", "issuedate": "2026-03-02"},
    ]

    order_lines = {
        1: [{"unitprice": 10, "quantity": 2, "unitcode": "A1", "productname": "Apple"}],
        2: [{"unitprice": 20, "quantity": 1, "unitcode": "B1", "productname": "Banana"}],
    }

    def mock_findOrders(**kwargs):
        if kwargs.get("selleremail"):
            return orders
        return []

    monkeypatch.setattr("app.services.analytics_service.findOrders", mock_findOrders)
    monkeypatch.setattr(
        "app.services.analytics_service.findOrderDetailsByOrderIds",
        lambda order_ids: {order_id: order_lines[order_id] for order_id in order_ids},
    )

    result = get_user_analytics(
        username="seller@test.com",
        fromDate=datetime(2026, 3, 1),
        toDate=datetime(2026, 3, 5),
    )

    assert result["role"] == "seller"
    assert result["analytics"]["totalOrders"] == 2
    assert result["analytics"]["itemsSold"] == 3.0
    assert result["analytics"]["totalIncome"] == 40
    assert result["analytics"]["averageDailyOrders"] == 0.4
    assert result["analytics"]["averageDailyIncome"] == 8.0


def test_buyer_only_analytics(monkeypatch):

    orders = [
        {"id": 1, "status": "Complete", "issuedate": "2026-03-01"},
    ]

    order_lines = {
        1: [{"unitprice": 15, "quantity": 2}],
    }

    def mock_findOrders(**kwargs):
        if kwargs.get("buyeremail"):
            return orders
        return []

    monkeypatch.setattr("app.services.analytics_service.findOrders", mock_findOrders)
    monkeypatch.setattr(
        "app.services.analytics_service.findOrderDetailsByOrderIds",
        lambda order_ids: {order_id: order_lines[order_id] for order_id in order_ids},
    )

    result = get_user_analytics(
        username="buyer@test.com",
        fromDate=datetime(2026, 3, 1),
        toDate=datetime(2026, 3, 5),
    )

    assert result["role"] == "buyer"
    assert result["analytics"]["totalSpent"] == 30
    assert result["analytics"]["itemsBought"] == 2.0
    assert result["analytics"]["averageDailyOrders"] == 0.2
    assert result["analytics"]["averageDailySpend"] == 6.0


def test_buyer_and_seller(monkeypatch):

    seller_orders = [
        {"id": 1, "status": "Complete", "issuedate": "2026-03-01"},
    ]

    buyer_orders = [
        {"id": 2, "status": "Complete", "issuedate": "2026-03-02"},
    ]

    order_lines = {
        1: [{"unitprice": 20, "quantity": 1, "unitcode": "A", "productname": "ItemA"}],
        2: [{"unitprice": 5, "quantity": 2}],
    }

    def mock_findOrders(**kwargs):
        if kwargs.get("selleremail"):
            return seller_orders
        if kwargs.get("buyeremail"):
            return buyer_orders
        return []

    monkeypatch.setattr("app.services.analytics_service.findOrders", mock_findOrders)
    monkeypatch.setattr(
        "app.services.analytics_service.findOrderDetailsByOrderIds",
        lambda order_ids: {order_id: order_lines[order_id] for order_id in order_ids},
    )

    result = get_user_analytics(
        username="user@test.com",
        fromDate=datetime(2026, 3, 1),
        toDate=datetime(2026, 3, 5),
    )

    assert result["role"] == "buyer_and_seller"
    assert result["sellerAnalytics"]["totalIncome"] == 20
    assert result["buyerAnalytics"]["totalSpent"] == 10
    assert result["netProfit"] == 10
    assert result["sellerAnalytics"]["averageDailyOrders"] == 0.2
    assert result["buyerAnalytics"]["averageDailyOrders"] == 0.2


def test_no_orders(monkeypatch):

    def mock_findOrders(**kwargs):
        return []

    monkeypatch.setattr("app.services.analytics_service.findOrders", mock_findOrders)

    result = get_user_analytics(
        username="user@test.com",
        fromDate=datetime(2026, 3, 1),
        toDate=datetime(2026, 3, 5),
    )

    assert result["message"] == "No orders found"


def test_seller_analytics_handles_orders_without_details(monkeypatch):
    orders = [
        {"id": 1, "status": "DRAFT", "issuedate": "2026-03-01"},
    ]

    monkeypatch.setattr(
        "app.services.analytics_service.findOrders",
        lambda **kwargs: orders if kwargs.get("selleremail") else [],
    )
    monkeypatch.setattr(
        "app.services.analytics_service.findOrderDetailsByOrderIds",
        lambda order_ids: {order_id: [] for order_id in order_ids},
    )

    result = get_user_analytics(
        username="seller@test.com",
        fromDate=datetime(2026, 3, 1),
        toDate=datetime(2026, 3, 1),
    )

    assert result["analytics"]["ordersPending"] == 1
    assert result["analytics"]["mostPopularProductSales"] == 0
    assert result["analytics"]["averageDailyOrders"] == 1.0

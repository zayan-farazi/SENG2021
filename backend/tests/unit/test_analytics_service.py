from datetime import datetime

from app.services.analytics_service import get_user_analytics


class MockResponse:
    def __init__(self, data):
        self.data = data
        self.count = len(data)


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
            return MockResponse(orders)
        return MockResponse([])

    def mock_findOrderDetails(order_id):
        return MockResponse(order_lines[order_id])

    monkeypatch.setattr("app.services.analytics_service.findOrders", mock_findOrders)
    monkeypatch.setattr("app.services.analytics_service.findOrderDetails", mock_findOrderDetails)

    result = get_user_analytics(
        username="seller@test.com",
        fromDate=datetime(2026, 3, 1),
        toDate=datetime(2026, 3, 5),
    )

    assert result["role"] == "seller"
    assert result["analytics"]["totalOrders"] == 2
    assert result["analytics"]["itemsSold"] == 3
    assert result["analytics"]["totalIncome"] == 40


def test_buyer_only_analytics(monkeypatch):

    orders = [
        {"id": 1, "status": "Complete", "issuedate": "2026-03-01"},
    ]

    order_lines = {
        1: [{"unitprice": 15, "quantity": 2}],
    }

    def mock_findOrders(**kwargs):
        if kwargs.get("buyeremail"):
            return MockResponse(orders)
        return MockResponse([])

    def mock_findOrderDetails(order_id):
        return MockResponse(order_lines[order_id])

    monkeypatch.setattr("app.services.analytics_service.findOrders", mock_findOrders)
    monkeypatch.setattr("app.services.analytics_service.findOrderDetails", mock_findOrderDetails)

    result = get_user_analytics(
        username="buyer@test.com",
        fromDate=datetime(2026, 3, 1),
        toDate=datetime(2026, 3, 5),
    )

    assert result["role"] == "buyer"
    assert result["analytics"]["totalSpent"] == 30
    assert result["analytics"]["itemsBought"] == 2


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
            return MockResponse(seller_orders)
        if kwargs.get("buyeremail"):
            return MockResponse(buyer_orders)
        return MockResponse([])

    def mock_findOrderDetails(order_id):
        return MockResponse(order_lines[order_id])

    monkeypatch.setattr("app.services.analytics_service.findOrders", mock_findOrders)
    monkeypatch.setattr("app.services.analytics_service.findOrderDetails", mock_findOrderDetails)

    result = get_user_analytics(
        username="user@test.com",
        fromDate=datetime(2026, 3, 1),
        toDate=datetime(2026, 3, 5),
    )

    assert result["role"] == "buyer_and_seller"
    assert result["sellerAnalytics"]["totalIncome"] == 20
    assert result["buyerAnalytics"]["totalSpent"] == 10
    assert result["netProfit"] == 10


def test_no_orders(monkeypatch):

    def mock_findOrders(**kwargs):
        return MockResponse([])

    monkeypatch.setattr("app.services.analytics_service.findOrders", mock_findOrders)

    result = get_user_analytics(
        username="user@test.com",
        fromDate=datetime(2026, 3, 1),
        toDate=datetime(2026, 3, 5),
    )

    assert result["message"] == "No orders found"

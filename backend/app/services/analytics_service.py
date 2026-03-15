from __future__ import annotations

from datetime import datetime
from typing import Any

from app.other import findOrderDetailsByOrderIds, findOrders


def _round_metric(value: float) -> float:
    return round(value, 2)


def _normalize_quantity(value: Any) -> float:
    if value is None:
        return 0.0
    return float(value)


def get_user_analytics(username: str, fromDate: datetime | None, toDate: datetime | None):
    if fromDate is None or toDate is None:
        raise ValueError("fromDate and toDate must be provided")

    seller_orders = findOrders(selleremail=username, fromDate=fromDate, toDate=toDate)
    buyer_orders = findOrders(buyeremail=username, fromDate=fromDate, toDate=toDate)

    seller_exists = len(seller_orders) > 0
    buyer_exists = len(buyer_orders) > 0

    seller_data = None
    buyer_data = None

    if seller_exists:
        seller_data = calculate_seller_analytics(seller_orders, fromDate, toDate)

    if buyer_exists:
        buyer_data = calculate_buyer_analytics(buyer_orders, fromDate, toDate)

    if seller_exists and buyer_exists:
        return {
            "role": "buyer_and_seller",
            "sellerAnalytics": seller_data,
            "buyerAnalytics": buyer_data,
            "netProfit": _round_metric(seller_data["totalIncome"] - buyer_data["totalSpent"]),
        }

    if seller_exists:
        return {"role": "seller", "analytics": seller_data}

    if buyer_exists:
        return {"role": "buyer", "analytics": buyer_data}

    return {"message": "No orders found"}


def calculate_seller_analytics(res, fromDate, toDate):
    totalIncome = 0.0
    itemsSold = 0.0
    ordersPending = 0
    ordersComplete = 0
    ordersCancelled = 0
    productFreq: dict[str, dict[str, float]] = {}
    dateFreq: dict[str, int] = {}
    numDays = max((toDate - fromDate).days + 1, 1)

    order_details = _details_by_order_id(res)

    for order in res:
        data = order_details.get(order["id"], [])

        for line in data:
            quantity = _normalize_quantity(line.get("quantity"))
            unit_price = float(line.get("unitprice") or 0.0)
            totalIncome += unit_price * quantity
            itemsSold += quantity

            code = line.get("unitcode")
            name = line.get("productname")
            if code and name:
                productFreq.setdefault(code, {})
                productFreq[code][name] = productFreq[code].get(name, 0.0) + quantity

        status = (order.get("status") or "").upper()
        if status in {"PENDING", "DRAFT"}:
            ordersPending += 1
        elif status in {"COMPLETE", "COMPLETED", "SUBMITTED"}:
            ordersComplete += 1
        elif status == "CANCELLED":
            ordersCancelled += 1

        date = order.get("issuedate")
        if isinstance(date, str) and date:
            dateFreq[date] = dateFreq.get(date, 0) + 1

    highestCode = None
    highestProd = None
    highestDaySales = None

    if productFreq:
        highestCode = max(productFreq, key=lambda key: max(productFreq[key].values()))
        highestProd = max(productFreq[highestCode], key=productFreq[highestCode].get)

    if dateFreq:
        highestDaySales = max(dateFreq, key=dateFreq.get)

    return {
        "totalOrders": len(res),
        "totalIncome": _round_metric(totalIncome),
        "itemsSold": _round_metric(itemsSold),
        "averageItemSoldPrice": _round_metric(totalIncome / itemsSold) if itemsSold else 0,
        "averageOrderAmount": _round_metric(totalIncome / len(res)) if res else 0,
        "averageOrderItemNumber": _round_metric(itemsSold / len(res)) if res else 0,
        "averageDailyIncome": _round_metric(totalIncome / numDays),
        "averageDailyOrders": _round_metric(len(res) / numDays),
        "ordersPending": ordersPending,
        "ordersCompleted": ordersComplete,
        "ordersCancelled": ordersCancelled,
        "mostSuccessfulDay": highestDaySales,
        "mostSalesMade": dateFreq.get(highestDaySales, 0),
        "mostPopularProductCode": highestCode,
        "mostPopularProductName": highestProd,
        "mostPopularProductSales": (
            _round_metric(productFreq[highestCode][highestProd])
            if highestCode and highestProd
            else 0
        ),
    }


def calculate_buyer_analytics(res, fromDate, toDate):
    totalSpent = 0.0
    itemsBought = 0.0
    numDays = max((toDate - fromDate).days + 1, 1)

    order_details = _details_by_order_id(res)

    for order in res:
        for line in order_details.get(order["id"], []):
            quantity = _normalize_quantity(line.get("quantity"))
            unit_price = float(line.get("unitprice") or 0.0)
            totalSpent += unit_price * quantity
            itemsBought += quantity

    return {
        "totalOrders": len(res),
        "totalSpent": _round_metric(totalSpent),
        "itemsBought": _round_metric(itemsBought),
        "averageItemPrice": _round_metric(totalSpent / itemsBought) if itemsBought else 0,
        "averageOrderAmount": _round_metric(totalSpent / len(res)) if res else 0,
        "averageItemsPerOrder": _round_metric(itemsBought / len(res)) if res else 0,
        "averageDailySpend": _round_metric(totalSpent / numDays),
        "averageDailyOrders": _round_metric(len(res) / numDays),
    }


def _details_by_order_id(orders: list[dict[str, Any]]) -> dict[int | str, list[dict]]:
    order_ids = [order.get("id") for order in orders if order.get("id") is not None]
    return findOrderDetailsByOrderIds(order_ids)

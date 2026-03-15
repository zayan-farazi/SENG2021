from datetime import datetime

from app.other import findOrders, findOrderDetails

def get_user_analytics(username: str, fromDate: datetime | None, toDate: datetime | None):

    if fromDate is None or toDate is None:
      raise ValueError("fromDate and toDate must be provided")

    seller_orders = findOrders(selleremail=username, fromDate=fromDate, toDate=toDate)
    buyer_orders = findOrders(buyeremail=username, fromDate=fromDate, toDate=toDate)

    seller_exists = seller_orders.count > 0
    buyer_exists = buyer_orders.count > 0

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
            "netProfit": seller_data["totalIncome"] - buyer_data["totalSpent"],
        }

    if seller_exists:
        return {"role": "seller", "analytics": seller_data}

    if buyer_exists:
        return {"role": "buyer", "analytics": buyer_data}

    return {"message": "No orders found"}

def calculate_seller_analytics(res, fromDate, toDate):

    totalIncome = 0
    itemsSold = 0
    ordersPending = 0
    ordersComplete = 0
    ordersCancelled = 0

    productFreq = {}
    dateFreq = {}

    for order in res.data:

        orderLines = findOrderDetails(order["id"])
        data = orderLines.data

        for line in data:

            totalIncome += line["unitprice"] * line["quantity"]
            itemsSold += line["quantity"]

            code = line["unitcode"]
            name = line["productname"]

            if code not in productFreq:
                productFreq[code] = {}

            if name not in productFreq[code]:
                productFreq[code][name] = 0

            productFreq[code][name] += line["quantity"]

        if order["status"] == "Pending":
            ordersPending += 1
        elif order["status"] == "Complete":
            ordersComplete += 1
        elif order["status"] == "Cancelled":
            ordersCancelled += 1

        date = order["issuedate"]

        if date not in dateFreq:
            dateFreq[date] = 0

        dateFreq[date] += 1

        highestCode = None
        highestProd = None
        highestDaySales = None

        if productFreq:
            highestCode = max(productFreq, key=lambda k: max(productFreq[k].values()))
            highestProd = max(productFreq[highestCode], key=productFreq[highestCode].get)

        if dateFreq:
            highestDaySales = max(dateFreq, key=dateFreq.get)
        
        numDays = max((toDate - fromDate).days + 1, 1)

    return {
        "totalOrders": res.count,
        "totalIncome": totalIncome,
        "itemsSold": itemsSold,
        "averageItemSoldPrice": totalIncome / itemsSold if itemsSold else 0 ,
        "averageOrderAmount": totalIncome / res.count if itemsSold else 0,
        "averageOrderItemNumber": itemsSold / res.count if itemsSold else 0,
        "averageDailyIncome": totalIncome / numDays,
        "averageDailyOrders": res.count / numDays,
        "ordersPending": ordersPending,
        "ordersCompleted": ordersComplete,
        "ordersCancelled": ordersCancelled,
        "mostSuccessfulDay": highestDaySales,
        "mostSalesMade": dateFreq.get(highestDaySales, 0),
        "mostPopularProductCode": highestCode,
        "mostPopularProductName": highestProd,
        "mostPopularProductSales": productFreq[highestCode][highestProd],
    }

def calculate_buyer_analytics(res, fromDate, toDate):

    totalSpent = 0
    itemsBought = 0

    for order in res.data:

        orderLines = findOrderDetails(order["id"])

        for line in orderLines.data:

            totalSpent += line["unitprice"] * line["quantity"]
            itemsBought += line["quantity"]

    numDays = max((toDate - fromDate).days + 1, 1)

    return {
        "totalOrders": res.count,
        "totalSpent": totalSpent,
        "itemsBought": itemsBought,
        "averageItemPrice": totalSpent / itemsBought if itemsBought else 0,
        "averageOrderAmount": totalSpent / res.count if itemsBought else 0,
        "averageItemsPerOrder": itemsBought / res.count if itemsBought else 0,
        "averageDailySpend": totalSpent / numDays,
        "averageDailyOrders": res.count / numDays,
    }


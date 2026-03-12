from datetime import datetime

from app.other import findOrderDetails, findOrders


def get_user_analytics_seller(username: str, fromDate: datetime | None, toDate: datetime | None):

    res = findOrders(username, fromDate=fromDate, toDate=toDate)

    if res.count == 0:
        return {}

    totalIncome = 0
    itemsSold = 0
    ordersPending = 0
    ordersComplete = 0
    ordersCancelled = 0
    productFreq = {}
    dateFreq = {}

    for j in range(res.count):
        orderLines = findOrderDetails(res.data[j]["id"])
        order = res.data[j]
        data = orderLines.data

        for i in range(orderLines.count):
            lineInfo = data[i]
            totalIncome = totalIncome + lineInfo["unitprice"] * lineInfo["quantity"]
            itemsSold = itemsSold + lineInfo["quantity"]

            if lineInfo["unitcode"] not in productFreq:
                productFreq[lineInfo["unitcode"]] = {}

            if lineInfo["productname"] not in productFreq[lineInfo["unitcode"]]:
                productFreq[lineInfo["unitcode"]][lineInfo["productname"]] = 0

            productFreq[lineInfo["unitcode"]][lineInfo["productname"]] += lineInfo["quantity"]

        if order["status"] == "Pending":
            ordersPending += 1
        if order["status"] == "Complete":
            ordersComplete += 1
        if order["status"] == "Cancelled":
            ordersCancelled += 1

        if order["issuedate"] not in dateFreq:
            dateFreq[order["issuedate"]] = 0

        dateFreq[order["issuedate"]] += 1

    highestCode = max(productFreq, key=lambda k: max(productFreq[k].values()))
    highestProd = max(productFreq[highestCode], key=productFreq[highestCode].get)

    highestDaySales = max(dateFreq, key=(dateFreq.get))
    numDays = (toDate - fromDate).days

    return {
        "totalOrders": res.count,
        "totalIncome": totalIncome,
        "itemsSold": itemsSold,
        "averageItemSoldPrice": totalIncome / itemsSold,
        "averageOrderAmount": totalIncome / res.count,
        "averageOrderItemNumber": itemsSold / res.count,
        "averageDailyIncome": totalIncome / numDays,
        "averageDailyOrders": res.count / numDays,
        "ordersPending": ordersPending,
        "ordersCompleted": ordersComplete,
        "ordersCancelled": ordersCancelled,
        "mostSuccessfulDay": highestDaySales,
        "mostSalesMade": dateFreq[highestDaySales],
        "mostPopularProductCode": highestCode,
        "mostPopularProductName": highestProd,
        "mostPopularProductSales": productFreq[highestCode][highestProd],
    }

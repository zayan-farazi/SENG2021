import datetime
import os

from supabase import Client, create_client

SUPABASE_URL = os.getenv["SUPABASE_URL"]
SUPABASE_KEY = os.getenv["SUPABASE_KEY"]

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# how to save order example
"""
    this works but pls make sure all details are correct before running the functions
    and do a try except so we don't up w rubbish data / duplicate info

    # default currency is AUD
    # default issue date is today
    # default status is Pending

    orderid = saveOrder(
        "Rita",
        "Tina",
        "321 Road",
        "Sydney",
        344,
        "Australia",
        "pls work",
        datetime.datetime.now().isoformat(),
        "Pending",
    )
    saveOrderDetails(orderid, "pears", "def", 5.9, 9.8)
    return findOrders(orderId="12")

"""


# saves or updates order information and returns order Id
# creates an entry when orderid is empty, updates existing entry otherwise
# saves or updates order information and returns order Id
# creates an entry when orderid is empty, updates existing entry otherwise
def saveOrder(
    buyername,
    sellername,
    deliverystreet,
    deliverycity,
    deliverypostcode,
    deliverycountry,
    notes,
    issueDate=None,
    status=None,
    currency=None,
    orderId=None,
):
    query = {
        "buyername": buyername,
        "sellername": sellername,
        "deliverystreet": deliverystreet,
        "deliverycity": deliverycity,
        "deliverypostcode": deliverypostcode,
        "deliverycountry": deliverycountry,
        "notes": notes,
        "lastchanged": datetime.datetime.now().isoformat(),
    }

    if orderId is None:
        if issueDate is None:
            issueDate = datetime.datetime.now().isoformat()
        query["issuedate"] = issueDate

        if status is None:
            status = "Pending"
        if currency is None:
            currency = "AUD"
    else:
        query["id"] = orderId

    query["status"] = status
    query["currency"] = "AUD"

    try:
        response = supabase.table("orders").upsert(query).execute()
        return response.data[0]["id"]
    except Exception as e:
        raise RuntimeError(f"Failed to save order: {e}") from e


# saves a single line of order details, does not return anything
# NEEDS ORDER ID TO ATTATCH TO
def saveOrderDetails(orderId, productName, unitCode, quantity, unitPrice):
    if orderId is None:
        raise ValueError("Failed to parse order details: orderId can't be empty")

    query = {
        "orderid": orderId,
        "productname": productName,
        "unitcode": unitCode,
        "quantity": float(quantity),
        "unitprice": float(unitPrice),
    }

    try:
        supabase.table("orderdetails").upsert(query).execute()
    except Exception as e:
        raise RuntimeError(f"Failed to save or update order details: {e}") from e


# (greedily) returns all tuples mathing the filter(s).
# must write the variable name as all fields have empty default values
# if there are several matches, it returns list (up to 1000 tuples)
# if there is only one match, it returns it as well as its order line list
def findOrders(
    orderId=None,
    buyername=None,
    sellername=None,
    deliverystreet=None,
    deliverycity=None,
    deliverypostcode=None,
    deliverycountry=None,
    notes=None,
    issueDate=None,
    lastChanged=None,
    status=None,
):
    query = supabase.table("orders").select("*", count="exact")

    if orderId:
        query = query.eq("id", orderId)
    if buyername:
        query = query.eq("buyername", buyername)
    if sellername:
        query = query.eq("sellername", sellername)
    if deliverystreet:
        query = query.eq("deliverystreet", deliverystreet)
    if deliverycity:
        query = query.eq("deliverycity", deliverycity)
    if deliverypostcode:
        query = query.eq("deliverypostcode", deliverypostcode)
    if deliverycountry:
        query = query.eq("deliverycountry", deliverycountry)
    if notes:
        query = query.ilike("notes", notes)
    if status:
        query = query.eq("status", status)
    if issueDate:
        query = query.eq("issuedate", issueDate)
    if lastChanged:
        query = query.eq("lastchanged", lastChanged)
    if status:
        query = query.eq("status", status)

    res = query.execute()
    orders = res.data

    if res.count == 1:
        details = findOrderDetails(orders[0]["id"])
        orders[0]["details"] = details.data

    return orders


# looks for order detail list through order id
def findOrderDetails(orderId):
    return (
        supabase.table("orderdetails")
        .select("productname", "unitcode", "quantity", "unitprice")
        .eq("orderid", orderId)
        .execute()
    )


# deletes all order lines related to a query
def deleteOrderDetails(orderId):
    return supabase.table("orderdetails").delete().eq("orderid", orderId).execute()


# deletes given order (including order details)
def deleteOrder(orderId):
    return supabase.table("orders").delete().eq("id", orderId).execute()

# mostly for debug purposes, returns all information stored in both databases
def DBInfo():
    orders = supabase.table("orders").select("*").execute()
    orderDetails = supabase.table("orderdetails").select("*").execute()
    return orders, orderDetails

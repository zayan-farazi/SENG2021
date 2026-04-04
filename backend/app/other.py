import os
from datetime import datetime

import httpx
from supabase import Client, create_client
from supabase.lib.client_options import SyncClientOptions

from app.env import load_local_env_files

_SUPABASE_CLIENT: Client | None = None
_SUPABASE_HTTPX_CLIENT: httpx.Client | None = None


def get_supabase_client() -> Client:
    global _SUPABASE_CLIENT, _SUPABASE_HTTPX_CLIENT

    if _SUPABASE_CLIENT is None:
        load_local_env_files()
        supabase_url = os.getenv("SUPABASE_URL")
        supabase_key = os.getenv("SUPABASE_KEY")
        if not supabase_url:
            raise RuntimeError("SUPABASE_URL is not configured.")
        if not supabase_key:
            raise RuntimeError("SUPABASE_KEY is not configured.")
        _SUPABASE_HTTPX_CLIENT = httpx.Client(timeout=120.0)
        options = SyncClientOptions(httpx_client=_SUPABASE_HTTPX_CLIENT)
        _SUPABASE_CLIENT = create_client(supabase_url, supabase_key, options=options)

    return _SUPABASE_CLIENT


def close_supabase_client() -> None:
    global _SUPABASE_CLIENT, _SUPABASE_HTTPX_CLIENT

    if _SUPABASE_HTTPX_CLIENT is not None:
        _SUPABASE_HTTPX_CLIENT.close()

    _SUPABASE_CLIENT = None
    _SUPABASE_HTTPX_CLIENT = None


# how to save order example
# this works but pls make sure all details are correct before running the functions
# and do a try except so we don't up w rubbish data / duplicate info

# default currency is AUD
# default issue date is today
# default status is Pending

"""
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
def saveOrder(
    buyeremail,
    buyername,
    selleremail,
    sellername,
    deliverystreet,
    deliverycity,
    deliverystate,
    deliverypostcode,
    deliverycountry,
    requesteddate,
    notes,
    issueDate=None,
    status=None,
    currency=None,
    externalOrderId=None,
    ublXml=None,
    createdAt=None,
    updatedAt=None,
    orderId=None,
):
    query = {
        "buyer_id": buyeremail,
        "seller_id": selleremail,
        "deliverystreet": deliverystreet,
        "deliverycity": deliverycity,
        "deliverystate": deliverystate,
        "deliverypostcode": deliverypostcode,
        "deliverycountry": deliverycountry,
        "requesteddate": requesteddate,
        "notes": notes,
        "lastchanged": updatedAt or datetime.now().isoformat(),
    }

    if orderId is None:
        if issueDate is None:
            issueDate = datetime.now()
        query["issuedate"] = issueDate.isoformat()

        if status is None:
            status = "Pending"
        if currency is None:
            currency = "AUD"
    else:
        query["id"] = orderId
    if issueDate is not None:
        query["issuedate"] = issueDate.isoformat()
    if status is not None:
        query["status"] = status
    if currency is not None:
        query["currency"] = currency
    if externalOrderId is not None:
        query["order_id"] = externalOrderId
    if ublXml is not None:
        query["ublxml"] = ublXml
    if createdAt is not None:
        query["createdat"] = createdAt
    if updatedAt is not None:
        query["updatedat"] = updatedAt

    # TODO remove if conditions when people have changeed their functions

    if buyeremail:
        query["buyer_id"] = buyeremail
    if selleremail:
        query["seller_id"] = selleremail

    try:
        response = get_supabase_client().table("orders").upsert(query).execute()
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
    }
    if unitPrice is not None:
        query["unitprice"] = float(unitPrice)

    try:
        get_supabase_client().table("orderdetails").upsert(query).execute()
    except Exception as e:
        raise RuntimeError(f"Failed to save order details: {e}") from e


# (greedily) returns all tuples matching the filter(s).
# must write the variable name as all fields have empty default values
# if there are matches, it returns list (up to 1000 tuples)
# res.count gives you the total number of tuples, even if >1000
def findOrders(
    orderId=None,
    externalOrderId=None,
    buyeremail=None,
    buyername=None,
    selleremail=None,
    sellername=None,
    deliverystreet=None,
    deliverycity=None,
    deliverypostcode=None,
    deliverycountry=None,
    notes=None,
    issueDate=None,
    lastChanged=None,
    status=None,
    fromDate: datetime | None = None,
    toDate: datetime | None = None,
):
    query = get_supabase_client().table("orders").select("*", count="exact")

    if orderId:
        query = query.eq("id", orderId)
    if externalOrderId:
        query = query.eq("order_id", externalOrderId)
    if buyeremail:
        query = query.eq("buyer_id", buyeremail)
    if selleremail:
        query = query.eq("seller_id", selleremail)
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
    if fromDate:
        query = query.gte("issuedate", fromDate.isoformat())
    if toDate:
        query = query.lte("issuedate", toDate.isoformat())

    res = query.execute()
    return res.data


def findOrderByExternalId(externalOrderId):
    orders = findOrders(externalOrderId=externalOrderId)
    if not orders:
        return None

    order = dict(orders[0])
    details = findOrderDetails(order["id"])
    order["details"] = details.data
    order["count"] = details.count
    return order


# looks for order detail list through order id
def findOrderDetails(orderId):
    return (
        get_supabase_client()
        .table("orderdetails")
        .select("productname", "unitcode", "quantity", "unitprice", count="exact")
        .eq("orderid", orderId)
        .execute()
    )


def findOrderDetailsByOrderIds(orderIds: list[int | str]) -> dict[int | str, list[dict]]:
    normalized_ids = [order_id for order_id in orderIds if order_id is not None]
    if not normalized_ids:
        return {}

    response = (
        get_supabase_client()
        .table("orderdetails")
        .select("orderid,productname,unitcode,quantity,unitprice")
        .in_("orderid", normalized_ids)
        .execute()
    )

    grouped: dict[int | str, list[dict]] = {order_id: [] for order_id in normalized_ids}
    for row in response.data or []:
        grouped.setdefault(row["orderid"], []).append(row)
    return grouped


def findPartyByContactEmail(contactEmail):
    response = (
        get_supabase_client()
        .table("parties")
        .select("*")
        .eq("contact_email", contactEmail)
        .execute()
    )
    row = response.data[0] if response.data else None
    return _with_party_identity_alias(row)


def findPartyByPartyId(partyId):
    # `partyId` is kept as a public API compatibility field, but the persisted
    # identity is now the normalized contact email.
    return findPartyByContactEmail(partyId)


def findAppKeyByHash(keyHash):
    response = get_supabase_client().table("parties").select("*").eq("key_hash", keyHash).execute()
    row = response.data[0] if response.data else None
    return _with_party_identity_alias(row)


def saveParty(partyId, partyName, contactEmail):
    response = (
        get_supabase_client()
        .table("parties")
        .insert({"party_name": partyName, "contact_email": contactEmail})
        .execute()
    )
    return _with_party_identity_alias(response.data[0] if response.data else None)


def saveAppKey(partyId, keyHash):
    response = (
        get_supabase_client()
        .table("parties")
        .update({"key_hash": keyHash})
        .eq("contact_email", partyId)
        .execute()
    )
    return _with_party_identity_alias(response.data[0] if response.data else None)


def deleteParty(partyId):
    get_supabase_client().table("parties").delete().eq("contact_email", partyId).execute()


def updateOrderRuntimeMetadata(
    orderId, externalOrderId=None, ublXml=None, createdAt=None, updatedAt=None
):
    query = {}
    if externalOrderId is not None:
        query["order_id"] = externalOrderId
    if ublXml is not None:
        query["ublxml"] = ublXml
    if createdAt is not None:
        query["createdat"] = createdAt
    if updatedAt is not None:
        query["updatedat"] = updatedAt
        query["lastchanged"] = updatedAt

    if not query:
        return None

    try:
        response = get_supabase_client().table("orders").update(query).eq("id", orderId).execute()
        return response.data[0] if response.data else None
    except Exception as e:
        raise RuntimeError(f"Failed to update order runtime metadata: {e}") from e


# deletes all order lines related to a query
def deleteOrderDetails(orderId):
    get_supabase_client().table("orderdetails").delete().eq("orderid", orderId).execute()


# deletes given order (including order details)
def deleteOrder(orderId):
    get_supabase_client().table("orders").delete().eq("id", orderId).execute()


# mostly for debug purposes, returns all information stored in both databases
def DBInfo():
    client = get_supabase_client()
    orders = client.table("orders").select("*").execute()
    orderDetails = client.table("orderdetails").select("*").execute()
    return orders, orderDetails


def _load_local_env_files() -> None:
    load_local_env_files()


def _with_party_identity_alias(row):
    if not row:
        return None

    normalized = dict(row)
    contact_email = normalized.get("contact_email")
    if isinstance(contact_email, str) and contact_email.strip():
        normalized["contact_email"] = contact_email.strip().lower()
        normalized.setdefault("party_id", normalized["contact_email"])
    return normalized

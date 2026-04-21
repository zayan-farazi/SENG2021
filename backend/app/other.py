import os
from datetime import datetime
from typing import Any

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


def _uses_legacy_order_party_columns(exc: Exception) -> bool:
    message = str(exc)
    return "buyer_id" in message or "seller_id" in message


def _normalize_order_row(row: dict[str, Any] | None) -> dict[str, Any] | None:
    if not row:
        return None

    normalized = dict(row)
    buyer_email = normalized.get("buyer_id") or normalized.get("buyeremail")
    seller_email = normalized.get("seller_id") or normalized.get("selleremail")
    if buyer_email is not None:
        normalized.setdefault("buyer_id", buyer_email)
        normalized.setdefault("buyeremail", buyer_email)
    if seller_email is not None:
        normalized.setdefault("seller_id", seller_email)
        normalized.setdefault("selleremail", seller_email)
    return normalized


# how to save order example
# this works but pls make sure all details are correct before running the functions
# and do a try except so we don't up w rubbish data / duplicate info

# default currency is AUD
# default issue date is today
# default status is DRAFT


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
    if createdAt is not None:
        query["createdat"] = createdAt
    if updatedAt is not None:
        query["updatedat"] = updatedAt
    if ublXml is not None:
        query["ublXml"] = ublXml

    # TODO remove if conditions when people have changeed their functions

    if buyeremail:
        query["buyer_id"] = buyeremail
    if selleremail:
        query["seller_id"] = selleremail

    try:
        response = get_supabase_client().table("orders").upsert(query).execute()
    except Exception as e:
        if not _uses_legacy_order_party_columns(e):
            raise RuntimeError(f"Failed to save order: {e}") from e

        legacy_query = dict(query)
        if buyeremail:
            legacy_query["buyeremail"] = legacy_query.pop("buyer_id")
        if selleremail:
            legacy_query["selleremail"] = legacy_query.pop("seller_id")
        try:
            response = get_supabase_client().table("orders").upsert(legacy_query).execute()
            if ublXml is not None:
                saveOrder("order_gen_xml", response.data[0]["id"], ublXml)
        except Exception as legacy_exc:
            raise RuntimeError(f"Failed to save order: {legacy_exc}") from legacy_exc

    try:
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
    orderCount=None,
    orderBy=None,
    productList: list[str] | None = None,
    isDescending: bool | None = True,
    fromDate: datetime | None = None,
    toDate: datetime | None = None,
):
    def _execute_query(*, buyer_column: str, seller_column: str) -> list[dict[str, Any]]:
        query = get_supabase_client().table("orders").select("*", count="exact")

        if orderId:
            query = query.eq("id", orderId)
        if externalOrderId:
            query = query.eq("order_id", externalOrderId)
        if buyeremail:
            query = query.eq(buyer_column, buyeremail)
        if selleremail:
            query = query.eq(seller_column, selleremail)
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
        if orderCount:
            query = query.limit(orderCount)
        if orderBy:
            query = query.order(str(orderBy), desc=isDescending)

        res = query.execute()
        if productList:
            required_set = set(productList)
            details_map = findOrderDetailsByOrderIds([line["id"] for line in res.data])
            order_to_products = {
                order_id: {item["productname"] for item in items}
                for order_id, items in details_map.items()
            }
            res.data = [
                order
                for order in res.data
                if required_set.issubset(order_to_products.get(order["id"], set()))
            ]

        return [_normalize_order_row(row) or {} for row in res.data or []]

    try:
        return _execute_query(buyer_column="buyer_id", seller_column="seller_id")
    except Exception as e:
        if not _uses_legacy_order_party_columns(e):
            raise
        return _execute_query(buyer_column="buyeremail", seller_column="selleremail")


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


def findPartyByEmail(email):
    return findPartyByContactEmail(email)


def findPartyByPartyId(partyId):
    # `partyId` is kept as a public API compatibility field, but the persisted
    # identity is now the normalized contact email.
    return findPartyByContactEmail(partyId)


def findAppKeyByHash(keyHash):
    response = get_supabase_client().table("parties").select("*").eq("key_hash", keyHash).execute()
    row = response.data[0] if response.data else None
    return _with_party_identity_alias(row)


def saveParty(partyName, contactEmail, keyHash=None):
    query = {"party_name": partyName, "contact_email": contactEmail}
    if keyHash is not None:
        query["key_hash"] = keyHash

    response = get_supabase_client().table("parties").insert(query).execute()
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
    orderId, externalOrderId=None, ublXml=None, createdAt=None, updatedAt=None, status=None
):
    query = {}
    if externalOrderId is not None:
        query["order_id"] = externalOrderId
    if createdAt is not None:
        query["createdat"] = createdAt
    if updatedAt is not None:
        query["updatedat"] = updatedAt
        query["lastchanged"] = updatedAt
    if ublXml is not None:
        query["ublXml"] = ublXml
    if status is not None:
        query["status"] = status
    if not query:
        return None

    try:
        response = get_supabase_client().table("orders").update(query).eq("id", orderId).execute()
        if ublXml is not None:
            saveXml("order_gen_xml", externalOrderId, ublXml)
        return response.data[0] if response.data else None
    except Exception as e:
        raise RuntimeError(f"Failed to update order runtime metadata: {e}") from e


def saveXml(table_name: str, orderId: str, buyer_id: str, seller_id: str, ublXml: str) -> None:
    query = {"order_id": orderId, "seller_id": seller_id, "buyer_id": buyer_id, "xml": ublXml}
    get_supabase_client().table(table_name).upsert(query).execute()


def getXml(table_name: str, orderId: str):
    result = get_supabase_client().table(table_name).select("*").eq("order_id", orderId).execute()
    return result.data if result.data else []


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


def addProduct(
    partyemail: str,
    name: str,
    price: float | int,
    description: str,
    category: str,
    available_units: float | int,
    is_visible: bool,
    show_soldout: bool,
    unit="EA",
    release_date: datetime | None = None,
    image_url=None,
) -> dict[str, Any]:

    query = {
        "party_id": partyemail,
        "name": name,
        "price": price,
        "unit": unit,
        "description": description,
        "category": category,
        "is_visible": is_visible,
        "show_soldout": show_soldout,
        "available_units": available_units,
        "image_url": image_url,
    }

    # only allow custom / null release dates when product is not visible
    if is_visible:
        query["release_date"] = datetime.now().isoformat()
    elif release_date:
        query["release_date"] = release_date.isoformat()

    response = get_supabase_client().table("products").insert(query).execute()
    return response.data[0] if response.data else query


def getCatalogue(partyemail: str, limit: int | None, offset: int | None) -> list[dir]:
    return getProducts(partyemail, False, limit, offset)


def getInventory(partyemail: str, limit: int | None, offset: int | None) -> list[dir]:
    return getProducts(partyemail, True, limit, offset)


def getProducts(
    partyemail: str, showUnreleased: bool, limit: int | None, offset: int | None
) -> list[dir]:
    updateAvailability(partyemail)
    query = get_supabase_client().table("products").select("*").eq("party_id", partyemail)

    if not showUnreleased:
        query = query.eq("is_visible", True)

    if offset is not None and limit is not None:
        query = query.range(offset, offset + limit - 1)

    if limit is not None:
        query = query.limit(limit)

    return query.execute()


def updateAvailability(partyemail: str) -> None:
    now = datetime.now().isoformat()
    query = get_supabase_client().table("products")
    if partyemail != "*":
        query = query.eq("party_id", partyemail)
    query.update({"is_visible": True}).lte("release_date", now).execute()

    soldout_query = get_supabase_client().table("products")
    if partyemail != "*":
        soldout_query = soldout_query.eq("party_id", partyemail)
    soldout_query.update({"is_visible": False}).eq("show_soldout", False).lte(
        "available_units", 0
    ).execute()


def findProducts(
    prod_id=None,
    partyemail=None,
    name=None,
    priceExact=None,
    priceLowerBound=None,
    priceUpperBound=None,
    unit=None,
    category=None,
    available_units=None,
    is_visible=None,
    show_soldout=None,
    description: str | None = None,
):
    updateAvailability("*")
    query = get_supabase_client().table("products").select("*", count="exact")

    if prod_id is not None:
        query = query.eq("prod_id", prod_id)
    if partyemail:
        query = query.eq("party_id", partyemail)
    if is_visible is not None:
        query = query.eq("is_visible", is_visible)
    if show_soldout is not None:
        query = query.eq("show_soldout", show_soldout)
    if name:
        query = query.ilike("name", f"%{name}%")
    if priceExact is not None:
        query = query.eq("price", priceExact)
    if priceLowerBound is not None:
        query = query.gte("price", priceLowerBound)
    if priceUpperBound is not None:
        query = query.lte("price", priceUpperBound)
    if unit:
        query = query.eq("unit", unit)
    if category is not None:
        query = query.eq("category", category)
    if available_units is not None:
        query = query.gte("available_units", available_units)
    if description:
        query = query.ilike("description", f"%{description}%")

    return query.execute()


def updateProduct(
    prod_id,
    name=None,
    price=None,
    unit=None,
    description=None,
    category=None,
    available_units=None,
    is_visible=None,
    show_soldout=None,
    image_url=None,
    release_date: datetime | None = None,
):
    query = {}

    if is_visible is not None:
        query["is_visible"] = is_visible
        # if user manually makes a product visible, set release date to now
        if is_visible:
            query["release_date"] = datetime.now().isoformat()
        # if user makes a product invisible, change release date to given or null
        # to avoid making product visible in next update products in case now > scheduled_date
        else:
            query["release_date"] = release_date if release_date else None
    if show_soldout is not None:
        query["show_soldout"] = show_soldout
    if name is not None:
        query["name"] = name
    if price is not None:
        query["price"] = price
    if unit is not None:
        query["unit"] = unit
    if category is not None:
        query["category"] = category
    if available_units is not None:
        query["available_units"] = available_units
    if description is not None:
        query["description"] = description
    if release_date is not None:
        query["release_date"] = release_date.isoformat()
    if image_url is not None:
        query["image_url"] = image_url

    get_supabase_client().table("products").update(query).eq("prod_id", prod_id).execute()


def deleteProduct(prod_id: int):
    get_supabase_client().table("products").delete().eq("prod_id", prod_id).execute()

import os
from datetime import datetime
from pathlib import Path

from supabase import Client, create_client

_SUPABASE_CLIENT: Client | None = None


def get_supabase_client() -> Client:
    global _SUPABASE_CLIENT

    if _SUPABASE_CLIENT is None:
        _load_local_env_files()
        supabase_url = os.getenv("SUPABASE_URL")
        supabase_key = os.getenv("SUPABASE_KEY")
        if not supabase_url:
            raise RuntimeError("SUPABASE_URL is not configured.")
        if not supabase_key:
            raise RuntimeError("SUPABASE_KEY is not configured.")
        _SUPABASE_CLIENT = create_client(supabase_url, supabase_key)

    return _SUPABASE_CLIENT

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
        "unitprice": float(unitPrice),
    }

    try:
        get_supabase_client().table("orderdetails").upsert(query).execute()
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
    query = get_supabase_client().table("orders").select("*", count="exact")

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
        get_supabase_client().table("orderdetails")
        .select("productname", "unitcode", "quantity", "unitprice")
        .eq("orderid", orderId)
        .execute()
    )


# deletes all order lines related to a query
def deleteOrderDetails(orderId):
    return get_supabase_client().table("orderdetails").delete().eq("orderid", orderId).execute()


# deletes given order (including order details)
def deleteOrder(orderId):
    return get_supabase_client().table("orders").delete().eq("id", orderId).execute()

# mostly for debug purposes, returns all information stored in both databases
def DBInfo():
    orders = get_supabase_client().table("orders").select("*").execute()
    orderDetails = get_supabase_client().table("orderdetails").select("*").execute()
    return orders, orderDetails


def _load_local_env_files() -> None:
    for env_file in _candidate_env_files():
        if not env_file.is_file():
            continue
        for line in env_file.read_text(encoding="utf-8").splitlines():
            key, value = _parse_env_line(line)
            if key and value is not None:
                os.environ.setdefault(key, value)


def _candidate_env_files() -> list[Path]:
    backend_dir = Path(__file__).resolve().parents[1]
    repo_root = backend_dir.parent
    return [
        backend_dir / ".env",
        backend_dir / ".env.local",
        repo_root / ".env",
        repo_root / ".env.local",
    ]


def _parse_env_line(line: str) -> tuple[str | None, str | None]:
    stripped = line.strip()
    if not stripped or stripped.startswith("#"):
        return None, None

    if stripped.startswith("export "):
        stripped = stripped.removeprefix("export ").strip()

    if "=" not in stripped:
        return None, None

    key, raw_value = stripped.split("=", 1)
    key = key.strip()
    value = raw_value.strip()
    if not key:
        return None, None

    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        value = value[1:-1]

    return key, value

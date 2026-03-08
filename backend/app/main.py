from fastapi import FastAPI
from other import findOrders  # , saveOrder, saveOrderDetails, DBInfo
# import datetime

app = FastAPI()


@app.get("/")
def root():
    # how to save order example
    # this works but pls make sure all details are correct before running the functions
    # and do a try except so we don't up w rubbish data / duplicate info

    # default currency is AUD

    """
    orderid = saveOrder(
        "Rita",
        "Tina",
        "321 Road",
        "Sydney",
        344,
        "Australia",
        datetime.datetime.now().isoformat(),
        "Pending",
        "pls work",
    )
    saveOrderDetails(orderid, "pears", "def", 5.9, 9.8)
    """
    return findOrders(orderId="12")

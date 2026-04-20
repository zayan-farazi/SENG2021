from __future__ import annotations

import logging

from app.services.app_key_auth import get_current_party_email, resolve_party_email_from_app_key

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    File,
    UploadFile,
    WebSocket,
    WebSocketDisconnect,
)

from app.models.schemas import (
    PRODUCT_CREATE_RESPONSE_EXAMPLE,
    PRODUCT_LIST_RESPONSE_EXAMPLE,
    PRODUCT_CREATE_ERROR_EXAMPLES,
    ORDER_CONVERSION_RESPONSE_INCOMPLETE_EXAMPLE,
    ORDER_CONVERSION_RESPONSE_SUCCESS_EXAMPLE,
    ORDER_CREATE_RESPONSE_EXAMPLE,
    ORDER_FETCH_RESPONSE_EXAMPLE,
    ORDER_LIST_FINAL_PAGE_RESPONSE_EXAMPLE,
    ORDER_LIST_RESPONSE_EXAMPLE,
    ORDER_PAYLOAD_FETCH_RESPONSE_EXAMPLE,
    ORDER_UPDATE_RESPONSE_EXAMPLE,
    ProductRequest,
    AnalyticsResponse,
    OrderConversionResponse,
    OrderCreateResponse,
    OrderFetchResponse,
    OrderListResponse,
    OrderPayloadFetchResponse,
    OrderRequest,
    OrderUpdateResponse,
    TranscriptConversionRequest,
    InventoryCreateResponse,
)

from app.services.product_store import (
    ProductGenerationError,
    ProductPersistenceError,
    ProductNotFoundError,
    create_product_record,
)

router = APIRouter(tags=["Inventory"])
logger = logging.getLogger(__name__)



UNAUTHORIZED_RESPONSE = {
    "description": (
        "Missing, malformed, or unknown bearer credential, or missing `X-Party-Email` for the "
        "`v2` password flow."
    ),
    "content": {
        "application/json": {
            "example": {"detail": "Unauthorized"},
        }
    },
}

FORBIDDEN_RESPONSE = {
    "description": (
        "The authenticated party's registered email does not match the inventory's "
        "owner. "
    ),
    "content": {
        "application/json": {
            "example": {
                "detail": (
                    "Forbidden: your registered email does not match this inventory's owner's"
                )
            },
        }
    },
}

NOT_FOUND_RESPONSE = {
    "description": "The requested inventory item was not found.",
    "content": {
        "application/json": {
            "example": {"detail": "Not Found"},
        }
    },
}

VALIDATION_FAILURE_RESPONSE = {
    "description": "The inventory payload failed validation.",
    "content": {
        "application/json": {
            "example": {
                "detail": [
                    {"path": "name", "issue": "product name is required"},
                ],
            }
        }
    },
}

@router.post(
    "v1/inventory/add",
    response_model=InventoryCreateResponse,
    status_code=200,
    summary="Add an inventory item.",
    description=(
        "Add a new product to your catalogue inventory"
        "oprionally adding an image."
    ),
    responses={
        200: {
            "description": "Inventory item added successfully!",
            "content": {"application/json": {"example": PRODUCT_CREATE_RESPONSE_EXAMPLE}},
        },
        400: VALIDATION_FAILURE_RESPONSE,
        401: UNAUTHORIZED_RESPONSE,
        403: FORBIDDEN_RESPONSE,
        500: {
            "description": "Inventory item generation or persistence failed.",
            "content": {"application/json": {"example": {"detail": "Unable to add inventory item."}}}
        }
    }
)
def add_Inventory_Item(req: ProductRequest, current_party_email: str = Depends(get_current_party_email)):
    issues = _validate_product(req)
    if issues:
        raise HTTPException(status_code=400, detail=issues)
    
    try:
        record = create_product_record(req, current_party_email)
    except ProductGenerationError as exc:
        logger.exception("Product creation failed.")
        raise HTTPException(status_code=500, detail="Unable to add product.") from exc
    except ProductPersistenceError as exc:
        logger.exception("Product persistence verification failed.")
        raise HTTPException(status_code=500, detail="Unable to persist product.") from exc

    return {
        "prod_id": record["prod_id"],  
        "party_id": "orders@buyerco.example",
        "name": "Apples",
        "price": 5,
        "unit": "EA",
        "description": "Delicious red apples",
        "release_date": "2026-03-20",
        #"image_url": ""
        "is_visible": True,
        "show_soldout": True
    }


def _validate_product(product: ProductRequest):
    return
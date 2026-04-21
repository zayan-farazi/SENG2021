from __future__ import annotations

import logging
from datetime import datetime

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    UploadFile,
)

from app.models.schemas import (
    PRODUCT_CREATE_RESPONSE_EXAMPLE,
    PRODUCT_LIST_RESPONSE_EXAMPLE,
    ProductCreateResponse,
    ProductRequest,
)
from app.services.app_key_auth import get_current_party_email
from app.services.product_store import (
    DEFAULT_PRODUCT_LIST_LIMIT,
    DEFAULT_PRODUCT_LIST_OFFSET,
    MAX_PRODUCT_LIST_LIMIT,
    DuplicateProductError,
    ProductNotFoundError,
    ProductPersistenceError,
    UnexpectedError,
    create_product_record,
    get_image_url,
    get_user_catalogue,
    get_user_inventory,
    update_product_record,
)

router = APIRouter(tags=["Catalogue and Inventory"])
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
        "The authenticated party's registered email does not match the inventory's owner. "
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

DUPLICATE_ITEM_FOUND_RESPONSE = {
    "description": "Product name already exists in inventory.",
    "content": {"application/json": {"example": {"name": "Already exists"}}},
}

CATALOGUE_NOT_FOUND_RESPONSE = {
    "description": "Catalogue not found.",
    "content": {"application/json": {"example": {"detail": ("Catalogue not found for user")}}},
}


@router.post(
    "/v2/inventory/add",
    response_model=ProductCreateResponse,
    status_code=200,
    summary="Add an inventory item.",
    description="Add a new product to your catalogue inventory, optionally adding an image.",
    responses={
        200: {
            "description": "Inventory item added successfully!",
            "content": {"application/json": {"example": PRODUCT_CREATE_RESPONSE_EXAMPLE}},
        },
        400: VALIDATION_FAILURE_RESPONSE,
        401: UNAUTHORIZED_RESPONSE,
        403: FORBIDDEN_RESPONSE,
        409: DUPLICATE_ITEM_FOUND_RESPONSE,
        500: {
            "description": "Inventory item generation or persistence failed.",
            "content": {
                "application/json": {"example": {"detail": "Unable to add inventory item."}}
            },
        },
    },
)
async def add_Inventory_Item(
    party_id: str = Form(..., min_length=3),
    name: str = Form(..., min_length=3),
    price: float = Form(..., ge=0),
    unit: str = Form(default="EA", min_length=1),
    description: str | None = Form(None),
    category: str = Form(...),
    is_visible: bool = Form(True),
    available_units: float = Form(..., ge=0),
    show_soldout: bool = Form(True),
    image: UploadFile | None = File(None),  # noqa B008
    current_party_email: str = Depends(get_current_party_email),
):
    validate_party_access(party_id, current_party_email)

    req = ProductRequest(
        party_id=party_id,
        name=name,
        price=price,
        unit=unit,
        description=description,
        category=category,
        is_visible=is_visible,
        available_units=available_units,
        show_soldout=show_soldout,
    )

    issues = validate_product(req)
    if issues:
        raise HTTPException(status_code=400, detail=issues)
    image_url = get_image_url(image, current_party_email, name)
    try:
        record = create_product_record(req, current_party_email, image_url=image_url)
    except ProductPersistenceError as exc:
        logger.exception("Product persistence verification failed.")
        raise HTTPException(status_code=500, detail="Unable to persist product.") from exc
    except DuplicateProductError as exc:
        logger.exception(f"Product with name {name} already exists in user inventory.")
        raise HTTPException(status_code=409, detail="Duplicate product found.") from exc
    return ProductCreateResponse(record)


@router.patch(
    "/v2/inventory/{prod_id}",
    response_model=ProductCreateResponse,
    status_code=200,
    summary="Update an inventory item.",
    description="Modify an existing product. Only the owner can perform this action.",
    responses={
        200: {"description": "Item updated successfully."},
        400: VALIDATION_FAILURE_RESPONSE,
        401: UNAUTHORIZED_RESPONSE,
        403: FORBIDDEN_RESPONSE,
        404: {"description": "Product not found."},
        409: DUPLICATE_ITEM_FOUND_RESPONSE,
        500: {"description": "Update failed."},
    },
)
async def update_item_endpoint(
    prod_id: int,
    name: str | None = Form(None, min_length=3),
    price: int | None = Form(None, ge=0),
    unit: str | None = Form(None),
    description: str | None = Form(None),
    available_units: float | None = Form(None, ge=0),
    category: str | None = Form(None),
    is_visible: bool | None = Form(None),
    show_soldout: bool | None = Form(None),
    release_date: datetime | None = Form(None),  # noqa b008
    image: UploadFile | None = File(None),  # noqa B008
    current_party_email: str = Depends(get_current_party_email),
):
    req = ProductRequest(
        name=name,
        price=price,
        unit=unit,
        description=description,
        category=category,
        is_visible=is_visible,
        available_units=available_units,
        show_soldout=show_soldout,
        release_date=release_date,
    )
    try:
        record = update_product_record(req, prod_id, current_party_email, image)
    except ProductNotFoundError as exc:
        logger.exception("Unable to find product to update.")
        raise HTTPException(status_code=404, detail="Product not found") from exc
    except DuplicateProductError as exc:
        logger.exception(f"Product with name {name} already exists in user inventory.")
        raise HTTPException(status_code=409, detail="Duplicate product found.") from exc
    except ProductPersistenceError as exc:
        logger.exception("Product persistence verification failed.")
        raise HTTPException(status_code=500, detail="Unable to persist product.") from exc
    return record


@router.get(
    "/v2/catalogue/{party_id}",
    response_model=dict,
    summary="Get public catalogue.",
    description="View visible and released products for a specific party.",
    responses={
        200: {"content": {"application/json": {"example": PRODUCT_LIST_RESPONSE_EXAMPLE}}},
        404: CATALOGUE_NOT_FOUND_RESPONSE,
    },
)
async def get_public_catalogue(
    party_id: str,
    limit: int = Query(
        default=DEFAULT_PRODUCT_LIST_LIMIT,
        ge=1,
        le=MAX_PRODUCT_LIST_LIMIT,
    ),
    offset: int = Query(default=DEFAULT_PRODUCT_LIST_OFFSET, ge=0),
):
    try:
        results = get_user_catalogue(party_id, limit, offset)
        return results
    except UnexpectedError as e:
        logger.exception("Unexpected error while fetching catalogue.")
        raise HTTPException(
            status_code=500, detail="Unexpected error while fetching catalogue"
        ) from e


@router.get(
    "/v2/inventory",
    response_model=dict,
    summary="Get owner inventory.",
    description="View all products including unreleased and hidden items. Owner only.",
    responses={
        200: {"content": {"application/json": {"example": PRODUCT_LIST_RESPONSE_EXAMPLE}}},
        401: UNAUTHORIZED_RESPONSE,
    },
)
async def get_private_inventory(current_party_email: str = Depends(get_current_party_email)):
    try:
        results = get_user_inventory(current_party_email)
        return results
    except UnexpectedError as e:
        logger.exception("Unexpected error while fetching inventory.")
        raise HTTPException(
            status_code=500, detail="Unexpected error while fetching catalogue"
        ) from e


def _validate_product_core(product: ProductRequest, issues: list[dict[str, str]]) -> None:
    if not product.party_id:
        issues.append({"path": "party_id", "issue": "party_id (seller email) is required"})
    if not product.name:
        issues.append({"path": "name", "issue": "Product name is required"})
    if product.price is None or product.price < 0:
        issues.append({"path": "price", "issue": "Price must be a non-negative number"})
    if not product.unit:
        issues.append({"path": "unit", "issue": "Unit is required (e.g., EA, KG)"})


def _validate_product_inventory(product: ProductRequest, issues: list[dict[str, str]]) -> None:
    if product.available_units is not None and product.available_units < 0:
        issues.append({"path": "available_units", "issue": "Available units cannot be negative"})


def validate_product(product: ProductRequest) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    _validate_product_core(product, issues)
    _validate_product_inventory(product, issues)
    return issues


def validate_party_access(party_id, current_party_email):
    if not isinstance(party_id, str) or not isinstance(current_party_email, str):
        raise HTTPException(status_code=500, detail="Catalogue owner information missing.")

    if current_party_email.strip().lower() not in {party_id.strip().lower()}:
        raise HTTPException(
            status_code=403,
            detail=(
                "Forbidden: your registered email does not match this catalogue owner's email."
            ),
        )

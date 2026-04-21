import logging

from app.models.schemas import (
    ProductCreateResponse,
    ProductListResponse,
    ProductListResponseItem,
    ProductRequest,
    ProductUpdateRequest,
)
from app.other import (
    addProduct,
    deleteProduct,
    findProducts,
    get_supabase_client,
    getCatalogue,
    getInventory,
    updateProduct,
)


class ProductGenerationError(RuntimeError):
    pass


class ProductPersistenceError(RuntimeError):
    """Raised when the database verification step fails."""


class ProductNotFoundError(KeyError):
    """Raised when the requested prod_id does not exist."""


class DuplicateProductError(KeyError):
    """Raised when seller already has a product with product name"""


class ImageUploadError(KeyError):
    """Raised when image was not successfully uploaded"""


class UnexpectedError(KeyError):
    """Raised when database fails"""


logger = logging.getLogger(__name__)

DEFAULT_IMAGE_URL = (
    "https://zfkanfxuznozqpqfxbly.supabase.co/storage/v1/object/public/products/default.webp"
)

NOT_FOUND_RESPONSE = {
    "description": "The requested inventory item was not found.",
    "content": {
        "application/json": {
            "example": {"detail": "Not Found"},
        }
    },
}

AVAILABLE_CATEGORIES = [
    "Fashion",
    "Home and Kitchen",
    "Groceries and Consumables",
    "Antiques and Collectibles",
    "Jewellery and Accessories",
    "Health and Beauty",
    "Sports",
    "Furniture",
    "Electronics",
    "Arts & Crafts",
    "Books, Music and Film",
    "Gifts",
    "Handcrafted",
    "Others",
]


def create_product_record(prod: ProductRequest, curr_party_email: str, image_url: str):
    lookup = findProducts(partyemail=curr_party_email, name=prod.name)
    existing = lookup.data if lookup is not None else []
    if existing:
        raise DuplicateProductError(f"Product '{prod.name}' already exists in your catalogue.")
    try:
        record = addProduct(
            curr_party_email,
            prod.name,
            prod.price,
            prod.description,
            prod.category,
            prod.available_units,
            prod.is_visible,
            prod.show_soldout,
            prod.unit,
            prod.release_date,
            image_url,
        )
    except Exception as e:
        if getattr(e, "code", None) == "23505":
            raise DuplicateProductError(
                f"Product '{prod.name}' already exists in your catalogue."
            ) from e

        raise ProductGenerationError("Database persistence failed.") from e
    return _build_product_response(record)


async def update_product_record(
    req: ProductUpdateRequest, prod_id: int, curr_party: str, image=None
):
    try:
        record = findProducts(prod_id=prod_id).data
    except Exception as e:
        raise ProductNotFoundError(f"Unable to find product with id {prod_id}") from e

    if len(record) == 0:
        raise ProductNotFoundError(f"Unable to find product with id {prod_id}")

    record = record[0]
    from app.api.routes.inventory import validate_party_access

    validate_party_access(record.get("party_id"), curr_party)
    image_url = (
        await get_image_url(image, curr_party, req.name if req.name else record.get("name"))
        if image
        else None
    )
    try:
        updateProduct(
            prod_id,
            req.name,
            req.price,
            req.unit,
            req.description,
            req.category,
            req.available_units,
            req.is_visible,
            req.show_soldout,
            image_url,
            req.release_date,
        )
    except Exception as e:
        roll_back_prod_changes(prod_id, record)
        raise DuplicateProductError(f"Product with name {req.name} already exists.") from e

    refreshed = findProducts(prod_id=prod_id).data
    if not refreshed:
        raise ProductNotFoundError(f"Unable to find product with id {prod_id}")
    return _build_product_response(refreshed[0])


async def get_image_url(image, current_party_email: str, name: str):
    if not image or not image.filename:
        return DEFAULT_IMAGE_URL
    try:
        ext = image.filename.split(".")[-1] if "." in image.filename else "jpg"
        file_name = f"{current_party_email}_{name}.{ext}"

        contents = await image.read()
        storage = get_supabase_client().storage.from_("products")
        storage.upload(file_name, contents, {"upsert": "true"})

        image_url = storage.get_public_url(file_name)
    except Exception as e:
        raise ImageUploadError("Unable to save image") from e
    return image_url


def roll_back_prod_changes(prod_id, record):
    updateProduct(
        prod_id,
        record.get("name"),
        record.get("price"),
        record.get("unit"),
        record.get("description"),
        record.get("category"),
        record.get("available_units"),
        record.get("is_visible"),
        record.get("show_soldout"),
        record.get("image_url"),
        record.get("release_date"),
    )


def get_user_catalogue(party_id: str, limit: int | None, offset: int | None) -> ProductListResponse:
    try:
        response = getCatalogue(party_id, limit, offset)
        data = response.data
        total_count = response.count or 0

        resolved_offset = offset or 0
        return ProductListResponse(
            items=[ProductListResponseItem(**item) for item in data],
            page={
                "limit": limit,
                "offset": offset,
                "hasMore": (resolved_offset + len(data)) < total_count,
                "total": total_count,
            },
        )

    except Exception as e:
        raise UnexpectedError("There was an unexpected error looking up the catalogue.") from e


def get_user_inventory(
    party_id: str, limit: int | None = None, offset: int | None = None
) -> ProductListResponse:
    try:
        response = getInventory(party_id, limit, offset)
        data = response.data
        total_count = response.count or 0

        resolved_offset = offset or 0
        return ProductListResponse(
            items=[ProductListResponseItem(**item) for item in data],
            page={
                "limit": limit,
                "offset": offset,
                "hasMore": (resolved_offset + len(data)) < total_count,
                "total": total_count,
            },
        )

    except Exception as e:
        raise UnexpectedError("There was an unexpected error looking up the catalogue.") from e


def delete_product_record(prod_id: int, curr_party: str):
    try:
        response = findProducts(prod_id=prod_id)
        record_list = response.data
    except Exception as e:
        raise ProductNotFoundError(f"Unable to find product with id {prod_id}") from e

    if not record_list or len(record_list) == 0:
        raise ProductNotFoundError(f"Unable to find product with id {prod_id}")

    record = record_list[0]

    from app.api.routes.inventory import validate_party_access

    validate_party_access(record.get("party_id"), curr_party)

    try:
        deleteProduct(prod_id)
    except Exception as e:
        raise UnexpectedError("An error occurred while deleting the product.") from e

    return {"detail": "Product successfully deleted"}


def _build_product_response(record: dict) -> ProductCreateResponse:
    normalized = dict(record)
    if "prod_description" in normalized and "description" not in normalized:
        normalized["description"] = normalized.pop("prod_description")
    if "imageUrl" in normalized and "image_url" not in normalized:
        normalized["image_url"] = normalized.pop("imageUrl")
    return ProductCreateResponse.model_validate(normalized)

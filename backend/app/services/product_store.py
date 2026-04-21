import logging

from app.api.routes.inventory import validate_party_access
from app.models.schemas import (
    ProductCreateResponse,
    ProductListResponseItem,
    ProductRequest,
)
from app.other import (
    addProduct,
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

DEFAULT_PRODUCT_LIST_LIMIT = 20
DEFAULT_PRODUCT_LIST_OFFSET = 0
MAX_PRODUCT_LIST_LIMIT = 100
MAX_PRODUCT_ORDERS = 256


def create_product_record(prod: ProductRequest, curr_party_email: str, image_url: str):
    if findProducts(curr_party_email, prod.name) is not None or []:
        raise DuplicateProductError(f"Product '{prod.name}' already exists in your catalogue.")
    try:
        addProduct(
            curr_party_email,
            prod.name,
            prod.price,
            prod.description,
            prod.available_units,
            prod.is_visible,
            prod.show_soldout,
            prod.unit,
            prod.release_date,
            image_url,
        )
    except Exception as e:
        if e.code == "23505":
            raise DuplicateProductError(
                f"Product '{prod.name}' already exists in your catalogue."
            ) from e

        raise ProductGenerationError(status_code=500, detail="Database persistence failed.") from e
    return ProductCreateResponse(
        prod.name, prod.price, prod.unit, prod.units_available, prod.description, image_url
    )


def update_product_record(req: ProductRequest, prod_id: int, curr_party: str, image=None):
    try:
        record = findProducts(prod_id=prod_id).data
    except Exception as e:
        raise ProductNotFoundError(f"Unable to find product with id {prod_id}") from e

    if record is None or []:
        raise ProductNotFoundError(f"Unable to find product with id {prod_id}")

    record = record[0]
    validate_party_access(record.get("party_id"), curr_party)
    try:
        updateProduct(
            prod_id,
            req.name if req.name else None,
            req.price if req.price else None,
            req.unit if req.unit else None,
            req.description if req.description else None,
            req.available_units if req.available_units else None,
            req.is_visible if req.is_visible else None,
            req.show_soldout if req.show_soldout else None,
            req.release_date if req.release_date else None,
        )
        image_url = get_image_url(image, curr_party, req.name if req.name else record.get("name"))
        try:
            updateProduct(prod_id, image_url=image_url)
        except Exception as e:
            roll_back_prod_changes(prod_id, record)
            raise UnexpectedError("Unexpected error ocurred when trying to update product") from e
    except Exception as e:
        roll_back_prod_changes(prod_id, record)
        raise DuplicateProductError(f"Product with name {req.name} already exists.") from e

    return ProductCreateResponse(
        req.name if req.name else record.get("name"),
        req.price if req.price else record.get("price"),
        req.unit if req.unit else record.get("unit"),
        req.units_available if req.units_available else record.get("units_available"),
        req.description if req.description else record.get("description"),
        req.image_url if req.image_url else record.get("image_url"),
    )


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
        record.get("available_units"),
        record.get("is_visible"),
        record.get("show_soldout"),
        record.get("image_url"),
        record.get("release_date"),
    )


def get_user_catalogue(party_id: str, limit: int | None, offset: int | None):
    try:
        response = getCatalogue(party_id, limit, offset)
        data = response.data
        total_count = response.count or 0

        return {
            "items": [ProductListResponseItem(**item).model_dump() for item in data],
            "page": {
                "limit": limit,
                "offset": offset,
                "hasMore": (offset + len(data)) < total_count,
                "total": total_count,
            },
        }

    except Exception as e:
        raise UnexpectedError("There was an unexpected error looking up the catalogue.") from e


def get_user_inventory(party_id: str, limit: int | None, offset: int | None):
    try:
        response = getInventory(party_id, limit, offset)
        data = response.data
        total_count = response.count or 0

        return {
            "items": [ProductListResponseItem(**item).model_dump() for item in data],
            "page": {
                "limit": limit,
                "offset": offset,
                "hasMore": (offset + len(data)) < total_count,
                "total": total_count,
            },
        }

    except Exception as e:
        raise UnexpectedError("There was an unexpected error looking up the catalogue.") from e


def delete_product(party_id: str, prod_id: int):
    return

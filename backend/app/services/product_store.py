
from app.models.schemas import (
    ProductRequest,
)

from app.other import (
    addProduct,
    updateProduct,
    deleteProduct
)
DEFAULT_IMAGE_URL = ""

class ProductGenerationError(RuntimeError):
    pass

class ProductPersistenceError(RuntimeError):
    """Raised when the database verification step fails."""


class ProductNotFoundError(KeyError):
    """Raised when the requested orderId does not exist."""

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
    "Others"
]

def create_product_record(prod: ProductRequest, curr_party_email: str, image_url: str = DEFAULT_IMAGE_URL):
    try:
        addProduct
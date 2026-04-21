from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.product_store import (
    DEFAULT_IMAGE_URL,
    ProductNotFoundError,
    create_product_record,
    get_image_url,
)

# 1. Use real values for Pydantic models to avoid ValidationErrors
MOCK_PARTY = "test@example.com"


class MockReq:
    name = "Apple"
    price = 10.0
    description = "Fresh"
    available_units = 5
    units_available = 5  # Matches your ProductCreateResponse call
    is_visible = True
    show_soldout = True
    unit = "kg"
    release_date = "2023-01-01"
    image_url = "http://old.com"


MOCK_PROD_REQ = MockReq()


@pytest.fixture
def mock_db_calls():
    # Ensure paths match your app structure
    with (
        patch("app.services.product_store.findProducts") as mock_find,
        patch("app.services.product_store.addProduct") as mock_add,
        patch("app.services.product_store.updateProduct") as mock_update,
    ):
        yield mock_find, mock_add, mock_update


class TestCreateProduct:
    def test_create_product_success(self, mock_db_calls):
        mock_find, mock_add, _ = mock_db_calls
        mock_find.return_value = None

        result = create_product_record(MOCK_PROD_REQ, MOCK_PARTY, "http://image.com")
        assert result.name == "Apple"


class TestImageUpload:
    # 2. Add the asyncio marker
    @pytest.mark.asyncio
    async def test_get_image_url_default(self):
        url = await get_image_url(None, MOCK_PARTY, "Apple")
        assert url == DEFAULT_IMAGE_URL

    @pytest.mark.asyncio
    async def test_get_image_url_upload_success(self):
        with patch("app.services.product_store.get_supabase_client") as mock_client:
            mock_image = AsyncMock()
            mock_image.filename = "test.jpg"
            mock_image.read.return_value = b"content"

            mock_storage = mock_client.return_value.storage.from_.return_value
            mock_storage.get_public_url.return_value = "http://new-image.com"

            url = await get_image_url(mock_image, MOCK_PARTY, "Apple")
            assert url == "http://new-image.com"


class TestUpdateProduct:
    def test_update_product_not_found(self, mock_db_calls):
        mock_find, _, _ = mock_db_calls
        # Simulate Supabase PostgrestResponse with .data = []
        mock_find.return_value.data = []

        with pytest.raises(ProductNotFoundError):
            from app.services.product_store import update_product_record

            update_product_record(MOCK_PROD_REQ, 999, MOCK_PARTY)


class TestCatalogue:
    def test_get_user_catalogue_structure(self):
        with patch("app.services.product_store.getCatalogue") as mock_get:
            mock_response = MagicMock()
            # 3. Add MISSING FIELDS required by ProductListResponseItem
            mock_response.data = [
                {
                    "id": 1,
                    "name": "P1",
                    "price": 10,
                    "unit": "pc",
                    "available_units": 1,
                    "description": "d",
                    "image_url": "u",
                    "release_date": "2023-01-01",
                    "is_visible": True,
                }
            ]
            mock_response.count = 100
            mock_get.return_value = mock_response

            from app.services.product_store import get_user_catalogue

            result = get_user_catalogue(MOCK_PARTY, limit=10, offset=0)
            assert len(result["items"]) == 1

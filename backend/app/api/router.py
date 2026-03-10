from fastapi import APIRouter

from app.api.routes.orders import router as orders_router
from app.api.routes.health import router as health_router

router = APIRouter()
router.include_router(orders_router)
router.include_router(health_router)

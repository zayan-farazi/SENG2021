from fastapi import APIRouter

from app.api.routes.health import router as health_router
from app.api.routes.inventory import router as inventory_router
from app.api.routes.invoices import router as invoices_router
from app.api.routes.orders import router as orders_router
from app.api.routes.parties import router as parties_router
from app.api.routes.parties import router_v2 as parties_v2_router
from app.api.routes.despatch import router as despatch_router

router = APIRouter()
router.include_router(orders_router)
router.include_router(health_router)
router.include_router(parties_router)
router.include_router(parties_v2_router)
router.include_router(invoices_router)
router.include_router(inventory_router)
router.include_router(despatch_router)

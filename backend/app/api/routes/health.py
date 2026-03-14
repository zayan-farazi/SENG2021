# app/routes/health.py
from time import monotonic

from fastapi import APIRouter, HTTPException, Request

from app.models.schemas import HealthResponse

router = APIRouter(prefix="/v1", tags=["Health"])


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Health check",
    description=(
        "Return basic service health, uptime, API version, and request count. "
        "This endpoint does not require authentication."
    ),
    responses={
        200: {
            "description": "Service is healthy.",
        },
        503: {
            "description": "Service is unhealthy.",
            "content": {"application/json": {"example": {"detail": "Service unhealthy"}}},
        },
    },
)
def health_check(request: Request):

    healthy = True
    if not healthy:
        raise HTTPException(status_code=503, detail="Service unhealthy")

    uptime = monotonic() - request.app.state.start_time
    version = request.app.version
    request_count = request.app.state.request_count

    return HealthResponse(
        status="healthy", uptimeSeconds=uptime, version=version, requestCount=request_count
    )

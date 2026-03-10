# app/routes/health.py
from fastapi import APIRouter, Request, HTTPException
from app.models.schemas import HealthResponse
from time import time


router = APIRouter(prefix="/v1", tags=["Health"])

@router.get("/health", response_model=HealthResponse)
def health_check(request: Request):

    healthy = True
    if not healthy:
        raise HTTPException(status_code=503, detail="Service unhealthy")

    uptime = time() - request.app.state.start_time
    version = request.app.state.version
    request_count = request.app.state.request_count

    return HealthResponse(
        status="healthy",
        uptimeSeconds=uptime,
        version=version,
        requestCount=request_count
    )
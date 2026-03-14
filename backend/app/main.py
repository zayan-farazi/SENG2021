import os
from contextlib import asynccontextmanager
from time import monotonic

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import router

DEFAULT_ALLOWED_ORIGINS = (
    "http://localhost:3000",
    "http://localhost:5173",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:5173",
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.start_time = monotonic()
    app.state.request_count = 0
    yield


def _parse_allowed_origins(value: str | None) -> list[str]:
    if not value:
        return list(DEFAULT_ALLOWED_ORIGINS)

    parsed = [origin.strip() for origin in value.split(",")]
    return [origin for origin in parsed if origin]


app = FastAPI(title="DigitalBook Order Creation API", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_parse_allowed_origins(os.getenv("ALLOWED_ORIGINS")),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(router)


@app.middleware("http")
async def metrics_middleware(request, call_next):
    request.app.state.request_count += 1
    return await call_next(request)

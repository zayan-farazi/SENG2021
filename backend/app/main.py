from contextlib import asynccontextmanager
from time import monotonic

from fastapi import FastAPI

from app.api.router import router


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.start_time = monotonic()
    app.state.request_count = 0
    yield


app = FastAPI(title="DigitalBook Order Creation API", version="0.1.0", lifespan=lifespan)
app.include_router(router)


@app.middleware("http")
async def metrics_middleware(request, call_next):
    request.app.state.request_count += 1
    return await call_next(request)

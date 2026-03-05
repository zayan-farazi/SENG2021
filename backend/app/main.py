from time import time

from fastapi import FastAPI

from app.api.router import router

app = FastAPI(title="DigitalBook Order Creation API", version="0.1.0")
app.include_router(router)


@app.middleware("http")
async def metrics_middleware(request, call_next):
    if not hasattr(request.app.state, "start_time"):
        request.app.state.start_time = time()
        request.app.state.request_count = 0
        request.app.state.version = "0.1.0"
    request.app.state.request_count += 1
    return await call_next(request)

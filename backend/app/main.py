import os
from contextlib import asynccontextmanager
from pathlib import Path
from time import monotonic

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from app.api.router import router

DEFAULT_ALLOWED_ORIGINS = (
    "http://localhost:3000",
    "http://localhost:5173",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:5173",
)
STATIC_DIR = Path(__file__).resolve().parent / "static"
SWAGGER_UI_VERSION = "5.32.0"
SWAGGER_UI_CSS_URL = f"/static/swagger-ui-{SWAGGER_UI_VERSION}.css"
SWAGGER_UI_JS_URL = f"/static/swagger-ui-bundle-{SWAGGER_UI_VERSION}.js"
SWAGGER_UI_PLUGIN_URL = "/static/swagger-runtime-xml-plugin.js"


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


app = FastAPI(
    title="DigitalBook Order Creation API",
    version="0.1.0",
    docs_url=None,
    separate_input_output_schemas=False,
    description=(
        "A buyer/seller order API for B2B integrations.\n\n"
        "## Authentication\n"
        "1. Register once with `POST /v1/parties/register`.\n"
        "2. Store the returned `appKey` securely.\n"
        "3. Call protected endpoints with `Authorization: Bearer <appKey>`.\n\n"
        "Protected order endpoints only allow the authenticated party when their registered "
        "contact email matches the order's `buyerEmail` or `sellerEmail`."
    ),
    lifespan=lifespan,
    openapi_tags=[
        {
            "name": "Health",
            "description": "Operational health and readiness endpoints.",
        },
        {
            "name": "Parties",
            "description": "Party registration and app-key onboarding for new integrators.",
        },
        {
            "name": "Orders",
            "description": (
                "Order creation, retrieval, update, deletion, validation, and helper conversion "
                "endpoints."
            ),
        },
    ],
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_parse_allowed_origins(os.getenv("ALLOWED_ORIGINS")),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
app.include_router(router)


def _render_swagger_html() -> str:
    return f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <link type="text/css" rel="stylesheet" href="{SWAGGER_UI_CSS_URL}">
  <link rel="shortcut icon" href="https://fastapi.tiangolo.com/img/favicon.png">
  <title>{app.title} - Swagger UI</title>
</head>
<body>
  <div id="swagger-ui"></div>
  <script src="{SWAGGER_UI_JS_URL}"></script>
  <script src="{SWAGGER_UI_PLUGIN_URL}"></script>
  <script>
    window.ui = SwaggerUIBundle({{
      url: "{app.openapi_url}",
      dom_id: "#swagger-ui",
      layout: "BaseLayout",
      deepLinking: true,
      showExtensions: true,
      showCommonExtensions: true,
      presets: [
        SwaggerUIBundle.presets.apis,
        SwaggerUIBundle.SwaggerUIStandalonePreset
      ],
      plugins: [
        window.RuntimeXmlExamplePlugin
      ]
    }})
  </script>
</body>
</html>"""


@app.get("/docs", include_in_schema=False)
def custom_swagger_ui():
    return HTMLResponse(_render_swagger_html())


@app.middleware("http")
async def metrics_middleware(request, call_next):
    request.app.state.request_count += 1
    return await call_next(request)

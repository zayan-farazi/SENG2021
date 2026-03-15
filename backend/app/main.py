import os
from contextlib import asynccontextmanager
from pathlib import Path
from time import monotonic

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api.router import router
from app.models.schemas import (
    REQUEST_VALIDATION_DISABLED_ROUTES,
    REQUEST_VALIDATION_ERROR_RESPONSE_EXAMPLES,
    REQUEST_VALIDATION_ROUTE_DOCS,
    RequestValidationErrorResponse,
)

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
REQUEST_VALIDATION_COMPONENT_REF = "#/components/schemas/RequestValidationErrorResponse"


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


def _format_validation_path(segments: list[str | int]) -> str:
    path = ""
    for segment in segments:
        if isinstance(segment, int):
            path += f"[{segment}]"
        elif not path:
            path = str(segment)
        else:
            path += f".{segment}"
    return path


def _normalize_validation_errors(exc: RequestValidationError) -> list[dict[str, str]]:
    normalized: list[dict[str, str]] = []
    for error in exc.errors():
        loc = list(error.get("loc", ()))
        source = str(loc[0]) if loc else "body"
        if source not in {"body", "path", "query", "header", "cookie"}:
            source = "body"
        normalized.append(
            {
                "source": source,
                "path": _format_validation_path(loc[1:]),
                "message": str(error.get("msg", "Invalid request value.")),
                "code": str(error.get("type", "validation_error")),
            }
        )
    return normalized


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


@app.exception_handler(RequestValidationError)
async def request_validation_exception_handler(_request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content={
            "message": "Request validation failed.",
            "errors": _normalize_validation_errors(exc),
        },
    )


def _custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema

    schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
        tags=app.openapi_tags,
        separate_input_output_schemas=app.separate_input_output_schemas,
    )

    components = schema.setdefault("components", {})
    schemas = components.setdefault("schemas", {})
    validation_schema = RequestValidationErrorResponse.model_json_schema(
        ref_template="#/components/schemas/{model}"
    )
    validation_defs = validation_schema.pop("$defs", {})

    for name, definition in validation_defs.items():
        schemas[name] = definition
    schemas["RequestValidationErrorResponse"] = validation_schema

    schemas.pop("HTTPValidationError", None)
    schemas.pop("ValidationError", None)

    for path, methods in schema.get("paths", {}).items():
        for method, operation in methods.items():
            responses = operation.get("responses", {})
            route_key = (path, method)

            if route_key in REQUEST_VALIDATION_DISABLED_ROUTES:
                responses.pop("422", None)
                continue

            validation_response = responses.get("422")
            if not validation_response:
                continue

            validation_docs = REQUEST_VALIDATION_ROUTE_DOCS.get(
                route_key,
                {
                    "description": "The request payload is invalid.",
                    "examples": REQUEST_VALIDATION_ERROR_RESPONSE_EXAMPLES,
                },
            )
            content = validation_response.setdefault("content", {})
            validation_response["description"] = validation_docs["description"]
            content["application/json"] = {
                "schema": {"$ref": REQUEST_VALIDATION_COMPONENT_REF},
                "examples": validation_docs["examples"],
            }

    app.openapi_schema = schema
    return app.openapi_schema


app.openapi = _custom_openapi


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

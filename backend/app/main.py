import os
from contextlib import asynccontextmanager
from copy import deepcopy
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
from app.other import close_supabase_client

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
OPENAPI_JSON_URL = "/openapi.json"


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.start_time = monotonic()
    app.state.request_count = 0
    yield
    close_supabase_client()


def _parse_allowed_origins(value: str | None) -> list[str]:
    if not value:
        return list(DEFAULT_ALLOWED_ORIGINS)

    parsed = [origin.strip() for origin in value.split(",")]
    return [origin for origin in parsed if origin]


def _first_forwarded_value(value: str | None) -> str | None:
    if not value:
        return None

    first = value.split(",", 1)[0].strip()
    return first or None


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
    title="LockedOut",
    version="0.1.0",
    docs_url=None,
    openapi_url=None,
    separate_input_output_schemas=False,
    description=(
        "A buyer/seller order API for B2B integrations.\n\n"
        "## Authentication\n"
        "Protected order and party-lookup endpoints support two bearer credential modes.\n\n"
        "### Legacy `v1` app-key flow\n"
        "1. Register once with `POST /v1/parties/register`.\n"
        "2. Save the returned `appKey` securely.\n"
        "3. Call protected endpoints with `Authorization: Bearer <appKey>`.\n\n"
        "### `v2` password flow\n"
        "1. Register with `POST /v2/parties/register` using `partyName`, `contactEmail`, and "
        "`password`.\n"
        "2. Log in with `POST /v2/parties/login` using `contactEmail` and `password`.\n"
        "3. Call protected endpoints with:\n"
        "   - `Authorization: Bearer <password>`\n"
        "   - `X-Party-Email: <registered contact email>`\n\n"
        "Protected order endpoints only allow the authenticated party when their registered "
        "contact email matches the order's `buyerEmail` or `sellerEmail`. "
        "For legacy `v1`, the app key must belong to either the buyer or the seller email used "
        "in the order body.\n\n"
        "## Successful Use Case\n"
        "### 1. Register a party and get a legacy app key\n"
        "Purpose: create a buyer or seller identity and receive the legacy Bearer app key used "
        "by existing `v1` integrations.\n\n"
        "```bash\n"
        "curl -X POST '<baseUrl>/v1/parties/register' \\\n"
        "  -H 'Content-Type: application/json' \\\n"
        "  -d '{\n"
        '    "partyName": "Buyer Co",\n'
        '    "contactEmail": "orders@buyerco.example"\n'
        "  }'\n"
        "```\n\n"
        "Look for:\n\n"
        "```json\n"
        "{\n"
        '  "partyId": "orders@buyerco.example",\n'
        '  "partyName": "Buyer Co",\n'
        '  "appKey": "appKey",\n'
        '  "message": "Store this key securely. It will not be shown again."\n'
        "}\n"
        "```\n\n"
        "### 2. Create a draft order with the legacy `v1` app key\n"
        "Purpose: create a draft order using the same buyer identity and a seller email/name.\n\n"
        "```bash\n"
        "curl -X POST '<baseUrl>/v1/order/create' \\\n"
        "  -H 'Authorization: Bearer <appKey>' \\\n"
        "  -H 'Content-Type: application/json' \\\n"
        "  -d '{\n"
        '    "buyerEmail": "orders@buyerco.example",\n'
        '    "buyerName": "Buyer Co",\n'
        '    "sellerEmail": "sales@supplier.example",\n'
        '    "sellerName": "Supplier Pty Ltd",\n'
        '    "currency": "AUD",\n'
        '    "issueDate": "2026-03-14",\n'
        '    "notes": "Please deliver before noon.",\n'
        '    "delivery": {\n'
        '      "street": "123 Harbour Street",\n'
        '      "city": "Sydney",\n'
        '      "state": "NSW",\n'
        '      "postcode": "2000",\n'
        '      "country": "AU",\n'
        '      "requestedDate": "2026-03-20"\n'
        "    },\n"
        '    "lines": [\n'
        "      {\n"
        '        "productName": "Oranges",\n'
        '        "quantity": 4,\n'
        '        "unitCode": "EA",\n'
        '        "unitPrice": "3.50"\n'
        "      }\n"
        "    ]\n"
        "  }'\n"
        "```\n\n"
        "Look for:\n\n"
        "```json\n"
        "{\n"
        '  "orderId": "<orderId>",\n'
        '  "status": "DRAFT",\n'
        '  "createdAt": "2026-03-14T10:30:00Z"\n'
        "}\n"
        "```\n\n"
        "### 3. Create a draft order with the `v2` password flow\n"
        "Purpose: call the same protected draft-order endpoint using the `v2` password plus "
        "`X-Party-Email`.\n\n"
        "```bash\n"
        "curl -X POST '<baseUrl>/v1/order/create' \\\n"
        "  -H 'Authorization: Bearer <password>' \\\n"
        "  -H 'X-Party-Email: orders@buyerco.example' \\\n"
        "  -H 'Content-Type: application/json' \\\n"
        "  -d '{\n"
        '    "buyerEmail": "orders@buyerco.example",\n'
        '    "buyerName": "Buyer Co",\n'
        '    "sellerEmail": "sales@supplier.example",\n'
        '    "sellerName": "Supplier Pty Ltd",\n'
        '    "currency": "AUD",\n'
        '    "issueDate": "2026-03-14",\n'
        '    "lines": [\n'
        "      {\n"
        '        "productName": "Oranges",\n'
        '        "quantity": 4,\n'
        '        "unitCode": "EA",\n'
        '        "unitPrice": "3.50"\n'
        "      }\n"
        "    ]\n"
        "  }'\n"
        "```\n\n"
        "### 4. List your orders\n"
        "Purpose: confirm the created order is visible to the authenticated party.\n\n"
        "```bash\n"
        "curl -X GET '<baseUrl>/v1/orders?limit=20&offset=0' \\\n"
        "  -H 'Authorization: Bearer <appKey>'\n"
        "```\n\n"
        "Look for:\n\n"
        "```json\n"
        "{\n"
        '  "items": [\n'
        "    {\n"
        '      "orderId": "<orderId>",\n'
        '      "status": "DRAFT"\n'
        "    }\n"
        "  ],\n"
        '  "page": {\n'
        '    "limit": 20,\n'
        '    "offset": 0,\n'
        '    "hasMore": false,\n'
        '    "total": 1\n'
        "  }\n"
        "}\n"
        "```\n\n"
        "### 5. Fetch the order JSON\n"
        "Purpose: inspect the current order metadata by `orderId`.\n\n"
        "```bash\n"
        "curl -X GET '<baseUrl>/v1/order/<orderId>' \\\n"
        "  -H 'Authorization: Bearer <appKey>'\n"
        "```\n\n"
        "Look for:\n\n"
        "```json\n"
        "{\n"
        '  "orderId": "<orderId>",\n'
        '  "status": "DRAFT",\n'
        '  "createdAt": "2026-03-14T10:30:00Z",\n'
        '  "updatedAt": "2026-03-14T10:30:00Z"\n'
        "}\n"
        "```\n\n"
        "### 6. Fetch the UBL XML\n"
        "Purpose: retrieve the persisted order document as raw XML.\n\n"
        "```bash\n"
        "curl -X GET '<baseUrl>/v1/order/<orderId>/ubl' \\\n"
        "  -H 'Authorization: Bearer <appKey>'\n"
        "```\n\n"
        "Look for raw XML output beginning with:\n\n"
        "```xml\n"
        '<?xml version="1.0" encoding="utf-8"?>\n'
        "<Order ...>\n"
        "```\n\n"
        "`GET /v1/order/{order_id}/ubl` returns XML, not JSON.\n\n"
        "Optional helper path: if you want speech-assisted drafting before create, call "
        "`POST /v1/orders/convert/transcript` after authentication and before "
        "`POST /v1/order/create`. Include buyer and seller emails in the transcript when you can, "
        "or provide them in `currentPayload`, so the returned draft resolves the right parties."
    ),
    lifespan=lifespan,
    openapi_tags=[
        {
            "name": "Parties",
            "description": (
                "Party registration, credential onboarding, and identity lookup for integrators."
            ),
        },
        {
            "name": "Orders",
            "description": (
                "Order creation, retrieval, update, deletion, and helper conversion endpoints."
            ),
        },
        {
            "name": "Catalogue and Inventory",
            "descriprion": ("Product addition, retrieval, update and deletion endpoints."),
        },
        {
            "name": "Health",
            "description": "Operational health and readiness endpoints.",
        },
        {
            "name": "Invoices",
            "description": "Invoice integration endpoints backed by the LastMinutePush invoice API.",
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


def _normalized_request_origin(request: Request) -> str:
    forwarded_proto = _first_forwarded_value(request.headers.get("x-forwarded-proto"))
    forwarded_host = _first_forwarded_value(request.headers.get("x-forwarded-host"))

    if forwarded_proto and forwarded_host:
        return f"{forwarded_proto}://{forwarded_host}"

    return str(request.base_url).rstrip("/")


def _render_request_openapi_schema(request: Request) -> dict:
    schema = deepcopy(app.openapi())
    origin = _normalized_request_origin(request)
    schema["info"]["description"] = schema["info"]["description"].replace("<baseUrl>", origin)
    schema["servers"] = [{"url": origin}]
    return schema


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
    const orderRouteRanks = {{
      "post /v1/order/create": 0,
      "put /v1/order/{{order_id}}": 1,
      "get /v1/order/{{order_id}}": 2,
      "get /v1/order/{{order_id}}/payload": 3,
      "delete /v1/order/{{order_id}}": 4,
      "get /v1/orders": 5,
      "get /v1/order/{{order_id}}/ubl": 6,
      "post /v1/orders/convert/transcript": 7
    }};

    const getOperationKey = (operation) => {{
      const method = String(operation.get("method") || "").toLowerCase();
      const path = String(operation.get("path") || "");
      return `${{method}} ${{path}}`;
    }};

    const orderOperationsSorter = (a, b) => {{
      const leftRank = orderRouteRanks[getOperationKey(a)];
      const rightRank = orderRouteRanks[getOperationKey(b)];
      if (leftRank === undefined && rightRank === undefined) {{
        return 0;
      }}
      if (leftRank === undefined) {{
        return 1;
      }}
      if (rightRank === undefined) {{
        return -1;
      }}
      return leftRank - rightRank;
    }};

    window.ui = SwaggerUIBundle({{
      url: "{OPENAPI_JSON_URL}",
      dom_id: "#swagger-ui",
      layout: "BaseLayout",
      deepLinking: true,
      showExtensions: true,
      showCommonExtensions: true,
      operationsSorter: orderOperationsSorter,
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


@app.get(OPENAPI_JSON_URL, include_in_schema=False)
def openapi_schema(request: Request):
    return JSONResponse(_render_request_openapi_schema(request))


@app.get("/", include_in_schema=False)
def root_swagger_ui():
    return HTMLResponse(_render_swagger_html())


@app.get("/docs", include_in_schema=False)
def custom_swagger_ui():
    return HTMLResponse(_render_swagger_html())


@app.middleware("http")
async def metrics_middleware(request, call_next):
    request.app.state.request_count += 1
    return await call_next(request)

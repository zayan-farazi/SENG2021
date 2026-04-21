from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app
from app.services.ubl_order import generate_docs_example_ubl_order_xml


def _openapi(base_url: str = "http://testserver") -> dict:
    with TestClient(app, base_url=base_url, raise_server_exceptions=False) as client:
        response = client.get("/openapi.json")

    assert response.status_code == 200
    return response.json()


def _openapi_with_headers(
    *, base_url: str = "http://testserver", headers: dict[str, str] | None = None
) -> dict:
    with TestClient(app, base_url=base_url, raise_server_exceptions=False) as client:
        response = client.get("/openapi.json", headers=headers or {})

    assert response.status_code == 200
    return response.json()


def test_openapi_exposes_bearer_auth_security_scheme():
    schema = _openapi()
    bearer_scheme = schema["components"]["securitySchemes"]["HTTPBearer"]

    assert schema["info"]["title"] == "LockedOut"
    assert "/" not in schema["paths"]
    assert "## Authentication" in schema["info"]["description"]
    assert "## Successful Use Case" in schema["info"]["description"]
    assert "POST /v1/parties/register" in schema["info"]["description"]
    assert "POST /v2/parties/register" in schema["info"]["description"]
    assert "POST /v2/parties/login" in schema["info"]["description"]
    assert "POST /v1/order/create" in schema["info"]["description"]
    assert "<baseUrl>" not in schema["info"]["description"]
    assert "http://testserver/v1/parties/register" in schema["info"]["description"]
    assert "two bearer credential modes" in schema["info"]["description"]
    assert "http://testserver/v1/order/create" in schema["info"]["description"]
    assert "http://testserver/v1/orders?limit=20&offset=0" in schema["info"]["description"]
    assert "http://testserver/v1/order/<orderId>" in schema["info"]["description"]
    assert "http://testserver/v1/order/<orderId>/ubl" in schema["info"]["description"]
    assert "Authorization: Bearer <appKey>" in schema["info"]["description"]
    assert "Authorization: Bearer <password>" in schema["info"]["description"]
    assert "X-Party-Email: <registered contact email>" in schema["info"]["description"]
    assert (
        "legacy `v1`, the app key must belong to either the buyer" in schema["info"]["description"]
    )
    assert '"buyerEmail": "orders@buyerco.example"' in schema["info"]["description"]
    assert "`GET /v1/order/{order_id}/ubl` returns XML, not JSON." in schema["info"]["description"]
    assert "POST /v1/orders/convert/transcript" in schema["info"]["description"]
    assert schema["servers"] == [{"url": "http://testserver"}]
    assert bearer_scheme["type"] == "http"
    assert bearer_scheme["scheme"] == "bearer"
    assert "legacy `v1` app key" in bearer_scheme["description"]
    assert "`v2` password" in bearer_scheme["description"]
    assert "X-Party-Email" in bearer_scheme["description"]


def test_openapi_description_uses_request_host_without_cross_request_leakage():
    render_schema = _openapi("https://seng2021.onrender.com")
    railway_schema = _openapi("https://lockedout.up.railway.app")

    render_description = render_schema["info"]["description"]
    railway_description = railway_schema["info"]["description"]

    assert "https://seng2021.onrender.com/v1/parties/register" in render_description
    assert render_schema["servers"] == [{"url": "https://seng2021.onrender.com"}]
    assert "https://lockedout.up.railway.app/v1/parties/register" in railway_description
    assert railway_schema["servers"] == [{"url": "https://lockedout.up.railway.app"}]
    assert "https://lockedout.up.railway.app" not in render_description
    assert "https://seng2021.onrender.com" not in railway_description


def test_openapi_prefers_forwarded_proto_and_host_for_proxy_deployments():
    schema = _openapi_with_headers(
        base_url="http://testserver",
        headers={
            "x-forwarded-proto": "https",
            "x-forwarded-host": "lockedout.up.railway.app",
        },
    )

    assert schema["servers"] == [{"url": "https://lockedout.up.railway.app"}]
    assert "https://lockedout.up.railway.app/v1/parties/register" in schema["info"]["description"]
    assert "http://testserver/v1/parties/register" not in schema["info"]["description"]


def test_protected_order_routes_declare_bearer_security():
    schema = _openapi()
    protected_paths = [
        ("/v1/orders", "get"),
        ("/v1/order/create", "post"),
        ("/v1/order/{order_id}", "get"),
        ("/v1/order/{order_id}/payload", "get"),
        ("/v1/order/{order_id}/ubl", "get"),
        ("/v1/order/{order_id}", "put"),
        ("/v1/order/{order_id}", "delete"),
        ("/v1/orders/convert/transcript", "post"),
        ("/v1/analytics/orders", "get"),
    ]

    for path, method in protected_paths:
        operation = schema["paths"][path][method]
        assert operation["security"] == [{"HTTPBearer": []}]
        parameter_names = {param["name"] for param in operation.get("parameters", [])}
        assert "X-Party-Email" in parameter_names


def test_user_fetch_docs_reflect_mixed_bearer_auth():
    schema = _openapi()
    user_fetch = schema["paths"]["/v1/parties/userFetch"]["get"]

    assert user_fetch["summary"] == "Fetch the current party from the supplied bearer credential"
    assert "legacy `v1` app key" in user_fetch["description"]
    assert "`v2` password flow" in user_fetch["description"]
    assert "X-Party-Email" in user_fetch["description"]
    assert user_fetch["security"] == [{"HTTPBearer": []}]
    parameters = {param["name"]: param for param in user_fetch["parameters"]}
    assert parameters["X-Party-Email"]["required"] is False
    assert (
        "Required when sending `Authorization: Bearer <password>`"
        in parameters["X-Party-Email"]["description"]
    )


def test_http_endpoints_include_summaries_and_tags():
    schema = _openapi()

    assert [tag["name"] for tag in schema["tags"]] == [
        "Parties",
        "Orders",
        "Catalogue and Inventory",
        "Health",
    ]
    assert schema["paths"]["/v1/health"]["get"]["summary"] == "Health check"
    assert schema["paths"]["/v1/health"]["get"]["tags"] == ["Health"]
    assert schema["paths"]["/v1/parties/register"]["post"]["summary"] == (
        "Register a party and issue an app key"
    )
    assert schema["paths"]["/v1/parties/register"]["post"]["tags"] == ["Parties"]
    assert schema["paths"]["/v2/parties/register"]["post"]["summary"] == (
        "Register a party with email and password"
    )
    assert schema["paths"]["/v2/parties/login"]["post"]["summary"] == (
        "Log in with contact email and password"
    )
    assert (
        schema["paths"]["/v1/order/create"]["post"]["summary"]
        == "Create a draft order (authenticated)"
    )
    assert schema["paths"]["/v1/order/create"]["post"]["tags"] == ["Orders"]
    assert schema["paths"]["/v1/orders"]["get"]["summary"] == "List orders (authenticated)"
    assert (
        schema["paths"]["/v1/order/{order_id}"]["get"]["summary"] == "Get an order (authenticated)"
    )
    assert schema["paths"]["/v1/order/{order_id}/payload"]["get"]["summary"] == (
        "Get order payload (authenticated)"
    )
    assert (
        schema["paths"]["/v1/order/{order_id}"]["put"]["summary"]
        == "Save draft order updates (authenticated)"
    )
    assert schema["paths"]["/v1/order/{order_id}/ubl"]["get"]["summary"] == (
        "Get order UBL XML (authenticated)"
    )
    assert schema["paths"]["/v1/analytics/orders"]["get"]["summary"] == (
        "Get order analytics (authenticated)"
    )
    assert "/v1/orders/validate" not in schema["paths"]


def test_key_schemas_include_examples():
    schema = _openapi()
    schemas = schema["components"]["schemas"]

    assert schemas["OrderRequest"]["example"]["buyerEmail"] == "orders@buyerco.example"
    assert "OrderRequest-Input" not in schemas
    assert "OrderRequest-Output" not in schemas
    assert "LineItem-Input" not in schemas
    assert "LineItem-Output" not in schemas
    assert "HTTPValidationError" not in schemas
    assert "ValidationError" not in schemas
    assert "Severity" not in schemas
    assert "Issue" not in schemas
    assert "ValidationResponse" not in schemas
    assert schemas["PartyRegistrationRequest"]["example"]["partyName"] == "Acme Books"
    assert schemas["PartyRegistrationV2Request"]["example"]["password"] == "super-secure-password"
    assert schemas["PartyLoginV2Request"]["example"]["contactEmail"] == "orders@acmebooks.example"
    assert schemas["OrderConversionResponse"]["examples"][0]["source"] == "transcript"
    assert (
        schemas["OrderConversionResponse"]["examples"][1]["issues"][0]
        == "buyerName: Field required"
    )
    assert schemas["RequestValidationErrorResponse"]["examples"][0]["message"] == (
        "Request validation failed."
    )
    assert schemas["OrderListResponse"]["examples"][0]["items"][0]["orderId"] == "ord_abc123def456"
    assert schemas["SellerAnalytics"]["example"]["averageDailyOrders"] == 0.33
    assert schemas["BuyerAnalytics"]["example"]["averageDailySpend"] == 5.0
    assert schemas["BuyerAndSellerAnalyticsResponse"]["example"]["netProfit"] == 10.5
    assert schemas["NoOrdersAnalyticsResponse"]["example"]["message"] == "No orders found"
    assert (
        schemas["RequestValidationErrorResponse"]["properties"]["errors"]["items"]["$ref"]
        == "#/components/schemas/ValidationFieldError"
    )
    assert schemas["ValidationFieldError"]["example"]["path"] == "lines[0].quantity"
    assert '"#/$defs/ValidationFieldError"' not in str(schema)


def test_endpoint_responses_include_examples_for_common_flows():
    schema = _openapi()
    expected_xml_example = generate_docs_example_ubl_order_xml()

    list_orders = schema["paths"]["/v1/orders"]["get"]
    assert (
        list_orders["responses"]["200"]["content"]["application/json"]["examples"]["firstPage"][
            "value"
        ]["page"]["hasMore"]
        is True
    )
    assert (
        list_orders["responses"]["200"]["content"]["application/json"]["examples"]["finalPage"][
            "value"
        ]["page"]["offset"]
        == 20
    )
    assert (
        list_orders["responses"]["200"]["content"]["application/json"]["examples"]["firstPage"][
            "value"
        ]["page"]["total"]
        == 57
    )
    list_order_parameters = {param["name"]: param for param in list_orders["parameters"]}
    assert set(list_order_parameters) == {"limit", "offset", "X-Party-Email"}
    assert (
        "Required when sending `Authorization: Bearer <password>`"
        in list_order_parameters["X-Party-Email"]["description"]
    )
    assert "400" not in list_orders["responses"]
    assert list_orders["responses"]["422"]["content"]["application/json"]["schema"]["$ref"] == (
        "#/components/schemas/RequestValidationErrorResponse"
    )

    create_post = schema["paths"]["/v1/order/create"]["post"]
    assert "Create a new draft order" in create_post["description"]
    assert "remain editable in the current MVP" in create_post["description"]
    assert create_post["responses"]["201"]["content"]["application/json"]["example"]["orderId"] == (
        "ord_abc123def456"
    )
    assert create_post["responses"]["201"]["description"] == "Draft order created successfully."
    assert "ublXml" not in create_post["responses"]["201"]["content"]["application/json"]["example"]
    assert (
        create_post["responses"]["401"]["content"]["application/json"]["example"]["detail"]
        == "Unauthorized"
    )

    update_put = schema["paths"]["/v1/order/{order_id}"]["put"]
    assert "Save changes to an existing draft order" in update_put["description"]
    assert "Only orders in `DRAFT` status remain editable" in update_put["description"]
    assert (
        update_put["responses"]["200"]["content"]["application/json"]["example"]["updatedAt"]
        == "2026-03-14T11:00:00Z"
    )
    assert update_put["responses"]["200"]["description"] == "Draft order updated successfully."
    assert "ublXml" not in update_put["responses"]["200"]["content"]["application/json"]["example"]

    get_order = schema["paths"]["/v1/order/{order_id}"]["get"]
    assert "ublXml" not in get_order["responses"]["200"]["content"]["application/json"]["example"]
    assert "warnings" not in get_order["responses"]["200"]["content"]["application/json"]["example"]
    assert "500" not in get_order["responses"]
    assert "422" not in get_order["responses"]

    get_order_payload = schema["paths"]["/v1/order/{order_id}/payload"]["get"]
    assert (
        get_order_payload["responses"]["200"]["content"]["application/json"]["example"]["payload"][
            "buyerEmail"
        ]
        == "orders@buyerco.example"
    )
    assert (
        get_order_payload["responses"]["422"]["content"]["application/json"]["schema"]["$ref"]
        == "#/components/schemas/RequestValidationErrorResponse"
    )

    get_ubl = schema["paths"]["/v1/order/{order_id}/ubl"]["get"]
    xml_example = get_ubl["responses"]["200"]["content"]["application/xml"]["example"]
    assert get_ubl["operationId"] == "get_order_ubl_xml"
    assert xml_example == expected_xml_example
    assert xml_example.startswith('<?xml version="1.0" encoding="utf-8"?>')
    assert (
        'xmlns:cac="urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2"'
        in (xml_example)
    )
    assert 'currencyID="AUD"' in xml_example
    assert "application/json" not in get_ubl["responses"]["200"]["content"]
    assert "422" not in get_ubl["responses"]

    delete_order = schema["paths"]["/v1/order/{order_id}"]["delete"]
    assert "422" not in delete_order["responses"]

    validation_422 = create_post["responses"]["422"]["content"]["application/json"]
    assert validation_422["schema"]["$ref"] == "#/components/schemas/RequestValidationErrorResponse"
    assert create_post["responses"]["422"]["description"] == (
        "The order create payload is missing required fields or contains invalid order values."
    )
    assert validation_422["examples"]["invalidLineQuantity"]["value"]["errors"][0]["path"] == (
        "lines[0].quantity"
    )
    assert validation_422["examples"]["invalidCurrency"]["value"]["errors"][0]["path"] == "currency"

    register_post = schema["paths"]["/v1/parties/register"]["post"]
    register_422 = register_post["responses"]["422"]["content"]["application/json"]
    assert register_post["responses"]["422"]["description"] == (
        "The registration payload is missing required party details or uses an invalid contact email."
    )
    assert register_422["examples"]["missingPartyName"]["value"]["errors"][0]["path"] == (
        "partyName"
    )
    assert register_422["examples"]["invalidContactEmail"]["value"]["errors"][0]["path"] == (
        "contactEmail"
    )

    transcript_post = schema["paths"]["/v1/orders/convert/transcript"]["post"]
    assert "legacy `v1` app key" in transcript_post["description"]
    assert "`v2` password flow" in transcript_post["description"]
    assert "X-Party-Email" in transcript_post["description"]
    transcript_422 = transcript_post["responses"]["422"]["content"]["application/json"]
    assert "buyer and seller emails" in transcript_post["description"]
    assert transcript_post["responses"]["422"]["description"] == (
        "The transcript conversion request is missing the required transcript body."
    )
    assert transcript_422["examples"]["missingTranscript"]["value"]["errors"][0]["path"] == (
        "transcript"
    )
    transcript_examples = transcript_post["responses"]["200"]["content"]["application/json"][
        "examples"
    ]
    assert transcript_examples["success"]["value"]["issues"] == []
    assert "warnings" not in transcript_examples["success"]["value"]
    assert (
        transcript_examples["incomplete"]["value"]["issues"][1]
        == "currency: currency is recommended before create or update."
    )
    transcript_request_example = schema["components"]["schemas"]["TranscriptConversionRequest"][
        "example"
    ]
    assert "orders@buyerco.example" in transcript_request_example["transcript"]
    assert "sales@supplier.example" in transcript_request_example["transcript"]
    analytics_get = schema["paths"]["/v1/analytics/orders"]["get"]
    assert analytics_get["summary"] == "Get order analytics (authenticated)"
    assert "legacy `v1` app key" in analytics_get["description"]
    assert "`v2` password flow" in analytics_get["description"]
    assert "X-Party-Email" in analytics_get["description"]
    analytics_parameters = {param["name"]: param for param in analytics_get["parameters"]}
    assert analytics_parameters["fromDate"]["required"] is True
    assert analytics_parameters["toDate"]["required"] is True
    assert analytics_parameters["X-Party-Email"]["required"] is False
    assert (
        analytics_get["responses"]["200"]["content"]["application/json"]["examples"]["seller"][
            "value"
        ]["analytics"]["averageDailyOrders"]
        == 0.33
    )
    assert (
        analytics_get["responses"]["200"]["content"]["application/json"]["examples"][
            "buyerAndSeller"
        ]["value"]["sellerAnalytics"]["averageDailyIncome"]
        == 6.67
    )
    assert (
        analytics_get["responses"]["200"]["content"]["application/json"]["examples"]["noOrders"][
            "value"
        ]["message"]
        == "No orders found"
    )
    assert (
        analytics_get["responses"]["422"]["description"]
        == "The analytics request is missing one or both required date-range query parameters."
    )
    analytics_422 = analytics_get["responses"]["422"]["content"]["application/json"]["examples"]
    assert analytics_422["missingFromDate"]["value"]["errors"][0]["path"] == "fromDate"
    assert analytics_422["missingToDate"]["value"]["errors"][0]["path"] == "toDate"

    fetch_status = schema["components"]["schemas"]["OrderFetchResponse"]["properties"]["status"]
    assert (
        "`DRAFT` means the order is stored as an editable draft in the current MVP flow."
        in fetch_status["description"]
    )
    assert "not user-reachable in the current backend MVP" in fetch_status["description"]
    assert "`CANCELLED` means the order was cancelled." in fetch_status["description"]
    assert "/v1/orders/convert/csv" not in schema["paths"]


def test_docs_routes_use_custom_swagger_wrapper_for_ubl_xml_example():
    with TestClient(app, raise_server_exceptions=False) as client:
        root_response = client.get("/")
        docs_response = client.get("/docs")

    for response in (root_response, docs_response):
        assert response.status_code == 200
        assert "/static/swagger-ui-5.32.0.css" in response.text
        assert "/static/swagger-ui-bundle-5.32.0.js" in response.text
        assert "/static/swagger-runtime-xml-plugin.js" in response.text
        assert "window.RuntimeXmlExamplePlugin" in response.text
        assert "MutationObserver" not in response.text
        assert "orderOperationsSorter" in response.text
        assert '"post /v1/order/create": 0' in response.text
        assert '"put /v1/order/{order_id}": 1' in response.text
        assert '"get /v1/order/{order_id}": 2' in response.text
        assert '"get /v1/order/{order_id}/payload": 3' in response.text
        assert '"delete /v1/order/{order_id}": 4' in response.text
        assert '"get /v1/orders": 5' in response.text
        assert '"get /v1/order/{order_id}/ubl": 6' in response.text
        assert '"post /v1/orders/convert/transcript": 7' in response.text


def test_custom_swagger_plugin_asset_is_served():
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/static/swagger-runtime-xml-plugin.js")

    assert response.status_code == 200
    assert "runtime-xml-example-plugin" in response.text
    assert "getXmlSampleSchema" in response.text

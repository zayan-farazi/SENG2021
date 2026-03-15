from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app
from app.services.ubl_order import generate_docs_example_ubl_order_xml


def _openapi() -> dict:
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/openapi.json")

    assert response.status_code == 200
    return response.json()


def test_openapi_exposes_bearer_auth_security_scheme():
    schema = _openapi()

    assert schema["components"]["securitySchemes"]["HTTPBearer"] == {
        "type": "http",
        "scheme": "bearer",
        "description": "Register once to receive an app key, then send it as 'Authorization: Bearer <appKey>'.",
    }


def test_protected_order_routes_declare_bearer_security():
    schema = _openapi()
    protected_paths = [
        ("/v1/order/create", "post"),
        ("/v1/order/{order_id}", "get"),
        ("/v1/order/{order_id}/ubl", "get"),
        ("/v1/order/{order_id}", "put"),
        ("/v1/order/{order_id}", "delete"),
        ("/v1/orders/validate", "post"),
        ("/v1/orders/convert/transcript", "post"),
        ("/v1/orders/convert/csv", "post"),
    ]

    for path, method in protected_paths:
        operation = schema["paths"][path][method]
        assert operation["security"] == [{"HTTPBearer": []}]


def test_http_endpoints_include_summaries_and_tags():
    schema = _openapi()

    assert schema["paths"]["/v1/health"]["get"]["summary"] == "Health check"
    assert schema["paths"]["/v1/health"]["get"]["tags"] == ["Health"]
    assert schema["paths"]["/v1/parties/register"]["post"]["summary"] == (
        "Register a party and issue an app key"
    )
    assert schema["paths"]["/v1/parties/register"]["post"]["tags"] == ["Parties"]
    assert schema["paths"]["/v1/order/create"]["post"]["summary"] == (
        "Create an order (Bearer app key required)"
    )
    assert schema["paths"]["/v1/order/create"]["post"]["tags"] == ["Orders"]
    assert schema["paths"]["/v1/order/{order_id}"]["get"]["summary"] == (
        "Get an order (Bearer app key required)"
    )
    assert schema["paths"]["/v1/order/{order_id}/ubl"]["get"]["summary"] == (
        "Get order UBL XML (Bearer app key required)"
    )
    assert schema["paths"]["/v1/orders/validate"]["post"]["summary"] == (
        "Validate an order payload (Bearer app key required)"
    )


def test_key_schemas_include_examples():
    schema = _openapi()
    schemas = schema["components"]["schemas"]

    assert schemas["OrderRequest-Input"]["example"]["buyerEmail"] == "orders@buyerco.example"
    assert schemas["PartyRegistrationRequest"]["example"]["partyName"] == "Acme Books"
    assert schemas["ValidationResponse"]["examples"][1]["valid"] is False
    assert schemas["OrderConversionResponse"]["examples"][0]["source"] == "transcript"


def test_endpoint_responses_include_examples_for_common_flows():
    schema = _openapi()
    expected_xml_example = generate_docs_example_ubl_order_xml()

    create_post = schema["paths"]["/v1/order/create"]["post"]
    assert create_post["responses"]["201"]["content"]["application/json"]["example"]["orderId"] == (
        "ord_abc123def456"
    )
    assert "ublXml" not in create_post["responses"]["201"]["content"]["application/json"]["example"]
    assert (
        create_post["responses"]["401"]["content"]["application/json"]["example"]["detail"]
        == "Unauthorized"
    )

    update_put = schema["paths"]["/v1/order/{order_id}"]["put"]
    assert (
        update_put["responses"]["200"]["content"]["application/json"]["example"]["updatedAt"]
        == "2026-03-14T11:00:00Z"
    )
    assert "ublXml" not in update_put["responses"]["200"]["content"]["application/json"]["example"]

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

    validate_post = schema["paths"]["/v1/orders/validate"]["post"]
    examples = validate_post["responses"]["200"]["content"]["application/json"]["examples"]
    assert examples["valid"]["value"]["valid"] is True
    assert examples["invalid"]["value"]["valid"] is False

    csv_post = schema["paths"]["/v1/orders/convert/csv"]["post"]
    assert "buyerEmail,buyerName,sellerEmail" in csv_post["description"]
    assert (
        csv_post["responses"]["400"]["content"]["application/json"]["examples"]["wrongFileType"][
            "value"
        ]["detail"]
        == "CSV upload must use a .csv file."
    )


def test_docs_route_uses_custom_swagger_wrapper_for_ubl_xml_example():
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/docs")

    assert response.status_code == 200
    assert "/static/swagger-ui-5.32.0.css" in response.text
    assert "/static/swagger-ui-bundle-5.32.0.js" in response.text
    assert "/static/swagger-runtime-xml-plugin.js" in response.text
    assert "window.RuntimeXmlExamplePlugin" in response.text
    assert "MutationObserver" not in response.text


def test_custom_swagger_plugin_asset_is_served():
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/static/swagger-runtime-xml-plugin.js")

    assert response.status_code == 200
    assert "runtime-xml-example-plugin" in response.text
    assert "getXmlSampleSchema" in response.text

import os
from urllib.parse import urlparse

import httpx


class InvoiceServiceError(RuntimeError):
    def __init__(
        self,
        *,
        reason: str,
        message: str,
        status_code: int | None = None,
        response_body: str | None = None,
    ):
        super().__init__(message)
        self.reason = reason
        self.status_code = status_code
        self.response_body = response_body


def _base_url() -> str:
    configured = os.getenv("INVOICE_API_BASE", "https://api.lastminutepush.one").rstrip("/")
    parsed = urlparse(configured)
    if parsed.scheme and parsed.netloc in {"lastminutepush.one", "www.lastminutepush.one"}:
        return f"{parsed.scheme}://api.lastminutepush.one"
    return configured


def _headers(accept: str = "application/json") -> dict[str, str]:
    key = os.getenv("INVOICE_API_KEY")
    if not key:
        raise InvoiceServiceError(
            reason="misconfigured",
            message="INVOICE_API_KEY not configured",
        )
    return {"X-API-Key": key, "Accept": accept}


def _trim_response_body(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    if not normalized:
        return None
    return normalized[:500]


def _classify_status(status_code: int) -> str:
    if status_code in {401, 403}:
        return "auth"
    if status_code in {400, 404, 409, 422}:
        return "payload"
    if status_code >= 500:
        return "unavailable"
    return "unexpected"


def _translate_http_error(exc: httpx.HTTPStatusError) -> InvoiceServiceError:
    response = exc.response
    return InvoiceServiceError(
        reason=_classify_status(response.status_code),
        message=str(exc),
        status_code=response.status_code,
        response_body=_trim_response_body(response.text),
    )


def _translate_request_error(exc: httpx.RequestError) -> InvoiceServiceError:
    return InvoiceServiceError(
        reason="unavailable",
        message=str(exc),
    )


def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(timeout=20.0, follow_redirects=True)


async def _request_json(
    method: str,
    path: str,
    *,
    payload: dict | None = None,
    accept: str = "application/json",
) -> dict:
    try:
        async with _client() as client:
            response = await client.request(
                method,
                f"{_base_url()}{path}",
                json=payload,
                headers=_headers(accept=accept),
            )
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        raise _translate_http_error(exc) from exc
    except httpx.RequestError as exc:
        raise _translate_request_error(exc) from exc
    return response.json()


async def _request_text(
    method: str,
    path: str,
    *,
    accept: str,
) -> str:
    try:
        async with _client() as client:
            response = await client.request(
                method,
                f"{_base_url()}{path}",
                headers=_headers(accept=accept),
            )
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        raise _translate_http_error(exc) from exc
    except httpx.RequestError as exc:
        raise _translate_request_error(exc) from exc
    return response.text


async def _request_bytes(
    method: str,
    path: str,
    *,
    accept: str,
) -> bytes:
    try:
        async with _client() as client:
            response = await client.request(
                method,
                f"{_base_url()}{path}",
                headers=_headers(accept=accept),
            )
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        raise _translate_http_error(exc) from exc
    except httpx.RequestError as exc:
        raise _translate_request_error(exc) from exc
    return response.content


async def create_invoice(payload: dict) -> dict:
    return await _request_json("POST", "/v1/invoices", payload=payload)


async def get_invoice(invoice_id: str) -> dict:
    return await _request_json("GET", f"/v1/invoices/{invoice_id}")


async def get_invoice_ubl_xml(invoice_id: str) -> str:
    return await _request_text("GET", f"/v1/invoices/{invoice_id}", accept="application/xml")


async def get_invoice_pdf(invoice_id: str) -> bytes:
    return await _request_bytes("GET", f"/v1/invoices/{invoice_id}/pdf", accept="application/pdf")


async def update_invoice(invoice_id: str, payload: dict) -> dict:
    return await _request_json("PUT", f"/v1/invoices/{invoice_id}", payload=payload)


async def delete_invoice(invoice_id: str) -> None:
    try:
        async with _client() as client:
            response = await client.request(
                "DELETE",
                f"{_base_url()}/v1/invoices/{invoice_id}",
                headers=_headers(),
            )
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        raise _translate_http_error(exc) from exc
    except httpx.RequestError as exc:
        raise _translate_request_error(exc) from exc


async def transition_invoice_status(invoice_id: str, payload: dict) -> dict:
    return await _request_json("POST", f"/v1/invoices/{invoice_id}/status", payload=payload)

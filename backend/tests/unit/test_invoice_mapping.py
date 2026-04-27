from __future__ import annotations

import pytest

from app.integrations import lastminutepush_client
from app.integrations.lastminutepush_client import InvoiceServiceError


class _FakeResponse:
    def __init__(self, json_data=None, text_data="", content_data=b"", status_ok=True):
        self._json = json_data or {}
        self.text = text_data
        self.content = content_data
        self._ok = status_ok

    def raise_for_status(self):
        if not self._ok:
            raise RuntimeError("http error")

    def json(self):
        return self._json


class _FakeAsyncClient:
    init_kwargs: list[dict] = []

    def __init__(self, *args, **kwargs):
        self.calls = []
        self.__class__.init_kwargs.append(kwargs)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def post(self, url, json=None, headers=None):
        self.calls.append(("POST", url, json, headers))
        return _FakeResponse(json_data={"invoice_id": "inv_1"})

    async def get(self, url, headers=None):
        self.calls.append(("GET", url, None, headers))
        if url.endswith("/pdf"):
            return _FakeResponse(content_data=b"%PDF-1.4")
        if headers and headers.get("Accept") == "application/xml":
            return _FakeResponse(text_data="<Invoice/>")
        return _FakeResponse(json_data={"invoice_id": "inv_1", "status": "draft"})

    async def request(self, method, url, json=None, headers=None):
        if method == "POST":
            return await self.post(url, json=json, headers=headers)
        if method == "GET":
            return await self.get(url, headers=headers)
        if method == "DELETE":
            self.calls.append(("DELETE", url, None, headers))
            return _FakeResponse()
        raise AssertionError(f"Unexpected method {method}")


def test_headers_raises_when_missing_key(monkeypatch):
    monkeypatch.delenv("INVOICE_API_KEY", raising=False)
    with pytest.raises(InvoiceServiceError, match="INVOICE_API_KEY not configured"):
        lastminutepush_client._headers()  # type: ignore[attr-defined]


def test_base_url_normalizes_frontend_host_to_api_host(monkeypatch):
    monkeypatch.setenv("INVOICE_API_BASE", "https://lastminutepush.one")
    assert lastminutepush_client._base_url() == "https://api.lastminutepush.one"  # type: ignore[attr-defined]

    monkeypatch.setenv("INVOICE_API_BASE", "https://www.lastminutepush.one")
    assert lastminutepush_client._base_url() == "https://api.lastminutepush.one"  # type: ignore[attr-defined]


@pytest.mark.anyio
async def test_create_and_fetch_invoice(monkeypatch):
    monkeypatch.setenv("INVOICE_API_KEY", "k_test")
    monkeypatch.setenv("INVOICE_API_BASE", "https://lastminutepush.one")
    _FakeAsyncClient.init_kwargs.clear()

    # Patch the module's httpx.AsyncClient
    import httpx

    monkeypatch.setattr(httpx, "AsyncClient", _FakeAsyncClient)

    created = await lastminutepush_client.create_invoice({"order_reference": "ord_1", "items": []})
    assert created["invoice_id"] == "inv_1"

    inv = await lastminutepush_client.get_invoice("inv_1")
    assert inv["invoice_id"] == "inv_1"

    xml = await lastminutepush_client.get_invoice_ubl_xml("inv_1")
    assert xml == "<Invoice/>"

    pdf = await lastminutepush_client.get_invoice_pdf("inv_1")
    assert pdf.startswith(b"%PDF-1.4")
    assert _FakeAsyncClient.init_kwargs
    assert all(kwargs.get("follow_redirects") is True for kwargs in _FakeAsyncClient.init_kwargs)

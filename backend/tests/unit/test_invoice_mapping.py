from __future__ import annotations

import os
import types

import pytest

from app.integrations import lastminutepush_client


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
    def __init__(self, *args, **kwargs):
        self.calls = []

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


def test_headers_raises_when_missing_key(monkeypatch):
    monkeypatch.delenv("INVOICE_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="INVOICE_API_KEY not configured"):
        lastminutepush_client._headers()  # type: ignore[attr-defined]


@pytest.mark.anyio
async def test_create_and_fetch_invoice(monkeypatch):
    monkeypatch.setenv("INVOICE_API_KEY", "k_test")
    monkeypatch.setenv("INVOICE_API_BASE", "https://lastminutepush.one")

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
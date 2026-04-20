import os

import httpx


def _base_url() -> str:
    return os.getenv("INVOICE_API_BASE", "https://lastminutepush.one").rstrip("/")


def _headers(accept: str = "application/json") -> dict[str, str]:
    key = os.getenv("INVOICE_API_KEY")
    if not key:
        raise RuntimeError("INVOICE_API_KEY not configured")
    return {"X-API-Key": key, "Accept": accept}


async def create_invoice(payload: dict) -> dict:
    async with httpx.AsyncClient(timeout=20.0) as client:
        r = await client.post(f"{_base_url()}/v1/invoices", json=payload, headers=_headers())
    r.raise_for_status()
    return r.json()


async def get_invoice(invoice_id: str) -> dict:
    async with httpx.AsyncClient(timeout=20.0) as client:
        r = await client.get(f"{_base_url()}/v1/invoices/{invoice_id}", headers=_headers())
    r.raise_for_status()
    return r.json()


async def get_invoice_ubl_xml(invoice_id: str) -> str:
    async with httpx.AsyncClient(timeout=20.0) as client:
        r = await client.get(
            f"{_base_url()}/v1/invoices/{invoice_id}",
            headers=_headers(accept="application/xml"),
        )
    r.raise_for_status()
    return r.text


async def get_invoice_pdf(invoice_id: str) -> bytes:
    async with httpx.AsyncClient(timeout=20.0) as client:
        r = await client.get(
            f"{_base_url()}/v1/invoices/{invoice_id}/pdf",
            headers=_headers(accept="application/pdf"),
        )
    r.raise_for_status()
    return r.content


async def update_invoice(invoice_id: str, payload: dict) -> dict:
    async with httpx.AsyncClient(timeout=20.0) as client:
        r = await client.put(
            f"{_base_url()}/v1/invoices/{invoice_id}",
            json=payload,
            headers=_headers(),
        )
    r.raise_for_status()
    return r.json()


async def delete_invoice(invoice_id: str) -> None:
    async with httpx.AsyncClient(timeout=20.0) as client:
        r = await client.delete(
            f"{_base_url()}/v1/invoices/{invoice_id}",
            headers=_headers(),
        )
    r.raise_for_status()
    # API returns 204 No Content


async def transition_invoice_status(invoice_id: str, payload: dict) -> dict:
    async with httpx.AsyncClient(timeout=20.0) as client:
        r = await client.post(
            f"{_base_url()}/v1/invoices/{invoice_id}/status",
            json=payload,
            headers=_headers(),
        )
    r.raise_for_status()
    return r.json()

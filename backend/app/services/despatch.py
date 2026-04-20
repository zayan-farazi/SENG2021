import os

import httpx

from app.env import load_local_env_files

DEFAULT_DEVEX_TIMEOUT_SECONDS = 30.0


def _parse_timeout_seconds(value: str | None) -> float:
    if value is None:
        return DEFAULT_DEVEX_TIMEOUT_SECONDS
    try:
        parsed = float(value)
    except ValueError:
        return DEFAULT_DEVEX_TIMEOUT_SECONDS
    return parsed if parsed > 0 else DEFAULT_DEVEX_TIMEOUT_SECONDS


async def create_despatch_from_order_xml(ubl_xml: str) -> dict:
    load_local_env_files()
    api_key = os.getenv("DEVEX_API_KEY")
    if not api_key:
        raise ValueError("DevEx API key not configured. Set DEVEX_API_KEY to enable despatch creation.")
    
    base_url = os.getenv("DEVEX_BASE_URL", "https://devex.cloud.tcore.network").rstrip("/")
    timeout_seconds = _parse_timeout_seconds(os.getenv("DEVEX_TIMEOUT_SECONDS"))
    
    async with httpx.AsyncClient(timeout=timeout_seconds) as client:
        create_response = await client.post(
            f"{base_url}/api/v1/despatch/create",
            headers={
                "Api-Key": api_key,
                "Content-Type": "application/xml",
            },
            content=ubl_xml,
        )
        create_response.raise_for_status()
        advice_ids = create_response.json().get("adviceIds", [])

        if not advice_ids:
            raise ValueError("No despatch advice IDs returned.")

        retrieve_response = await client.get(
            f"{base_url}/api/v1/despatch/retrieve",
            headers={"Api-Key": api_key},
            params={
                "search-type": "advice-id",
                "query": advice_ids[0],
            },
        )
        retrieve_response.raise_for_status()
        data = retrieve_response.json()

        return {
            "adviceId": data.get("advice-id"),
            "xml": data.get("despatch-advice"),
        }

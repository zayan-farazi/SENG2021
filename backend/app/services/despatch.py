import httpx
from typing import Any
from fastapi import HTTPException

DEVEX_API_KEY = "6cd1b678cb0e7942eb3185e294f1552994ea41b2d16af7e2c36676fe23ab0850"
DEVEX_BASE_URL = "https://devex.cloud.tcore.network"

async def create_despatch_from_order_xml(ubl_xml: str) -> dict:
    async with httpx.AsyncClient() as client:
        create_response = await client.post(
            f"{DEVEX_BASE_URL}/api/v1/despatch/create",
            headers={
                "Api-Key": DEVEX_API_KEY,
                "Content-Type": "application/xml",
            },
            content=ubl_xml,
        )
        create_response.raise_for_status()
        advice_ids = create_response.json().get("adviceIds", [])

        if not advice_ids:
            raise ValueError("No despatch advice IDs returned.")

        retrieve_response = await client.get(
            f"{DEVEX_BASE_URL}/api/v1/despatch/retrieve",
            headers={"Api-Key": DEVEX_API_KEY},
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

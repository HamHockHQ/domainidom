from __future__ import annotations

import os
from typing import Optional

import httpx

NAMECOM_API_USERNAME = os.getenv("NAME_COM_USERNAME") or os.getenv("name_com_DEV_USERNAME")
NAMECOM_API_TOKEN = os.getenv("NAME_COM_API_KEY") or os.getenv("name_com_DEV_API_KEY")
NAMECOM_BASE = os.getenv("NAME_COM_BASE", "https://api.dev.name.com/v4")


async def get_namecom_price(domain: str) -> Optional[float]:
    if not (NAMECOM_API_USERNAME and NAMECOM_API_TOKEN):
        return None
    url = f"{NAMECOM_BASE}/domains:checkAvailability"
    payload = {"domainNames": [domain]}
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                url, json=payload, auth=(NAMECOM_API_USERNAME, NAMECOM_API_TOKEN)
            )
            resp.raise_for_status()
            data = resp.json()
            item = data.get("results", [{}])[0]
            price = None
            if "purchasePrice" in item and isinstance(item["purchasePrice"], dict):
                amount = item["purchasePrice"].get("amount")
                try:
                    price = float(amount) if amount is not None else None
                except Exception:
                    price = None
            return price
    except Exception:
        return None

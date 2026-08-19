"""Fetch and tabularise Hypixel's Bazaar quick status data."""

from typing import Any
import pandas as pd

BAZAAR_URL = "https://api.hypixel.net/v2/skyblock/bazaar"
columns = [
    "item_id",
    "buyPrice",
    "buyVolume",
    "sellPrice",
    "sellVolume",
    "buyMovingWeek",
    "sellMovingWeek",
    "buyOrders",
    "sellOrders",
]
_STATUS_COLUMNS = columns[1:]


def fetch_bazaar(
    *, url: str = BAZAAR_URL, client: Any | None = None, timeout: float = 10.0
) -> pd.DataFrame:
    import httpx

    owns_client = client is None
    if owns_client:
        client = httpx.Client(timeout=timeout)
    try:
        response = client.get(url)
        response.raise_for_status()
        payload = response.json()
    finally:
        if owns_client:
            client.close()
    rows = []
    for item_id, product in payload.get("products", {}).items():
        status = product.get("quick_status", {})
        rows.append(
            {"item_id": item_id, **{key: status.get(key) for key in _STATUS_COLUMNS}}
        )
    return pd.DataFrame(rows, columns=columns)

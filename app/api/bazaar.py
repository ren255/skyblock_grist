"""Fetch and tabularise Hypixel's Bazaar quick status data."""

from enum import StrEnum
from typing import Any, Literal, overload

import pandas as pd

BAZAAR_URL = "https://api.hypixel.net/v2/skyblock/bazaar"
# Public column list: importing this gives editors a discoverable list of fields.

BazaarColumn = Literal[
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


class BazaarColumns(StrEnum):
    item_id = "item_id"
    buyPrice = "buyPrice"
    buyVolume = "buyVolume"
    sellPrice = "sellPrice"
    sellVolume = "sellVolume"
    buyMovingWeek = "buyMovingWeek"
    sellMovingWeek = "sellMovingWeek"
    buyOrders = "buyOrders"
    sellOrders = "sellOrders"


class BazaarDataFrame(pd.DataFrame):
    @property
    def _constructor(self) -> type["BazaarDataFrame"]:
        return BazaarDataFrame

    @overload
    def __getitem__(self, key: BazaarColumn) -> pd.Series: ...

    @overload
    def __getitem__(self, key: Any) -> Any: ...

    def __getitem__(self, key: Any) -> Any:
        return super().__getitem__(key)


def fetch_bazaar(
    *, url: str = BAZAAR_URL, client: Any | None = None, timeout: float = 10.0
) -> BazaarDataFrame:
    """Return one row per Bazaar product, preserving API values unchanged."""
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

    products = payload.get("products", {})
    rows: list[dict[str, Any]] = []
    for item_id, product in products.items():
        status = product.get("quick_status", {})
        rows.append(
            {"item_id": item_id, **{key: status.get(key) for key in _STATUS_COLUMNS}}
        )
    return BazaarDataFrame(rows, columns=columns)

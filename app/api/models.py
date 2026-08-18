from pydantic import BaseModel, ConfigDict

# Field names mirror the Hypixel API spelling exactly (camelCase inside
# `quick_status`, snake_case for the summaries) rather than being aliased, so a
# reader can match them against the raw response without a translation step.


class BazaarOrder(BaseModel):
    """One price level of an order book (`buy_summary` / `sell_summary`).

    The first element of each summary is the best price available.
    """

    model_config = ConfigDict(extra="ignore")

    pricePerUnit: float


class BazaarQuickStatus(BaseModel):
    """Aggregate stats for a product.

    Only the weekly traded volume is used. The `buyPrice` / `sellPrice` fields
    are weighted averages of the top orders, not the best price, and are
    deliberately not modelled here.
    """

    model_config = ConfigDict(extra="ignore")

    buyMovingWeek: float


class BazaarProduct(BaseModel):
    """A single tradable product.

    `buy_summary` holds the sell offers (what you pay to buy now, ascending) and
    `sell_summary` holds the buy orders (what you get selling now, descending).
    """

    model_config = ConfigDict(extra="ignore")

    sell_summary: list[BazaarOrder]
    buy_summary: list[BazaarOrder]
    quick_status: BazaarQuickStatus


class BazaarResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    success: bool
    products: dict[str, BazaarProduct]

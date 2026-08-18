from pydantic import BaseModel

from app.api.models import BazaarProduct

MINUTES_PER_WEEK = 7 * 24 * 60
PRICE_DECIMALS = 2
RATE_DECIMALS = 4


class GemPrices(BaseModel):
    """Prices for one gem pair, ready to be written to the gem table."""

    buy_order: float
    sell_order: float
    insta_sell: float
    avg_selling_per_minute: float


def compute_gem_prices(
    flawed: BazaarProduct, flawless: BazaarProduct
) -> GemPrices | None:
    """Derive gem flip prices from the two products' order books.

    Every price is the best price on the book — the first element of a summary.
    `quick_status.buyPrice` / `sellPrice` must NOT be used: they are weighted
    averages of the top orders, and substituting them inflates the craft cost
    past the sale price, which silently breaks every profit column.

    Returns `None` when a required side of the book is empty, since no price can
    be established then.
    """
    if not flawed.sell_summary or not flawless.buy_summary or not flawless.sell_summary:
        return None

    # Buying flawed gems by placing a buy order: match the highest standing one.
    buy_order = flawed.sell_summary[0].pricePerUnit
    # Selling flawless gems by placing a sell offer: match the lowest standing one.
    sell_order = flawless.buy_summary[0].pricePerUnit
    # Selling flawless gems immediately: take the highest standing buy order.
    insta_sell = flawless.sell_summary[0].pricePerUnit
    # How fast players buy flawless gems, i.e. how fast ours can be sold.
    avg_selling_per_minute = flawless.quick_status.buyMovingWeek / MINUTES_PER_WEEK

    return GemPrices(
        buy_order=round(buy_order, PRICE_DECIMALS),
        sell_order=round(sell_order, PRICE_DECIMALS),
        insta_sell=round(insta_sell, PRICE_DECIMALS),
        avg_selling_per_minute=round(avg_selling_per_minute, RATE_DECIMALS),
    )

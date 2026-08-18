"""Feeds Bazaar prices into the Grist gem table.

This is the only module that depends on both `app.api` and `app.grist`; the two
packages stay independent of each other.
"""

import logging

from app.api.client import BazaarClient
from app.api.models import BazaarProduct
from app.api.pricing import GemPrices, compute_gem_prices
from app.grist.client import GristClient
from app.grist.models import (
    AVG_SELLING_PER_MINUTE_COL,
    BUY_ORDER_COL,
    FLAWED_NAME_COL,
    FLAWLESS_NAME_COL,
    INSTA_SELL_COL,
    SELL_ORDER_COL,
    GristRecord,
)

logger = logging.getLogger(__name__)


def build_price_fields(prices: GemPrices) -> dict:
    """Map computed prices onto Grist column ids.

    Returns the four price columns and nothing else, so formula columns cannot
    be written by construction.
    """
    return {
        BUY_ORDER_COL: prices.buy_order,
        SELL_ORDER_COL: prices.sell_order,
        INSTA_SELL_COL: prices.insta_sell,
        AVG_SELLING_PER_MINUTE_COL: prices.avg_selling_per_minute,
    }


def collect_product_ids(records: list[GristRecord]) -> set[str]:
    """Gather the Bazaar product ids the given rows refer to."""
    ids: set[str] = set()
    for record in records:
        for col in (FLAWED_NAME_COL, FLAWLESS_NAME_COL):
            name = record.fields.get(col)
            if isinstance(name, str) and name:
                ids.add(name)
    return ids


def compute_price_updates(
    records: list[GristRecord], products: dict[str, BazaarProduct]
) -> list[tuple[int, dict]]:
    """Work out which rows need new prices.

    Rows whose gem is missing from the Bazaar, or whose order book is too empty
    to price, are skipped so one bad gem cannot stop the rest. Rows whose stored
    values already match are left out entirely, keeping repeat runs write-free.
    """
    updates: list[tuple[int, dict]] = []

    for record in records:
        flawed_name = record.fields.get(FLAWED_NAME_COL)
        flawless_name = record.fields.get(FLAWLESS_NAME_COL)
        if not isinstance(flawed_name, str) or not isinstance(flawless_name, str):
            continue

        flawed = products.get(flawed_name)
        flawless = products.get(flawless_name)
        if flawed is None or flawless is None:
            missing = [
                name
                for name, product in ((flawed_name, flawed), (flawless_name, flawless))
                if product is None
            ]
            logger.warning("Skipping row %s: not on the Bazaar: %s", record.id, missing)
            continue

        prices = compute_gem_prices(flawed, flawless)
        if prices is None:
            logger.warning(
                "Skipping row %s (%s): order book too empty to price",
                record.id,
                flawed_name,
            )
            continue

        fields = build_price_fields(prices)
        if all(record.fields.get(col) == value for col, value in fields.items()):
            continue

        updates.append((record.id, fields))

    return updates


def sync_gem_prices(
    grist_client: GristClient,
    bazaar_client: BazaarClient,
    doc_id: str,
    table_id: str,
) -> list[tuple[int, dict]]:
    """Refresh the price columns of `table_id` from the Bazaar.

    Assumes the table and its rows already exist — run the schema and record
    syncs first.
    """
    # Rows first: they decide which of the ~2100 Bazaar products are worth parsing.
    records = grist_client.list_records(doc_id, table_id)
    if not records:
        logger.info("Table %s has no rows, skipping price sync", table_id)
        return []

    products = bazaar_client.fetch_products(collect_product_ids(records))

    updates = compute_price_updates(records, products)
    logger.info(
        "Table %s: %d of %d rows need new prices", table_id, len(updates), len(records)
    )
    if not updates:
        return updates

    grist_client.update_record_fields(doc_id, table_id, updates)
    return updates

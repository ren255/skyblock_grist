from app.api.models import BazaarProduct
from app.gem_prices import (
    build_price_fields,
    collect_product_ids,
    compute_price_updates,
    sync_gem_prices,
)
from app.grist.models import (
    AVG_SELLING_PER_MINUTE_COL,
    BUY_ORDER_COL,
    FLAWED_NAME_COL,
    FLAWLESS_NAME_COL,
    GEM_TABLE_SCHEME,
    INSTA_SELL_COL,
    SELL_ORDER_COL,
    GristRecord,
)

DOC_ID = "docABC"
TABLE_ID = "gem"

PRICE_COLS = {
    BUY_ORDER_COL,
    SELL_ORDER_COL,
    INSTA_SELL_COL,
    AVG_SELLING_PER_MINUTE_COL,
}


def _product(sell_top: float, buy_top: float, buy_moving_week: float = 10080.0):
    return BazaarProduct.model_validate(
        {
            "sell_summary": [{"pricePerUnit": sell_top}],
            "buy_summary": [{"pricePerUnit": buy_top}],
            "quick_status": {"buyMovingWeek": buy_moving_week},
        }
    )


def _products(*names: str) -> dict[str, BazaarProduct]:
    """Flawed gems priced cheaply, flawless ones expensively."""
    out = {}
    for name in names:
        out[f"FLAWED_{name}_GEM"] = _product(100.0, 120.0)
        out[f"FLAWLESS_{name}_GEM"] = _product(900000.0, 950000.0)
    return out


def _record(row_id: int, name: str, **prices) -> GristRecord:
    fields = {
        FLAWED_NAME_COL: f"FLAWED_{name}_GEM",
        FLAWLESS_NAME_COL: f"FLAWLESS_{name}_GEM",
    }
    fields.update(prices)
    return GristRecord(id=row_id, fields=fields)


class FakeGristClient:
    def __init__(self, records: list[GristRecord]):
        self._records = records
        self.calls: list[tuple] = []

    def list_records(self, doc_id, table_id):
        self.calls.append(("list_records", doc_id, table_id))
        return self._records

    def update_record_fields(self, doc_id, table_id, updates):
        self.calls.append(("update_record_fields", doc_id, table_id, updates))


class FakeBazaarClient:
    def __init__(self, products: dict[str, BazaarProduct]):
        self._products = products
        self.requested_ids: set[str] | None = None
        self.call_count = 0

    def fetch_products(self, product_ids=None):
        self.call_count += 1
        self.requested_ids = product_ids
        if product_ids is None:
            return self._products
        return {k: v for k, v in self._products.items() if k in product_ids}


def test_build_price_fields_returns_only_price_columns():
    from app.api.pricing import GemPrices

    fields = build_price_fields(
        GemPrices(
            buy_order=1.0, sell_order=2.0, insta_sell=3.0, avg_selling_per_minute=4.0
        )
    )

    assert set(fields) == PRICE_COLS


def test_updates_only_price_columns():
    client = FakeGristClient([_record(1, "JADE")])

    sync_gem_prices(client, FakeBazaarClient(_products("JADE")), DOC_ID, TABLE_ID)

    _, _, _, updates = client.calls[1]
    sent_fields = updates[0][1]

    assert set(sent_fields) == PRICE_COLS
    formula_cols = {c.col_id for c in GEM_TABLE_SCHEME if c.is_formula}
    assert formula_cols.isdisjoint(sent_fields)
    assert FLAWED_NAME_COL not in sent_fields
    assert FLAWLESS_NAME_COL not in sent_fields


def test_skips_gem_missing_from_bazaar():
    records = [_record(1, "RUBY"), _record(2, "JADE")]
    # Only JADE is tradable; RUBY is absent entirely.
    client = FakeGristClient(records)

    updates = sync_gem_prices(
        client, FakeBazaarClient(_products("JADE")), DOC_ID, TABLE_ID
    )

    assert [row_id for row_id, _ in updates] == [2]


def test_skips_row_when_only_flawless_is_missing():
    products = _products("JADE")
    del products["FLAWLESS_JADE_GEM"]
    client = FakeGristClient([_record(1, "JADE")])

    updates = sync_gem_prices(client, FakeBazaarClient(products), DOC_ID, TABLE_ID)

    assert updates == []
    assert [c[0] for c in client.calls] == ["list_records"]


def test_skips_row_with_blank_gem_name():
    client = FakeGristClient([GristRecord(id=1, fields={})])

    updates = sync_gem_prices(
        client, FakeBazaarClient(_products("JADE")), DOC_ID, TABLE_ID
    )

    assert updates == []


def test_no_write_when_all_prices_match():
    in_sync = _record(
        1,
        "JADE",
        **{
            BUY_ORDER_COL: 100.0,
            SELL_ORDER_COL: 950000.0,
            INSTA_SELL_COL: 900000.0,
            AVG_SELLING_PER_MINUTE_COL: 1.0,
        },
    )
    client = FakeGristClient([in_sync])

    updates = sync_gem_prices(
        client, FakeBazaarClient(_products("JADE")), DOC_ID, TABLE_ID
    )

    assert updates == []
    assert [c[0] for c in client.calls] == ["list_records"]


def test_updates_when_current_value_missing():
    partial = _record(1, "JADE", **{BUY_ORDER_COL: 100.0})
    client = FakeGristClient([partial])

    updates = sync_gem_prices(
        client, FakeBazaarClient(_products("JADE")), DOC_ID, TABLE_ID
    )

    assert [row_id for row_id, _ in updates] == [1]


def test_single_patch_for_multiple_rows():
    records = [_record(1, "JADE"), _record(2, "AMBER"), _record(3, "TOPAZ")]
    client = FakeGristClient(records)

    sync_gem_prices(
        client, FakeBazaarClient(_products("JADE", "AMBER", "TOPAZ")), DOC_ID, TABLE_ID
    )

    op_names = [c[0] for c in client.calls]
    assert op_names == ["list_records", "update_record_fields"]
    assert len(client.calls[1][3]) == 3


def test_compute_price_updates_is_pure():
    """No client needed — the diff logic must be callable without any I/O."""
    updates = compute_price_updates([_record(1, "JADE")], _products("JADE"))

    assert [row_id for row_id, _ in updates] == [1]


def test_collect_product_ids_from_rows():
    ids = collect_product_ids([_record(1, "JADE"), _record(2, "AMBER")])

    assert ids == {
        "FLAWED_JADE_GEM",
        "FLAWLESS_JADE_GEM",
        "FLAWED_AMBER_GEM",
        "FLAWLESS_AMBER_GEM",
    }


def test_collect_product_ids_ignores_blank_names():
    records = [GristRecord(id=1, fields={FLAWED_NAME_COL: "", FLAWLESS_NAME_COL: None})]

    assert collect_product_ids(records) == set()


def test_only_needed_products_are_fetched():
    """The full payload is ~2100 products; only the rows' gems get parsed."""
    bazaar = FakeBazaarClient(_products("JADE", "AMBER"))
    client = FakeGristClient([_record(1, "JADE")])

    sync_gem_prices(client, bazaar, DOC_ID, TABLE_ID)

    assert bazaar.requested_ids == {"FLAWED_JADE_GEM", "FLAWLESS_JADE_GEM"}


def test_empty_table_skips_bazaar_fetch():
    bazaar = FakeBazaarClient(_products("JADE"))
    client = FakeGristClient([])

    updates = sync_gem_prices(client, bazaar, DOC_ID, TABLE_ID)

    assert updates == []
    assert bazaar.call_count == 0
    assert [c[0] for c in client.calls] == ["list_records"]

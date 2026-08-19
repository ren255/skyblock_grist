import pytest
from pydantic import ValidationError

from app.grist.models import (
    FLAWED_NAME_COL,
    FLAWLESS_NAME_COL,
    GEM_TABLE_ROWS,
    GEM_TABLE_SCHEME,
    ColumnDef,
    GemRowDef,
)


def test_formula_column_requires_formula():
    with pytest.raises(ValidationError):
        ColumnDef(col_id="X", label="X", type="Numeric", is_formula=True, formula=None)


def test_non_formula_column_rejects_formula():
    with pytest.raises(ValidationError):
        ColumnDef(col_id="X", label="X", type="Numeric", is_formula=False, formula="$A")


def test_gem_table_scheme_matches_spec():
    expected = [
        ("FLAWED_GEM_NAME", "Text", False, None),
        ("FLAWLESS_GEM_NAME", "Text", False, None),
        ("BUY_ORDER", "Numeric", False, None),
        ("CRAFT_COST", "Numeric", True, "$BUY_ORDER * 80 * 80"),
        ("SELL_ORDER", "Numeric", False, None),
        ("ORDER_PROFIT", "Numeric", True, "$SELL_ORDER - $CRAFT_COST"),
        ("INSTA_SELL", "Numeric", False, None),
        ("INSTA_PROFIT", "Numeric", True, "$INSTA_SELL - $CRAFT_COST"),
        ("PLACEHOLDER", "Any", False, None),
        ("FULL_COST", "Numeric", True, "$BUY_ORDER * 71000"),
        ("TOTAL_PROFIT", "Numeric", True, "$ORDER_PROFIT * 71000 / 6400"),
        ("AVG_SELLING_PER_MINUTE", "Numeric", False, None),
        (
            "PROFIT_PER_HOUR",
            "Numeric",
            True,
            "$AVG_SELLING_PER_MINUTE * 60 * $ORDER_PROFIT",
        ),
    ]

    actual = [
        (c.col_id, c.type, c.is_formula, c.formula) for c in GEM_TABLE_SCHEME
    ]

    assert actual == expected


def test_full_cost_column_present_instead_of_71000_cost():
    col_ids = [c.col_id for c in GEM_TABLE_SCHEME]
    assert "FULL_COST" in col_ids
    assert "71000_COST" not in col_ids


def test_gem_table_rows_matches_spec():
    expected = [
        ("FLAWED_SAPPHIRE_GEM", "FLAWLESS_SAPPHIRE_GEM"),
        ("FLAWED_AMETHYST_GEM", "FLAWLESS_AMETHYST_GEM"),
        ("FLAWED_AMBER_GEM", "FLAWLESS_AMBER_GEM"),
        ("FLAWED_TOPAZ_GEM", "FLAWLESS_TOPAZ_GEM"),
        ("FLAWED_PERIDOT_GEM", "FLAWLESS_PERIDOT_GEM"),
        ("FLAWED_JADE_GEM", "FLAWLESS_JADE_GEM"),
    ]

    actual = [(r.flawed_gem_name, r.flawless_gem_name) for r in GEM_TABLE_ROWS]

    assert actual == expected


def test_gem_row_to_fields_contains_only_name_columns():
    fields = GemRowDef(
        flawed_gem_name="FLAWED_JADE_GEM", flawless_gem_name="FLAWLESS_JADE_GEM"
    ).to_fields()

    assert fields == {
        FLAWED_NAME_COL: "FLAWED_JADE_GEM",
        FLAWLESS_NAME_COL: "FLAWLESS_JADE_GEM",
    }

    formula_col_ids = {c.col_id for c in GEM_TABLE_SCHEME if c.is_formula}
    assert formula_col_ids.isdisjoint(fields)


def test_gem_row_fields_are_writable_columns_in_scheme():
    writable_col_ids = {c.col_id for c in GEM_TABLE_SCHEME if not c.is_formula}

    for row in GEM_TABLE_ROWS:
        assert set(row.to_fields()) <= writable_col_ids

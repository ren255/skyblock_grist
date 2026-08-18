import pytest
from pydantic import ValidationError

from app.grist.models import GEM_TABLE_SCHEME, ColumnDef


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

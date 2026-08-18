from app.grist.models import GEM_TABLE_SCHEME, ColumnDef, GristColumn, GristColumnFields
from app.grist.sync import compute_diff


def _as_current(columns: list[ColumnDef]) -> list[GristColumn]:
    return [
        GristColumn(
            id=c.col_id,
            fields=GristColumnFields(
                label=c.label, type=c.type, isFormula=c.is_formula, formula=c.formula
            ),
        )
        for c in columns
    ]


def test_missing_columns_marked_for_add():
    diff = compute_diff(GEM_TABLE_SCHEME, current=[])

    assert {c.col_id for c in diff.to_add} == {c.col_id for c in GEM_TABLE_SCHEME}
    assert diff.to_update == []
    assert diff.to_delete == []


def test_extra_column_marked_for_delete():
    current = _as_current(GEM_TABLE_SCHEME) + [
        GristColumn(
            id="LEGACY_COLUMN",
            fields=GristColumnFields(label="LEGACY_COLUMN", type="Text", isFormula=False),
        )
    ]

    diff = compute_diff(GEM_TABLE_SCHEME, current)

    assert diff.to_delete == ["LEGACY_COLUMN"]
    assert diff.to_add == []
    assert diff.to_update == []


def test_mismatched_column_marked_for_update():
    current = _as_current(GEM_TABLE_SCHEME)
    for column in current:
        if column.id == "BUY_ORDER":
            column.fields.type = "Text"

    diff = compute_diff(GEM_TABLE_SCHEME, current)

    assert [c.col_id for c in diff.to_update] == ["BUY_ORDER"]
    assert diff.to_add == []
    assert diff.to_delete == []


def test_mismatched_formula_marked_for_update():
    current = _as_current(GEM_TABLE_SCHEME)
    for column in current:
        if column.id == "CRAFT_COST":
            column.fields.formula = "$BUY_ORDER * 2"

    diff = compute_diff(GEM_TABLE_SCHEME, current)

    assert [c.col_id for c in diff.to_update] == ["CRAFT_COST"]


def test_matching_schema_produces_empty_diff():
    current = _as_current(GEM_TABLE_SCHEME)

    diff = compute_diff(GEM_TABLE_SCHEME, current)

    assert diff.is_empty()

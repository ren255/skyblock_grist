from app.grist.models import (
    FLAWED_NAME_COL,
    FLAWLESS_NAME_COL,
    GEM_TABLE_ROWS,
    GEM_TABLE_SCHEME,
    ColumnDef,
    GristColumn,
    GristColumnFields,
    GristRecord,
)
from app.grist.sync import compute_diff, compute_record_diff


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


def _as_records(rows: list[tuple[int, str, str]]) -> list[GristRecord]:
    return [
        GristRecord(
            id=row_id,
            fields={FLAWED_NAME_COL: flawed, FLAWLESS_NAME_COL: flawless},
        )
        for row_id, flawed, flawless in rows
    ]


def _in_sync_records() -> list[GristRecord]:
    return _as_records(
        [
            (index, row.flawed_gem_name, row.flawless_gem_name)
            for index, row in enumerate(GEM_TABLE_ROWS, start=1)
        ]
    )


def test_empty_table_marks_all_rows_for_add():
    diff = compute_record_diff(GEM_TABLE_ROWS, current=[])

    assert diff.to_add == GEM_TABLE_ROWS
    assert diff.to_update == []
    assert diff.to_delete == []


def test_matching_rows_produce_empty_diff():
    diff = compute_record_diff(GEM_TABLE_ROWS, _in_sync_records())

    assert diff.is_empty()


def test_unknown_row_marked_for_delete():
    current = _in_sync_records() + _as_records(
        [(99, "FLAWED_RUBY_GEM", "FLAWLESS_RUBY_GEM")]
    )

    diff = compute_record_diff(GEM_TABLE_ROWS, current)

    assert diff.to_delete == [99]
    assert diff.to_add == []
    assert diff.to_update == []


def test_mismatched_flawless_name_marked_for_update():
    current = _in_sync_records()
    current[2].fields[FLAWLESS_NAME_COL] = "WRONG_NAME"
    expected_row = GEM_TABLE_ROWS[2]

    diff = compute_record_diff(GEM_TABLE_ROWS, current)

    assert diff.to_update == [(current[2].id, expected_row)]
    assert diff.to_add == []
    assert diff.to_delete == []


def test_duplicate_flawed_name_keeps_first_deletes_rest():
    first = GEM_TABLE_ROWS[0]
    current = _in_sync_records() + _as_records(
        [
            (101, first.flawed_gem_name, first.flawless_gem_name),
            (102, first.flawed_gem_name, first.flawless_gem_name),
        ]
    )

    diff = compute_record_diff(GEM_TABLE_ROWS, current)

    assert diff.to_delete == [101, 102]
    assert diff.to_add == []
    assert diff.to_update == []


def test_blank_flawed_name_marked_for_delete():
    current = _in_sync_records() + [
        GristRecord(id=201, fields={FLAWED_NAME_COL: "", FLAWLESS_NAME_COL: ""}),
        GristRecord(id=202, fields={}),
    ]

    diff = compute_record_diff(GEM_TABLE_ROWS, current)

    assert diff.to_delete == [201, 202]
    assert diff.to_add == []
    assert diff.to_update == []

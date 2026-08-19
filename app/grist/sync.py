import logging

from pydantic import BaseModel

from app.grist.client import GristClient
from app.grist.models import (
    FLAWED_NAME_COL,
    FLAWLESS_NAME_COL,
    GEM_TABLE_ROWS,
    GEM_TABLE_SCHEME,
    ColumnDef,
    GemRowDef,
    GristColumn,
    GristRecord,
)

logger = logging.getLogger(__name__)


class SchemaDiff(BaseModel):
    to_add: list[ColumnDef] = []
    to_update: list[ColumnDef] = []
    to_delete: list[str] = []

    def is_empty(self) -> bool:
        return not (self.to_add or self.to_update or self.to_delete)


def _matches(desired: ColumnDef, current: GristColumn) -> bool:
    fields = current.fields
    return (
        fields.label == desired.label
        and fields.type == desired.type
        and bool(fields.isFormula) == desired.is_formula
        and fields.formula == desired.formula
    )


def compute_diff(desired: list[ColumnDef], current: list[GristColumn]) -> SchemaDiff:
    current_by_id = {column.id: column for column in current}
    desired_by_id = {column.col_id: column for column in desired}

    to_add = [column for column in desired if column.col_id not in current_by_id]
    to_delete = [col_id for col_id in current_by_id if col_id not in desired_by_id]
    to_update = [
        column
        for column in desired
        if column.col_id in current_by_id
        and not _matches(column, current_by_id[column.col_id])
    ]

    return SchemaDiff(to_add=to_add, to_update=to_update, to_delete=to_delete)


def apply_diff(client: GristClient, doc_id: str, table_id: str, diff: SchemaDiff) -> None:
    for col_id in diff.to_delete:
        logger.info("Deleting column %s.%s", table_id, col_id)
        client.delete_column(doc_id, table_id, col_id)

    if diff.to_add:
        logger.info(
            "Adding columns to %s: %s", table_id, [c.col_id for c in diff.to_add]
        )
        client.create_columns(doc_id, table_id, diff.to_add)

    if diff.to_update:
        logger.info(
            "Updating columns on %s: %s", table_id, [c.col_id for c in diff.to_update]
        )
        client.update_columns(doc_id, table_id, diff.to_update)


def sync_gem_table_schema(
    client: GristClient,
    doc_id: str,
    table_id: str,
    scheme: list[ColumnDef] | None = None,
) -> SchemaDiff:
    scheme = scheme if scheme is not None else GEM_TABLE_SCHEME

    if not client.table_exists(doc_id, table_id):
        logger.info("Table %s does not exist, creating with full scheme", table_id)
        client.create_table(doc_id, table_id, scheme)
        return SchemaDiff(to_add=scheme)

    current = client.list_columns(doc_id, table_id)
    diff = compute_diff(scheme, current)
    if diff.is_empty():
        logger.info("Table %s schema already in sync, no changes needed", table_id)
    apply_diff(client, doc_id, table_id, diff)
    return diff


class RecordDiff(BaseModel):
    to_add: list[GemRowDef] = []
    to_update: list[tuple[int, GemRowDef]] = []
    to_delete: list[int] = []

    def is_empty(self) -> bool:
        return not (self.to_add or self.to_update or self.to_delete)


def compute_record_diff(
    desired: list[GemRowDef], current: list[GristRecord]
) -> RecordDiff:
    """Reconcile gem rows against `desired`, keyed on the flawed gem name.

    Rows whose flawed name is absent from `desired` are marked for deletion, so
    the table ends up matching the definition exactly. Rows with a blank or
    non-string key can never match and are deleted too. When the same key
    appears more than once, the first occurrence wins and the rest are deleted.
    """
    desired_by_name = {row.flawed_gem_name: row for row in desired}

    current_by_name: dict[str, GristRecord] = {}
    to_delete: list[int] = []
    for record in current:
        name = record.fields.get(FLAWED_NAME_COL)
        if not isinstance(name, str) or name not in desired_by_name:
            to_delete.append(record.id)
        elif name in current_by_name:
            to_delete.append(record.id)
        else:
            current_by_name[name] = record

    to_add: list[GemRowDef] = []
    to_update: list[tuple[int, GemRowDef]] = []
    for row in desired:
        record = current_by_name.get(row.flawed_gem_name)
        if record is None:
            to_add.append(row)
        elif record.fields.get(FLAWLESS_NAME_COL) != row.flawless_gem_name:
            to_update.append((record.id, row))

    return RecordDiff(to_add=to_add, to_update=to_update, to_delete=to_delete)


def apply_record_diff(
    client: GristClient, doc_id: str, table_id: str, diff: RecordDiff
) -> None:
    if diff.to_delete:
        logger.info("Deleting rows from %s: %s", table_id, diff.to_delete)
        client.delete_records(doc_id, table_id, diff.to_delete)

    if diff.to_add:
        logger.info(
            "Adding rows to %s: %s", table_id, [r.flawed_gem_name for r in diff.to_add]
        )
        client.create_records(doc_id, table_id, diff.to_add)

    if diff.to_update:
        logger.info(
            "Updating rows on %s: %s",
            table_id,
            [r.flawed_gem_name for _, r in diff.to_update],
        )
        client.update_records(doc_id, table_id, diff.to_update)


def sync_gem_table_records(
    client: GristClient,
    doc_id: str,
    table_id: str,
    rows: list[GemRowDef] | None = None,
) -> RecordDiff:
    """Make the rows of `table_id` match the gem definition exactly.

    Assumes the table exists and already has the name columns — run
    `sync_gem_table_schema` first.
    """
    rows = rows if rows is not None else GEM_TABLE_ROWS

    current = client.list_records(doc_id, table_id)
    diff = compute_record_diff(rows, current)
    if diff.is_empty():
        logger.info("Table %s rows already in sync, no changes needed", table_id)
    apply_record_diff(client, doc_id, table_id, diff)
    return diff

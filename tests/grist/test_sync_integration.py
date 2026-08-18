from app.grist.models import GEM_TABLE_SCHEME, ColumnDef, GristColumn, GristColumnFields
from app.grist.sync import sync_gem_table_schema

DOC_ID = "docABC"
TABLE_ID = "gem"


class FakeGristClient:
    def __init__(self, table_exists: bool, columns: list[GristColumn]):
        self._table_exists = table_exists
        self._columns = columns
        self.calls: list[tuple] = []

    def table_exists(self, doc_id, table_id):
        self.calls.append(("table_exists", doc_id, table_id))
        return self._table_exists

    def create_table(self, doc_id, table_id, columns):
        self.calls.append(("create_table", doc_id, table_id, columns))

    def list_columns(self, doc_id, table_id):
        self.calls.append(("list_columns", doc_id, table_id))
        return self._columns

    def create_columns(self, doc_id, table_id, columns):
        self.calls.append(("create_columns", doc_id, table_id, columns))

    def update_columns(self, doc_id, table_id, columns):
        self.calls.append(("update_columns", doc_id, table_id, columns))

    def delete_column(self, doc_id, table_id, col_id):
        self.calls.append(("delete_column", doc_id, table_id, col_id))


def test_creates_table_when_missing():
    client = FakeGristClient(table_exists=False, columns=[])

    diff = sync_gem_table_schema(client, DOC_ID, TABLE_ID)

    op_names = [c[0] for c in client.calls]
    assert op_names == ["table_exists", "create_table"]
    assert client.calls[1][3] == GEM_TABLE_SCHEME
    assert diff.to_add == GEM_TABLE_SCHEME


def test_reconciles_existing_table_with_add_update_delete():
    current = [
        GristColumn(
            id="BUY_ORDER",
            fields=GristColumnFields(label="BUY_ORDER", type="Text", isFormula=False),
        ),
        GristColumn(
            id="LEGACY",
            fields=GristColumnFields(label="LEGACY", type="Text", isFormula=False),
        ),
    ]
    client = FakeGristClient(table_exists=True, columns=current)

    diff = sync_gem_table_schema(client, DOC_ID, TABLE_ID)

    op_names = [c[0] for c in client.calls]
    assert op_names == [
        "table_exists",
        "list_columns",
        "delete_column",
        "create_columns",
        "update_columns",
    ]
    assert diff.to_delete == ["LEGACY"]
    assert [c.col_id for c in diff.to_update] == ["BUY_ORDER"]
    assert len(diff.to_add) == len(GEM_TABLE_SCHEME) - 1


def test_no_op_when_already_in_sync():
    current = [
        GristColumn(
            id=c.col_id,
            fields=GristColumnFields(
                label=c.label, type=c.type, isFormula=c.is_formula, formula=c.formula
            ),
        )
        for c in GEM_TABLE_SCHEME
    ]
    client = FakeGristClient(table_exists=True, columns=current)

    diff = sync_gem_table_schema(client, DOC_ID, TABLE_ID)

    op_names = [c[0] for c in client.calls]
    assert op_names == ["table_exists", "list_columns"]
    assert diff.is_empty()

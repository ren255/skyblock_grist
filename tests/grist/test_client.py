import json

import httpx
import pytest

from app.grist.client import GristClient
from app.grist.models import ColumnDef, GemRowDef

DOC_ID = "docABC"
TABLE_ID = "gem"


def _client(handler) -> GristClient:
    http_client = httpx.Client(
        base_url="https://grist.example.com/api",
        headers={"Authorization": "Bearer key"},
        transport=httpx.MockTransport(handler),
    )
    return GristClient(base_url="https://grist.example.com", api_key="key", http_client=http_client)


def test_default_construction_sets_base_url_and_auth_header():
    client = GristClient(base_url="https://grist.example.com", api_key="secret-key")

    assert str(client._client.base_url) == "https://grist.example.com/api/"
    assert client._client.headers["authorization"] == "Bearer secret-key"

    client.close()


def test_context_manager_closes_underlying_client():
    client = GristClient(base_url="https://grist.example.com", api_key="secret-key")

    with client:
        assert not client._client.is_closed

    assert client._client.is_closed


def test_list_columns_parses_response():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert request.url.path == f"/api/docs/{DOC_ID}/tables/{TABLE_ID}/columns"
        assert request.headers["authorization"] == "Bearer key"
        return httpx.Response(
            200,
            json={
                "columns": [
                    {"id": "BUY_ORDER", "fields": {"label": "BUY_ORDER", "type": "Numeric", "isFormula": False}}
                ]
            },
        )

    client = _client(handler)
    columns = client.list_columns(DOC_ID, TABLE_ID)

    assert len(columns) == 1
    assert columns[0].id == "BUY_ORDER"
    assert columns[0].fields.type == "Numeric"


def test_create_columns_sends_correct_body():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["method"] = request.method
        captured["path"] = request.url.path
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json={"columns": []})

    client = _client(handler)
    client.create_columns(
        DOC_ID,
        TABLE_ID,
        [ColumnDef(col_id="BUY_ORDER", label="BUY_ORDER", type="Numeric")],
    )

    assert captured["method"] == "POST"
    assert captured["path"] == f"/api/docs/{DOC_ID}/tables/{TABLE_ID}/columns"
    assert captured["body"] == {
        "columns": [
            {"id": "BUY_ORDER", "fields": {"label": "BUY_ORDER", "type": "Numeric", "isFormula": False}}
        ]
    }


def test_update_columns_sends_correct_body():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["method"] = request.method
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json={})

    client = _client(handler)
    client.update_columns(
        DOC_ID,
        TABLE_ID,
        [
            ColumnDef(
                col_id="CRAFT_COST",
                label="CRAFT_COST",
                type="Numeric",
                is_formula=True,
                formula="$BUY_ORDER * 80 * 80",
            )
        ],
    )

    assert captured["method"] == "PATCH"
    assert captured["body"] == {
        "columns": [
            {
                "id": "CRAFT_COST",
                "fields": {
                    "label": "CRAFT_COST",
                    "type": "Numeric",
                    "isFormula": True,
                    "formula": "$BUY_ORDER * 80 * 80",
                },
            }
        ]
    }


def test_delete_column_calls_correct_url():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["method"] = request.method
        captured["path"] = request.url.path
        return httpx.Response(200, json={})

    client = _client(handler)
    client.delete_column(DOC_ID, TABLE_ID, "OLD_COLUMN")

    assert captured["method"] == "DELETE"
    assert captured["path"] == f"/api/docs/{DOC_ID}/tables/{TABLE_ID}/columns/OLD_COLUMN"


def test_create_table_sends_columns():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["method"] = request.method
        captured["path"] = request.url.path
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json={})

    client = _client(handler)
    client.create_table(
        DOC_ID,
        TABLE_ID,
        [ColumnDef(col_id="BUY_ORDER", label="BUY_ORDER", type="Numeric")],
    )

    assert captured["method"] == "POST"
    assert captured["path"] == f"/api/docs/{DOC_ID}/tables"
    assert captured["body"] == {
        "tables": [
            {
                "id": TABLE_ID,
                "columns": [
                    {
                        "id": "BUY_ORDER",
                        "fields": {"label": "BUY_ORDER", "type": "Numeric", "isFormula": False},
                    }
                ],
            }
        ]
    }


def test_list_table_ids_returns_ids():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"tables": [{"id": "gem"}, {"id": "bazaar"}]})

    client = _client(handler)
    assert client.list_table_ids(DOC_ID) == ["gem", "bazaar"]


def test_table_exists_true_and_false():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"tables": [{"id": "gem"}]})

    client = _client(handler)
    assert client.table_exists(DOC_ID, "gem") is True
    assert client.table_exists(DOC_ID, "missing") is False


def test_list_records_parses_response():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert request.url.path == f"/api/docs/{DOC_ID}/tables/{TABLE_ID}/records"
        return httpx.Response(
            200,
            json={
                "records": [
                    {
                        "id": 3,
                        "fields": {
                            "FLAWED_GEM_NAME": "FLAWED_JADE_GEM",
                            "FLAWLESS_GEM_NAME": "FLAWLESS_JADE_GEM",
                            "BUY_ORDER": 12.5,
                        },
                        "manualSort": 1,
                    }
                ]
            },
        )

    client = _client(handler)
    records = client.list_records(DOC_ID, TABLE_ID)

    assert len(records) == 1
    assert records[0].id == 3
    assert records[0].fields["FLAWED_GEM_NAME"] == "FLAWED_JADE_GEM"
    assert records[0].fields["BUY_ORDER"] == 12.5


def test_create_records_sends_correct_body():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["method"] = request.method
        captured["path"] = request.url.path
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json={"records": [{"id": 1}]})

    client = _client(handler)
    client.create_records(
        DOC_ID,
        TABLE_ID,
        [
            GemRowDef(
                flawed_gem_name="FLAWED_JADE_GEM",
                flawless_gem_name="FLAWLESS_JADE_GEM",
            )
        ],
    )

    assert captured["method"] == "POST"
    assert captured["path"] == f"/api/docs/{DOC_ID}/tables/{TABLE_ID}/records"
    assert captured["body"] == {
        "records": [
            {
                "fields": {
                    "FLAWED_GEM_NAME": "FLAWED_JADE_GEM",
                    "FLAWLESS_GEM_NAME": "FLAWLESS_JADE_GEM",
                }
            }
        ]
    }


def test_update_records_sends_correct_body():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["method"] = request.method
        captured["path"] = request.url.path
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json={})

    client = _client(handler)
    client.update_records(
        DOC_ID,
        TABLE_ID,
        [
            (
                7,
                GemRowDef(
                    flawed_gem_name="FLAWED_AMBER_GEM",
                    flawless_gem_name="FLAWLESS_AMBER_GEM",
                ),
            )
        ],
    )

    assert captured["method"] == "PATCH"
    assert captured["path"] == f"/api/docs/{DOC_ID}/tables/{TABLE_ID}/records"
    assert captured["body"] == {
        "records": [
            {
                "id": 7,
                "fields": {
                    "FLAWED_GEM_NAME": "FLAWED_AMBER_GEM",
                    "FLAWLESS_GEM_NAME": "FLAWLESS_AMBER_GEM",
                },
            }
        ]
    }


def test_update_record_fields_sends_correct_body():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["method"] = request.method
        captured["path"] = request.url.path
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json={})

    client = _client(handler)
    client.update_record_fields(
        DOC_ID, TABLE_ID, [(4, {"BUY_ORDER": 376.6, "INSTA_SELL": 2513194.6})]
    )

    assert captured["method"] == "PATCH"
    assert captured["path"] == f"/api/docs/{DOC_ID}/tables/{TABLE_ID}/records"
    assert captured["body"] == {
        "records": [{"id": 4, "fields": {"BUY_ORDER": 376.6, "INSTA_SELL": 2513194.6}}]
    }


def test_delete_records_sends_row_id_array():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["method"] = request.method
        captured["path"] = request.url.path
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json={})

    client = _client(handler)
    client.delete_records(DOC_ID, TABLE_ID, [3, 5])

    assert captured["method"] == "POST"
    assert captured["path"] == f"/api/docs/{DOC_ID}/tables/{TABLE_ID}/records/delete"
    assert captured["body"] == [3, 5]


def test_request_error_raises_runtime_error():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("boom")

    client = _client(handler)
    with pytest.raises(RuntimeError):
        client.list_table_ids(DOC_ID)


def test_http_status_error_raises_runtime_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"error": "not found"})

    client = _client(handler)
    with pytest.raises(RuntimeError):
        client.list_table_ids(DOC_ID)

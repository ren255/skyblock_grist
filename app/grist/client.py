from urllib.parse import quote

import httpx

from app.grist.models import (
    ColumnDef,
    GemRowDef,
    GristColumn,
    GristColumnsResponse,
    GristRecord,
    GristRecordsResponse,
    GristTablesResponse,
)


class GristClient:
    """Thin wrapper around the Grist REST API used for table/column schema management."""

    def __init__(self, base_url: str, api_key: str, http_client: httpx.Client | None = None):
        """If `http_client` is given, it is used as-is and `base_url`/`api_key` are ignored
        (the caller is responsible for configuring its base_url and auth headers)."""
        self._client = http_client or httpx.Client(
            base_url=f"{base_url}/api",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=10.0,
        )

    def __enter__(self) -> "GristClient":
        return self

    def __exit__(self, *exc_info) -> None:
        self.close()

    def close(self) -> None:
        self._client.close()

    def _request(self, method: str, path: str, **kwargs) -> httpx.Response:
        try:
            response = self._client.request(method, path, **kwargs)
            response.raise_for_status()
        except httpx.RequestError as e:
            raise RuntimeError(f"Failed to connect to Grist: {path}") from e
        except httpx.HTTPStatusError as e:
            raise RuntimeError(
                f"Grist returned HTTP {e.response.status_code}: {path}"
            ) from e
        return response

    def list_table_ids(self, doc_id: str) -> list[str]:
        response = self._request("GET", f"/docs/{quote(doc_id)}/tables")
        parsed = GristTablesResponse.model_validate(response.json())
        return [table.id for table in parsed.tables]

    def table_exists(self, doc_id: str, table_id: str) -> bool:
        return table_id in self.list_table_ids(doc_id)

    def create_table(self, doc_id: str, table_id: str, columns: list[ColumnDef]) -> None:
        body = {
            "tables": [
                {
                    "id": table_id,
                    "columns": [
                        {"id": column.col_id, "fields": column.to_fields()}
                        for column in columns
                    ],
                }
            ]
        }
        self._request("POST", f"/docs/{quote(doc_id)}/tables", json=body)

    def list_columns(self, doc_id: str, table_id: str) -> list[GristColumn]:
        response = self._request(
            "GET", f"/docs/{quote(doc_id)}/tables/{quote(table_id)}/columns"
        )
        parsed = GristColumnsResponse.model_validate(response.json())
        return parsed.columns

    def create_columns(self, doc_id: str, table_id: str, columns: list[ColumnDef]) -> None:
        body = {
            "columns": [
                {"id": column.col_id, "fields": column.to_fields()} for column in columns
            ]
        }
        self._request(
            "POST", f"/docs/{quote(doc_id)}/tables/{quote(table_id)}/columns", json=body
        )

    def update_columns(self, doc_id: str, table_id: str, columns: list[ColumnDef]) -> None:
        body = {
            "columns": [
                {"id": column.col_id, "fields": column.to_fields()} for column in columns
            ]
        }
        self._request(
            "PATCH", f"/docs/{quote(doc_id)}/tables/{quote(table_id)}/columns", json=body
        )

    def delete_column(self, doc_id: str, table_id: str, col_id: str) -> None:
        self._request(
            "DELETE",
            f"/docs/{quote(doc_id)}/tables/{quote(table_id)}/columns/{quote(col_id)}",
        )

    def list_records(self, doc_id: str, table_id: str) -> list[GristRecord]:
        response = self._request(
            "GET", f"/docs/{quote(doc_id)}/tables/{quote(table_id)}/records"
        )
        parsed = GristRecordsResponse.model_validate(response.json())
        return parsed.records

    def create_records(self, doc_id: str, table_id: str, rows: list[GemRowDef]) -> None:
        body = {"records": [{"fields": row.to_fields()} for row in rows]}
        self._request(
            "POST", f"/docs/{quote(doc_id)}/tables/{quote(table_id)}/records", json=body
        )

    def update_records(
        self, doc_id: str, table_id: str, rows: list[tuple[int, GemRowDef]]
    ) -> None:
        """Overwrite the managed fields of existing rows, identified by row id."""
        body = {
            "records": [
                {"id": row_id, "fields": row.to_fields()} for row_id, row in rows
            ]
        }
        self._request(
            "PATCH", f"/docs/{quote(doc_id)}/tables/{quote(table_id)}/records", json=body
        )

    def update_record_fields(
        self, doc_id: str, table_id: str, updates: list[tuple[int, dict]]
    ) -> None:
        """Patch arbitrary fields on existing rows, identified by row id.

        The caller owns the contents of each `fields` dict and must not include
        formula columns — Grist computes those, and writing them would clobber
        the formula.
        """
        body = {
            "records": [{"id": row_id, "fields": fields} for row_id, fields in updates]
        }
        self._request(
            "PATCH", f"/docs/{quote(doc_id)}/tables/{quote(table_id)}/records", json=body
        )

    def delete_records(self, doc_id: str, table_id: str, row_ids: list[int]) -> None:
        """Delete rows by id. The Grist API expects a bare array of row ids."""
        self._request(
            "POST",
            f"/docs/{quote(doc_id)}/tables/{quote(table_id)}/records/delete",
            json=row_ids,
        )

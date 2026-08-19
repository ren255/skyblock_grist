## Implementation Complete

### Files Created
- `app/grist/models.py` — `ColumnDef`, `GEM_TABLE_SCHEME`（13列定義）, Grist APIレスポンス用モデル
- `app/grist/client.py` — `GristClient`（テーブル一覧/作成、カラム一覧/作成/更新/削除）
- `app/grist/sync.py` — `SchemaDiff`, `compute_diff`, `apply_diff`, `sync_gem_table_schema`
- `tests/grist/__init__.py`
- `tests/grist/test_models.py`
- `tests/grist/test_sync.py`
- `tests/grist/test_client.py`
- `tests/grist/test_sync_integration.py`

### Files Modified
- `app/config.py` — `grist_gem_table_name: str = "gem"` を追加
- `app/main.py` — `main()` 内で `GristClient` を構築し `sync_gem_table_schema` を呼び出すよう追加
- `pyproject.toml` — `pydantic` を明示的依存に追加、`pytest` を dev 依存として追加（フラグ済み）
- `uv.lock` — `uv sync` により更新（未使用だったfastapi等がvenvから除去され、pytest等が追加）

### Acceptance Criteria
- [x] AC-01: Passed — `test_client.py#test_create_table_sends_columns`, `test_sync_integration.py#test_creates_table_when_missing`
- [x] AC-02: Passed — `test_sync.py#test_extra_column_marked_for_delete`, `test_client.py#test_delete_column_calls_correct_url`
- [x] AC-03: Passed — `test_sync.py#test_missing_columns_marked_for_add`, `test_client.py#test_create_columns_sends_correct_body`
- [x] AC-04: Passed — `test_sync.py#test_mismatched_column_marked_for_update`, `#test_mismatched_formula_marked_for_update`, `test_client.py#test_update_columns_sends_correct_body`
- [x] AC-05: Passed — `test_sync.py#test_matching_schema_produces_empty_diff`
- [x] AC-06: Passed — `test_models.py#test_gem_table_scheme_matches_spec`
- [x] AC-07: Passed — `test_client.py#test_request_error_raises_runtime_error`, `#test_http_status_error_raises_runtime_error`
- [x] AC-08: Passed — `test_models.py#test_full_cost_column_present_instead_of_71000_cost`

全21テスト成功（`uv run pytest`）。

### Notes
- `GristClient.__init__` に `http_client: httpx.Client | None` を追加（plan.mdには明記なし）。テストで `httpx.MockTransport` を注入するための実装詳細で、plan.mdの意図（Step 6でMockTransport使用）を実現するために必要だった。
- `pydantic` はplan.md通り明示依存化。`pytest` は新規dev依存として追加（docs/project.mdのApproved Dependenciesにテストフレームワークの記載が無かったため、ここでユーザーに報告）。
- Bazaar API連携によるレコード値の同期（BUY_ORDER等の実データ更新）はfeature.mdでOut of Scopeと確定した通り未実装。

## Implementation Complete

### Files Created
- `tests/conftest.py` — `.env` 非依存で `app.main` をインポートできるよう必須環境変数のダミー値を設定
- `tests/grist/test_main.py` — カラム同期→行同期の実行順序を検証

### Files Modified
- `app/grist/models.py` — `FLAWED_NAME_COL` / `FLAWLESS_NAME_COL` 定数、`GemRowDef`、`GEM_TABLE_ROWS`（6件）、`GristRecord` / `GristRecordsResponse` を追加
- `app/grist/client.py` — `list_records` / `create_records` / `update_records` / `delete_records` を追加
- `app/grist/sync.py` — `RecordDiff` / `compute_record_diff` / `apply_record_diff` / `sync_gem_table_records` を追加
- `app/main.py` — カラム同期の後に行同期を実行、`logging.basicConfig(level=INFO)` を追加
- `tests/grist/test_models.py` — 行定義・`to_fields()` の検証3ケースを追加
- `tests/grist/test_client.py` — Records API 4メソッドのリクエスト形状検証を追加
- `tests/grist/test_sync.py` — `compute_record_diff` の単体テスト6ケースを追加
- `tests/grist/test_sync_integration.py` — `FakeGristClient` に records 対応を後方互換で追加、行同期3ケースを追加

### Acceptance Criteria
- [x] AC-01: Passed — `test_models.py::test_gem_table_rows_matches_spec`
- [x] AC-02: Passed — `test_sync.py::test_empty_table_marks_all_rows_for_add`, `test_sync_integration.py::test_records_sync_adds_all_when_empty`
- [x] AC-03: Passed — `test_sync.py::test_matching_rows_produce_empty_diff`, `test_sync_integration.py::test_records_sync_is_noop_when_in_sync`
- [x] AC-04: Passed — `test_sync.py::test_unknown_row_marked_for_delete`
- [x] AC-05: Passed — `test_sync.py::test_mismatched_flawless_name_marked_for_update`
- [x] AC-06: Passed — `test_sync.py::test_duplicate_flawed_name_keeps_first_deletes_rest`
- [x] AC-07: Passed — `test_sync.py::test_blank_flawed_name_marked_for_delete`
- [x] AC-08: Passed — `test_client.py::test_list_records_parses_response`（未知キー `manualSort` を含むレスポンスで検証）
- [x] AC-09: Passed — `test_client.py::test_create_records_sends_correct_body`, `test_update_records_sends_correct_body`, `test_delete_records_sends_row_id_array`, `test_list_records_parses_response`
- [x] AC-10: Passed — `test_models.py::test_gem_row_to_fields_contains_only_name_columns`
- [x] AC-11: Passed — `test_main.py::test_schema_sync_runs_before_record_sync`
- [x] AC-12: Passed — 既存23ケースが全て継続パス（全40 passed）

### Notes
- Grist Records APIのエンドポイント・ボディ形状は公式OpenAPI定義（`gristlabs/grist-help` の `api/grist.yml`）で実装前に検証済み。削除は `POST /records/delete` に**裸のrow id配列**を送る仕様のため、他メソッドと異なりラッパーオブジェクトを使っていない。
- `GEM_TABLE_SCHEME` の先頭2列を新設の `FLAWED_NAME_COL` / `FLAWLESS_NAME_COL` 定数参照に置き換えた（plan Step 1-1どおり）。列IDリテラルが `models.py` / `sync.py` に散らばるのを防ぐため。既存テストは列ID文字列を直接比較しており、変更後もパスしている。
- `tests/conftest.py` が実際に必要であることを、`.env` を含まない複製環境で確認済み（conftestを外すと `ValidationError` で収集失敗、戻すと40件パス）。
- 新規依存の追加なし（`pyproject.toml` / `uv.lock` 無変更、NFR-01充足）。
- plan からの逸脱なし。

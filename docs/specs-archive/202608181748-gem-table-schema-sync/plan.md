# Implementation Plan: Gemテーブル カラムスキーマ自動同期

## Overview
`app/grist/` 配下に、Grist REST APIクライアント（`client.py`）、期待スキーマ定義とレスポンス用のpydanticモデル（`models.py`）、差分検出・反映ロジック（`sync.py`）を新設する。`app/main.py` から一連の同期処理を呼び出す。Grist REST APIの実仕様（`gristlabs/grist-help` の OpenAPI 定義 `api/grist.yml` を参照して確認済み）に基づき、以下のエンドポイントを使用する。

- `GET  {GRIST_URL}/api/docs/{docId}/tables` — テーブル一覧（存在確認用）
- `POST {GRIST_URL}/api/docs/{docId}/tables` — テーブル新規作成（`columns` を同時指定可能）
- `GET  {GRIST_URL}/api/docs/{docId}/tables/{tableId}/columns` — カラム一覧取得
- `POST {GRIST_URL}/api/docs/{docId}/tables/{tableId}/columns` — カラム追加
- `PATCH {GRIST_URL}/api/docs/{docId}/tables/{tableId}/columns` — カラム更新（body内 `id` で対象を指定、`fields` に変更内容）
- `DELETE {GRIST_URL}/api/docs/{docId}/tables/{tableId}/columns/{colId}` — カラム削除
- 認証: `Authorization: Bearer {GRIST_API_KEY}`

Grist列の `fields` は `type`（`Text`/`Numeric`/`Any` など）, `label`, `isFormula`, `formula` を持つ。これらをpydanticモデルの列定義（`ColumnDef`）とGristレスポンスモデル（`GristColumn`）の両方で表現し、差分比較を行う。

## Architecture Decisions
- **pydanticを採用（pandasではなく）**: 対象は13件程度の固定列スキーマの構造比較であり、表形式のデータ処理ではないため、型安全な構造比較にはpydanticモデル＋通常の集合/辞書比較が適している。`docs/project.md` の「同等に実現可能な場合はpandasを優先」という方針に対し、本用途は表データではなくスキーマ定義の一致比較のため、pydanticが適切と判断する。
- **既存の `app/grist/`, `app/config.py` 構成に従う**: 新規モジュールはすべて `app/grist/` 配下に置き、`app/config.py` の `Settings` パターン（環境変数→pydantic-settings）を拡張する。
- **層分割**: `models.py`（スキーマ定義・データ型）/ `client.py`（Grist REST API呼び出しのみ、ロジックを持たない）/ `sync.py`（差分検出・反映のロジック）に分離し、`sync.py` は `client.py` に依存するが、`client.py` は `sync.py` を知らない一方向依存とする。これにより差分ロジックのユニットテストがHTTP通信なしで書ける。
- **エラーハンドリングは既存の `check_grist()`（`app/main.py`）の方針を踏襲**: `httpx.RequestError` / `httpx.HTTPStatusError` を捕捉し `RuntimeError` に変換して再raiseする。

## Implementation Steps

### Step 1: 設定の追加
- [x] `app/config.py` の `Settings` に `grist_gem_table_name: str = "gem"` を追加する（既存の `grist_bz_table_name` / `grist_ah_table_name` と同じパターン）
- Files: `app/config.py`

### Step 2: ドメインモデル（column scheme定義 & Gristレスポンスモデル）
- [x] `GristColumnType`: `Literal["Text", "Numeric", "Any"]`（本機能で使う型のみ。将来Ref等が必要になれば拡張）
- [x] `ColumnDef(BaseModel)`: `col_id: str`, `label: str`, `type: GristColumnType`, `is_formula: bool = False`, `formula: str | None = None`
  - validator: `is_formula=True` のとき `formula` が必須、`is_formula=False` のとき `formula` は `None` であること
  - Grist APIとの送受信用に `alias_generator` または `model_config(populate_by_name=True)` で `colId`/`isFormula` 等のキーに変換できるようにする
- [x] `GEM_TABLE_SCHEME: list[ColumnDef]` — feature.md FR-01 の13列定義（`FULL_COST` を含む）をモジュールレベル定数として定義
- [x] Grist APIレスポンス用モデル: `GristColumnFields`（`type`, `label`, `formula`, `isFormula` を optional、`extra="ignore"`）, `GristColumn`（`id: str`, `fields: GristColumnFields`）, `GristColumnsResponse`（`columns: list[GristColumn]`）
- [x] テーブル存在確認用モデル: `GristTable`（`id: str`）, `GristTablesResponse`（`tables: list[GristTable]`）
- Files to create: `app/grist/models.py`

### Step 3: Gristクライアント（Infrastructure層）
- [x] `GristClient` クラス（`httpx.Client` をラップ、base_url = `f"{settings.grist_url}/api"`, `Authorization: Bearer {settings.grist_api_key}` ヘッダーを付与）
  - `list_table_ids() -> list[str]`（`GET /docs/{docId}/tables`）
  - `table_exists(table_id: str) -> bool`
  - `create_table(table_id: str, columns: list[ColumnDef]) -> None`（`POST /docs/{docId}/tables`）
  - `list_columns(table_id: str) -> list[GristColumn]`（`GET /docs/{docId}/tables/{tableId}/columns`）
  - `create_columns(table_id: str, columns: list[ColumnDef]) -> None`（`POST /docs/{docId}/tables/{tableId}/columns`）
  - `update_columns(table_id: str, columns: list[ColumnDef]) -> None`（`PATCH /docs/{docId}/tables/{tableId}/columns`。body の `id` は既存colId、`fields` に変更内容）
  - `delete_column(table_id: str, col_id: str) -> None`（`DELETE /docs/{docId}/tables/{tableId}/columns/{colId}`）
  - 各メソッドで `httpx.RequestError` / `httpx.HTTPStatusError` を捕捉し `RuntimeError` に変換
- Files to create: `app/grist/client.py`

### Step 4: 差分検出・反映ロジック（Application層）
- [x] `SchemaDiff(BaseModel)`: `to_add: list[ColumnDef]`, `to_update: list[ColumnDef]`, `to_delete: list[str]`
- [x] `compute_diff(desired: list[ColumnDef], current: list[GristColumn]) -> SchemaDiff`
  - `current` を `col_id` でインデックス化
  - `desired` に存在し `current` に無い列 → `to_add`
  - `current` に存在し `desired` に無い列 → `to_delete`（colIdのみ）
  - 両方に存在し `type` / `is_formula` / `formula` / `label` のいずれかが不一致 → `to_update`
  - 完全一致 → 何もしない（AC-05のべき等性を保証する中核ロジック）
- [x] `apply_diff(client: GristClient, table_id: str, diff: SchemaDiff) -> None`
  - `to_delete` → `delete_column` を列ごとに呼ぶ
  - `to_add` → `create_columns` にまとめて渡す
  - `to_update` → `update_columns` にまとめて渡す
  - 各操作をログに記録し、どこまで反映されたかを追跡可能にする（Reliability要件）
- [x] `sync_gem_table_schema(client: GristClient, table_id: str, scheme: list[ColumnDef] = GEM_TABLE_SCHEME) -> SchemaDiff`
  - `client.table_exists(table_id)` が `False` の場合、`client.create_table(table_id, scheme)` を呼んで早期returnする（FR-03）
  - `True` の場合、`client.list_columns` → `compute_diff` → `apply_diff` を実行し、実行した `SchemaDiff` を返す
- Files to create: `app/grist/sync.py`

### Step 5: エントリーポイント統合
- [x] `app/main.py` の `main()` から `check_grist()` の後に `sync_gem_table_schema()` を呼び出す（`GristClient` を `settings` から構築）
- Files to modify: `app/main.py`

### Step 6: テスト
- [x] `tests/grist/test_models.py`
  - `ColumnDef(is_formula=True, formula=None)` がエラーになること
  - `ColumnDef(is_formula=False, formula="...")` がエラーになること（矛盾入力の拒否）
  - `GEM_TABLE_SCHEME` が feature.md FR-01 の13列（`FULL_COST` を含む）と一致すること（AC-06, AC-08）
- [x] `tests/grist/test_sync.py`（`compute_diff` の純粋関数テスト、HTTP不要）
  - `current=[]` の場合、`to_add` が `GEM_TABLE_SCHEME` 全列と一致（AC-03）
  - `desired` に無い列が `current` にある場合、`to_delete` に含まれる（AC-02）
  - `type`/`formula` が異なる既存列がある場合、`to_update` に含まれる（AC-04）
  - `current` と `desired` が完全一致する場合、`SchemaDiff` の全フィールドが空（AC-05, べき等性）
- [x] `tests/grist/test_client.py`（`httpx.MockTransport` を使い、実HTTP無しでリクエスト形式を検証）
  - `list_columns` が正しいURL・ヘッダーでGETし、レスポンスを `GristColumn` にパースすること
  - `create_columns` / `update_columns` が正しいJSONボディ（`{"columns": [...]}`、フィールドは `colId`/`isFormula` にalias変換済み）でPOST/PATCHすること
  - `delete_column` が `DELETE /.../columns/{colId}` を呼ぶこと
  - `create_table` が `POST /docs/{docId}/tables` に `columns` を含めて呼ぶこと（AC-01）
  - ネットワークエラー・4xx/5xxレスポンス時に `RuntimeError` が発生すること（AC-07）
- [x] `tests/grist/test_sync_integration.py`（`GristClient` をモック化した `sync_gem_table_schema` の統合的な単体テスト）
  - テーブル未存在時 `create_table` のみが呼ばれ、差分計算は行われないこと（AC-01）
  - テーブル存在時、差分検出→反映（add/update/delete）が正しい順序・引数で呼ばれること
- Files to create: `tests/grist/__init__.py`, `tests/grist/test_models.py`, `tests/grist/test_sync.py`, `tests/grist/test_client.py`, `tests/grist/test_sync_integration.py`

## Acceptance Criteria Mapping
| AC | Verified By |
|----|-------------|
| AC-01: テーブル未存在時に全列で新規作成 | `test_client.py#test_create_table_sends_columns`, `test_sync_integration.py#test_creates_table_when_missing` |
| AC-02: 期待スキーマにない列は自動削除 | `test_sync.py#test_extra_column_marked_for_delete`, `test_client.py#test_delete_column_calls_correct_url` |
| AC-03: 不足列は正しいtype/isFormula/formulaでPOST | `test_sync.py#test_missing_columns_marked_for_add`, `test_client.py#test_create_columns_sends_correct_body` |
| AC-04: type/formula不一致列はPATCHで修正 | `test_sync.py#test_mismatched_column_marked_for_update`, `test_client.py#test_update_columns_sends_correct_body` |
| AC-05: 完全一致時は変更系リクエストなし（べき等性） | `test_sync.py#test_matching_schema_produces_empty_diff` |
| AC-06: pydanticモデルでの期待/実際スキーマ表現 | `test_models.py#test_gem_table_scheme_matches_spec` |
| AC-07: 接続失敗時に明確な例外 | `test_client.py#test_request_error_raises_runtime_error`, `test_client.py#test_http_status_error_raises_runtime_error` |
| AC-08: `71000_COST` は `FULL_COST` として定義 | `test_models.py#test_gem_table_scheme_matches_spec` |

## Risks & Mitigations
- Risk: 余分な列の自動削除により、手動で追加した列や意図しない列が消える → Mitigation: 削除対象をログに出力してから実行し、対象は固定の `gem` テーブルのみに限定する（ユーザーが自動削除を明示的に選択済み）
- Risk: `isFormula` の変更（データ列→formula列）をPATCHすると、Grist上の既存セル値が失われる可能性 → Mitigation: 反映前に変更対象列と操作内容をログ出力し、追跡可能にする。値保護自体は本機能のスコープ外（ユーザーが自動PATCHを選択済み）
- Risk: Grist REST APIのベースパスが `{GRIST_URL}/api` で固定できない環境（リバースプロキリ構成等）がある → Mitigation: base_urlの組み立てを `GristClient` の1箇所に集約し、将来設定で上書きできるようにしておく
- Risk: 反映処理が途中で失敗した場合、部分的にしか反映されない状態になる → Mitigation: `sync_gem_table_schema` はべき等（AC-05）なので、失敗後に再実行すれば残りの差分のみが再試行される

## Estimated Complexity
Medium — 新規モジュール3つ（models/client/sync）とテスト一式の追加だが、DB・UIを伴わず対象は単一テーブル・13列のスキーマ比較に限定されるため、規模は小さい。Grist REST APIの正確な仕様確認（OpenAPI定義参照済み）により実装時の手戻りリスクは低い。

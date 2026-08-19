# Implementation Plan: Gemテーブル 行データ自動同期

## Overview

既存の「カラムスキーマ同期」と対称な構造で「行データ同期」を追加する。
レイヤ方針（`models.py` → `client.py` → `sync.py` の一方向依存）は既存決定をそのまま踏襲し、
差分検出は純粋関数としてHTTP通信から分離する。

命名は既存の対称物に揃える:

| 列同期（既存） | 行同期（本機能） |
|---------------|-----------------|
| `ColumnDef` | `GemRowDef` |
| `GEM_TABLE_SCHEME` | `GEM_TABLE_ROWS` |
| `GristColumn` / `GristColumnsResponse` | `GristRecord` / `GristRecordsResponse` |
| `SchemaDiff` | `RecordDiff` |
| `compute_diff` | `compute_record_diff` |
| `apply_diff` | `apply_record_diff` |
| `sync_gem_table_schema` | `sync_gem_table_records` |

実装順序は依存の下流から上流へ: models → client → sync → main → tests。
各ステップ後に `uv run pytest` を実行し、失敗を次のステップへ持ち越さない。

---

## Step 1: 行データモデルと定義定数（`app/grist/models.py`）

**目的**: AC-01, AC-08, AC-10 の土台

### 1-1. `GemRowDef` モデルを追加

`ColumnDef` の直後、`GEM_TABLE_SCHEME` の前に配置する。

- フィールド: `flawed_gem_name: str`, `flawless_gem_name: str`
- `model_config = ConfigDict(populate_by_name=True)`（`ColumnDef` と揃える）
- `to_fields() -> dict` メソッド: Grist Records APIの `fields` ペイロードを生成する
  - 戻り値は `{"FLAWED_GEM_NAME": ..., "FLAWLESS_GEM_NAME": ...}` の2キーのみ
  - **formula列を含めないこと**（AC-10）。`to_fields()` が返すキーを2つに限定することでこれを構造的に保証する。
- 自然キー参照用に、`FLAWED_GEM_NAME` / `FLAWLESS_GEM_NAME` の列ID文字列をモジュールレベル定数として定義する
  （`sync.py` からも参照するため、文字列リテラルの二重管理を避ける）:
  - `FLAWED_NAME_COL = "FLAWED_GEM_NAME"`
  - `FLAWLESS_NAME_COL = "FLAWLESS_GEM_NAME"`
  - `GEM_TABLE_SCHEME` の該当 `ColumnDef` もこの定数を使うよう書き換える（定義の単一化）

### 1-2. `GEM_TABLE_ROWS` 定数を追加

`GEM_TABLE_SCHEME` の直後に配置。仕様の6件を記載順どおりに定義する:

```
SAPPHIRE, AMETHYST, AMBER, TOPAZ, PERIDOT, JADE
```

各要素は `GemRowDef(flawed_gem_name="FLAWED_<X>_GEM", flawless_gem_name="FLAWLESS_<X>_GEM")`。

> 注: `FLAWLESS_<X>_GEM` は `FLAWED_<X>_GEM` から機械的に導出可能だが、
> 命名規則の例外に耐えるため明示的にペアで書く（feature.md「Out of Scope」参照）。

### 1-3. Records APIレスポンスモデルを追加

`GristColumnsResponse` の後、`GristTable` の前に配置。

- `GristRecord`: `id: int`, `fields: dict` / `model_config = ConfigDict(extra="ignore")`
  - `fields` は列構成が可変なため `dict` のまま保持する（`GristColumnFields` のような固定モデルにはしない）
- `GristRecordsResponse`: `records: list[GristRecord]` / `extra="ignore"`

### Checklist
- [x] `GemRowDef` を追加し、`to_fields()` が2キーのみを返す
- [x] `FLAWED_NAME_COL` / `FLAWLESS_NAME_COL` 定数を追加し、`GEM_TABLE_SCHEME` からも参照する
- [x] `GEM_TABLE_ROWS` に6件を仕様どおりの順序で定義
- [x] `GristRecord` / `GristRecordsResponse` を追加
- [x] `uv run pytest` — 既存テスト全パス（AC-12 の中間確認）

---

## Step 2: Records APIクライアント（`app/grist/client.py`）

**目的**: AC-08, AC-09

`delete_column` の後に4メソッドを追加する。既存メソッドと同じスタイルを厳守:
`_request()` 経由 / `quote()` でパスエスケープ / 戻り値の型アノテーション付与。

| メソッド | シグネチャ | HTTP | パス | ボディ |
|---------|-----------|------|------|-------|
| `list_records` | `(doc_id, table_id) -> list[GristRecord]` | GET | `/docs/{doc}/tables/{table}/records` | — |
| `create_records` | `(doc_id, table_id, rows: list[GemRowDef]) -> None` | POST | 同上 | `{"records": [{"fields": r.to_fields()}]}` |
| `update_records` | `(doc_id, table_id, rows: list[tuple[int, GemRowDef]]) -> None` | PATCH | 同上 | `{"records": [{"id": rid, "fields": r.to_fields()}]}` |
| `delete_records` | `(doc_id, table_id, row_ids: list[int]) -> None` | POST | `/docs/{doc}/tables/{table}/records/delete` | `row_ids`（裸のJSON配列） |

- `list_records` は `GristRecordsResponse.model_validate(response.json())` でパースし `.records` を返す
- インポート行に `GemRowDef`, `GristRecord`, `GristRecordsResponse` を追加

> **削除のボディ形状に注意**: Grist公式OpenAPI定義（`RowIds` スキーマ）では
> オブジェクトでラップせず `[101, 102, 103]` のような**裸の配列**を送る。

### Checklist
- [x] 4メソッドを追加
- [x] 全メソッドが `_request()` を経由し、`quote()` を使用
- [x] `delete_records` が裸の配列を送信
- [x] `uv run pytest` — 既存テスト全パス

---

## Step 3: 行の差分検出と適用（`app/grist/sync.py`）

**目的**: AC-02〜AC-07

`sync_gem_table_schema` の後に追加する。

### 3-1. `RecordDiff` モデル

```
to_add:    list[GemRowDef]              追加する行
to_update: list[tuple[int, GemRowDef]]  (対象行id, 期待値)
to_delete: list[int]                    削除する行id
is_empty() -> bool
```

### 3-2. `compute_record_diff(desired: list[GemRowDef], current: list[GristRecord]) -> RecordDiff`

純粋関数（HTTP通信なし）。アルゴリズム:

1. `current` を先頭から走査し、`record.fields.get(FLAWED_NAME_COL)` をキーとする
   「キー → 最初に出現したrecord」のマップを構築する。
   - **2件目以降の同一キー（重複行）は即座に `to_delete` へ**（AC-06: 先頭1件を残す）
   - `desired` に無いキーの行も `to_delete` へ（AC-04）
   - キーが `None` / 空文字 / 非str の行は `desired` に一致し得ないため `to_delete` へ（AC-07）
2. `desired` を走査:
   - キーがマップに無ければ `to_add`（AC-02）
   - あれば `record.fields.get(FLAWLESS_NAME_COL)` と `flawless_gem_name` を比較し、
     異なる場合のみ `(record.id, desired_row)` を `to_update` へ（AC-05）
   - 一致していれば何もしない（AC-03）

> `to_delete` の順序は `current` の走査順に従う（テストで順序を検証できるように決定的にする）。

### 3-3. `apply_record_diff(client, doc_id, table_id, diff) -> None`

`apply_diff` と同じ方針: **削除 → 追加 → 更新** の順。
各リストが非空の場合のみAPIを呼ぶ（NFR-02: 各操作1リクエスト）。
`logger.info` で対象を出力する（既存の列同期と同じ粒度: 対象キー/id のリスト）。

### 3-4. `sync_gem_table_records(client, doc_id, table_id, rows=None) -> RecordDiff`

`sync_gem_table_schema` と同じシグネチャ規約:

- `rows` が `None` なら `GEM_TABLE_ROWS` を使う（テストからの差し替えを可能にする）
- `client.list_records()` → `compute_record_diff()` → 空なら `logger.info` → `apply_record_diff()` → `diff` を返す
- **テーブル存在チェックは行わない** — 呼び出し側でスキーマ同期が先に走りテーブル作成を保証するため（FR-05）。
  この前提はdocstringに明記する。

### Checklist
- [x] `RecordDiff` を追加
- [x] `compute_record_diff` を純粋関数として追加（重複・空キーを含む全分類を処理）
- [x] `apply_record_diff` が削除→追加→更新の順で、非空時のみ呼び出す
- [x] `sync_gem_table_records` を追加（docstringに事前条件を明記）
- [x] `uv run pytest` — 既存テスト全パス

---

## Step 4: エントリーポイント統合（`app/main.py`）

**目的**: AC-11

`main()` 内、`sync_gem_table_schema(...)` の**直後**（同じ `with` ブロック内）に
`sync_gem_table_records(client, settings.grist_doc_id, settings.grist_gem_table_name)` を追加する。

- インポートに `sync_gem_table_records` を追加
- 列が無い状態で行を書き込めないため、順序を入れ替えないことをコメントで示す
- `logging.basicConfig(level=logging.INFO)` が未設定のため、同期ログが標準出力に出ない。
  `main()` の先頭に追加してログが見えるようにする（既存機能のログも同時に有効化される）。

### Checklist
- [x] スキーマ同期の後に行同期を呼び出す
- [x] `logging.basicConfig` を設定
- [x] `uv run pytest` — 全パス

---

## Step 5: テスト追加

**目的**: 全ACの検証 + AC-12（リグレッションなし）

### 5-1. `tests/grist/test_models.py`

- `test_gem_table_rows_matches_spec`: `GEM_TABLE_ROWS` の
  `(flawed_gem_name, flawless_gem_name)` タプル列が仕様の6件と順序込みで一致（**AC-01**）
- `test_gem_row_to_fields_contains_only_name_columns`: `to_fields()` のキー集合が
  ちょうど `{FLAWED_GEM_NAME, FLAWLESS_GEM_NAME}` であり、formula列（`CRAFT_COST` 等）を含まない（**AC-10**）
- `test_gem_row_names_covered_by_scheme`: `to_fields()` の全キーが `GEM_TABLE_SCHEME` の
  非formula列に存在する（行データ用の列がスキーマ側に定義されていることの整合性チェック）

### 5-2. `tests/grist/test_client.py`

既存の `_client(handler)` ヘルパをそのまま再利用する。

- `test_list_records_parses_response`: メソッド/パス検証 + `id`・`fields` のパース。
  レスポンスに未知キー（例: `manualSort`）を含めてもエラーにならないこと（**AC-08**）
- `test_create_records_sends_correct_body`: POST / 正しいパス / `{"records":[{"fields":{...}}]}`（**AC-09**）
- `test_update_records_sends_correct_body`: PATCH / `{"records":[{"id":N,"fields":{...}}]}`（**AC-09**）
- `test_delete_records_sends_row_id_array`: POST `/records/delete` / ボディが裸の配列 `[3, 5]`（**AC-09**）

### 5-3. `tests/grist/test_sync.py`

`compute_record_diff` の単体テスト。`GristRecord` を直接組み立てるヘルパ
`_as_records(pairs: list[tuple[int, str, str]])` を追加する。

- `test_empty_table_marks_all_rows_for_add`（**AC-02**）
- `test_matching_rows_produce_empty_diff`（**AC-03**）
- `test_unknown_row_marked_for_delete`（`FLAWED_RUBY_GEM`）（**AC-04**）
- `test_mismatched_flawless_name_marked_for_update`: 正しい `id` と期待値が入り、
  `to_add` / `to_delete` が空（**AC-05**）
- `test_duplicate_flawed_name_keeps_first_deletes_rest`（**AC-06**）
- `test_blank_flawed_name_marked_for_delete`: `""` と欠損キーの両方（**AC-07**）

### 5-4. `tests/grist/test_sync_integration.py`

`FakeGristClient` を拡張する（既存の列同期テストを壊さないよう、コンストラクタ引数
`records` はデフォルト値付きで追加する）:

- `records: list[GristRecord] | None = None` を受け取り `list_records` で返す
- `create_records` / `update_records` / `delete_records` を `self.calls` に記録

追加テスト:

- `test_records_sync_adds_all_when_empty`: 呼び出し列が
  `["list_records", "create_records"]` で、6件が渡される（**AC-02**）
- `test_records_sync_applies_delete_add_update_in_order`: 呼び出し順が
  `["list_records", "delete_records", "create_records", "update_records"]`（**FR-04**）
- `test_records_sync_is_noop_when_in_sync`: 呼び出し列が `["list_records"]` のみで、
  書き込み系が一度も呼ばれない（**AC-03 / AC-06 冪等性 = FR-06**）

### 5-5. `app/main.py` の順序検証（**AC-11**）

`tests/grist/test_main.py` を新規作成。`app.config.settings` が `.env` 依存で
インポート時に評価されるため、テストは環境変数を注入せずに済む形にする:

- `monkeypatch` で `app.main.check_grist` / `GristClient` / 両同期関数を差し替え、
  呼び出し順が `["sync_gem_table_schema", "sync_gem_table_records"]` になることを検証する
- `app.main` のインポート時に `settings` の必須項目（`grist_api_key` / `grist_doc_id`）が
  未設定だと `ValidationError` になる。`.env` が存在しないCI環境でも動くよう、
  `monkeypatch.setenv` ではなく **`conftest.py` で必須環境変数のダミー値を設定**する
  （`tests/conftest.py` を新規作成し、`os.environ.setdefault` で設定）。
  - 実装時に `.env` の有無で挙動が変わらないことを確認する

> このステップで既存テストが壊れる場合は、`main.py` のテスト容易性を優先して
> `main()` の構造（同期関数をモジュールレベルから参照する形）を保つ。

### Checklist
- [x] `tests/conftest.py` を追加（必須環境変数のダミー値）
- [x] `test_models.py` に3ケース追加
- [x] `test_client.py` に4ケース追加
- [x] `test_sync.py` に6ケース追加
- [x] `test_sync_integration.py` に3ケース追加 + `FakeGristClient` 拡張（後方互換）
- [x] `test_main.py` を新規追加（順序検証）
- [x] `uv run pytest` — **全テストパス**

---

## Step 6: 最終検証

- [x] `uv run pytest -v` を実行し、全テストがパスすることを確認（40 passed）
- [x] 全AC（AC-01〜AC-12）が対応するテストで検証されていることを確認
- [x] 新規依存が追加されていないことを確認（`pyproject.toml` 無変更 / NFR-01）
- [x] `git diff` でレイヤ違反（`models.py` が `client.py` を参照する等）が無いことを確認

---

## AC → Test Mapping

| AC | 検証内容 | テスト |
|----|---------|-------|
| AC-01 | 6件のGemペア定義 | `test_models.py::test_gem_table_rows_matches_spec` |
| AC-02 | 空テーブル → 全件追加 | `test_sync.py::test_empty_table_marks_all_rows_for_add`, `test_sync_integration.py::test_records_sync_adds_all_when_empty` |
| AC-03 | 一致時は差分空・書き込みなし | `test_sync.py::test_matching_rows_produce_empty_diff`, `test_sync_integration.py::test_records_sync_is_noop_when_in_sync` |
| AC-04 | 定義外の行を削除 | `test_sync.py::test_unknown_row_marked_for_delete` |
| AC-05 | FLAWLESS不一致は更新 | `test_sync.py::test_mismatched_flawless_name_marked_for_update` |
| AC-06 | 重複行は先頭を残す | `test_sync.py::test_duplicate_flawed_name_keeps_first_deletes_rest` |
| AC-07 | 空キー行は削除 | `test_sync.py::test_blank_flawed_name_marked_for_delete` |
| AC-08 | レスポンスのパース（未知キー許容） | `test_client.py::test_list_records_parses_response` |
| AC-09 | 4メソッドのHTTP形状 | `test_client.py::test_create_records_sends_correct_body`, `test_update_records_sends_correct_body`, `test_delete_records_sends_row_id_array`, `test_list_records_parses_response` |
| AC-10 | formula列を送らない | `test_models.py::test_gem_row_to_fields_contains_only_name_columns` |
| AC-11 | 列同期 → 行同期の順序 | `test_main.py` |
| AC-12 | リグレッションなし | 既存の `test_models.py` / `test_client.py` / `test_sync.py` / `test_sync_integration.py` 全ケース |

## Risks / Notes

- **`FakeGristClient` の後方互換**: 既存3テストが `FakeGristClient(table_exists=..., columns=...)` を
  位置/キーワード引数で呼んでいる。`records` はデフォルト値付きで追加し、既存呼び出しを壊さない。
- **`settings` のインポート時評価**: `app/config.py` はモジュールレベルで `Settings()` を実行するため、
  `app.main` をインポートするテストは環境変数が必要。`tests/conftest.py` で吸収する。
- **削除の破壊性**: 「定義に無い行は削除」はユーザー確認済みの方針だが、Grist上で手動追加した行が
  消える。ドライラン機能はOut of Scopeのため、ログ出力で削除対象を明示することで可視性を担保する。
- **依存追加なし**: httpx / pydantic のみで完結する（NFR-01）。

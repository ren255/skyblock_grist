# Code Review: Gemテーブル 行データ自動同期

## Summary

実装は既存のカラムスキーマ同期と対称な構造で書かれており、レイヤリング（`models.py` → `client.py` → `sync.py`）・命名・エラーハンドリング方針のいずれも既存コードの規約を正確に踏襲している。差分検出が純粋関数として分離されているため、12件のACすべてがHTTP通信なしで直接検証されており、テストは実装を後追いした形跡がなく本質を突いている。Grist Records APIのエンドポイント形状（特に `records/delete` が裸の配列を取る点）が公式OpenAPI定義で事前検証されているのも良い。

CriticalおよびMajorな問題は無い。指摘は堅牢性・テスト重複・ログレベルに関する軽微なもののみで、いずれもマージを妨げない。

## Findings

### 🔴 Critical

| Done | Location | Category | Problem | Suggestion |
|------|----------|----------|---------|------------|
| — | — | — | 該当なし | — |

### 🟠 Major

| Done | Location | Category | Problem | Suggestion |
|------|----------|----------|---------|------------|
| — | — | — | 該当なし | — |

### 🟡 Minor

| Done | Location | Category | Problem | Suggestion |
|------|----------|----------|---------|------------|
| [ ] | `app/grist/sync.py:113` | Robustness | `desired` 側に同一 `flawed_gem_name` が重複していても検出されず、初回実行時に重複行がGristに作られる（次回実行で片方が削除され自己修復するが、一時的に不正な行が残る） | `test_models.py` に `GEM_TABLE_ROWS` のキー一意性アサーションを追加し、将来Gemを追記した際の事故を防ぐ |
| [ ] | `tests/grist/test_sync.py:78`, `tests/grist/test_sync_integration.py:56` | Test Duplication | `_in_sync_records()` と行生成ヘルパが2つのテストモジュールにほぼ同一内容で重複している | どちらか一方に寄せるか `tests/grist/conftest.py` にfixtureとして切り出す |

### 🔵 Info / Suggestions

| Done | Location | Category | Problem | Suggestion |
|------|----------|----------|---------|------------|
| [ ] | `app/grist/sync.py:142` | Observability | 行削除は破壊的操作だがログレベルが `INFO` で、追加・更新と同じ重みで流れる | 削除のみ `logger.warning` に上げ、ユーザーデータ消失を目視で追えるようにする |
| [ ] | `app/grist/sync.py:166` | Error Handling | テーブル未存在時の事前条件がdocstringのみで、単独呼び出しすると `list_records` が不透明な `RuntimeError: Grist returned HTTP 404` を投げる | 現状はmain.pyで順序が担保されているため許容。将来公開APIとして使うなら `table_exists` ガードを追加 |
| [ ] | `app/main.py:26` | Test Hygiene | `logging.basicConfig()` が `main()` 内にありグローバルなロギング状態を変更するため、`test_main.py` 実行時にも副作用が出る | 実害は無いが、`if __name__ == '__main__'` ブロック側へ移すとエントリーポイント専用の設定として明確になる |
| [ ] | `app/grist/sync.py:119` | Data Safety | 名前列を持たない既存テーブルにスキーマ同期で列が追加された場合、既存行は全て空キー扱いとなり初回実行で削除される | 確認済みの「完全一致」方針どおりの挙動。初回実行前に価格データのバックアップを取ることを推奨 |

## Acceptance Criteria Coverage

| AC | Test | Status |
|----|------|--------|
| AC-01: 6件のGemペア定義 | `test_models.py::test_gem_table_rows_matches_spec` | ✅ Covered |
| AC-02: 空テーブル → 全件追加 | `test_sync.py::test_empty_table_marks_all_rows_for_add`, `test_sync_integration.py::test_records_sync_adds_all_when_empty` | ✅ Covered |
| AC-03: 一致時は差分空・書き込みなし | `test_sync.py::test_matching_rows_produce_empty_diff`, `test_sync_integration.py::test_records_sync_is_noop_when_in_sync` | ✅ Covered |
| AC-04: 定義外の行を削除 | `test_sync.py::test_unknown_row_marked_for_delete` | ✅ Covered |
| AC-05: FLAWLESS不一致は更新 | `test_sync.py::test_mismatched_flawless_name_marked_for_update` | ✅ Covered |
| AC-06: 重複行は先頭を残す | `test_sync.py::test_duplicate_flawed_name_keeps_first_deletes_rest` | ✅ Covered |
| AC-07: 空キー行は削除 | `test_sync.py::test_blank_flawed_name_marked_for_delete` | ✅ Covered |
| AC-08: レスポンスのパース（未知キー許容） | `test_client.py::test_list_records_parses_response` | ✅ Covered |
| AC-09: 4メソッドのHTTP形状 | `test_client.py::test_create_records_sends_correct_body` 他3件 | ✅ Covered |
| AC-10: formula列を送らない | `test_models.py::test_gem_row_to_fields_contains_only_name_columns` | ✅ Covered |
| AC-11: 列同期 → 行同期の順序 | `test_main.py::test_schema_sync_runs_before_record_sync` | ✅ Covered |
| AC-12: リグレッションなし | 既存23ケース継続パス（全40 passed） | ✅ Covered |

### 検証メモ

- **AC-08** は record レベルの未知キー（`manualSort`）と `fields` 内の未知キー（`BUY_ORDER`）の両方で検証されており、`extra="ignore"` と `fields: dict` の双方が効いていることを確認した。
- **AC-03 / FR-06（冪等性）** は integration テストが `op_names == ["list_records"]` を主張しており、書き込み系が1回も呼ばれないことが構造的に保証されている。
- **AC-10** は `to_fields()` の戻り値キー集合が2件に限定されている実装により構造的に担保されており、テストは `GEM_TABLE_SCHEME` のformula列との排他性まで検証している。
- `tests/conftest.py` が飾りでないことを、`.env` を除いた複製環境で確認済み（除去すると収集失敗、復元で40件パス）。

## Dimension Notes

| 観点 | 評価 |
|------|------|
| 言語・イディオム | ✅ 型注釈完備、`isinstance` ガードで外部データを防御、print等のデバッグ出力なし |
| レイヤリング | ✅ `models.py` は外部importゼロを維持。差分検出は純粋関数でHTTPから分離 |
| セキュリティ | ✅ APIキーはログ・例外メッセージに出ない。パスは `quote()` でエスケープ、ボディはJSON化のみで注入余地なし |
| 依存関係 | ✅ 新規依存なし（`pyproject.toml` / `uv.lock` 無変更、NFR-01充足） |
| パフォーマンス | ✅ 追加・更新・削除がそれぞれ1リクエストにまとめられており、行ごとのループ呼び出しなし（NFR-02充足） |
| 重複コード | 🟡 テストヘルパのみ重複（上記Minor参照）。プロダクションコードに重複なし |
| テスト品質 | ✅ AAA構造、シナリオが明確な命名、モックは境界（HTTP/クライアント）のみ、sleep不使用 |

## Verdict

- [ ] ✅ Ready to merge
- [x] 🟡 Merge after minor fixes (no re-review needed)
- [ ] 🟠 Requires fixes and re-review
- [ ] 🔴 Do not merge — significant issues found

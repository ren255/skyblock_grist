# Gemテーブル 行データ自動同期

Implemented on: 2026-08-18

## 概要

Grist `gem` テーブルの**行**（分析対象のGem一覧）を、Python側に定義した6件のGemペアと完全一致させる機能。
既存の「Gemテーブル カラムスキーマ自動同期」が列構成を宣言的に管理しているのに対し、本機能は同じ宣言的アプローチを行データに適用する。

対象Gem（6件）: SAPPHIRE / AMETHYST / AMBER / TOPAZ / PERIDOT / JADE
（各Gemについて `FLAWED_<X>_GEM` と `FLAWLESS_<X>_GEM` のペアを定義）

## 同期セマンティクス

`FLAWED_GEM_NAME` を行の自然キーとして突き合わせ、以下を実施する:

| 状態 | 動作 |
|------|------|
| 定義にあるがGristに無い | 追加 |
| キー一致・`FLAWLESS_GEM_NAME` 不一致 | 更新（2列のみ上書き） |
| Gristにあるが定義に無い | 削除 |
| 同一キーの重複行 | 先頭を残し残りを削除 |
| キーが空/未設定/非文字列 | 削除 |

価格列（`BUY_ORDER` / `SELL_ORDER` 等）は行の同一性が保たれる限り保持される（更新は名前2列のみをPATCHするため）。

## 主要ファイル

| ファイル | 役割 |
|---------|------|
| `app/grist/models.py` | `GemRowDef` / `GEM_TABLE_ROWS`（6件）/ `GristRecord` / `GristRecordsResponse`、列ID定数 `FLAWED_NAME_COL` `FLAWLESS_NAME_COL` |
| `app/grist/client.py` | `list_records` / `create_records` / `update_records` / `delete_records` |
| `app/grist/sync.py` | `RecordDiff` / `compute_record_diff`（純粋関数）/ `apply_record_diff` / `sync_gem_table_records` |
| `app/main.py` | カラム同期の**後**に行同期を実行、`logging.basicConfig` 設定 |
| `tests/conftest.py` | `.env` 非依存で `app.main` をインポートするための環境変数ダミー値 |

## 注目すべき決定事項

- **宣言的な完全同期**: 定義に無い行は削除する方針をユーザー確認のうえ採用。列スキーマ同期と同じ思想で統一した。
- **formula列の構造的な保護**: `GemRowDef.to_fields()` が名前2列のみを返すため、formula列（`CRAFT_COST` 等）をクライアントから書き込むことが構造的に不可能。呼び出し側の注意に依存しない。
- **削除エンドポイントの形状**: `POST /records/delete` は他のrecords操作と異なり**裸のrow id配列**を送る。公式OpenAPI定義（`gristlabs/grist-help` の `api/grist.yml`、`RowIds` スキーマ）で実装前に検証済み。
- **差分検出の純粋関数化**: `compute_record_diff` はHTTP通信を含まないため、全同期セマンティクスがモックなしで単体テスト可能。

## テスト

全40テストパス（本機能で17ケース追加、既存23ケースは継続パス）。
12件のACすべてが対応するテストで検証されている（詳細は `review.md` の AC カバレッジ表を参照）。

## レビュー結果

Verdict: 🟡 **Merge after minor fixes (no re-review needed)** — Critical / Major の指摘なし。

未対応の軽微な指摘（`review.md` にチェックボックス付きで記載）:

- 🟡 `GEM_TABLE_ROWS` 側のキー重複を検出しない（初回実行時に重複行が作られ、3回目の実行で自己修復する）
- 🟡 テストヘルパ `_in_sync_records()` が2つのテストモジュールで重複
- 🔵 破壊的な行削除のログレベルが `INFO`（`WARNING` 推奨）
- 🔵 `sync_gem_table_records` のテーブル存在前提がdocstringのみ
- 🔵 `logging.basicConfig()` が `main()` 内でグローバル状態を変更

## 既知の注意点

名前列を持たない既存テーブルにスキーマ同期で列が追加された場合、既存の全行が空キー扱いとなり初回実行で削除される。
これは確認済みの「完全一致」方針どおりの挙動だが、初回実行前に価格データのバックアップを推奨する。

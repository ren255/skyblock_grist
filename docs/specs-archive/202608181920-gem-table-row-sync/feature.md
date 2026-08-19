# Feature: Gemテーブル 行データ自動同期

## Summary

Grist `gem` テーブルに、対象とするGem（宝石）の行データをPython側の定義から自動的に同期する。

既存の「Gemテーブル カラムスキーマ自動同期」がテーブルの**列構成**を宣言的に管理しているのに対し、本機能はテーブルの**行**（どのGemを分析対象にするか）を同じ宣言的アプローチで管理する。Python側に定義した6件のGemペア（`FLAWED_GEM_NAME` / `FLAWLESS_GEM_NAME`）が、Grist側の行と常に完全一致する状態を保つ。

対象Gem（6件）:

| FLAWED_GEM_NAME | FLAWLESS_GEM_NAME |
|-----------------|-------------------|
| FLAWED_SAPPHIRE_GEM | FLAWLESS_SAPPHIRE_GEM |
| FLAWED_AMETHYST_GEM | FLAWLESS_AMETHYST_GEM |
| FLAWED_AMBER_GEM | FLAWLESS_AMBER_GEM |
| FLAWED_TOPAZ_GEM | FLAWLESS_TOPAZ_GEM |
| FLAWED_PERIDOT_GEM | FLAWLESS_PERIDOT_GEM |
| FLAWED_JADE_GEM | FLAWLESS_JADE_GEM |

## User Stories

- **US-01**: 開発者として、対象Gemの一覧をPythonコード上の1箇所で定義したい。Grist UIで手作業で行を作りたくないため。
- **US-02**: 開発者として、同期処理を何度実行してもGrist側の行が重複しないようにしたい。定期的なバッチ実行を前提としているため。
- **US-03**: 開発者として、対象Gemを追加・削除したときにコード側の定義を変えるだけでGrist側が追従してほしい。定義とデータストアの乖離を防ぐため。
- **US-04**: 開発者として、既に入力済みの価格データ（`BUY_ORDER` 等）を同期処理で消したくない。行の同一性が保たれている限り価格列は保持されるべきため。

## Functional Requirements

### FR-01: 期待行データの定義
- `app/grist/models.py` に、1行分のGemデータを表すpydanticモデルと、対象6件の定義定数を追加する。
- 定義は `FLAWED_GEM_NAME` と `FLAWLESS_GEM_NAME` の2列のみを持つ。他の列（`BUY_ORDER`、`SELL_ORDER`、`AVG_SELLING_PER_MINUTE` 等）は本機能の管理対象外。
- `FLAWED_GEM_NAME` を行の自然キー（一意識別子）として扱う。

### FR-02: Grist Records APIクライアント
`app/grist/client.py` の `GristClient` に以下を追加する。エンドポイントはGrist公式OpenAPI定義（`gristlabs/grist-help` の `api/grist.yml`）に準拠する。

| メソッド | HTTP | パス | ボディ |
|---------|------|------|-------|
| `list_records` | GET | `/docs/{docId}/tables/{tableId}/records` | — |
| `create_records` | POST | `/docs/{docId}/tables/{tableId}/records` | `{"records": [{"fields": {...}}]}` |
| `update_records` | PATCH | `/docs/{docId}/tables/{tableId}/records` | `{"records": [{"id": N, "fields": {...}}]}` |
| `delete_records` | POST | `/docs/{docId}/tables/{tableId}/records/delete` | `[rowId, ...]` |

- レスポンス（`GET`）は `{"records": [{"id": <number>, "fields": {...}}]}` 形式。pydanticモデルで検証する。
- 既存メソッドと同じく `_request()` を経由し、`doc_id` / `table_id` は `quote()` でURLエスケープする。

### FR-03: 行の差分検出
- `app/grist/sync.py` に、期待行リストとGrist現行行リストからの差分を算出する純粋関数を追加する（HTTP通信を含まない＝単体テスト可能）。
- 差分は以下の3分類:
  - **追加**: `FLAWED_GEM_NAME` がGrist側に存在しない期待行。
  - **更新**: `FLAWED_GEM_NAME` が一致する行が存在するが、`FLAWLESS_GEM_NAME` の値が期待値と異なる行（対象行の `id` と期待値を保持）。
  - **削除**: Grist側に存在するが期待定義に無い `FLAWED_GEM_NAME` を持つ行の `id`。
- 差分が空かどうかを判定できること。

### FR-04: 差分の反映
- 削除 → 追加 → 更新 の順に適用する（既存の `apply_diff` と同じ順序方針）。
- 各操作は該当行が存在する場合のみAPI呼び出しを行う（空リストでの無駄なリクエストを送らない）。
- 適用内容は `logging` で出力する（既存の列同期と同水準）。

### FR-05: エントリーポイント統合
- `app/main.py` で、既存のカラムスキーマ同期の**後**に行同期を実行する。列が存在しない状態で行を書き込めないため、この順序は必須。

### FR-06: 冪等性
- 同期処理を連続実行した場合、2回目以降は差分が空となり、Grist側への書き込みAPI呼び出しが発生しないこと。

## Acceptance Criteria

- [x] **AC-01**: 期待行定義に、指定された6件のGemペアが `FLAWED_GEM_NAME` / `FLAWLESS_GEM_NAME` の対応通りに定義されている。
- [x] **AC-02**: Gristの行が空（0件）の状態で同期すると、6件すべてが「追加」対象として検出される。
- [x] **AC-03**: Gristの行が期待定義と完全一致している状態で同期すると、差分が空になり、書き込み系API（POST/PATCH/delete）が一度も呼ばれない。
- [x] **AC-04**: 期待定義に無い `FLAWED_GEM_NAME` を持つ行（例: `FLAWED_RUBY_GEM`）が存在すると、その行の `id` が「削除」対象として検出される。
- [x] **AC-05**: `FLAWED_GEM_NAME` は一致するが `FLAWLESS_GEM_NAME` が異なる行は、「更新」対象として正しい行 `id` と期待値付きで検出される（追加・削除には分類されない）。
- [x] **AC-06**: 同じ `FLAWED_GEM_NAME` を持つ行がGrist側に重複して存在する場合、先頭1件を残し、残りが「削除」対象として検出される。
- [x] **AC-07**: `FLAWED_GEM_NAME` が空文字/未設定の行は期待定義に無い行として「削除」対象になる。
- [x] **AC-08**: `list_records` がGristのレスポンス（`records[].id` / `records[].fields`）を正しくパースし、`fields` に未知のキーが含まれていてもエラーにならない。
- [x] **AC-09**: `create_records` / `update_records` / `delete_records` が、FR-02の表どおりのHTTPメソッド・パス・ボディを送信する（MockTransportで検証）。
- [x] **AC-10**: 行の書き込みボディに、formula列（`CRAFT_COST` 等）が含まれていない。
- [x] **AC-11**: 行同期はカラムスキーマ同期の後に実行される。
- [x] **AC-12**: 既存のカラムスキーマ同期のテストが全て引き続きパスする（リグレッションなし）。

## Technical Scope

| ファイル | 変更内容 |
|---------|---------|
| `app/grist/models.py` | 行データモデル・6件の定義定数・Records APIレスポンスモデルを追加 |
| `app/grist/client.py` | `list_records` / `create_records` / `update_records` / `delete_records` を追加 |
| `app/grist/sync.py` | 行の差分モデル・差分検出関数・差分適用関数・行同期エントリ関数を追加 |
| `app/main.py` | 行同期呼び出しを追加（カラム同期の後） |
| `tests/grist/test_models.py` | 行定義の内容検証を追加 |
| `tests/grist/test_client.py` | Records API 4メソッドのリクエスト検証を追加 |
| `tests/grist/test_sync.py` | 行差分検出のケースを追加 |
| `tests/grist/test_sync_integration.py` | 行同期の一連の流れ（追加/更新/削除/冪等）を追加 |

**アーキテクチャ方針（既存決定を踏襲）**
- `models.py`（スキーマ定義）/ `client.py`（API呼び出しのみ）/ `sync.py`（差分検出・反映）の一方向依存レイヤを維持する。
- 差分検出は純粋関数としてHTTP通信から分離し、単体テスト可能に保つ。
- データ形式の検証・変換はpydanticを用いる（固定2列・6行の構造比較であり表形式データ処理ではないため、pandasは採用しない）。

## Non-Functional Requirements

- **NFR-01**: 依存ライブラリの追加は行わない（httpx / pydantic のみで実装する）。
- **NFR-02**: API呼び出し回数は同期1回あたり定数回に抑える（行ごとの個別リクエストを行わず、追加・更新・削除はそれぞれ1リクエストにまとめる）。
- **NFR-03**: 型アノテーションを既存コードと同水準で付与する。
- **NFR-04**: エラーは既存の `_request()` の方針どおり `RuntimeError` に正規化する（独自例外階層は導入しない）。

## Out of Scope

- 価格列（`BUY_ORDER` / `SELL_ORDER` / `INSTA_SELL` / `AVG_SELLING_PER_MINUTE`）への値の投入 — Hypixel Bazaar API連携は別機能。
- Grist上の行の並び順（`manualSort`）の制御 — 列順が対象外であるのと同じ理由（公開APIでの制御手段が未検証）。
- `FLAWLESS_GEM_NAME` を `FLAWED_GEM_NAME` から自動導出する仕組み — 明示的なペア定義とする（命名規則の例外に耐えるため）。
- 上記6件以外のGem（RUBY / JASPER / OPAL 等）の追加 — 定義定数に追記すれば対応可能な設計とするが、本機能では含めない。
- CLI引数によるドライラン（差分表示のみ）オプション。

## Open Questions

なし（「定義に無い行は削除して完全一致させる」方針をユーザー確認済み）。

# Feature: Gemテーブル カラムスキーマ自動同期

## Summary
Grist上の `gem` テーブルのカラム構成（列名・型・formula）を、Python側で定義した単一のスキーマ定義（column scheme）に自動的に一致させる機能。Grist REST APIの `/tables/{tableId}/columns` エンドポイントから現在のカラム定義を取得し、pydanticモデルとして扱い、Python側の期待スキーマとの差分（追加・削除・変更）を検出した上で、Grist REST API（POST/PATCH/DELETE）を用いて自動的に反映する。これにより、スキーマ定義を変更するだけでGrist上のテーブル構造を追従させられるようにする。

## User Stories
- As a開発者（データ基盤の保守者）として、Python側でcolumn schemeを1箇所変更すれば、Grist上の `gem` テーブルの列構成が自動的に追従してほしい。手動でGrist UIから列を作り直す作業をなくしたい。
- As a開発者として、初回セットアップ時に `gem` テーブルが存在しない場合でも、スキーマ定義から自動でテーブルと全列が作成されてほしい。
- As a開発者として、同じ処理を何度実行しても（べき等性）、スキーマが既に一致していれば何も変更されないことを期待する。

## Functional Requirements

### FR-01: Column Scheme の定義（Python側）
`gem` テーブルの期待スキーマを、pydanticモデルとして以下の内容で定義する。

| # | colId | label | Grist type | isFormula | formula |
|---|-------|-------|-----------|-----------|---------|
| 1 | FLAWED_GEM_NAME | FLAWED_GEM_NAME | Text | false | - |
| 2 | FLAWLESS_GEM_NAME | FLAWLESS_GEM_NAME | Text | false | - |
| 3 | BUY_ORDER | BUY_ORDER | Numeric | false | - |
| 4 | CRAFT_COST | CRAFT_COST | Numeric | true | `$BUY_ORDER * 80 * 80` |
| 5 | SELL_ORDER | SELL_ORDER | Numeric | false | - |
| 6 | ORDER_PROFIT | ORDER_PROFIT | Numeric | true | `$SELL_ORDER - $CRAFT_COST` |
| 7 | INSTA_SELL | INSTA_SELL | Numeric | false | - |
| 8 | INSTA_PROFIT | INSTA_PROFIT | Numeric | true | `$INSTA_SELL - $CRAFT_COST` |
| 9 | PLACEHOLDER | PLACEHOLDER | Any | false | - |
| 10 | FULL_COST | FULL_COST | Numeric | true | `$BUY_ORDER * 71000` |
| 11 | TOTAL_PROFIT | TOTAL_PROFIT | Numeric | true | `$ORDER_PROFIT * 71000 / 6400` |
| 12 | AVG_SELLING_PER_MINUTE | AVG_SELLING_PER_MINUTE | Numeric | false | - |
| 13 | PROFIT_PER_HOUR | PROFIT_PER_HOUR | Numeric | true | `$AVG_SELLING_PER_MINUTE * 60 * $ORDER_PROFIT` |

備考: 元の要求にあった列名 `71000_COST` はGristのcolId命名規則（識別子として数字始まり不可）に抵触するため、`FULL_COST` にリネームする（colId・labelとも `FULL_COST` に統一）。

### FR-02: 現在のスキーマ取得
Grist REST API `GET /api/docs/{docId}/tables/gem/columns` を呼び出し、レスポンスを pydantic モデル（列ごとの `colId` / `label` / `type` / `isFormula` / `formula`）としてパースする。

### FR-03: テーブル存在チェックと自動作成
対象ドキュメント内に `gem` テーブルが存在しない場合、`POST /api/docs/{docId}/tables` でテーブルを新規作成し、column scheme全列を初期カラムとして併せて作成する。

### FR-04: スキーマ差分検出
FR-01の期待スキーマと、FR-02で取得した現在のスキーマを比較し、以下を分類する。
- 追加が必要な列（期待スキーマにあるが現在存在しない）
- 削除対象の列（現在存在するが期待スキーマに定義されていない）
- 更新が必要な列（`colId` は一致するが `type` / `isFormula` / `formula` のいずれかが不一致）
- 一致している列（変更不要）

### FR-05: スキーマ反映（自動リコンサイル）
FR-04の差分結果に基づき、Grist REST APIを用いて以下を実行する。
- 追加対象列: `POST /api/docs/{docId}/tables/gem/columns`
- 更新対象列: `PATCH /api/docs/{docId}/tables/gem/columns`
- 削除対象列: `DELETE /api/docs/{docId}/tables/gem/columns/{colId}`（または対応するバルクDELETE API）

### FR-06: べき等性
差分が存在しない状態で本処理を再実行した場合、Grist APIへの変更系リクエスト（POST/PATCH/DELETE）は一切発行されないこと。

## Acceptance Criteria
- [x] AC-01: `gem` テーブルが存在しない場合、スキーマ定義の全13列を持つテーブルが新規作成される
- [x] AC-02: Grist側に期待スキーマにない列が存在する場合、その列は自動的にDELETEされる
- [x] AC-03: Grist側に期待スキーマの列が存在しない場合、その列は正しい `type` / `isFormula` / `formula` でPOSTされる
- [x] AC-04: 既存列の `type` またはformulaが期待値と異なる場合、PATCHにより期待値へ修正される
- [x] AC-05: 現在のスキーマが期待スキーマと完全一致している場合、Grist APIへの変更系リクエストは発生しない（べき等性）
- [x] AC-06: 期待スキーマはpydanticモデルとして定義され、Grist `/columns` レスポンスもpydanticモデルとしてパースされる
- [x] AC-07: Grist APIへの接続失敗（ネットワークエラー・認証エラー・HTTPエラー）時、原因を判別できる例外が発生する
- [x] AC-08: `71000_COST` は `FULL_COST`（colId・label共通）として定義・作成される

## Technical Scope

### Affected Modules
- `app/grist/` — Grist REST APIクライアントおよびスキーマ同期ロジックを実装する中心モジュール
- `app/config.py` — `gem` テーブル名を設定値として追加（既存の `grist_bz_table_name` / `grist_ah_table_name` と同様のパターン）

### New Components Required
- `app/grist/models.py`（仮）— pydanticモデル群
  - `GristColumnType`（Text / Numeric / Any などGristの型を表すEnum）
  - `ColumnDef`（`colId`, `label`, `type`, `isFormula`, `formula`）
  - `GEM_TABLE_SCHEMA`（FR-01の期待スキーマを保持する定数、`list[ColumnDef]`）
  - Grist `/columns` APIレスポンスのパース用モデル（`fields.type`, `fields.isFormula`, `fields.formula`, `fields.label` を含む）
- `app/grist/client.py`（仮）— Grist REST APIクライアント
  - カラム一覧取得、テーブル存在確認・作成、列の作成/更新/削除の各メソッド
  - 認証: `Authorization: Bearer {GRIST_API_KEY}` ヘッダー
- `app/grist/sync.py`（仮）— 差分検出（FR-04）とリコンサイル実行（FR-05）ロジック

### Integration Points
- Grist REST API（`{GRIST_URL}/api/docs/{GRIST_DOC_ID}/tables/gem/columns` 等）— 既存の `app/config.py` の `Settings`（`grist_url`, `grist_api_key`, `grist_doc_id`）を利用
- 既存の `check_grist()`（`app/main.py`）と同様のエラーハンドリング方針（`httpx.RequestError` / `httpx.HTTPStatusError` を捕捉し明確な例外を投げる）を踏襲する

## Non-Functional Requirements
- Performance: カラム数は最大13程度であり、性能要件は特になし
- Security: `GRIST_API_KEY` はログに出力しない。既存の `.env` 管理方式を継続する
- Scalability: 対象外（単一テーブル・小規模スキーマのため）
- Reliability: 差分検出および反映処理は、部分失敗時にどの列まで反映されたかが分かるよう、列単位の処理結果を記録する

## Out of Scope
- Hypixel Bazaar API（`https://api.hypixel.net/v2/skyblock/bazaar`）から実際の価格データを取得し、`BUY_ORDER` / `SELL_ORDER` / `INSTA_SELL` などのレコード値を更新する処理（別機能として今後実装）
- `gem` テーブルの行（レコード）データ自体の作成・編集（どの宝石を行として持つか、等）
- 列の並び順（表示順）をスキーマ定義と一致させる処理（型・formula・存在有無のみを対象とする）
- Grist以外のドキュメント／テーブル（`bazaar`, `auction`）に対するスキーマ同期

## Open Questions
- Grist REST APIのベースパスは `{GRIST_URL}/api/docs/...` を前提とするが、実際のGristサーバー構成（セルフホスト等）によりパスが異なる場合は実装時に調整が必要
- 列削除（DELETE）を単一列ごとに呼ぶか、複数列をまとめて削除できるバルクAPIを使うかは、実装時にGrist APIドキュメントを確認して決定する

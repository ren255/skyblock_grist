# Project: skyblock-flip

## Mission
Hypixel SkyblockのBazaar/Auction価格データをGristに同期し、フリップ（転売）の収益性を分析するための個人向けツール。

## Tech Stack
- Language: Python >=3.12
- Framework: なし（軽量スクリプト/ライブラリ構成、Webフレームワーク未使用）
- Build tool: uv (pyproject.toml + uv.lock, build-backend: hatchling)
- Database: なし（Gristをデータストアとして利用）
- ORM: なし（GristへはREST API経由でアクセス）
- Migrations: none
- Messaging: none
- Testing: pytest（`tests/grist/` 配下にユニットテストあり）
- Other: httpx（HTTP通信）, pydantic-settings（環境変数設定管理）, pydantic（スキーマ検証・データモデル）

## Architecture
機能ごとのモジュール分割構成。
- `app/grist/` — Grist REST APIとの連携（ドキュメント/テーブル/レコードのCRUD）
- `app/api/` — 外部API連携（Hypixel Skyblock Bazaar実装済み / Auctionは未実装）
- `app/gem_prices.py` — Bazaar価格をGrist gemテーブルへ反映するオーケストレーション（`app/api` と `app/grist` の唯一の接点）
- `app/utils/` — 共通ユーティリティ
- `app/config.py` — pydantic-settingsによる環境変数設定（`Settings`）
- `app/main.py` — エントリーポイント

## Conventions
- 設定値は `app/config.py` の `Settings`（pydantic-settings, `.env`から読込）に集約する
- Grist接続先・APIキー・ドキュメントID・テーブル名は環境変数管理（`.env.example`参照: `GRIST_URL`, `GRIST_API_KEY`, `GRIST_DOC_ID`, `GRIST_BZ_TABLE_NAME`, `GRIST_AH_TABLE_NAME`）
- HTTP通信は httpx を使用
- 外部API（Grist / Hypixel）から取得したデータのスキーマ検証・変換は、pydanticまたはpandasのうち適した方を用いる。同等に実現可能な場合はpandasを優先する
- 現時点でREST APIサーバーとしての公開エンドポイントは無し（バッチ/CLI的な同期処理）
- エラーハンドリングの共通機構（グローバル例外ハンドラ等）は未整備

## Approved Dependencies
- httpx
- pydantic-settings
- pydantic（データスキーマ検証用途）
- pandas（データ変換・差分検出用途、pydanticより適する場合は優先）
- pytest（テストランナー、dev依存）
- 追加ライブラリに関する制約は無し（必要に応じて追加可）

## Features
- **Gemテーブル カラムスキーマ自動同期**: Grist `gem` テーブルの列構成（列名・型・formula）をPython側で定義したcolumn schemeに自動的に一致させる（不足列の追加・不一致列の修正・余分な列の削除、テーブル自体が無ければ新規作成）(`docs/specs-archive/202608181748-gem-table-schema-sync/`)
- **Gemテーブル 行データ自動同期**: Grist `gem` テーブルの行（分析対象のGem一覧）をPython側で定義した行定義に自動的に一致させる（不足行の追加・`FLAWLESS_GEM_NAME` 不一致行の修正・定義外/重複/空キー行の削除）。価格列は行の同一性が保たれる限り保持される (`docs/specs-archive/202608181920-gem-table-row-sync/`)
- **Bazaar価格の取得とGem価格列への反映**: Hypixel Bazaar APIから相場を取得し、`gem` テーブルの価格列（`BUY_ORDER` / `SELL_ORDER` / `INSTA_SELL` / `AVG_SELLING_PER_MINUTE`）を更新する。Bazaarに無いGemや板が空のGemはスキップして継続し、値が変わらない行は書き込まない (`docs/specs-archive/202608182039-bazaar-price-sync/`)

## Architecture Decisions

| Date | Decision | Rationale | Feature |
|------|----------|-----------|---------|
| 2026-08-18 | Gristのカラムスキーマ管理は、期待スキーマとGrist `/columns` APIレスポンスの両方をpydanticモデルとして扱い、差分比較で同期する（pandasではなくpydanticを採用） | 対象は13列程度の固定スキーマの構造比較であり表形式データ処理ではないため、型安全な構造比較にpydanticが適する | [Gemテーブル カラムスキーマ自動同期](docs/specs-archive/202608181748-gem-table-schema-sync/) |
| 2026-08-18 | 外部API連携モジュールは `models.py`（スキーマ定義）/ `client.py`（API呼び出しのみ）/ `sync.py`（差分検出・反映ロジック）の一方向依存レイヤに分割する | HTTP通信なしで差分ロジックを単体テスト可能にするため。今後Grist/Hypixel等の外部API連携機能を追加する際もこのレイヤリングに従う想定 | [Gemテーブル カラムスキーマ自動同期](docs/specs-archive/202608181748-gem-table-schema-sync/) |
| 2026-08-18 | Grist REST APIの公開ドキュメント化されたエンドポイント（`/columns`）には列の並び順（表示位置）を指定する手段が無いため、列順の同期は対象外とする | OpenAPI定義（gristlabs/grist-help）を調査し確認した制約。並び順制御には`_grist_Views_section_field`（ビュー表示順）や内部メタデータテーブル`_grist_Tables_column`の直接操作が必要だが未検証・未実装 | [Gemテーブル カラムスキーマ自動同期](docs/specs-archive/202608181748-gem-table-schema-sync/) |
| 2026-08-18 | 行データも列スキーマと同様に宣言的に完全同期する（Python定義に無い行は削除する）。行の同一性は業務的な自然キー（`gem` テーブルでは `FLAWED_GEM_NAME`）で突き合わせる | 定義とデータストアの乖離を防ぎ、バッチの冪等性を担保するため。Grist側のrow idは安定だがPython側の定義から指定できないため、行の対応付けには自然キーが必須となる。重複キーは先頭を残し、キーが空/非文字列の行は定義に一致し得ないため削除する | [Gemテーブル 行データ自動同期](docs/specs-archive/202608181920-gem-table-row-sync/) |
| 2026-08-18 | Grist行の書き込みでは、クライアントから送る `fields` を非formula列に限定する（行モデルの `to_fields()` が管理対象列のみを返す構造で担保する） | formula列はGrist側で計算されるため、クライアントから値を送ると計算式を破壊するおそれがある。呼び出し側の注意ではなくシリアライズ側の構造で送信不能にすることで、将来の行書き込み機能でも事故を防ぐ | [Gemテーブル 行データ自動同期](docs/specs-archive/202608181920-gem-table-row-sync/) |
| 2026-08-18 | Grist Records APIの行削除は `POST /records/delete` に**裸のrow id配列**（`[101, 102]`）を送る。他のrecords操作（POST/PATCH）の `{"records": [...]}` ラッパー形状とは異なる | 公式OpenAPI定義（gristlabs/grist-help の `api/grist.yml`、`RowIds` スキーマ）で確認した仕様。形状が直感に反するため、今後Bazaar/Auction行の書き込みを実装する際も同じ落とし穴を踏まないよう記録する | [Gemテーブル 行データ自動同期](docs/specs-archive/202608181920-gem-table-row-sync/) |
| 2026-08-18 | Bazaar価格は板の最良気配（`buy_summary[0]` / `sell_summary[0]`）を用い、`quick_status` の `buyPrice` / `sellPrice`（上位注文の加重平均）は使わない。`buy_summary` は売り注文の板、`sell_summary` は買い注文の板である | APIの `buy`/`sell` は直感に反し、取り違えると全ての利益計算が壊れる。加重平均を用いると `CRAFT_COST` が売値を超えて破綻することで最良気配の解釈が一意に確定した。なお `CRAFT_COST < INSTA_SELL` は普遍的不変条件では**ない**（即時売却が赤字の市況が実在する）ため、誤マッピング検出には「板は交差しない」（実レスポンス全2124商品で違反ゼロ）を用いる | [Bazaar価格の取得とGem価格列への反映](docs/specs-archive/202608182039-bazaar-price-sync/) |
| 2026-08-18 | `app/api`（外部API）と `app/grist`（データストア）は相互に依存させない。両者を繋ぐのは `app/gem_prices.py` のみとし、この制約はソース走査によるテストで機械的に担保する | 外部APIとデータストアはそれぞれ独立した理由で変更されるため、直接結合させると片方の都合が他方へ波及する。今後Auction連携を追加する際も同じ形（`app/api` に取得層、専用モジュールで接続）に従う | [Bazaar価格の取得とGem価格列への反映](docs/specs-archive/202608182039-bazaar-price-sync/) |
| 2026-08-18 | Grist `REQUEST()` formula関数による外部データ取得は採用しない | 実装（grist-core `sandbox/grist/functions/info.py`）を確認したところ、リクエストは引数のハッシュをキーに一度しか実行されずURL固定では価格が凍結する。加えてGristはformulaをタイマー再計算しないため定期更新には外部トリガーが必須。`GRIST_ENABLE_REQUEST_FUNCTION` は既定無効で、公式READMEが「significant security risk」と明記している | [Bazaar価格の取得とGem価格列への反映](docs/specs-archive/202608182039-bazaar-price-sync/) |

## Environment & Configuration
| Key | Description | Required | Default |
|-----|-------------|----------|---------|
| GRIST_URL | Gristサーバーのベースurl | No | http://localhost:3000 |
| GRIST_API_KEY | Grist APIキー（`Authorization: Bearer`） | Yes | — |
| GRIST_DOC_ID | 対象のGristドキュメントID | Yes | — |
| GRIST_BZ_TABLE_NAME | Bazaarデータ用テーブル名 | No | bazaar |
| GRIST_AH_TABLE_NAME | Auctionデータ用テーブル名 | No | auction |
| GRIST_GEM_TABLE_NAME | Gemテーブル名（カラムスキーマ自動同期の対象） | No | gem |
| HYPIXEL_BAZAAR_URL | Hypixel Bazaar APIのURL（**APIキー不要**の公開エンドポイント。ミラー指定時のみ設定） | No | https://api.hypixel.net/v2/skyblock/bazaar |

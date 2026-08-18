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
- `app/api/` — 外部API連携（Hypixel Skyblock Bazaar/Auction APIなど）
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

## Architecture Decisions

| Date | Decision | Rationale | Feature |
|------|----------|-----------|---------|
| 2026-08-18 | Gristのカラムスキーマ管理は、期待スキーマとGrist `/columns` APIレスポンスの両方をpydanticモデルとして扱い、差分比較で同期する（pandasではなくpydanticを採用） | 対象は13列程度の固定スキーマの構造比較であり表形式データ処理ではないため、型安全な構造比較にpydanticが適する | [Gemテーブル カラムスキーマ自動同期](docs/specs-archive/202608181748-gem-table-schema-sync/) |
| 2026-08-18 | 外部API連携モジュールは `models.py`（スキーマ定義）/ `client.py`（API呼び出しのみ）/ `sync.py`（差分検出・反映ロジック）の一方向依存レイヤに分割する | HTTP通信なしで差分ロジックを単体テスト可能にするため。今後Grist/Hypixel等の外部API連携機能を追加する際もこのレイヤリングに従う想定 | [Gemテーブル カラムスキーマ自動同期](docs/specs-archive/202608181748-gem-table-schema-sync/) |
| 2026-08-18 | Grist REST APIの公開ドキュメント化されたエンドポイント（`/columns`）には列の並び順（表示位置）を指定する手段が無いため、列順の同期は対象外とする | OpenAPI定義（gristlabs/grist-help）を調査し確認した制約。並び順制御には`_grist_Views_section_field`（ビュー表示順）や内部メタデータテーブル`_grist_Tables_column`の直接操作が必要だが未検証・未実装 | [Gemテーブル カラムスキーマ自動同期](docs/specs-archive/202608181748-gem-table-schema-sync/) |

## Environment & Configuration
| Key | Description | Required | Default |
|-----|-------------|----------|---------|
| GRIST_URL | Gristサーバーのベースurl | No | http://localhost:3000 |
| GRIST_API_KEY | Grist APIキー（`Authorization: Bearer`） | Yes | — |
| GRIST_DOC_ID | 対象のGristドキュメントID | Yes | — |
| GRIST_BZ_TABLE_NAME | Bazaarデータ用テーブル名 | No | bazaar |
| GRIST_AH_TABLE_NAME | Auctionデータ用テーブル名 | No | auction |
| GRIST_GEM_TABLE_NAME | Gemテーブル名（カラムスキーマ自動同期の対象） | No | gem |

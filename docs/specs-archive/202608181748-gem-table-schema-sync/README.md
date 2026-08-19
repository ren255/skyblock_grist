# Gemテーブル カラムスキーマ自動同期

Implemented on: 2026-08-18

Grist上の `gem` テーブルのカラム構成（列名・型・formula）を、Python側で定義した単一のcolumn scheme（`app/grist/models.py` の `GEM_TABLE_SCHEME`）に自動的に一致させる機能。

## 主なファイル
- `app/grist/models.py` — `ColumnDef`, `GEM_TABLE_SCHEME`（13列定義）, Grist APIレスポンス用pydanticモデル
- `app/grist/client.py` — `GristClient`（Grist REST API: テーブル/カラムのGET/POST/PATCH/DELETE）
- `app/grist/sync.py` — `compute_diff` / `apply_diff` / `sync_gem_table_schema`（差分検出・反映）
- `app/main.py` — エントリーポイントから同期処理を呼び出し
- `tests/grist/` — 全23テスト

## 主な決定事項
- Grist REST APIのエンドポイント仕様は `gristlabs/grist-help` のOpenAPI定義を実際に取得して確認済み
- 元要求の列名 `71000_COST` はGristのcolId制約（数字始まり不可）のため `FULL_COST` にリネーム
- CRAFT_COST等6列はGrist側のformula列として定義し、Grist自身に計算させる（Pythonは生値のみ書き込み想定）
- スキーマ差分反映は「テーブル未存在→自動作成」「余分な列→自動削除」「型/formula不一致→自動PATCH」を全て自動実行（べき等性あり）
- 列の並び順（表示位置）の同期はGrist REST APIの制約により対象外（Out of Scope）としたまま実装完了

## 未対応・今後の課題
- Hypixel Bazaar APIから実際の価格データ（BUY_ORDER等）を取得してレコードを更新する処理は別機能として未実装
- formula文字列の完全一致比較によるべき等性は、実際のGrist環境での動作確認が必要（レビューでの指摘、コード修正では解決不可）

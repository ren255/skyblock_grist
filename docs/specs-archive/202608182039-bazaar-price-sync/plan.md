# Implementation Plan: Bazaar価格の取得とGem価格列への反映

## Overview

既存のGrist連携（`models.py` / `client.py` / ロジック層の一方向依存）と同じ構造を `app/api/` にも適用し、
両者を `app/gem_prices.py` で繋ぐ。`app/api` と `app/grist` は相互に依存させない。

```
app/api/models.py ──> app/api/client.py
        │
        └──────────> app/api/pricing.py  (純粋関数)
                              │
app/grist/models.py ──> app/grist/client.py
        │                     │
        └─────────────────────┴──> app/gem_prices.py ──> app/main.py
```

実装順序は依存の下流から上流へ。各ステップ後に `uv run pytest` を実行し失敗を持ち越さない。

**テストフィクスチャ方針**: 実APIレスポンス（3.6MB）はリポジトリに含めない。
実データから採取した2商品分の断片を手書きの最小フィクスチャとしてテスト内に置く。

---

## Step 1: Bazaarレスポンスモデル（`app/api/models.py` 新規）

**目的**: AC-04 の土台

`app/grist/models.py` と同じスタイル（`ConfigDict(extra="ignore")`、docstring付き）で定義する。

- `BazaarOrder`: `pricePerUnit: float` / `extra="ignore"`
  - `amount`・`orders` は本機能で未使用のため定義しない
- `BazaarQuickStatus`: `buyMovingWeek: float` / `extra="ignore"`
- `BazaarProduct`: `sell_summary: list[BazaarOrder]`, `buy_summary: list[BazaarOrder]`, `quick_status: BazaarQuickStatus` / `extra="ignore"`
- `BazaarResponse`: `success: bool`, `products: dict[str, BazaarProduct]` / `extra="ignore"`

> APIのフィールド名はcamelCase（`pricePerUnit`）とsnake_case（`sell_summary`）が混在している。
> Grist側の `GristColumnFields.isFormula` と同様、**APIの綴りをそのままフィールド名にする**（エイリアス変換をしない）。

### Checklist
- [x] 4モデルを追加
- [x] `uv run pytest` — 既存40件パス

---

## Step 2: Bazaarクライアント（`app/api/client.py` 新規）

**目的**: AC-01, AC-02, AC-03

`GristClient` と対称な設計にする。

```
class BazaarClient:
    def __init__(self, url: str, http_client: httpx.Client | None = None)
    def __enter__ / __exit__ / close
    def fetch_products(self) -> dict[str, BazaarProduct]
```

- **認証ヘッダを付けない**（bazaarエンドポイントはキー不要）。この理由をコメントで残す。
- `httpx.Client(timeout=30.0)` — レスポンスが約3.6MBあるためGristの10秒より長めにする。
- エラー正規化は `GristClient._request` と同じ方針:
  - `httpx.RequestError` → `RuntimeError(f"Failed to connect to Hypixel Bazaar: {url}")`
  - `httpx.HTTPStatusError` → `RuntimeError(f"Hypixel Bazaar returned HTTP {status}: {url}")`
- `success` が `false` → `RuntimeError("Hypixel Bazaar API returned success=false")`
- 戻り値は `BazaarResponse.products`（dict）とし、レスポンス全体を保持しない（NFR-03）。

### Checklist
- [x] `BazaarClient` を追加
- [x] 認証ヘッダを送らない
- [x] `success=false` で `RuntimeError`
- [x] `uv run pytest`

---

## Step 3: 価格算出の純粋関数（`app/api/pricing.py` 新規）

**目的**: AC-05, AC-06, AC-07, AC-08

### 3-1. 定数

```
MINUTES_PER_WEEK = 7 * 24 * 60   # 10080
PRICE_DECIMALS = 2
RATE_DECIMALS = 4
```

### 3-2. `GemPrices` モデル

`buy_order: float`, `sell_order: float`, `insta_sell: float`, `avg_selling_per_minute: float`

### 3-3. `compute_gem_prices(flawed, flawless) -> GemPrices | None`

**マッピングを取り違えないことが本機能の要**。各代入行に意味をコメントで併記する。

| 出力 | 入力 | 意味 |
|------|------|------|
| `buy_order` | `flawed.sell_summary[0].pricePerUnit` | 現在の最高買い注文 |
| `sell_order` | `flawless.buy_summary[0].pricePerUnit` | 現在の最安売り注文 |
| `insta_sell` | `flawless.sell_summary[0].pricePerUnit` | 即時売却価格 |
| `avg_selling_per_minute` | `flawless.quick_status.buyMovingWeek / 10080` | 売り捌ける速度 |

- 必要な板（`flawed.sell_summary` / `flawless.buy_summary` / `flawless.sell_summary`）のいずれかが空なら `None` を返す。
- 価格は `round(x, 2)`、分あたり数量は `round(x, 4)` で丸めてから返す（FR-06の差分安定化）。

> **注意**: `quick_status.buyPrice` / `sellPrice` は上位注文の加重平均であり最良気配ではない。
> 使わないこと。この禁止事項をdocstringに明記する。

### Checklist
- [x] 定数・`GemPrices`・`compute_gem_prices` を追加
- [x] 板が空のとき `None` を返す
- [x] docstringに加重平均を使わない旨を明記
- [x] `uv run pytest`

---

## Step 4: Grist側の価格書き込み口（`app/grist/models.py`, `app/grist/client.py`）

**目的**: AC-11, AC-12

### 4-1. 価格列の列ID定数（`models.py`）

`FLAWED_NAME_COL` の並びに追加する:

```
BUY_ORDER_COL = "BUY_ORDER"
SELL_ORDER_COL = "SELL_ORDER"
INSTA_SELL_COL = "INSTA_SELL"
AVG_SELLING_PER_MINUTE_COL = "AVG_SELLING_PER_MINUTE"
```

`GEM_TABLE_SCHEME` の該当 `ColumnDef` もこれらの定数を参照するよう書き換える（定義の単一化）。
**formula列は書き込み対象外なので定数化しない**（構造的に書き込めない状態を保つ）。

### 4-2. `update_record_fields`（`client.py`）

```
def update_record_fields(self, doc_id, table_id, updates: list[tuple[int, dict]]) -> None
```

- PATCH `/docs/{docId}/tables/{tableId}/records`、ボディ `{"records": [{"id": N, "fields": {...}}]}`
- 既存 `update_records`（名前2列専用）は変更しない。
- docstringに「呼び出し側が渡す `fields` に formula 列を含めてはならない」と明記する。

### Checklist
- [x] 価格列定数4件を追加し `GEM_TABLE_SCHEME` から参照
- [x] `update_record_fields` を追加
- [x] `uv run pytest` — 既存の列スキーマテストが定数化後もパス

---

## Step 5: オーケストレーション（`app/gem_prices.py` 新規）

**目的**: AC-09, AC-10, AC-14

この層のみが `app.api` と `app.grist` の両方を import する。

### 5-1. `build_price_fields(prices: GemPrices) -> dict`

`GemPrices` → Grist列名の辞書へ変換する小さな純粋関数。
**価格4列のみ**を返す（AC-11をこの関数で構造的に担保する）。

### 5-2. `compute_price_updates(records, products) -> list[tuple[int, dict]]`（純粋関数）

HTTP通信なし。単体テスト可能。

1. 各 `GristRecord` から `FLAWED_GEM_NAME` / `FLAWLESS_GEM_NAME` を読む。
   - どちらかが未設定/非文字列の行はスキップ（行同期側が削除対象とする行のため）。
2. `products` から2商品を引く。**片方でも欠けていればスキップし `logger.warning`**（AC-09）。
3. `compute_gem_prices` が `None` を返したらスキップし `logger.warning`（板が空）。
4. `build_price_fields` の結果を、現在の `record.fields` の同名キーと比較する。
   - 全て一致すれば更新対象に**含めない**（AC-10）。
   - 比較は丸め済みの値同士で行う。現在値が `None`（未入力）なら不一致として更新対象にする。
5. 更新対象の `(row_id, fields)` リストを返す。

### 5-3. `sync_gem_prices(grist_client, bazaar_client, doc_id, table_id) -> list[tuple[int, dict]]`

1. `bazaar_client.fetch_products()`
2. `grist_client.list_records(doc_id, table_id)`
3. `compute_price_updates(records, products)`
4. 更新が空なら `logger.info` して終了（**書き込みAPIを呼ばない**）
5. 非空なら `grist_client.update_record_fields(...)` を1回だけ呼ぶ（NFR-02）
6. 更新件数・スキップ件数を `logger.info` で出力（NFR-05）

### Checklist
- [x] `build_price_fields` が価格4列のみを返す
- [x] `compute_price_updates` を純粋関数として追加（欠損・空板・一致をすべて処理）
- [x] `sync_gem_prices` が更新0件のとき書き込まない
- [x] `app/api` と `app/grist` の相互importが無いことを確認
- [x] `uv run pytest`

---

## Step 6: 設定とエントリーポイント（`app/config.py`, `app/main.py`, `.env.example`）

**目的**: AC-13

### 6-1. `config.py`

```
hypixel_bazaar_url: str = "https://api.hypixel.net/v2/skyblock/bazaar"
```

APIキー用の設定は追加しない（不要）。

### 6-2. `.env.example`

`HYPIXEL_BAZAAR_URL` を追記し、「省略可・キー不要」である旨をコメントで示す。

### 6-3. `main.py`

`with GristClient(...)` ブロック内で、行同期の**後**に:

```
with BazaarClient(settings.hypixel_bazaar_url) as bazaar:
    sync_gem_prices(client, bazaar, settings.grist_doc_id, settings.grist_gem_table_name)
```

順序の理由（行が無ければ書き込む対象が無い）をコメントで残す。

### Checklist
- [x] `hypixel_bazaar_url` を追加
- [x] `.env.example` を更新
- [x] `main.py` で行同期の後に価格同期を呼ぶ
- [x] `uv run pytest`

---

## Step 7: テスト追加

**目的**: 全ACの検証 + AC-15

### 7-1. `tests/api/__init__.py`, `tests/api/test_client.py`（新規）

`tests/grist/test_client.py` の `_client(handler)` と同じMockTransport方式を使う。

- `test_fetch_products_parses_response`: GETされること、`BazaarProduct` にパースされること（**AC-01**）
- `test_fetch_products_sends_no_auth_header`: リクエストに `authorization` ヘッダが無い（**AC-01**）
- `test_unsuccessful_response_raises`: `{"success": false}` で `RuntimeError`（**AC-02**）
- `test_request_error_raises_runtime_error` / `test_http_status_error_raises_runtime_error`（**AC-03**）
- `test_unknown_fields_are_ignored`: `product_id` や `quick_status` の未使用キー、`buy_summary[].amount` を含めてもパース成功（**AC-04**）

### 7-2. `tests/api/test_pricing.py`（新規）

実データ由来の最小フィクスチャ（FLAWED_SAPPHIRE / FLAWLESS_SAPPHIRE の実測値）をヘルパで組む。

- `test_prices_are_taken_from_top_of_book`: 4値が期待どおりに割り当てられる（**AC-05**）
  - 特に `buy_order` が FLAWED の `sell_summary[0]`（376.6）であり、
    `buy_summary[0]`（876.9）や `quick_status.buyPrice`（1169.7）**ではない**ことを明示的にアサートする
- `test_avg_selling_per_minute_derived_from_flawless_buy_moving_week`（**AC-06**）
- `test_returns_none_when_order_book_empty`: 3種の空パターンをそれぞれ検証（**AC-07**）
- `test_order_book_is_not_crossed`: 実データ由来のフィクスチャで `sell_summary[0] <= buy_summary[0]`（**AC-08**）
- `test_insta_sell_does_not_exceed_sell_order`: `insta_sell <= sell_order`（スプレッドが正）（**AC-08**）
- `test_swapped_summaries_break_the_spread_invariant`: `buy_summary`/`sell_summary` を入れ替えた
  フィクスチャでスプレッド不変条件が破れることを確認し、テスト自体が誤マッピングを検出できることを示す（**AC-08**）
- `test_values_are_rounded`: 丸め桁数の確認

### 7-3. `tests/test_gem_prices.py`（新規）

`FakeGristClient` 相当を用意し、呼び出しを記録する。

- `test_updates_only_price_columns`: 送信fieldsのキー集合が価格4列と一致し、
  formula列・名前列を含まない（**AC-11**）
- `test_skips_gem_missing_from_bazaar`: 片方の商品が欠けている行はスキップされ、
  他の行の更新は継続、例外を送出しない（**AC-09**）
- `test_no_write_when_all_prices_match`: 現在値が一致していれば `update_record_fields` が呼ばれない（**AC-10**）
- `test_updates_when_current_value_missing`: 価格列が未入力（`None`）の行は更新対象になる
- `test_single_patch_for_multiple_rows`: 複数行の更新が1リクエストにまとまる（**NFR-02**）

### 7-4. `tests/grist/test_client.py` に追加

- `test_update_record_fields_sends_correct_body`: PATCH・パス・ボディ形状（**AC-12**）

### 7-5. `tests/grist/test_main.py` を更新

- 実行順序が `["sync_gem_table_schema", "sync_gem_table_records", "sync_gem_prices"]` になること（**AC-13**）
- `BazaarClient` もモンキーパッチしてネットワークアクセスを防ぐ

### 7-6. `tests/test_layering.py`（新規）

- `test_api_does_not_import_grist` / `test_grist_does_not_import_api`（**AC-14**）
  - `app/api/*.py` と `app/grist/*.py` のソースを読み、相手パッケージのimport文が無いことを確認する
  - importの有無をソース走査で見る（実行時のsys.modules依存だと他テストの影響を受けるため）

### Checklist
- [x] `tests/api/` パッケージを作成
- [x] `test_client.py` に6ケース
- [x] `test_pricing.py` に5ケース
- [x] `test_gem_prices.py` に5ケース
- [x] `test_client.py`(grist) に1ケース追加
- [x] `test_main.py` を更新
- [x] `test_layering.py` に2ケース
- [x] `uv run pytest` — **全テストパス**

---

## Step 8: 最終検証

- [x] `uv run pytest -v` で全テストパス
- [x] 全AC（AC-01〜AC-15）が対応するテストで検証されていることを確認
- [x] 新規依存なし（`pyproject.toml` / `uv.lock` 無変更、NFR-01）
- [x] `app/api` ⇄ `app/grist` の相互import無し（AC-14）
- [x] テストがネットワークへ出ていないことを確認（全てMockTransport / Fake）

---

## AC → Test Mapping

| AC | 検証内容 | テスト |
|----|---------|-------|
| AC-01 | GET・パース・認証ヘッダ無し | `tests/api/test_client.py::test_fetch_products_parses_response`, `::test_fetch_products_sends_no_auth_header` |
| AC-02 | `success=false` で例外 | `tests/api/test_client.py::test_unsuccessful_response_raises` |
| AC-03 | エラー正規化 | `tests/api/test_client.py::test_request_error_raises_runtime_error`, `::test_http_status_error_raises_runtime_error` |
| AC-04 | 未知フィールド無視 | `tests/api/test_client.py::test_unknown_fields_are_ignored` |
| AC-05 | 価格マッピングの取り違え防止 | `tests/api/test_pricing.py::test_prices_are_taken_from_top_of_book` |
| AC-06 | 分あたり売却速度 | `tests/api/test_pricing.py::test_avg_selling_per_minute_derived_from_flawless_buy_moving_week` |
| AC-07 | 板が空なら `None` | `tests/api/test_pricing.py::test_returns_none_when_order_book_empty` |
| AC-08 | 板構造の不変条件（取り違え検出） | `tests/api/test_pricing.py::test_order_book_is_not_crossed`, `::test_insta_sell_does_not_exceed_sell_order`, `::test_swapped_summaries_break_the_spread_invariant` |
| AC-09 | 欠損Gemのスキップ | `tests/test_gem_prices.py::test_skips_gem_missing_from_bazaar` |
| AC-10 | 一致時は書き込まない | `tests/test_gem_prices.py::test_no_write_when_all_prices_match` |
| AC-11 | 価格4列のみ書き込む | `tests/test_gem_prices.py::test_updates_only_price_columns` |
| AC-12 | PATCHボディ形状 | `tests/grist/test_client.py::test_update_record_fields_sends_correct_body` |
| AC-13 | 実行順序 | `tests/grist/test_main.py::test_sync_order` |
| AC-14 | レイヤ独立性 | `tests/test_layering.py::test_api_does_not_import_grist`, `::test_grist_does_not_import_api` |
| AC-15 | リグレッションなし | 既存40ケース |

## Risks / Notes

- **価格マッピングの取り違えが最大のリスク**。Bazaar APIの `buy`/`sell` は直感に反するため、
  AC-05（明示的な誤り値との比較）とAC-08（板構造の不変条件）の二重で守る。
- **`CRAFT_COST < INSTA_SELL` を不変条件として使わないこと**。実装中に実データで検証したところ
  AMETHYSTがこれを満たさず（即時売却が赤字という正当な市況）、当初の想定が誤りだと判明した。
  代わりに「板は交差しない」（全2124商品で違反ゼロを確認）を用いる。
- **`GEM_TABLE_SCHEME` の定数化**（Step 4-1）は既存テスト `test_gem_table_scheme_matches_spec` が
  列ID文字列を直接比較しているため、値が変わらなければパスする。値を変えないこと。
- **レスポンスサイズ3.6MB**: テストには実レスポンスを含めず最小フィクスチャを手書きする。
  タイムアウトはGrist(10s)より長い30sとする。
- **`quick_status.buyPrice` の誤用**が最も起きやすい間違い。pricing.pyのdocstringとテストの両方で封じる。
- **既存 `update_records` を壊さない**: 名前2列専用の既存メソッドは行同期が使用中。別メソッドとして追加する。

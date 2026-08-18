# Feature: Bazaar価格の取得とGem価格列への反映

## Summary

Hypixel Skyblock Bazaar API から Gem の価格データを取得し、Grist `gem` テーブルの価格列（`BUY_ORDER` / `SELL_ORDER` / `INSTA_SELL` / `AVG_SELLING_PER_MINUTE`）へ自動反映する。

これまで `gem` テーブルは列構成と行データが自動同期されていたが、価格列は手入力前提の空欄だった。本機能により、`main()` の実行だけで最新の相場に基づいたフリップ収益性（`ORDER_PROFIT` / `INSTA_PROFIT` / `PROFIT_PER_HOUR` 等のformula列）がGrist側で算出される状態になる。

### 価格マッピング（実データで整合性を検証済み）

Bazaar APIの `buy_summary` / `sell_summary` は板情報で、先頭要素が最良気配。

| Grist列 | 取得元 | 意味 |
|---------|--------|------|
| `BUY_ORDER` | **FLAWED** の `sell_summary[0].pricePerUnit` | 現在の最高買い注文＝買い注文を出すときの価格 |
| `SELL_ORDER` | **FLAWLESS** の `buy_summary[0].pricePerUnit` | 現在の最安売り注文＝売り注文を出すときの価格 |
| `INSTA_SELL` | **FLAWLESS** の `sell_summary[0].pricePerUnit` | 即時売却で得られる価格 |
| `AVG_SELLING_PER_MINUTE` | **FLAWLESS** の `quick_status.buyMovingWeek / 10080` | プレイヤーがFLAWLESSを買う速度＝売り捌ける速度の上限 |

`quick_status` の `buyPrice` / `sellPrice` は上位注文の加重平均であり、板の最良気配とは異なるため**使用しない**。

この対応付けは既存formula列との整合性で裏付けられている（FLAWED_SAPPHIRE実測値）:

```
BUY_ORDER = 376.6  →  CRAFT_COST = 376.6 × 6400 = 2,410,240
INSTA_SELL = 2,513,194  →  INSTA_PROFIT =   102,954
SELL_ORDER = 2,624,834  →  ORDER_PROFIT =   214,594   (INSTA_PROFIT < ORDER_PROFIT ✓)
```

加重平均（`buyPrice` = 1,169.7）を用いると `CRAFT_COST` が 5,612,160 となり売値251万を大きく超えて破綻するため、最良気配の解釈が一意に確定する。

> **注意**: `CRAFT_COST < INSTA_SELL` は普遍的な不変条件では**ない**。実測時点でAMETHYSTは
> `CRAFT_COST` 2,167,680 > `INSTA_SELL` 2,100,000 であり、即時売却が赤字という正当な市況だった
> （売り注文経由では `ORDER_PROFIT` +182,318 の黒字）。誤マッピングの検出にはAC-08の
> 板構造不変条件を用いること。

## User Stories

- **US-01**: 分析者として、`main()` を実行するだけで最新のBazaar相場が `gem` テーブルに入ってほしい。手入力の手間と転記ミスを無くすため。
- **US-02**: 分析者として、収益性（`ORDER_PROFIT` / `PROFIT_PER_HOUR`）が実勢価格に基づいて自動算出されてほしい。フリップ判断を即座に行うため。
- **US-03**: 開発者として、Bazaar側に存在しないGemがあっても処理全体が落ちないでほしい。ゲーム側のアイテム変更に耐えるため。
- **US-04**: 開発者として、価格の意味（買い注文か即時購入か）がコード上で明示されていてほしい。Bazaar APIの `buy`/`sell` は直感に反しやすく、取り違えると全ての利益計算が壊れるため。

## Functional Requirements

### FR-01: Bazaar APIクライアント
- `app/api/client.py` に `BazaarClient` を追加する。既存 `GristClient` と同じ設計とする（`httpx.Client` 注入可能、`_request()` 相当のエラー正規化、コンテキストマネージャ対応）。
- エンドポイントは `GET {bazaar_url}`（既定 `https://api.hypixel.net/v2/skyblock/bazaar`）。
- **APIキー不要**（v2のbazaarエンドポイントは認証なしで200を返すことを実測で確認済み）。認証ヘッダは送らない。
- レスポンスの `success` が `false` の場合は `RuntimeError` を送出する。
- 通信失敗・HTTPエラーは既存方針どおり `RuntimeError` に正規化する。

### FR-02: Bazaarレスポンスのスキーマ検証
- `app/api/models.py` にpydanticモデルを定義する。
  - `BazaarOrder`: `pricePerUnit: float`（`amount` / `orders` は本機能で未使用のため `extra="ignore"` で無視）
  - `BazaarQuickStatus`: `buyMovingWeek: float`
  - `BazaarProduct`: `sell_summary: list[BazaarOrder]`, `buy_summary: list[BazaarOrder]`, `quick_status: BazaarQuickStatus`
  - `BazaarResponse`: `success: bool`, `products: dict[str, BazaarProduct]`
- レスポンスは2000商品超・約3.6MBあるため、未使用フィールドは `extra="ignore"` で捨てる。

### FR-03: 価格算出（純粋関数）
- `app/api/pricing.py` に、Bazaar商品から価格を算出する純粋関数を置く（HTTP通信を含まない＝単体テスト可能）。
- `GemPrices` モデル: `buy_order`, `sell_order`, `insta_sell`, `avg_selling_per_minute`。
- `compute_gem_prices(flawed: BazaarProduct, flawless: BazaarProduct) -> GemPrices | None`
  - 上記マッピング表のとおりに算出する。
  - `AVG_SELLING_PER_MINUTE` は `buyMovingWeek / 10080`（7日×24時間×60分）で分あたりに換算する。
  - 必要な板が空（`sell_summary` または `buy_summary` が空配列）の場合は価格を確定できないため `None` を返す。

### FR-04: Grist価格列の更新
- `app/grist/client.py` に、任意のフィールド辞書で行を更新する `update_record_fields(doc_id, table_id, updates: list[tuple[int, dict]])` を追加する。
  - 既存の `update_records`（名前2列専用）はそのまま残す。価格更新は書き込む列が異なるため別メソッドとする。
- **formula列（`CRAFT_COST` / `ORDER_PROFIT` 等）には一切書き込まない。** 書き込む列は上記4列のみ。
- 価格列の列ID定数を `app/grist/models.py` に追加する（`FLAWED_NAME_COL` と同じ方針で文字列リテラルの散在を防ぐ）。

### FR-05: 価格同期のオーケストレーション
- `app/gem_prices.py`（新規）に、Bazaar取得〜Grist反映を繋ぐ処理を置く。
  - この層のみが `app/api` と `app/grist` の両方に依存する。**`app/api` と `app/grist` は相互に依存させない。**
- 処理内容:
  1. Grist `gem` テーブルの行を取得（`FLAWED_GEM_NAME` / `FLAWLESS_GEM_NAME` / 現在の価格列を含む）。
  2. 各行について、Bazaarから対応する2商品を引き当てて `compute_gem_prices` で価格を算出。
  3. 現在値と異なる行のみ更新対象とし、1リクエストでまとめてPATCHする。
- 商品がBazaarに存在しない、または板が空で価格を算出できない行は**スキップし、既存値を保持する**（`logger.warning` を出力）。処理全体は継続する。

### FR-06: 差分更新（冪等性）
- 算出値が現在のGrist値と一致する行は更新対象に含めない。
- 全行が一致する場合、書き込みAPIを一度も呼ばない。
- 浮動小数の比較ノイズを避けるため、算出値は書き込み前に一定桁で丸める（価格は小数2桁、分あたり数量は小数4桁）。

### FR-07: エントリーポイント統合
- `app/main.py` で、カラムスキーマ同期・行データ同期の**後**に価格同期を実行する。
  - 行が存在しない状態では価格を書き込む対象が無いため、この順序は必須。

### FR-08: 設定
- Bazaar APIのURLを環境変数 `HYPIXEL_BAZAAR_URL` で上書き可能にする（既定値あり＝必須ではない）。
- APIキー用の環境変数は追加しない（不要なため）。

## Acceptance Criteria

- [x] **AC-01**: `BazaarClient` が既定URLへGETし、レスポンスを `BazaarResponse` としてパースする（MockTransportで検証）。認証ヘッダを送らないこと。
- [x] **AC-02**: レスポンスの `success` が `false` の場合、`RuntimeError` を送出する。
- [x] **AC-03**: 通信エラー・HTTPステータスエラーが `RuntimeError` に正規化される。
- [x] **AC-04**: `BazaarProduct` が未知フィールド（`product_id` や `quick_status` 内の未使用キー等）を含むレスポンスをエラーなくパースする。
- [x] **AC-05**: `compute_gem_prices` が、FLAWEDの `sell_summary[0]` を `buy_order`、FLAWLESSの `buy_summary[0]` を `sell_order`、FLAWLESSの `sell_summary[0]` を `insta_sell` に割り当てる（取り違えていないこと）。
- [x] **AC-06**: `compute_gem_prices` が `avg_selling_per_minute` を FLAWLESS の `buyMovingWeek / 10080` として算出する。
- [x] **AC-07**: 板が空（`sell_summary` または `buy_summary` が `[]`）の場合、`compute_gem_prices` が `None` を返す。
- [x] **AC-08**: 板の構造不変条件が成立する（`buy_summary` と `sell_summary` の取り違え検出）。
  - 同一商品において `sell_summary[0] ≤ buy_summary[0]`（板は交差しない）。実レスポンス全2124商品で違反ゼロを確認済み。
  - `compute_gem_prices` の出力が `insta_sell ≤ sell_order`（スプレッドが正）を満たす。
- [x] **AC-09**: Bazaarに存在しないGemの行はスキップされ、例外を送出せず他の行の更新が継続する。
- [x] **AC-10**: 算出値が現在のGrist値と一致する行は更新対象に含まれず、全行一致なら書き込みAPIが一度も呼ばれない。
- [x] **AC-11**: 更新ペイロードに含まれる列が価格4列のみであり、formula列（`CRAFT_COST` 等）と名前列を含まない。
- [x] **AC-12**: `update_record_fields` が PATCH `/docs/{docId}/tables/{tableId}/records` に `{"records": [{"id": N, "fields": {...}}]}` を送信する。
- [x] **AC-13**: 価格同期はカラムスキーマ同期・行データ同期の後に実行される。
- [x] **AC-14**: `app/api` が `app/grist` を、`app/grist` が `app/api` をインポートしていない（レイヤ独立性）。
- [x] **AC-15**: 既存40テストが引き続き全てパスする（リグレッションなし）。

## Technical Scope

| ファイル | 変更内容 |
|---------|---------|
| `app/api/models.py` | 新規。Bazaarレスポンスのpydanticモデル |
| `app/api/client.py` | 新規。`BazaarClient` |
| `app/api/pricing.py` | 新規。`GemPrices` と `compute_gem_prices`（純粋関数） |
| `app/gem_prices.py` | 新規。Bazaar〜Gristのオーケストレーション |
| `app/grist/models.py` | 価格列の列ID定数を追加 |
| `app/grist/client.py` | `update_record_fields` を追加 |
| `app/config.py` | `hypixel_bazaar_url` を追加 |
| `app/main.py` | 価格同期の呼び出しを追加 |
| `.env.example` | `HYPIXEL_BAZAAR_URL` を追記 |
| `tests/api/test_client.py` | 新規 |
| `tests/api/test_pricing.py` | 新規 |
| `tests/test_gem_prices.py` | 新規 |
| `tests/grist/test_client.py` | `update_record_fields` の検証を追加 |
| `tests/grist/test_main.py` | 実行順序の検証を更新 |

**アーキテクチャ方針**
- 既存の決定どおり `models.py`（スキーマ）/ `client.py`（API呼び出しのみ）/ ロジック層 の一方向依存を維持する。
- `app/api` と `app/grist` は相互に依存させず、`app/gem_prices.py` のみが両者を繋ぐ。
- 価格算出はHTTP通信から分離した純粋関数とし、実レスポンス断片を用いた単体テストで検証する。

## Non-Functional Requirements

- **NFR-01**: 新規依存ライブラリを追加しない（httpx / pydantic のみ）。
- **NFR-02**: Bazaar APIの呼び出しは同期1回あたり1リクエストのみ（Gem毎に呼ばない）。Grist更新も1 PATCHにまとめる。
- **NFR-03**: レスポンスが約3.6MBあるため、パース後は必要な商品のみ参照し全商品を保持し続けない。
- **NFR-04**: 型アノテーションを既存コードと同水準で付与する。
- **NFR-05**: スキップ・更新件数は `logging` で観測可能にする。

## Out of Scope

- 常駐プロセスによる定期ポーリング（単発実行とし、定期実行はcron等の外部に委ねる — ユーザー確認済み）。
- Grist `REQUEST()` formula関数による取得 — 調査の結果、同一引数はキャッシュされ再取得されず価格が凍結すること、`GRIST_ENABLE_REQUEST_FUNCTION` が既定無効かつベンダーが「significant security risk」と明記していることから不採用（ユーザー確認済み）。
- Auction House（`GRIST_AH_TABLE_NAME`）データの取得。
- 価格履歴の蓄積・時系列分析（現在値の上書きのみ）。
- 注文列の先頭に立つためのオフセット（±0.1）付与 — 最良気配をそのまま用いる（ユーザー確認済み）。
- Bazaar手数料・税の考慮。

## Open Questions

なし（価格マッピング・売却速度の基準・実行モデル・formula取得の可否はすべてユーザー確認済み）。

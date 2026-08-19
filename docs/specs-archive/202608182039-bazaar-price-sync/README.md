# Bazaar価格の取得とGem価格列への反映

Implemented on: 2026-08-18

## 概要

Hypixel Skyblock Bazaar API から相場を取得し、Grist `gem` テーブルの価格列を更新する機能。
これ以前は列構成と行データのみが自動同期されており、価格列は手入力前提の空欄だった。
本機能により `main()` の実行だけで収益性のformula列（`ORDER_PROFIT` / `PROFIT_PER_HOUR` 等）が実勢価格で算出される。

**Hypixel APIキーは不要**（v2の `/skyblock/bazaar` は認証なしで200を返すことを実測で確認）。

## 価格マッピング（本機能の核心）

Bazaar APIの `buy` / `sell` は直感に反する。`buy_summary` は**売り注文の板**（買うときに払う値、昇順）、
`sell_summary` は**買い注文の板**（売るときに得る値、降順）である。

| Grist列 | 取得元 |
|---------|--------|
| `BUY_ORDER` | FLAWED の `sell_summary[0].pricePerUnit`（現在の最高買い注文） |
| `SELL_ORDER` | FLAWLESS の `buy_summary[0].pricePerUnit`（現在の最安売り注文） |
| `INSTA_SELL` | FLAWLESS の `sell_summary[0].pricePerUnit`（即時売却価格） |
| `AVG_SELLING_PER_MINUTE` | FLAWLESS の `quick_status.buyMovingWeek / 10080` |

`quick_status.buyPrice` / `sellPrice` は**上位注文の加重平均**であり最良気配ではない。使用禁止。

## 主要ファイル

| ファイル | 役割 |
|---------|------|
| `app/api/models.py` | Bazaarレスポンスのpydanticモデル |
| `app/api/client.py` | `BazaarClient`。`fetch_products(product_ids)` で対象商品に絞ってから検証する |
| `app/api/pricing.py` | `GemPrices` と純粋関数 `compute_gem_prices` |
| `app/gem_prices.py` | オーケストレーション。`app/api` と `app/grist` の唯一の接点 |
| `app/grist/client.py` | `update_record_fields`（任意フィールドのPATCH）を追加 |
| `tests/test_layering.py` | `app/api` ⇄ `app/grist` の相互非依存をAST走査で検証 |

## 注目すべき決定事項

- **価格マッピングの二重防御**: 取り違えが最大のリスクのため、(1) 誤り候補値（`buy_summary[0]`=876.9、
  `quick_status.buyPrice`=1169.7）との非等価アサート、(2) 板構造の不変条件、の2層で守る。
  さらに「板を入れ替えると不変条件が破れる」テストを置き、回帰テストに実効性があることを保証している。
- **`CRAFT_COST < INSTA_SELL` は不変条件ではない**: 実装中に実データで検算し、AMETHYSTが
  `CRAFT_COST` 2,167,680 > `INSTA_SELL` 2,100,000（即時売却が赤字という正当な市況）となることを発見。
  当初の仕様はSAPPHIRE 1件からの誤った一般化だったため、仕様側を修正した。
  代わりに「板は交差しない」（実レスポンス全2124商品で違反ゼロ）を採用している。
- **レイヤ独立性の機械的担保**: `app/api` と `app/grist` の相互非依存を、`sys.modules` ではなく
  ASTによるソース走査でテストしている（テスト実行順に左右されないため）。
- **`REQUEST()` formula関数の不採用**: Grist内で取得できないか調査したが、grist-coreの実装上
  同一引数のリクエストは一度しか実行されず価格が凍結すること、既定無効かつ公式が
  「significant security risk」と明記していることから見送った。

## パフォーマンス

レスポンスは2124商品・約3.6MB。全件を検証すると **32.03 MB / 184 ms** を要するため、
行から必要な商品IDを集めて `model_validate` の前に絞り込む設計とした。

| | 商品数 | 時間 | メモリ |
|---|---|---|---|
| 絞り込みなし | 2124 | 184 ms | 32.03 MB |
| **絞り込みあり** | **12** | **28 ms** | **0.27 MB** |

## テスト

全75テストパス（本機能で35ケース追加、既存40ケースは継続パス）。
15件のACすべてが対応するテストで検証されている。
テストはすべてMockTransport / Fakeを経由し、ネットワークへ出ない。

実装コードが実エンドポイントに対して動作することは、Grist書き込みを伴わない
読み取り専用スモークテストで別途確認済み。

## レビュー結果

Verdict: 🟡 **Merge after minor fixes** — Critical / Major の指摘なし。
指摘された Minor 2件（NFR-03未達のメモリ消費、Bazaar取得の順序）は**レビュー後に修正済み**。

未対応の Info 3件（`review.md` にチェックボックス付きで記載）:

- 🔵 `response.json()` のデコード失敗と `ValidationError` が `RuntimeError` に正規化されない（既存 `GristClient` と同挙動のため許容）
- 🔵 スキップ件数の集計サマリが無い（個別warningのみ）
- 🔵 `update_record_fields` は任意fieldsを受けるため、将来の呼び出し側がformula列を渡す余地が構造的には残る

## 既知の注意点

- Bazaarに存在しないGem・板が空のGemはスキップされ、**既存の価格値がそのまま残る**（古い値が残りうる）。
  スキップは `logger.warning` に出力される。
- 定期実行は本機能の範囲外。単発実行のためcron等の外部スケジューラに委ねる。

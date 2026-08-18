# Code Review: Bazaar価格の取得とGem価格列への反映

## Summary

本機能の最大のリスクであるBazaar APIの `buy`/`sell` 取り違えに対し、設計・実装・テストの3層で正面から対処できている。特に「板は交差しない」という市場構造の不変条件を採用し、さらに**板を入れ替えると不変条件が破れることを示すテスト**（`test_swapped_summaries_break_the_spread_invariant`）を置いたことで、回帰テストが実際に誤りを検出できる保証がある。既存のレイヤリング規約も守られ、`app/api` ⇄ `app/grist` の独立性はソース走査で機械的に検証されている。

実装中に実データで検算し、当初の仕様（`CRAFT_COST < INSTA_SELL` を普遍的不変条件とする）が誤りであることを発見して仕様側を修正した判断は妥当。

Critical / Major な問題は無い。指摘した Minor 2件（NFR-03 未達によるメモリ消費、Bazaar取得の順序）は**レビュー後に修正済み**で、実測で 32.03 MB / 184 ms → 0.27 MB / 28 ms に改善した。残る Info 3件はマージを妨げない。

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
| [x] | `app/api/models.py:47` | NFR違反 / メモリ | `BazaarResponse.products` が全2124商品（板61,833段）を検証・保持し、実測で32MB・190msを消費する。必要なのは12商品のみで、NFR-03「必要な商品のみ参照し全商品を保持し続けない」を満たしていない | `fetch_products(product_ids: set[str] \| None = None)` として、`model_validate` の前に生のdictを対象IDで絞り込む |
| [x] | `app/gem_prices.py:97` | 効率 | Bazaar取得（3.6MB）をGrist行の取得より先に行うため、必要な商品IDが分かる前に全件を取りに行っている。Grist側が失敗する場合も3.6MBを無駄にダウンロードする | `list_records` を先に呼び、行から得た商品IDを上記 `fetch_products` に渡す。上のMinorと同時に解消できる |

**修正済み（実測）**: `32.03 MB / 184 ms` → `0.27 MB / 28 ms`（メモリ118分の1、時間6.5倍速）。
併せて行が0件ならBazaarを取得しないショートサーキットを追加し、実エンドポイントでも
指定した4商品のみが返ることを確認した。テスト5件を追加（全75 passed）。

### 🔵 Info / Suggestions

| Done | Location | Category | Problem | Suggestion |
|------|----------|----------|---------|------------|
| [x] | `tests/api/test_pricing.py:74` | Test Clarity | `test_order_book_is_not_crossed` のdocstringは「全2124商品で検証済み」と述べるが、テスト自体は自作フィクスチャ2件しか見ておらず、読み手が検証範囲を過大に受け取りうる | docstringを「設計時に実レスポンス全2124商品で確認した不変条件をフィクスチャで固定する」と実態に合わせる（修正済み） |
| [ ] | `app/api/client.py:44` | Error Handling | `response.json()` のデコード失敗と `model_validate` の `ValidationError` は `RuntimeError` に正規化されず素通しになる（HTTP/接続エラーのみ変換） | 既存 `GristClient` と同じ挙動のため許容。API側の仕様変更を早期に検知したい場合は変換を検討 |
| [ ] | `app/gem_prices.py:105` | Observability | 更新件数はログに出るが、スキップ件数の集計は出ない（個別warningのみ）。NFR-05は満たすが、6行程度を超えた際に全体像が掴みにくい | 完了時に `updated=N skipped=M` のサマリを1行出す |
| [ ] | `app/grist/client.py:99` | API Safety | `update_record_fields` は任意の `fields` を受け取るため、将来の呼び出し側がformula列を渡す余地が構造的には残る（現状は `build_price_fields` が4列に限定して担保） | docstringでの禁止に加え、必要になった時点で許可列のホワイトリスト検証を追加 |

## Acceptance Criteria Coverage

| AC | Test | Status |
|----|------|--------|
| AC-01: GET・パース・認証ヘッダ無し | `tests/api/test_client.py::test_fetch_products_parses_response`, `::test_fetch_products_sends_no_auth_header` | ✅ Covered |
| AC-02: `success=false` で例外 | `tests/api/test_client.py::test_unsuccessful_response_raises` | ✅ Covered |
| AC-03: エラー正規化 | `tests/api/test_client.py::test_request_error_raises_runtime_error`, `::test_http_status_error_raises_runtime_error` | ✅ Covered |
| AC-04: 未知フィールド無視 | `tests/api/test_client.py::test_unknown_fields_are_ignored` | ✅ Covered |
| AC-05: 価格マッピング | `tests/api/test_pricing.py::test_prices_are_taken_from_top_of_book` | ✅ Covered |
| AC-06: 分あたり売却速度 | `tests/api/test_pricing.py::test_avg_selling_per_minute_derived_from_flawless_buy_moving_week` | ✅ Covered |
| AC-07: 板が空なら `None` | `tests/api/test_pricing.py::test_returns_none_when_order_book_empty`（3パターン） | ✅ Covered |
| AC-08: 板構造の不変条件 | `tests/api/test_pricing.py::test_order_book_is_not_crossed`, `::test_insta_sell_does_not_exceed_sell_order`, `::test_swapped_summaries_break_the_spread_invariant` | ✅ Covered |
| AC-09: 欠損Gemのスキップ | `tests/test_gem_prices.py::test_skips_gem_missing_from_bazaar`, `::test_skips_row_when_only_flawless_is_missing` | ✅ Covered |
| AC-10: 一致時は書き込まない | `tests/test_gem_prices.py::test_no_write_when_all_prices_match` | ✅ Covered |
| AC-11: 価格4列のみ書き込む | `tests/test_gem_prices.py::test_updates_only_price_columns`, `::test_build_price_fields_returns_only_price_columns` | ✅ Covered |
| AC-12: PATCHボディ形状 | `tests/grist/test_client.py::test_update_record_fields_sends_correct_body` | ✅ Covered |
| AC-13: 実行順序 | `tests/grist/test_main.py::test_sync_order` | ✅ Covered |
| AC-14: レイヤ独立性 | `tests/test_layering.py::test_api_does_not_import_grist`, `::test_grist_does_not_import_api` | ✅ Covered |
| AC-15: リグレッションなし | 既存40ケース継続パス（全68 passed） | ✅ Covered |

### 検証メモ

- **AC-08 のテストには実効性がある**。`test_swapped_summaries_break_the_spread_invariant` が
  「板を入れ替えると不変条件が破れる」ことを明示的に固定しているため、この不変条件が
  誤マッピングを検出できることが担保されている。単に不変条件を主張するだけのテストより強い。
- **AC-05 は誤り候補値との非等価も検証している**（`buy_summary[0]`=876.9、`quick_status.buyPrice`=1169.7）。
  最も起きやすい2種類の取り違えを名指しで封じている。
- **AC-14 はソース走査（`ast`）で判定**しており、`sys.modules` のようなテスト実行順に左右される
  手法を避けている点が適切。
- 実エンドポイントに対する読み取り専用のスモークテストで、実装コードが2124商品を取得し
  価格算出まで通ることを確認済み（Gristへの書き込みなし）。

## Dimension Notes

| 観点 | 評価 |
|------|------|
| 言語・イディオム | ✅ 型注釈完備、`isinstance` ガード、デバッグ出力なし、pydanticの使い方が既存と一貫 |
| レイヤリング | ✅ `app/api` ⇄ `app/grist` の独立性をテストで機械的に担保。`gem_prices.py` のみが両者を繋ぐ |
| セキュリティ | ✅ Bazaarは認証不要でキーを送らない。URLは設定由来でリクエスト由来ではないためSSRF余地なし。秘匿情報のログ出力なし |
| 依存関係 | ✅ 新規依存なし（`pyproject.toml` / `uv.lock` 無変更、NFR-01充足） |
| パフォーマンス | ✅ API呼び出し・PATCHは各1回でNFR-02充足。NFR-03も修正後に充足（0.27MB / 28ms） |
| 重複コード | ✅ プロダクション・テストとも重複なし。`update_records` と `update_record_fields` は用途が異なり分離が妥当 |
| テスト品質 | ✅ AAA構造、命名が明確、parametrize活用、モックは境界のみ、ネットワークアクセスなし |
| 可観測性 | ✅ スキップは `warning`、更新は `info`。理由がメッセージに含まれる |

## Verdict

- [ ] ✅ Ready to merge
- [x] 🟡 Merge after minor fixes (no re-review needed)
- [ ] 🟠 Requires fixes and re-review
- [ ] 🔴 Do not merge — significant issues found

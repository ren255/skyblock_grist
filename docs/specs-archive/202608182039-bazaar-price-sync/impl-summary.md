## Implementation Complete

### Files Created
- `app/api/models.py` — Bazaarレスポンスのpydanticモデル（`BazaarOrder` / `BazaarQuickStatus` / `BazaarProduct` / `BazaarResponse`）
- `app/api/client.py` — `BazaarClient`（認証ヘッダなし、timeout 30s、`success=false` を `RuntimeError` に正規化）
- `app/api/pricing.py` — `GemPrices` と純粋関数 `compute_gem_prices`
- `app/gem_prices.py` — Bazaar〜Gristのオーケストレーション（`app.api` と `app.grist` の唯一の接点）
- `tests/api/__init__.py`, `tests/api/test_client.py`, `tests/api/test_pricing.py`
- `tests/test_gem_prices.py`, `tests/test_layering.py`

### Files Modified
- `app/grist/models.py` — 価格列の列ID定数4件を追加し `GEM_TABLE_SCHEME` から参照
- `app/grist/client.py` — `update_record_fields`（任意フィールドのPATCH）を追加
- `app/config.py` — `hypixel_bazaar_url` を追加
- `app/main.py` — 行同期の後に価格同期を実行
- `.env.example` — `HYPIXEL_BAZAAR_URL` を追記
- `tests/grist/test_client.py` — `update_record_fields` の検証を追加
- `tests/grist/test_main.py` — 実行順序を3段階に更新、`BazaarClient` もモンキーパッチ

### Acceptance Criteria
- [x] AC-01: Passed — `tests/api/test_client.py::test_fetch_products_parses_response`, `::test_fetch_products_sends_no_auth_header`
- [x] AC-02: Passed — `tests/api/test_client.py::test_unsuccessful_response_raises`
- [x] AC-03: Passed — `tests/api/test_client.py::test_request_error_raises_runtime_error`, `::test_http_status_error_raises_runtime_error`
- [x] AC-04: Passed — `tests/api/test_client.py::test_unknown_fields_are_ignored`
- [x] AC-05: Passed — `tests/api/test_pricing.py::test_prices_are_taken_from_top_of_book`
- [x] AC-06: Passed — `tests/api/test_pricing.py::test_avg_selling_per_minute_derived_from_flawless_buy_moving_week`
- [x] AC-07: Passed — `tests/api/test_pricing.py::test_returns_none_when_order_book_empty`（3パターンparametrize）
- [x] AC-08: Passed — `tests/api/test_pricing.py::test_order_book_is_not_crossed`, `::test_insta_sell_does_not_exceed_sell_order`, `::test_swapped_summaries_break_the_spread_invariant`
- [x] AC-09: Passed — `tests/test_gem_prices.py::test_skips_gem_missing_from_bazaar`, `::test_skips_row_when_only_flawless_is_missing`
- [x] AC-10: Passed — `tests/test_gem_prices.py::test_no_write_when_all_prices_match`
- [x] AC-11: Passed — `tests/test_gem_prices.py::test_updates_only_price_columns`, `::test_build_price_fields_returns_only_price_columns`
- [x] AC-12: Passed — `tests/grist/test_client.py::test_update_record_fields_sends_correct_body`
- [x] AC-13: Passed — `tests/grist/test_main.py::test_sync_order`
- [x] AC-14: Passed — `tests/test_layering.py::test_api_does_not_import_grist`, `::test_grist_does_not_import_api`
- [x] AC-15: Passed — 既存40ケースが全て継続パス（全68 passed）

### Notes
- **仕様を実装中に1件修正した**: 当初のAC-08「`BUY_ORDER × 6400 < INSTA_SELL` が常に成立」は誤りだった。
  実レスポンスで検算したところAMETHYSTが `CRAFT_COST` 2,167,680 > `INSTA_SELL` 2,100,000 となり、
  即時売却が赤字という正当な市況を「マッピング誤り」と誤判定してしまう。SAPPHIRE 1件だけを見た誤った一般化だった。
  代わりに板構造の不変条件（同一商品で `sell_summary[0] ≤ buy_summary[0]`、実レスポンス全2124商品で違反ゼロ）と
  スプレッド正（`insta_sell ≤ sell_order`）を採用し、`feature.md` / `plan.md` の両方を修正した。
  さらに「板を入れ替えると不変条件が破れる」テストを足し、テスト自体が誤マッピングを検出できることを示している。
- **Hypixel APIキーは不要**。v2の `/skyblock/bazaar` は認証なしで200を返すことを実測で確認済みのため、
  APIキー用の環境変数は追加していない。`test_fetch_products_sends_no_auth_header` で認証ヘッダを送らないことを固定。
- **実エンドポイントに対する読み取り専用スモークテストを実施**（Gristへの書き込みなし）。
  実装した `BazaarClient` で2124商品を取得し、JADEの価格算出とスプレッド不変条件の成立を確認した。
  取得時刻により値が変動していること（`buy_order` 385.4 → 386.5）も確認でき、ライブデータであることを裏付けた。
- **`GEM_TABLE_SCHEME` の価格列を定数参照に変更**したが、値は変えていないため既存の
  `test_gem_table_scheme_matches_spec`（列ID文字列を直接比較）はそのままパスしている。
- 新規依存の追加なし（`pyproject.toml` / `uv.lock` 無変更、NFR-01充足）。
- テストは全てMockTransport / Fakeを経由しネットワークへ出ない（スモークテストのみ手動実行）。
- **レビュー後に Minor 2件を修正**: `fetch_products(product_ids)` で `model_validate` 前に対象商品へ絞り込み、
  `sync_gem_prices` は行取得を先に行って必要な商品IDを渡すよう順序を入れ替えた（行0件ならBazaarを叩かない）。
  実測で **32.03 MB / 184 ms → 0.27 MB / 28 ms**（メモリ118分の1）となりNFR-03を充足。テスト5件追加で全75 passed。

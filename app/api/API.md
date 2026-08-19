# API 要件

## 方針

公式 API および NEU REPO のデータを取得し、取得したデータを pandas に格納する。API の値に対する独自の補正・推測・正規化は行わない。

## Bazaar

Hypixel の公式 Bazaar API を使用する。

```text
GET https://api.hypixel.net/v2/skyblock/bazaar
```

公式ドキュメント: <https://api.hypixel.net/>

レスポンスの `products` を item ID ごとに読み取り、各商品の `quick_status` を pandas DataFrame に格納する。

対象フィールド:

```text
buyPrice        # Sell Order価格/Instant Buy価格
buyVolume       # Buy Orderアイテム総数
sellPrice       # Buy Order価格/Instant Sell価格
sellVolume      # Sell Orderアイテム総数
buyMovingWeek   # 過去7日間のInstant Buy
sellMovingWeek  # 過去7日間のInstant Sell
buyOrders       # Buy Order件数
sellOrders      # Sell Order件数
```

DataFrame では API のフィールド名をそのまま使用する。item ID は `products` のキーを使用する。

想定する列:

```text
item_id, buyPrice, buyVolume, sellPrice, sellVolume,
buyMovingWeek, sellMovingWeek, buyOrders, sellOrders
```

`buyVolume` / `sellVolume` は全注文に存在する item 数の合計、`buyPrice` / `sellPrice` は注文量上位 2% の加重平均である。これらは Hypixel API の定義をそのまま採用する。

## Recipe

レシピはリポジトリ内の NEU REPO から取得する。

```text
NotEnoughUpdates-REPO/items/*.json
```

対象は JSON の `recipe` フィールドに定義された crafting table レシピのみとする。`recipe` が存在しない item、crafting table 以外のレシピ、その他のアイテム情報は対象外とする。

各 JSON の `internalname` を完成品の item ID とし、`recipe` の `A1`〜`C3` を crafting table の 3×3 スロットとして読み取る。

```json
{
  "internalname": "AATROX_BATPHONE",
  "recipe": {
    "A1": "ENCHANTED_COBBLESTONE:1",
    "B2": "ENCHANTED_REDSTONE:1"
  }
}
```

空文字または存在しないスロットは空きスロットとして扱う。値は NEU REPO の表記を保持したまま pandas DataFrame に格納する。

想定する列:

```text
output_item_id, A1, A2, A3, B1, B2, B3, C1, C2, C3, source_path
```

材料の展開、数量計算、価格計算、利益計算は API 層では行わない。

## pandas の利用

- Bazaar は API の `products` / `quick_status` を item 単位の DataFrame に格納する。
- Recipe は crafting table のスロット情報を recipe 単位の DataFrame に格納する。
- pandas 以外のデータ管理ライブラリは必須としない。

## 参照

- [Hypixel API](https://api.hypixel.net/)
- [NotEnoughUpdates-REPO](https://github.com/NotEnoughUpdates/NotEnoughUpdates-REPO)

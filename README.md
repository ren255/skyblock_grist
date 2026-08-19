# skyblock flip

Bazzarで利益高いFLIPを検出するスクリプト。
- FLIP: buy order -> sell orderの差
- COMPACT FLIP: itemを圧縮し上位itemで売り直す instant sellで利益が出ることもある

金額、利益率、BUY/SELL予測時間が大事。

## Quickstart

```sh
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

## Structure

appがnb内でもimportできる。
NotEnoughUpdates-REPO/からレシピを取得し、公式APIからbazaar情報を取得している。
pandas/pydynamicを使用してデータを管理してる。
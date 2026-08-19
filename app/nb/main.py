# %%
# %load_ext autoreload
# %autoreload 2
# %%
from app.api import load_recipes, fetch_bazaar

# %%

# 2千個近くのitem全てload
recipes = load_recipes()
bazaar = fetch_bazaar()
print(recipes.columns)
print(bazaar.columns)
# %%

# FLIPPER buy order -> sell order
flip = bazaar.copy()


MAX_COIN = 200e6  # 所有金額
MAX_ORDER = 6
TARGET_COIN_PER_ORDER = MAX_COIN / MAX_ORDER
MAX_CTN_PER_ORDER = 71e3
MAX_FILL_MIN = 30
MIN_MARGIN = 0.1
MAX_MARGIN = 0.7
MIN_PROFIT = 1e6

flip["ctn"] = TARGET_COIN_PER_ORDER / flip["sellPrice"]
flip["ctn"] = flip["ctn"].clip(upper=MAX_CTN_PER_ORDER)
flip["buy_total_coin"] = flip["ctn"] * flip["sellPrice"]

flip["buy_fill_min"] = flip["ctn"] / (flip["sellMovingWeek"] / 7 / 24 / 60)
flip["sell_fill_min"] = flip["ctn"] / (flip["buyMovingWeek"] / 7 / 24 / 60)
flip["fill_min"] = flip["buy_fill_min"] + flip["sell_fill_min"]

flip["profit_per_item"] = flip["buyPrice"] - flip["sellPrice"]
flip["margin"] = flip["profit_per_item"] / flip["buyPrice"]
flip["profit"] = flip["profit_per_item"] * flip["ctn"]

flip["score"] = 0  # large is better
flip["score"] += flip["fill_min"].rank(pct=True, ascending=False) * 0.5
flip["score"] += flip["profit"].rank(pct=True, ascending=True) * 0.4
flip["score"] += flip["margin"].rank(pct=True, ascending=True) * 0.1

# flip = flip[flip["fill_min"] < MAX_FILL_MIN]
flip = flip[(flip["margin"] > MIN_MARGIN) & (flip["margin"] < MAX_MARGIN)]
# flip = flip[flip["profit"] > MIN_PROFIT]
cols = [
    "item_id",
    "buyPrice",
    "sellPrice",
    "ctn",
    "fill_min",
    "margin",
    "profit",
    "score",
]
flip.sort_values("score", ascending=False).head(20)
# %%

"""Load crafting-table recipes from the bundled NEU repository."""

import json
from pathlib import Path
import pandas as pd
from app import PROJECT_ROOT

SLOTS = [f"{row}{column}" for row in "ABC" for column in "123"]
columns = ["output_item_id", *SLOTS, "source_path"]


def load_recipes(repo_path: str | Path = "NotEnoughUpdates-REPO") -> pd.DataFrame:
    items_path = PROJECT_ROOT / repo_path / "items"
    rows = []
    for source in sorted(items_path.glob("*.json")):
        with source.open(encoding="utf-8") as file:
            item = json.load(file)
        recipe = item.get("recipe")
        if not isinstance(recipe, dict):
            continue
        rows.append(
            {
                "output_item_id": item["internalname"],
                **{slot: recipe.get(slot, "") or "" for slot in SLOTS},
                "source_path": str(source),
            }
        )
    return pd.DataFrame(rows, columns=columns)

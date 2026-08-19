"""Load crafting-table recipes from the bundled NEU repository."""

from app import PROJECT_ROOT
import json
from enum import StrEnum
from pathlib import Path
from typing import Any, Literal, overload
import pandas as pd

RecipeColumn = Literal[
    "output_item_id",
    "A1",
    "A2",
    "A3",
    "B1",
    "B2",
    "B3",
    "C1",
    "C2",
    "C3",
    "source_path",
]


class RecipeColumns(StrEnum):
    output_item_id = "output_item_id"
    A1 = "A1"
    A2 = "A2"
    A3 = "A3"
    B1 = "B1"
    B2 = "B2"
    B3 = "B3"
    C1 = "C1"
    C2 = "C2"
    C3 = "C3"
    source_path = "source_path"


class RecipeDataFrame(pd.DataFrame):
    @property
    def _constructor(self) -> type["RecipeDataFrame"]:
        return RecipeDataFrame

    @overload
    def __getitem__(self, key: RecipeColumn) -> pd.Series: ...

    @overload
    def __getitem__(self, key: Any) -> Any: ...

    def __getitem__(self, key: Any) -> Any:
        return super().__getitem__(key)


def load_recipes(repo_path: str | Path = "NotEnoughUpdates-REPO") -> RecipeDataFrame:
    """Load crafting recipes from ``repo_path/items/*.json``.

    Missing or empty slots are represented by the empty string.  Recipe values
    are intentionally not parsed or otherwise normalised.
    """
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
    return RecipeDataFrame(rows, columns=columns)

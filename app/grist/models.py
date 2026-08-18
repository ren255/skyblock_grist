from typing import Literal

from pydantic import BaseModel, ConfigDict, model_validator

GristColumnType = Literal["Text", "Numeric", "Any"]

# Column IDs of the two name columns that identify a gem row.
# Referenced by both the column scheme and the row sync logic.
FLAWED_NAME_COL = "FLAWED_GEM_NAME"
FLAWLESS_NAME_COL = "FLAWLESS_GEM_NAME"

# Column IDs of the price columns fed from the Bazaar API. Formula columns are
# deliberately absent: they are computed by Grist and must never be written.
BUY_ORDER_COL = "BUY_ORDER"
SELL_ORDER_COL = "SELL_ORDER"
INSTA_SELL_COL = "INSTA_SELL"
AVG_SELLING_PER_MINUTE_COL = "AVG_SELLING_PER_MINUTE"


class ColumnDef(BaseModel):
    """Desired or observed definition of a single Grist column."""

    model_config = ConfigDict(populate_by_name=True)

    col_id: str
    label: str
    type: GristColumnType
    is_formula: bool = False
    formula: str | None = None

    @model_validator(mode="after")
    def _check_formula_consistency(self) -> "ColumnDef":
        if self.is_formula and not self.formula:
            raise ValueError("formula is required when is_formula is True")
        if not self.is_formula and self.formula is not None:
            raise ValueError("formula must be None when is_formula is False")
        return self

    def to_fields(self) -> dict:
        """Serialize to the `fields` payload expected by the Grist columns API."""
        fields: dict = {
            "label": self.label,
            "type": self.type,
            "isFormula": self.is_formula,
        }
        if self.formula is not None:
            fields["formula"] = self.formula
        return fields


class GemRowDef(BaseModel):
    """Desired content of a single gem row.

    Only the two name columns are managed here; price columns such as
    `BUY_ORDER` are populated by other processes and left untouched.
    """

    model_config = ConfigDict(populate_by_name=True)

    flawed_gem_name: str
    flawless_gem_name: str

    def to_fields(self) -> dict:
        """Serialize to the `fields` payload expected by the Grist records API.

        Deliberately limited to the two name columns: formula columns are
        computed by Grist and must never be written.
        """
        return {
            FLAWED_NAME_COL: self.flawed_gem_name,
            FLAWLESS_NAME_COL: self.flawless_gem_name,
        }


GEM_TABLE_SCHEME: list[ColumnDef] = [
    ColumnDef(col_id=FLAWED_NAME_COL, label=FLAWED_NAME_COL, type="Text"),
    ColumnDef(col_id=FLAWLESS_NAME_COL, label=FLAWLESS_NAME_COL, type="Text"),
    ColumnDef(col_id=BUY_ORDER_COL, label=BUY_ORDER_COL, type="Numeric"),
    ColumnDef(
        col_id="CRAFT_COST",
        label="CRAFT_COST",
        type="Numeric",
        is_formula=True,
        formula="$BUY_ORDER * 80 * 80",
    ),
    ColumnDef(col_id=SELL_ORDER_COL, label=SELL_ORDER_COL, type="Numeric"),
    ColumnDef(
        col_id="ORDER_PROFIT",
        label="ORDER_PROFIT",
        type="Numeric",
        is_formula=True,
        formula="$SELL_ORDER - $CRAFT_COST",
    ),
    ColumnDef(col_id=INSTA_SELL_COL, label=INSTA_SELL_COL, type="Numeric"),
    ColumnDef(
        col_id="INSTA_PROFIT",
        label="INSTA_PROFIT",
        type="Numeric",
        is_formula=True,
        formula="$INSTA_SELL - $CRAFT_COST",
    ),
    ColumnDef(col_id="PLACEHOLDER", label="PLACEHOLDER", type="Any"),
    ColumnDef(
        col_id="FULL_COST",
        label="FULL_COST",
        type="Numeric",
        is_formula=True,
        formula="$BUY_ORDER * 71000",
    ),
    ColumnDef(
        col_id="TOTAL_PROFIT",
        label="TOTAL_PROFIT",
        type="Numeric",
        is_formula=True,
        formula="$ORDER_PROFIT * 71000 / 6400",
    ),
    ColumnDef(
        col_id=AVG_SELLING_PER_MINUTE_COL,
        label=AVG_SELLING_PER_MINUTE_COL,
        type="Numeric",
    ),
    ColumnDef(
        col_id="PROFIT_PER_HOUR",
        label="PROFIT_PER_HOUR",
        type="Numeric",
        is_formula=True,
        formula="$AVG_SELLING_PER_MINUTE * 60 * $ORDER_PROFIT",
    ),
]


# The gems tracked in the gem table. The flawless name is written out explicitly
# rather than derived from the flawed one, so exceptions to the naming pattern
# can be expressed here.
GEM_TABLE_ROWS: list[GemRowDef] = [
    GemRowDef(
        flawed_gem_name="FLAWED_SAPPHIRE_GEM",
        flawless_gem_name="FLAWLESS_SAPPHIRE_GEM",
    ),
    GemRowDef(
        flawed_gem_name="FLAWED_AMETHYST_GEM",
        flawless_gem_name="FLAWLESS_AMETHYST_GEM",
    ),
    GemRowDef(
        flawed_gem_name="FLAWED_AMBER_GEM",
        flawless_gem_name="FLAWLESS_AMBER_GEM",
    ),
    GemRowDef(
        flawed_gem_name="FLAWED_TOPAZ_GEM",
        flawless_gem_name="FLAWLESS_TOPAZ_GEM",
    ),
    GemRowDef(
        flawed_gem_name="FLAWED_PERIDOT_GEM",
        flawless_gem_name="FLAWLESS_PERIDOT_GEM",
    ),
    GemRowDef(
        flawed_gem_name="FLAWED_JADE_GEM",
        flawless_gem_name="FLAWLESS_JADE_GEM",
    ),
]


class GristColumnFields(BaseModel):
    """The `fields` object of a column as returned by the Grist columns API."""

    model_config = ConfigDict(extra="ignore")

    label: str | None = None
    type: str | None = None
    formula: str | None = None
    isFormula: bool | None = None


class GristColumn(BaseModel):
    """A single column entry as returned by `GET .../tables/{tableId}/columns`."""

    model_config = ConfigDict(extra="ignore")

    id: str
    fields: GristColumnFields


class GristColumnsResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    columns: list[GristColumn]


class GristRecord(BaseModel):
    """A single row as returned by `GET .../tables/{tableId}/records`.

    `fields` is kept as a plain dict because the set of columns is driven by the
    table scheme rather than fixed at the model level.
    """

    model_config = ConfigDict(extra="ignore")

    id: int
    fields: dict


class GristRecordsResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    records: list[GristRecord]


class GristTable(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str


class GristTablesResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    tables: list[GristTable]

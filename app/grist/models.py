from typing import Literal

from pydantic import BaseModel, ConfigDict, model_validator

GristColumnType = Literal["Text", "Numeric", "Any"]


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


GEM_TABLE_SCHEME: list[ColumnDef] = [
    ColumnDef(col_id="FLAWED_GEM_NAME", label="FLAWED_GEM_NAME", type="Text"),
    ColumnDef(col_id="FLAWLESS_GEM_NAME", label="FLAWLESS_GEM_NAME", type="Text"),
    ColumnDef(col_id="BUY_ORDER", label="BUY_ORDER", type="Numeric"),
    ColumnDef(
        col_id="CRAFT_COST",
        label="CRAFT_COST",
        type="Numeric",
        is_formula=True,
        formula="$BUY_ORDER * 80 * 80",
    ),
    ColumnDef(col_id="SELL_ORDER", label="SELL_ORDER", type="Numeric"),
    ColumnDef(
        col_id="ORDER_PROFIT",
        label="ORDER_PROFIT",
        type="Numeric",
        is_formula=True,
        formula="$SELL_ORDER - $CRAFT_COST",
    ),
    ColumnDef(col_id="INSTA_SELL", label="INSTA_SELL", type="Numeric"),
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
        col_id="AVG_SELLING_PER_MINUTE", label="AVG_SELLING_PER_MINUTE", type="Numeric"
    ),
    ColumnDef(
        col_id="PROFIT_PER_HOUR",
        label="PROFIT_PER_HOUR",
        type="Numeric",
        is_formula=True,
        formula="$AVG_SELLING_PER_MINUTE * 60 * $ORDER_PROFIT",
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


class GristTable(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str


class GristTablesResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    tables: list[GristTable]

from typing import Annotated, Literal, Union

from pydantic import BaseModel, Field, TypeAdapter, ValidationError


class MathV(BaseModel):
    type: Literal["math"] = "math"
    tex: str
    display: bool = False


class _Step(BaseModel):
    text: str
    highlight: bool = False


class StepsV(BaseModel):
    type: Literal["steps"] = "steps"
    title: str | None = None
    steps: list[_Step]


class _Mark(BaseModel):
    value: float
    label: str | None = None
    color: str | None = None


class _Jump(BaseModel):
    from_: float = Field(alias="from")
    to: float
    label: str | None = None

    model_config = {"populate_by_name": True}


class NumberLineV(BaseModel):
    type: Literal["number_line"] = "number_line"
    min: float
    max: float
    ticks: int | None = None
    marks: list[_Mark] = Field(default_factory=list)
    jumps: list[_Jump] = Field(default_factory=list)


class _Bar(BaseModel):
    denominator: int
    shaded: int
    label: str | None = None


class FractionBarV(BaseModel):
    type: Literal["fraction_bar"] = "fraction_bar"
    bars: list[_Bar]


class PlaceValueV(BaseModel):
    type: Literal["place_value"] = "place_value"
    value: float
    columns: list[str] | None = None


class MultGridV(BaseModel):
    type: Literal["mult_grid"] = "mult_grid"
    rows: int
    cols: int
    partial: bool = False


VisualAction = Annotated[
    Union[MathV, StepsV, NumberLineV, FractionBarV, PlaceValueV, MultGridV],
    Field(discriminator="type"),
]

_ADAPTER: TypeAdapter = TypeAdapter(VisualAction)

# Canonical Core 6 type names keyed by their alphanumeric-only, lowercased form, so
# model drift like "numberline"/"NumberLine"/"place value" still maps to the real type.
_CANONICAL_TYPES = {
    "".join(c for c in t if c.isalnum()): t
    for t in ("math", "steps", "number_line", "fraction_bar", "place_value", "mult_grid")
}


def _canonical_type(value: object) -> object:
    if not isinstance(value, str):
        return value
    key = "".join(c for c in value.lower() if c.isalnum())
    return _CANONICAL_TYPES.get(key, value)


def validate_visuals(raw: list[dict]) -> list[BaseModel]:
    """Validate each raw visual against the Core 6 union; drop invalid/unknown ones.

    The model occasionally emits collapsed/cased type names (e.g. "numberline"); we
    normalize `type` to its canonical form before validating so valid visuals aren't
    silently dropped.
    """
    out: list[BaseModel] = []
    for item in raw or []:
        if isinstance(item, dict) and "type" in item:
            item = {**item, "type": _canonical_type(item["type"])}
        try:
            out.append(_ADAPTER.validate_python(item))
        except ValidationError:
            continue
    return out

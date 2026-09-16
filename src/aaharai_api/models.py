from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel


class StrictModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        serialize_by_alias=True,
        extra="forbid",
    )


class FoodLogParseRequest(StrictModel):
    text: str = Field(min_length=1, max_length=12_000)


class ParsedFoodEntry(StrictModel):
    original_text: str
    food_name: str
    modifiers: list[str]
    quantity_value: float | None = Field(ge=0)
    quantity_unit: str | None
    day_of_week: Literal[
        "monday",
        "tuesday",
        "wednesday",
        "thursday",
        "friday",
        "saturday",
        "sunday",
    ] | None
    meal: Literal["breakfast", "lunch", "snack", "dinner", "other"] | None
    cooking_method: Literal[
        "raw",
        "boiled",
        "pressure_cooked",
        "steamed",
        "sauteed",
        "fried",
        "deep_fried",
        "roasted",
        "baked",
        "fermented",
        "soaked",
        "sprouted",
        "other",
    ] | None
    state_or_ut: str | None
    district: str | None
    settlement_type: Literal["village", "town", "city"] | None
    quality_cue: Literal["fresh", "stored", "wilted", "frozen", "canned", "other"] | None
    needs_confirmation: bool


class ParsedFoodLog(StrictModel):
    entries: list[ParsedFoodEntry]
    ambiguities: list[str]


class FoodCandidate(StrictModel):
    name: str
    brand: str | None = None
    barcode: str | None = None
    serving_weight_g: float | None = Field(default=None, gt=0)
    source_label: str
    source_url: str | None = None
    serving_unit: str | None = None
    energy_kcal_per_serving: float | None = Field(default=None, ge=0)
    protein_g_per_serving: float | None = Field(default=None, ge=0)
    carbohydrate_g_per_serving: float | None = Field(default=None, ge=0)
    fat_g_per_serving: float | None = Field(default=None, ge=0)
    energy_kcal_per_100g: float | None = Field(
        default=None, ge=0, serialization_alias="energyKcalPer100g"
    )
    protein_g_per_100g: float | None = Field(
        default=None, ge=0, serialization_alias="proteinGPer100g"
    )
    carbohydrate_g_per_100g: float | None = Field(
        default=None, ge=0, serialization_alias="carbohydrateGPer100g"
    )
    fat_g_per_100g: float | None = Field(
        default=None, ge=0, serialization_alias="fatGPer100g"
    )


class MatchedFoodEntry(ParsedFoodEntry):
    candidates: list[FoodCandidate]


class MatchedFoodLog(StrictModel):
    entries: list[MatchedFoodEntry]
    ambiguities: list[str]


class HealthResponse(StrictModel):
    status: Literal["ok"] = "ok"
    groq_configured: bool
    google_auth_configured: bool
    google_auth_required: bool
    food_catalog_configured: bool

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class IngredientNutrient:
    raw_weight_g: float
    nutrient_per_100g: float
    retention_factor: float


def cooked_nutrient_per_100g(
    ingredients: list[IngredientNutrient], final_cooked_weight_g: float
) -> float:
    """Calculate a cooked-dish nutrient concentration using true retention.

    Retention factors are proportions in [0, 1]. Water/fat and final yield must be
    represented by the measured final cooked weight; zero or negative yield is rejected.
    """
    if final_cooked_weight_g <= 0:
        raise ValueError("final_cooked_weight_g must be positive")
    retained = 0.0
    for item in ingredients:
        if item.raw_weight_g < 0 or item.nutrient_per_100g < 0:
            raise ValueError("weights and nutrient concentrations cannot be negative")
        if not 0 <= item.retention_factor <= 1:
            raise ValueError("retention_factor must be between 0 and 1")
        retained += item.raw_weight_g * item.nutrient_per_100g / 100 * item.retention_factor
    return retained / final_cooked_weight_g * 100


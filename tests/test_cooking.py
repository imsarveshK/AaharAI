import unittest

from aaharai.cooking import IngredientNutrient, cooked_nutrient_per_100g


class CookingCalculationTests(unittest.TestCase):
    def test_retention_and_yield(self) -> None:
        result = cooked_nutrient_per_100g(
            [IngredientNutrient(raw_weight_g=200, nutrient_per_100g=10, retention_factor=0.8)],
            final_cooked_weight_g=160,
        )
        self.assertAlmostEqual(result, 10.0)

    def test_invalid_retention_rejected(self) -> None:
        with self.assertRaises(ValueError):
            cooked_nutrient_per_100g(
                [IngredientNutrient(raw_weight_g=100, nutrient_per_100g=10, retention_factor=1.1)],
                final_cooked_weight_g=100,
            )


if __name__ == "__main__":
    unittest.main()


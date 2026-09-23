from aaharai.geography import _town_band
from aaharai.ifct import _parse_value
from aaharai.nfhs6 import _parse_value as parse_nfhs_value
from aaharai.retention import COMPONENTS
from aaharai.hces import VEGETABLE_ITEMS, final_weight, household_key, monthly_per_capita
from aaharai.mobile_catalog import MOBILE_NUTRIENTS


def test_ifct_value_keeps_mean_sd_and_qualifier():
    assert _parse_value("12.30±0.41") == ("12.30", "0.41", "")
    assert _parse_value("<0.01") == ("0.01", "", "<")


def test_nfhs_suppression_and_low_sample_are_not_numbers():
    assert parse_nfhs_value("*") == (None, True, False)
    assert parse_nfhs_value("(17.4)") == (17.4, False, True)


def test_census_population_bands_are_boundary_safe():
    assert _town_band(4_999) == ("VI", "town_small")
    assert _town_band(5_000) == ("V", "town_small")
    assert _town_band(10_000) == ("IV", "town_mid")
    assert _town_band(100_000) == ("I", "city_large")


def test_usda_release_has_26_component_columns():
    assert len(COMPONENTS) == 26
    assert len(set(COMPONENTS)) == 26


def test_hces_weight_and_household_key_follow_official_readme():
    row = {
        "FSU_Serial_No": "46667",
        "Second_Stage_Stratum_No": "2",
        "Sample_Household_No": "01",
    }
    assert household_key(row) == "46667|2|01"
    assert final_weight("16669") == 166.69


def test_hces_7_day_value_is_converted_to_30_day_mpce():
    assert monthly_per_capita(700.0, 100.0) == 30.0


def test_hces_lemon_is_not_labelled_as_kilograms():
    assert VEGETABLE_ITEMS["216"] == ("lemon", "count")
    assert VEGETABLE_ITEMS["219"][1] == "not_applicable"


def test_mobile_catalog_has_only_unique_direct_nutrient_mappings():
    component_codes = [item.component_code for item in MOBILE_NUTRIENTS]
    product_fields = [item.product_field for item in MOBILE_NUTRIENTS]
    assert len(component_codes) == len(set(component_codes))
    assert len(product_fields) == len(set(product_fields))
    assert "VITD" not in component_codes
    assert "VITK1" not in component_codes
    assert "VITK2" not in component_codes
    assert "SUGARS" not in product_fields

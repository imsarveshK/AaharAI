"""Check that every quantitative claim in the manuscript matches the computed output.

Each entry names a figure asserted in paper/manuscript.md and the value it must
equal, read from the analysis outputs rather than retyped. A failure means the
manuscript and the analysis have drifted apart.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[2]
MANUSCRIPT = (ROOT / "paper/manuscript.md").read_text()
KEY = json.loads((ROOT / "analysis/output/key_numbers.json").read_text())
TABLES = ROOT / "analysis/output/tables"


def shares() -> pd.DataFrame:
    return pd.read_csv(TABLES / "t4_budget_shares.csv").set_index("outcome")


def cem() -> pd.DataFrame:
    return pd.read_csv(TABLES / "t9_cem_shares.csv").set_index("outcome")


def levels() -> pd.DataFrame:
    return pd.read_csv(TABLES / "t5_levels.csv").set_index("outcome")


def adoption() -> pd.DataFrame:
    return pd.read_csv(TABLES / "t3_adoption_model.csv").set_index("term")


def build_cases() -> list[tuple[str, str, float, float]]:
    s, c, lv, ad = shares(), cem(), levels(), adoption()
    p = KEY["prevalence"]
    cases: list[tuple[str, str, float, float]] = [
        ("analysis households", "261,895", KEY["sample"]["households_analysis"], 0),
        ("rural households", "154,314", KEY["sample"]["rural"], 0),
        ("urban households", "107,581", KEY["sample"]["urban"], 0),
        ("PSUs", "14,827", KEY["sample"]["psus"], 0),
        ("design strata", "863", KEY["sample"]["strata_design"], 0),
        ("adopters", "19,842", KEY["sample"]["adopters"], 0),
        ("online food any", "7.10", p["online_food_any"]["all"]["pct"], 0.005),
        ("online food CI low", "6.76", p["online_food_any"]["all"]["ci"][0], 0.005),
        ("online food CI high", "7.43", p["online_food_any"]["all"]["ci"][1], 0.005),
        ("online food rural", "2.48", p["online_food_any"]["rural"]["pct"], 0.005),
        ("online food urban", "16.24", p["online_food_any"]["urban"]["pct"], 0.005),
        ("online food 7d", "5.64", p["online_food_any_7d"]["all"]["pct"], 0.005),
        ("online overall", "45.6", p["online_overall_any"]["all"]["pct"], 0.05),
        ("online services", "39.7", p["online_services_any"]["all"]["pct"], 0.05),
        ("online durables", "23.3", p["online_durables_any"]["all"]["pct"], 0.05),
        ("durables urban", "40.83", p["online_durables_any"]["urban"]["pct"], 0.02),
        ("adopting households (m)", "20.7",
         KEY["weighted_adopting_households_millions"], 0.05),
        ("decile 1 adoption", "0.34", KEY["decile_gradient"]["d1_any_pct"], 0.005),
        ("decile 10 adoption", "23.84", KEY["decile_gradient"]["d10_any_pct"], 0.005),
        ("processed:fresh d1", "0.85", KEY["decile_gradient"]["d1_processed_to_fresh"], 0.005),
        ("processed:fresh d10", "2.35", KEY["decile_gradient"]["d10_processed_to_fresh"], 0.005),
        ("kappa", "0.885", KEY["module_reliability"]["cohens_kappa"], 0.0005),
        ("agreement", "98.21", KEY["module_reliability"]["agreement_pct"], 0.005),
        ("spend but no category", "4,685",
         KEY["module_reliability"]["spend_positive_but_no_category"], 0),
        ("dose response low", "1,274",
         KEY["module_reliability"]["dose_response_mean_spend"]["1"], 0),
        ("dose response high", "5,448",
         KEY["module_reliability"]["dose_response_mean_spend"]["7"], 0),
        ("median spend", "1,400",
         KEY["module_reliability"]["median_spend_among_adopters"], 0),
        ("veg g/day", "238.4", KEY["vegetable_acquisition"]["all"]["g_per_capita_day"], 0.05),
        ("veg pct of guideline", "59.6",
         KEY["vegetable_acquisition"]["all"]["pct_of_icmr_nin_400g"], 0.05),
        ("veg rural g/day", "239.5", KEY["vegetable_acquisition"]["rural"]["g_per_capita_day"], 0.05),
        ("veg urban g/day", "235.7", KEY["vegetable_acquisition"]["urban"]["g_per_capita_day"], 0.05),
        # The reconciliation is stated over the full 261,953-household sample, which
        # is what the published averages cover; KEY["mpce"] is the analysis sample.
        ("mpce rural", "4,121.78",
         KEY["mpce_reconciliation"]["computed"]["headline_excl_imputed_rent"]["rural"], 0.005),
        ("mpce urban", "6,996.25",
         KEY["mpce_reconciliation"]["computed"]["headline_excl_imputed_rent"]["urban"], 0.005),
        ("adopter mix served", "36.6", KEY["adopter_mix_pct"]["Served processed food"], 0.05),
        ("adopter mix packaged", "23.2", KEY["adopter_mix_pct"]["Packaged processed food"], 0.05),
        ("adopter mix vegetables", "18.6", KEY["adopter_mix_pct"]["Vegetables"], 0.05),
        ("adopter mix fruits", "14.1", KEY["adopter_mix_pct"]["Fresh fruits"], 0.05),
        ("adopter mix groceries", "60.5", KEY["adopter_mix_pct"]["Groceries"], 0.05),
        ("adopter mix efm", "8.4", KEY["adopter_mix_pct"]["Egg, fish and meat"], 0.05),
        ("OR log mpce", "6.61", ad.loc["log_mpce", "estimate"], 0.005),
        ("OR education", "1.100", ad.loc["max_edu_years", "estimate"], 0.0005),
        ("OR internet", "2.88", ad.loc["any_internet", "estimate"], 0.005),
        ("OR urban", "1.82", ad.loc["urban", "estimate"], 0.005),
        ("OR pds", "0.69", ad.loc["pds_user", "estimate"], 0.005),
        ("share packaged", "1.81", 100 * s.loc["share_packaged_processed_food", "estimate"], 0.005),
        ("share vegetables", "0.63", -100 * s.loc["share_vegetables", "estimate"], 0.005),
        ("share beverages", "0.56", 100 * s.loc["share_beverages", "estimate"], 0.005),
        ("share cereals", "0.69", -100 * s.loc["share_cereals", "estimate"], 0.005),
        ("share milk", "0.51", -100 * s.loc["share_milk_and_products", "estimate"], 0.005),
        ("share efm", "0.37", -100 * s.loc["share_egg_fish_meat", "estimate"], 0.005),
        ("cem vegetables", "0.98", -cem().loc["share_vegetables", "difference_pp"], 0.005),
        ("cem packaged", "1.47", cem().loc["share_packaged_processed_food", "difference_pp"], 0.005),
        ("veg quantity diff", "0.23", -lv.loc["veg_qty_kg_pc", "estimate"], 0.005),
        ("veg unit value", "0.76", lv.loc["veg_unit_value", "estimate"], 0.005),
        ("cem cells", "3,970", KEY["cem"]["cem_cells"], 0),
        ("cem households", "125,681", KEY["cem"]["households_retained"], 0),
        ("cem online retained", "19,325", KEY["cem"]["online_retained"], 0),
        ("online overall exact", "45.60", p["online_overall_any"]["all"]["pct"], 0.005),
        ("online services exact", "39.69", p["online_services_any"]["all"]["pct"], 0.005),
        ("online durables exact", "23.31", p["online_durables_any"]["all"]["pct"], 0.005),
        ("durables rural exact", "14.46", p["online_durables_any"]["rural"]["pct"], 0.005),
        ("expenditure-based adopters", "24,527", KEY["sample"]["adopters_expenditure"], 0),
    ]
    return cases


@pytest.mark.parametrize("label,text,value,tol", build_cases())
def test_manuscript_number(label: str, text: str, value: float, tol: float) -> None:
    assert text in MANUSCRIPT, f"{label}: '{text}' not found in manuscript"
    numeric = float(text.replace(",", ""))
    assert abs(numeric - float(value)) <= tol, \
        f"{label}: manuscript says {text}, analysis gives {value}"


def test_no_placeholder_statistics() -> None:
    """Nothing of the form XX.X or [number] should survive into the manuscript."""
    for pattern in [r"\bXX+\b", r"\bTODO\b", r"\bTBD\b", r"\[number\]", r"\bNaN\b"]:
        assert not re.search(pattern, MANUSCRIPT), f"placeholder {pattern} in manuscript"

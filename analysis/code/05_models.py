"""
Fit the paper's regression models and write the coefficient tables.

Three families of model:
  A. Adoption   - who buys food online at all, and who buys each category.
  B. Composition- how the food budget is allocated across groups, conditional on
                  online purchasing and a rich covariate set.
  C. Levels     - per-capita quantities and values, and unit values.

Every model carries state and survey-month fixed effects, is weighted by the survey
multiplier, and reports standard errors clustered on the primary sampling unit.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

import models

ROOT = Path(__file__).resolve().parents[2]
BUILD = ROOT / "analysis/build"
TABLES = ROOT / "analysis/output/tables"
LOGS = ROOT / "analysis/logs"

CONTINUOUS = ["log_mpce", "max_edu_years", "any_internet", "urban", "log_hh_size",
              "share_female", "n_children_u5", "n_elderly_60p", "mean_age",
              "owns_land", "clean_cooking_fuel", "pds_user"]
CATEGORICAL = ["social_group", "religion", "household_type", "State", "month"]
REFERENCE = {"social_group": "Others", "religion": "Hinduism",
             "household_type": "Others"}

# Budget shares modelled as composition outcomes, in the order used in the paper.
SHARE_OUTCOMES = [
    ("share_vegetables", "Vegetables"),
    ("share_fruits_fresh", "Fruits (fresh)"),
    ("share_milk_and_products", "Milk and milk products"),
    ("share_egg_fish_meat", "Egg, fish and meat"),
    ("share_cereals", "Cereals"),
    ("share_pulses", "Pulses"),
    ("share_edible_oil", "Edible oil"),
    ("share_packaged_processed_food", "Packaged processed food"),
    ("share_served_processed_food", "Served processed food"),
    ("share_beverages", "Beverages"),
]

LEVEL_OUTCOMES = [
    ("veg_qty_kg_pc", "Vegetable quantity (kg/capita/30d)"),
    ("log_val_food_total_pc", "log food expenditure per capita"),
    ("log_val_vegetables_pc", "log vegetable expenditure per capita"),
    ("log_val_packaged_processed_food_pc", "log packaged processed expenditure per capita"),
    ("log_val_served_processed_food_pc", "log served processed expenditure per capita"),
    ("log_val_beverages_pc", "log beverage expenditure per capita"),
    ("food_group_count", "Number of food groups acquired"),
    ("veg_unit_value", "Vegetable unit value (Rs/kg)"),
]

CATEGORY_MODELS = [
    ("online_vegetables", "Vegetables"),
    ("online_fresh_fruits", "Fresh fruits"),
    ("online_groceries", "Groceries"),
    ("online_milk", "Milk"),
    ("online_egg_fish_meat", "Egg, fish and meat"),
    ("online_served_processed", "Served processed food"),
    ("online_packed_processed", "Packaged processed food"),
]


def prepare(df: pd.DataFrame) -> pd.DataFrame:
    d = df[df["val_food_total_pc"].notna()].copy()
    d["urban"] = (d["sector"] == "urban").astype(float)
    d["month"] = d["fdq_month"].astype(str)
    d["log_hh_size"] = np.log(d["P_F"].clip(lower=1))
    d["max_edu_years"] = d["max_edu_years"].fillna(0.0)
    for col in ["val_food_total_pc", "val_vegetables_pc", "val_packaged_processed_food_pc",
                "val_served_processed_food_pc", "val_beverages_pc"]:
        d[f"log_{col}"] = np.log1p(d[col].clip(lower=0))
    d["food_group_count"] = d["food_group_count"].astype(float)
    # Continuous exposure: online food spend per capita, logged for the robustness model.
    d["log_online_food_exp_pc"] = np.log1p(d["online_food_exp_pc"].clip(lower=0))
    # Alternative exposure defined from question QA2.6, the 30-day total spent on
    # online food purchases. It shares the reference period of the grocery tick-box
    # but not of the other eight categories, and it captures households that buy
    # online less often than once a week, whom the 7-day tick-boxes miss.
    d["online_food_any_exp"] = (d["online_exp_F"].fillna(0) > 0).astype(float)
    return d


def run_family(d: pd.DataFrame, outcomes, exposure: str, family: str,
               label: str) -> pd.DataFrame:
    rows = []
    for outcome, pretty in outcomes:
        res = models.fit(d, outcome, [exposure] + CONTINUOUS, CATEGORICAL,
                         family=family, reference=REFERENCE)
        t = models.tidy(res, terms=[exposure]).iloc[0]
        base = d.loc[d[exposure] == 0, outcome].mean() if family == "gaussian" else np.nan
        rows.append({
            "outcome": outcome, "label": pretty, "exposure": exposure,
            "estimate": t["estimate"], "se": t["se"], "p": t["p"],
            "ci_low": t["ci_low"], "ci_high": t["ci_high"],
            "baseline_mean": base, "n": res.n_obs_used, "n_clusters": res.n_clusters,
        })
        print(f"  [{label}] {pretty:<46} b={t['estimate']:+.5f} "
              f"({t['ci_low']:+.5f}, {t['ci_high']:+.5f}) p={t['p']:.2e}")
    return pd.DataFrame(rows)


def main() -> int:
    TABLES.mkdir(parents=True, exist_ok=True)
    df = pd.read_parquet(BUILD / "analysis_households.parquet")
    d = prepare(df)
    print(f"analysis sample: {len(d):,} households\n")

    print("A1. Adoption of any online food purchase")
    adoption = models.fit(d, "online_food_any", CONTINUOUS, CATEGORICAL,
                          family="binomial", reference=REFERENCE)
    t = models.tidy(adoption, exponentiate=True)
    t["n"] = adoption.n_obs_used
    t["n_clusters"] = adoption.n_clusters
    t.to_csv(TABLES / "t3_adoption_model.csv", index=False)
    for _, r in t[t["term"].isin(CONTINUOUS)].iterrows():
        print(f"  {r['term']:<22} OR={r['estimate']:6.3f} "
              f"({r['ci_low']:.3f}, {r['ci_high']:.3f}) p={r['p']:.2e}")

    print("\nA2. Adoption by food category (odds ratios on log MPCE)")
    cat_rows = []
    for outcome, pretty in CATEGORY_MODELS:
        res = models.fit(d, outcome, CONTINUOUS, CATEGORICAL,
                         family="binomial", reference=REFERENCE)
        tt = models.tidy(res, terms=["log_mpce", "max_edu_years", "urban"],
                         exponentiate=True)
        row = {"outcome": outcome, "label": pretty,
               "n": res.n_obs_used, "n_clusters": res.n_clusters}
        for _, r in tt.iterrows():
            row[f"{r['term']}_or"] = r["estimate"]
            row[f"{r['term']}_lo"] = r["ci_low"]
            row[f"{r['term']}_hi"] = r["ci_high"]
            row[f"{r['term']}_p"] = r["p"]
        cat_rows.append(row)
        print(f"  {pretty:<24} OR(log MPCE)={row['log_mpce_or']:6.3f} "
              f"({row['log_mpce_lo']:.3f}, {row['log_mpce_hi']:.3f})")
    pd.DataFrame(cat_rows).to_csv(TABLES / "t3b_category_adoption.csv", index=False)

    print("\nB. Food budget composition (share outcomes, coefficient on online_food_any)")
    shares = run_family(d, SHARE_OUTCOMES, "online_food_any", "gaussian", "share")
    shares.to_csv(TABLES / "t4_budget_shares.csv", index=False)

    print("\nC. Levels and diversity")
    levels = run_family(d, LEVEL_OUTCOMES, "online_food_any", "gaussian", "level")
    levels.to_csv(TABLES / "t5_levels.csv", index=False)

    print("\nD. Robustness: continuous exposure (log online food spend per capita)")
    shares_cont = run_family(d, SHARE_OUTCOMES, "log_online_food_exp_pc",
                             "gaussian", "share-cont")
    shares_cont.to_csv(TABLES / "t6_budget_shares_continuous.csv", index=False)

    print("\nD2. Robustness: exposure from reported 30-day online food expenditure")
    shares_exp = run_family(d, SHARE_OUTCOMES, "online_food_any_exp", "gaussian",
                            "share-exp")
    shares_exp.to_csv(TABLES / "t6c_budget_shares_expenditure_exposure.csv", index=False)

    print("\nE0. Robustness: exposure restricted to the eight 7-day categories")
    shares_7d = run_family(d, SHARE_OUTCOMES, "online_food_any_7d", "gaussian", "share-7d")
    shares_7d.to_csv(TABLES / "t6b_budget_shares_7d_exposure.csv", index=False)

    print("\nE. Robustness: urban households only")
    urban = d[d["sector"] == "urban"]
    cont_u = [c for c in CONTINUOUS if c != "urban"]
    rows = []
    for outcome, pretty in SHARE_OUTCOMES:
        res = models.fit(urban, outcome, ["online_food_any"] + cont_u, CATEGORICAL,
                         family="gaussian", reference=REFERENCE)
        t2 = models.tidy(res, terms=["online_food_any"]).iloc[0]
        rows.append({"outcome": outcome, "label": pretty, "estimate": t2["estimate"],
                     "se": t2["se"], "p": t2["p"], "ci_low": t2["ci_low"],
                     "ci_high": t2["ci_high"], "n": res.n_obs_used,
                     "n_clusters": res.n_clusters})
        print(f"  [urban] {pretty:<40} b={t2['estimate']:+.5f} p={t2['p']:.2e}")
    pd.DataFrame(rows).to_csv(TABLES / "t7_budget_shares_urban.csv", index=False)

    (LOGS / "models_run.json").write_text(json.dumps({
        "analysis_sample": int(len(d)),
        "psu_clusters": int(d["psu"].nunique()),
        "continuous_covariates": CONTINUOUS,
        "categorical_covariates": CATEGORICAL,
        "reference_levels": REFERENCE,
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

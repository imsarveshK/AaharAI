"""
Descriptive tables: sample composition, adoption prevalence, and the category mix.

All estimates are survey-weighted with design-based standard errors from survey.py.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

import survey

ROOT = Path(__file__).resolve().parents[2]
BUILD = ROOT / "analysis/build"
TABLES = ROOT / "analysis/output/tables"
LOGS = ROOT / "analysis/logs"

CATEGORIES = [
    ("online_groceries", "Groceries"),
    ("online_milk", "Milk"),
    ("online_vegetables", "Vegetables"),
    ("online_fresh_fruits", "Fresh fruits"),
    ("online_dry_fruits", "Dry fruits"),
    ("online_egg_fish_meat", "Egg, fish and meat"),
    ("online_served_processed", "Served processed food"),
    ("online_packed_processed", "Packaged processed food"),
    ("online_other_food", "Other food items"),
]

FOOD_GROUPS = [
    ("val_cereals_pc", "Cereals"), ("val_pulses_pc", "Pulses"),
    ("val_milk_and_products_pc", "Milk and milk products"),
    ("val_vegetables_pc", "Vegetables"), ("val_fruits_fresh_pc", "Fruits (fresh)"),
    ("val_fruits_dry_pc", "Fruits (dry)"), ("val_egg_fish_meat_pc", "Egg, fish and meat"),
    ("val_edible_oil_pc", "Edible oil"), ("val_spices_pc", "Spices"),
    ("val_sugar_salt_pc", "Sugar and salt"), ("val_beverages_pc", "Beverages"),
    ("val_served_processed_food_pc", "Served processed food"),
    ("val_packaged_processed_food_pc", "Packaged processed food"),
]


def pct(df, col, **kw):
    return survey.proportion(df[col], df["weight"], df["stratum_vce"], df["psu"], **kw)


def per_capita(df, col):
    return survey.ratio(df[col.removesuffix("_pc")], df["P_F"], df["weight"],
                        df["stratum_vce"], df["psu"])


def main() -> int:
    TABLES.mkdir(parents=True, exist_ok=True)
    df = pd.read_parquet(BUILD / "analysis_households.parquet")
    df = df[df["val_food_total_pc"].notna()].copy()
    df["max_edu_years"] = df["max_edu_years"].fillna(0.0)

    # ---- Table 1: sample characteristics by online food purchase status ----
    rows = []
    def add(label, col, kind="mean", scale=1.0, unit=""):
        for tag, g in [("all", df), ("offline", df[df.online_food_any == 0]),
                       ("online", df[df.online_food_any == 1])]:
            if kind == "prop":
                e = pct(g, col)
            elif kind == "percap":
                e = survey.ratio(g[col], g["P_F"], g["weight"], g["stratum_vce"], g["psu"])
            else:
                e = survey.mean(g[col].astype(float), g["weight"], g["stratum_vce"], g["psu"])
            rows.append({"characteristic": label, "unit": unit, "group": tag,
                         "estimate": scale * e.value, "se": scale * e.se, "n": e.n})

    df["urban_flag"] = (df["sector"] == "urban").astype("int8")
    add("Urban residence", "urban_flag", "prop", 100, "%")
    add("MPCE", "mpce_excl", "mean", 1, "Rs/capita/30d")
    add("Household size", "P_F", "mean", 1, "persons")
    add("Highest education in household", "max_edu_years", "mean", 1, "years")
    add("Any member used internet (30 d)", "any_internet", "prop", 100, "%")
    add("Uses public distribution system", "pds_user", "prop", 100, "%")
    add("Owns land", "owns_land", "prop", 100, "%")
    add("Clean cooking fuel", "clean_cooking_fuel", "prop", 100, "%")
    add("Food expenditure", "val_food_total", "percap", 1, "Rs/capita/30d")
    add("Vegetable quantity", "veg_qty_kg", "percap", 1, "kg/capita/30d")
    add("Food groups acquired", "food_group_count", "mean", 1, "count")
    t1 = pd.DataFrame(rows).pivot(index=["characteristic", "unit"], columns="group",
                                  values=["estimate", "se", "n"])
    t1.to_csv(TABLES / "t1_sample_characteristics.csv")
    print("Table 1: sample characteristics")
    print(f"  {'characteristic':<34}{'all':>12}{'offline':>12}{'online':>12}")
    for (ch, unit), r in t1.iterrows():
        print(f"  {ch:<34}{r[('estimate','all')]:12.2f}"
              f"{r[('estimate','offline')]:12.2f}{r[('estimate','online')]:12.2f}   {unit}")

    # ---- Table 2: adoption prevalence ----
    rows = []
    for col, label in CATEGORIES + [("online_food_any", "Any food category"),
                                    ("online_fresh_any", "Any fresh (veg or fruit)"),
                                    ("online_processed_any", "Any processed"),
                                    ("online_services_any", "Any service or consumable"),
                                    ("online_durables_any", "Any durable good"),
                                    ("online_overall_any", "Any online purchase")]:
        for tag, g in [("all", df), ("rural", df[df.sector == "rural"]),
                       ("urban", df[df.sector == "urban"])]:
            e = pct(g, col)
            rows.append({"category": label, "domain": tag, "pct": 100 * e.value,
                         "se": 100 * e.se, "ci_low": 100 * e.ci95[0],
                         "ci_high": 100 * e.ci95[1], "n": e.n, "n_psu": e.n_psu})
    t2 = pd.DataFrame(rows)
    t2.to_csv(TABLES / "t2_adoption_prevalence.csv", index=False)
    print("\nTable 2: adoption prevalence (%)")
    piv = t2.pivot(index="category", columns="domain", values="pct")
    print(piv.round(2).to_string())

    # ---- Table 2b: adoption by MPCE decile ----
    rows = []
    for dec, g in df.groupby("mpce_decile"):
        m = survey.ratio(g["mpce_excl"] * g["P_F"], g["P_F"], g["weight"],
                         g["stratum_vce"], g["psu"])
        rec = {"mpce_decile": int(dec), "mpce": m.value}
        for col, label in [("online_food_any", "any"), ("online_vegetables", "vegetables"),
                           ("online_fresh_fruits", "fresh_fruits"),
                           ("online_fresh_any", "fresh_any"),
                           ("online_served_processed", "served_processed"),
                           ("online_packed_processed", "packed_processed"),
                           ("online_processed_any", "processed_any"),
                           ("online_groceries", "groceries")]:
            e = pct(g, col)
            rec[f"{label}_pct"] = 100 * e.value
            rec[f"{label}_se"] = 100 * e.se
        rec["processed_to_fresh_ratio"] = (rec["processed_any_pct"] / rec["fresh_any_pct"]
                                           if rec["fresh_any_pct"] else np.nan)
        rows.append(rec)
    t2b = pd.DataFrame(rows)
    t2b.to_csv(TABLES / "t2b_adoption_by_decile.csv", index=False)
    print("\nTable 2b: adoption by MPCE decile (%)")
    print(t2b[["mpce_decile", "mpce", "any_pct", "vegetables_pct", "processed_any_pct",
               "processed_to_fresh_ratio"]].round(2).to_string(index=False))

    # ---- Table 2c: category mix among adopters ----
    sub = df[df.online_food_any == 1]
    rows = []
    for col, label in CATEGORIES:
        e = pct(sub, col)
        rows.append({"category": label, "pct_of_adopters": 100 * e.value,
                     "se": 100 * e.se, "n": e.n})
    t2c = pd.DataFrame(rows).sort_values("pct_of_adopters", ascending=False)
    t2c.to_csv(TABLES / "t2c_category_mix_adopters.csv", index=False)
    print("\nTable 2c: category mix among online food buyers (%)")
    print(t2c.round(2).to_string(index=False))

    # ---- Table 2d: food budget composition, online vs offline ----
    rows = []
    for col, label in FOOD_GROUPS:
        rec = {"food_group": label}
        for tag, g in [("all", df), ("offline", df[df.online_food_any == 0]),
                       ("online", df[df.online_food_any == 1])]:
            e = survey.ratio(g[col.removesuffix("_pc")], g["P_F"], g["weight"],
                             g["stratum_vce"], g["psu"])
            s = survey.ratio(g[col.removesuffix("_pc")], g["val_food_total"],
                             g["weight"], g["stratum_vce"], g["psu"])
            rec[f"{tag}_rs_pc"] = e.value
            rec[f"{tag}_share_pct"] = 100 * s.value
        rows.append(rec)
    t2d = pd.DataFrame(rows)
    t2d.to_csv(TABLES / "t2d_food_composition.csv", index=False)
    print("\nTable 2d: food budget composition")
    print(t2d.round(2).to_string(index=False))

    # ---- state-level adoption, for the map/ranking figure ----
    rows = []
    for st, g in df.groupby("State"):
        e = pct(g, "online_food_any")
        v = pct(g, "online_vegetables")
        p = pct(g, "online_processed_any")
        rows.append({"state_code": st, "any_pct": 100 * e.value, "any_se": 100 * e.se,
                     "veg_pct": 100 * v.value, "processed_pct": 100 * p.value,
                     "n": e.n, "n_psu": e.n_psu})
    pd.DataFrame(rows).to_csv(TABLES / "t11_state_adoption.csv", index=False)

    (LOGS / "descriptives_run.json").write_text(json.dumps(
        {"analysis_sample": int(len(df)), "adopters": int(df.online_food_any.sum())},
        indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

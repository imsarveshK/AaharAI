"""
Assemble the household-level analytic dataset.

Combines, for each of the 261,953 HCES 2023-24 households:
  - survey design identifiers (stratum, PSU, weight);
  - online purchase exposure, across all three questionnaires;
  - food acquisition outcomes, per capita per 30 days;
  - household composition, education, internet use and social characteristics.

Reference periods differ by questionnaire section, so every value is scaled to a
30-day equivalent before being divided by household size. Sub-total item codes are
never summed alongside the items they aggregate.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
BUILD = ROOT / "analysis/build"
LOGS = ROOT / "analysis/logs"

# Level 04 online food categories, from question Q4.1.3. The reference period is NOT
# uniform: groceries is asked over 30 days and every other category over 7 days. A
# longer window mechanically yields a higher prevalence, so groceries must never be
# compared directly against the others. The eight 7-day categories are mutually
# comparable and carry the paper's fresh-versus-processed contrast.
ONLINE_FOOD = {
    "Online_Groceries": ("groceries", 30),
    "Online_Milk": ("milk", 7),
    "Online_Vegetables": ("vegetables", 7),
    "Online_Fresh_Fruits": ("fresh_fruits", 7),
    "Online_Dry_Fruits": ("dry_fruits", 7),
    "Online_Egg_Fish_Meat": ("egg_fish_meat", 7),
    "Online_Served_Processed_Food": ("served_processed", 7),
    "Online_Packed_Processed_Food": ("packed_processed", 7),
    "Online_Other_Food_Items": ("other_food", 7),
}
ONLINE_FOOD_7D = [n for n, (_, d) in
                  ((k, v) for k, v in ONLINE_FOOD.items()) if d == 7]
ONLINE_SERVICES = ["Online_purchase_fuel_light", "Online_purchase_toilet_articles",
                   "Online_purchase_education", "Online_purchase_medicine",
                   "Online_purchase_services"]
ONLINE_DURABLES = ["Online_Clothing", "Online_Footwear", "Online_Furniture",
                   "Online_Mobile", "Online_PersonalGoods", "Online_RecreationGoods",
                   "Online_HouseholdAppliances", "Online_Crockery", "Online_SportsGoods",
                   "Online_MedicalEquipment", "Online_Bedding"]

# Fresh, minimally processed groups versus processed/packaged groups.
FRESH_GROUPS = ["vegetables", "fruits_fresh", "milk_and_products", "egg_fish_meat"]
PROCESSED_GROUPS = ["served_processed_food", "packaged_processed_food"]

# Vegetable items measured in kilograms. Lemon (216) is recorded as a count and is
# excluded from the kilogram aggregate, as in the repository's HCES importer.
LEMON_ITEM = "216"

SOCIAL_GROUP = {"1": "ST", "2": "SC", "3": "OBC", "9": "Others", "0": "Not reported"}
RELIGION = {"1": "Hinduism", "2": "Islam", "3": "Christianity", "4": "Sikhism",
            "5": "Jainism", "6": "Buddhism", "7": "Zoroastrianism", "9": "Others",
            "0": "Not reported"}
HH_TYPE = {"1": "Self-employed in agriculture", "2": "Self-employed in non-agriculture",
           "3": "Regular wage in agriculture", "4": "Regular wage in non-agriculture",
           "5": "Casual labour in agriculture", "6": "Casual labour in non-agriculture",
           "9": "Others"}
CLEAN_COOKING_FUELS = {"02", "03", "07", "08", "11"}  # LPG, natural gas, biogas, electricity


# Tick-boxes are stored as "1" for yes and blank otherwise, except in Level 07 where
# the same ticks arrive float-formatted as "1.0". Both forms must count as yes; a
# strict "== '1'" test silently reports zero adoption for every Level 07 category.
YES_TOKENS = {"1", "1.0", "01"}


def yes(series: pd.Series) -> pd.Series:
    return series.fillna("").str.strip().isin(YES_TOKENS).astype("int8")


def build_design() -> pd.DataFrame:
    l1 = pd.read_parquet(BUILD / "hces_L01.parquet",
                         columns=["hh_id", "FSU_Serial_No", "State", "Sector",
                                  "NSS_Region", "District", "Stratum", "Sub_stratum",
                                  "Panel", "Sub_sample", "Second_Stage_Stratum_No"])
    l1 = l1.drop_duplicates("hh_id").set_index("hh_id")
    l1["psu"] = l1["FSU_Serial_No"]
    l1["stratum"] = (l1["State"] + "_" + l1["Sector"] + "_"
                     + l1["Stratum"] + "_" + l1["Sub_stratum"])
    l1["sector"] = l1["Sector"].map({"1": "rural", "2": "urban"})

    # Variance estimation needs at least two PSUs per stratum. The few singleton
    # strata are pooled within their state and sector rather than dropped, so no
    # household leaves the sample.
    npsu = l1.groupby("stratum")["psu"].transform("nunique")
    singleton = npsu < 2
    l1["stratum_vce"] = l1["stratum"].where(
        ~singleton, l1["State"] + "_" + l1["Sector"] + "_pooled_singleton")
    l1.attrs["singleton_households"] = int(singleton.sum())
    return l1


def build_exposure() -> pd.DataFrame:
    l4 = pd.read_parquet(BUILD / "hces_L04.parquet",
                         columns=["hh_id", *ONLINE_FOOD,
                                  "Ration_Any_Item_Last_30_Days"]).set_index("hh_id")
    out = pd.DataFrame(index=l4.index)
    names = [n for n, _ in ONLINE_FOOD.values()]
    for col, (name, _) in ONLINE_FOOD.items():
        out[f"online_{name}"] = yes(l4[col])
    out["online_food_any"] = out[[f"online_{n}" for n in names]].max(axis=1)
    out["online_food_n_categories"] = out[[f"online_{n}" for n in names]].sum(axis=1)
    # Restricted to the eight categories sharing a 7-day window, so that the
    # exposure itself is free of the reference-period asymmetry.
    names_7d = [n for n, d in ONLINE_FOOD.values() if d == 7]
    out["online_food_any_7d"] = out[[f"online_{n}" for n in names_7d]].max(axis=1)
    out["online_fresh_any"] = out[["online_vegetables", "online_fresh_fruits"]].max(axis=1)
    out["online_processed_any"] = out[["online_served_processed",
                                       "online_packed_processed"]].max(axis=1)
    out["pds_user"] = (l4["Ration_Any_Item_Last_30_Days"].str.strip() == "1").astype("int8")

    l7 = pd.read_parquet(BUILD / "hces_L07.parquet",
                         columns=["hh_id", *ONLINE_SERVICES]).set_index("hh_id")
    out["online_services_any"] = pd.concat([yes(l7[c]) for c in ONLINE_SERVICES],
                                           axis=1).max(axis=1)
    l11 = pd.read_parquet(BUILD / "hces_L11.parquet",
                          columns=["hh_id", *ONLINE_DURABLES]).set_index("hh_id")
    out["online_durables_any"] = pd.concat([yes(l11[c]) for c in ONLINE_DURABLES],
                                           axis=1).max(axis=1)
    out["online_overall_any"] = out[["online_food_any", "online_services_any",
                                     "online_durables_any"]].max(axis=1)
    return out


def build_food_outcomes(hh_size: pd.Series) -> pd.DataFrame:
    items = pd.read_csv(BUILD / "hces_item_dictionary.csv", dtype={"item_code": str})
    ref = dict(zip(items["item_code"], items["reference_period_days"]))
    grp = dict(zip(items["item_code"], items["food_group"]))
    subtotal = set(items.loc[items["is_subtotal"], "item_code"])

    # NOTE ON A MISLEADING COLUMN NAME. Level 05's `OutOfHome_Consumption_Value`
    # does NOT measure food away from home. The questionnaire column it comes from
    # is "consumption out of home produce", which the enumerator instructions define
    # as "produce of cultivation or produce of livestock". It is own-production
    # consumption, and is renamed here so it cannot be misread downstream. Food away
    # from home is captured instead by Section 7.1 (served processed food).
    frames = []
    for level, home_produce in [("05", "OutOfHome_Consumption_Value"), ("06", None)]:
        cols = ["hh_id", "Item_Code", "Total_Consumption_Quantity",
                "Total_Consumption_Value", "Source"]
        if home_produce:
            cols.append(home_produce)
        df = pd.read_parquet(BUILD / f"hces_L{level}.parquet", columns=cols)
        df = df.rename(columns={"Total_Consumption_Quantity": "qty",
                                "Total_Consumption_Value": "val"})
        df["home_produce_val"] = df.pop(home_produce) if home_produce else np.nan
        df["Item_Code"] = df["Item_Code"].str.strip()
        frames.append(df[["hh_id", "Item_Code", "qty", "val", "home_produce_val", "Source"]])
    d = pd.concat(frames, ignore_index=True)

    for c in ["qty", "val", "home_produce_val"]:
        d[c] = pd.to_numeric(d[c], errors="coerce")
    d["ref_days"] = d["Item_Code"].map(ref)
    d["food_group"] = d["Item_Code"].map(grp)
    d["is_subtotal"] = d["Item_Code"].isin(subtotal)
    if d["ref_days"].isna().any():
        bad = sorted(d.loc[d["ref_days"].isna(), "Item_Code"].unique())
        raise ValueError(f"items with no reference period: {bad}")

    scale = 30.0 / d["ref_days"]
    d["val_30d"] = d["val"] * scale
    d["qty_30d"] = d["qty"] * scale
    d["home_produce_30d"] = d["home_produce_val"] * scale

    # Group values come from the sub-total codes, which the ministry also uses.
    gv = (d[d["is_subtotal"]].pivot_table(index="hh_id", columns="food_group",
                                          values="val_30d", aggfunc="sum"))
    gv.columns = [f"val_{c}" for c in gv.columns]

    # Quantities are summed over constituent items, since sub-totals mix units.
    veg = d[(d["food_group"] == "vegetables") & (~d["is_subtotal"])
            & (d["Item_Code"] != LEMON_ITEM)]
    veg_qty = veg.groupby("hh_id")["qty_30d"].sum().rename("veg_qty_kg")
    veg_purchased = (veg[veg["Source"] == "1"].groupby("hh_id")["val_30d"].sum()
                     .rename("veg_val_purchased"))
    veg_homegrown = (veg[veg["Source"].isin(["2", "3"])].groupby("hh_id")["val_30d"].sum()
                     .rename("veg_val_homegrown"))

    home_produce = (d.groupby("hh_id")["home_produce_30d"].sum()
                    .rename("home_produce_val"))

    out = gv.join([veg_qty, veg_purchased, veg_homegrown, home_produce],
                  how="outer").fillna(0.0)
    out["val_food_total"] = out[[c for c in out.columns if c.startswith("val_")]].sum(axis=1)
    out["val_processed"] = out[[f"val_{g}" for g in PROCESSED_GROUPS]].sum(axis=1)
    out["val_fresh"] = out[[f"val_{g}" for g in FRESH_GROUPS]].sum(axis=1)

    # Dietary diversity: how many of the food groups the household acquired at all.
    diversity_groups = [c for c in gv.columns
                        if c not in ("val_sugar_salt", "val_spices")]
    out["food_group_count"] = (gv[diversity_groups] > 0).sum(axis=1)

    # Per capita per 30 days.
    size = hh_size.reindex(out.index)
    for c in [c for c in out.columns if c.startswith(("val_", "veg_qty", "home_produce"))]:
        out[f"{c}_pc"] = out[c] / size

    # Budget shares are the composition outcome: what fraction of the food budget a
    # group takes, which is comparable across households of different means.
    for col in [c for c in gv.columns] + ["val_processed", "val_fresh"]:
        out[f"share_{col[4:]}"] = np.where(out["val_food_total"] > 0,
                                           out[col] / out["val_food_total"], np.nan)
    out["processed_share"] = out["share_processed"]
    out["veg_unit_value"] = np.where(out["veg_qty_kg"] > 0,
                                     out["val_vegetables"] / out["veg_qty_kg"], np.nan)
    return out


def build_covariates() -> pd.DataFrame:
    l3 = pd.read_parquet(BUILD / "hces_L03.parquet",
                         columns=["hh_id", "Household_Type", "Religion_of_HH_Head",
                                  "Social_Group_of_HH_Head", "Land_Ownership",
                                  "Type_of_Land_Owned",
                                  "Total_Area_Land_Owned_Acres", "Energy_Source_Cooking",
                                  "Ration_Card_Type", "HH_Size_FDQ"]).set_index("hh_id")
    out = pd.DataFrame(index=l3.index)
    out["social_group"] = l3["Social_Group_of_HH_Head"].map(SOCIAL_GROUP).fillna("Not reported")
    out["religion"] = l3["Religion_of_HH_Head"].map(RELIGION).fillna("Not reported")
    out["household_type"] = l3["Household_Type"].map(HH_TYPE).fillna("Others")
    # Land_Ownership covers any land at all, homestead included, so it is near
    # universal and says little about farming. Type_of_Land_Owned separates the two:
    # 1 homestead only, 2 homestead and other land, 3 other land only.
    out["owns_land_any"] = (l3["Land_Ownership"].str.strip() == "1").astype("int8")
    out["owns_land_beyond_homestead"] = l3["Type_of_Land_Owned"].str.strip().isin(
        {"2", "3"}).astype("int8")
    out["owns_land"] = out["owns_land_beyond_homestead"]
    out["land_acres"] = pd.to_numeric(l3["Total_Area_Land_Owned_Acres"],
                                      errors="coerce").fillna(0.0)
    out["clean_cooking_fuel"] = l3["Energy_Source_Cooking"].str.strip().isin(
        CLEAN_COOKING_FUELS).astype("int8")

    l2 = pd.read_parquet(BUILD / "hces_L02.parquet",
                         columns=["hh_id", "Age", "Gender", "Relation_to_Head",
                                  "Years_of_Education", "Used_Internet_Last_30_Days",
                                  "Meals_At_Home", "Meals_On_Payment"])
    l2["age"] = pd.to_numeric(l2["Age"], errors="coerce")
    l2["edu_years"] = pd.to_numeric(l2["Years_of_Education"], errors="coerce")
    l2["internet"] = (l2["Used_Internet_Last_30_Days"].str.strip() == "1").astype("int8")
    l2["is_female"] = (l2["Gender"].str.strip() == "2").astype("int8")

    agg = l2.groupby("hh_id").agg(
        n_members=("age", "size"),
        max_edu_years=("edu_years", "max"),
        mean_age=("age", "mean"),
        share_female=("is_female", "mean"),
        n_children_u5=("age", lambda s: int((s < 5).sum())),
        n_elderly_60p=("age", lambda s: int((s >= 60).sum())),
        any_internet=("internet", "max"),
        share_internet=("internet", "mean"),
        meals_on_payment=("Meals_On_Payment", lambda s: pd.to_numeric(s, errors="coerce").sum()),
    )
    head = l2[l2["Relation_to_Head"].str.strip() == "1"].drop_duplicates("hh_id")
    head = head.set_index("hh_id")[["edu_years", "age", "is_female"]]
    head.columns = ["head_edu_years", "head_age", "head_is_female"]

    return out.join([agg, head])


def main() -> int:
    design = build_design()
    mpce = pd.read_parquet(BUILD / "hh_mpce.parquet")
    # `sector` is derived in build_design from Level 01; drop the duplicate copy
    # carried alongside MPCE so the join has a single source of truth.
    mpce = mpce.drop(columns=[c for c in ("sector", "Sector") if c in mpce.columns])
    exposure = build_exposure()
    covars = build_covariates()
    food = build_food_outcomes(mpce["P_F"])

    df = design.join([mpce, exposure, covars, food], how="left")

    df["log_mpce"] = np.log(df["mpce_excl"].clip(lower=1))
    df["online_food_exp_pc"] = df["online_exp_F"].fillna(0.0) / df["P_F"]

    # MPCE deciles are formed on person-weighted rank, since MPCE is a per-person
    # measure; deciles are cut nationally and again within sector.
    def weighted_decile(frame: pd.DataFrame) -> pd.Series:
        order = frame["mpce_excl"].sort_values().index
        w = (frame.loc[order, "weight"] * frame.loc[order, "P_F"]).to_numpy()
        cw = np.cumsum(w) / w.sum()
        return pd.Series(np.clip((cw * 10).astype(int) + 1, 1, 10), index=order)

    df["mpce_decile"] = weighted_decile(df)
    df["mpce_decile_sector"] = (df.groupby("sector", group_keys=False)
                                .apply(weighted_decile, include_groups=False))

    df["survey_month"] = pd.to_datetime(df["fdq_month"], format="%m%Y", errors="coerce")

    report = {
        "households": int(len(df)),
        "singleton_stratum_households_pooled": design.attrs["singleton_households"],
        "psus": int(df["psu"].nunique()),
        "strata_design": int(df["stratum"].nunique()),
        "strata_variance": int(df["stratum_vce"].nunique()),
        "weight_sum_households": float(df["weight"].sum()),
        "weight_sum_persons": float((df["weight"] * df["P_F"]).sum()),
        "missing": {c: int(df[c].isna().sum())
                    for c in ["mpce_excl", "online_food_any", "val_food_total_pc",
                              "veg_qty_kg_pc", "max_edu_years", "any_internet"]},
    }
    (LOGS / "analysis_dataset_report.json").write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))

    df.to_parquet(BUILD / "analysis_households.parquet")
    print(f"\nwrote {BUILD / 'analysis_households.parquet'}  shape={df.shape}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

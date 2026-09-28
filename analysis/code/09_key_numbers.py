"""Collect every figure quoted in the manuscript into one auditable file."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

import survey

ROOT = Path(__file__).resolve().parents[2]
BUILD = ROOT / "analysis/build"
TABLES = ROOT / "analysis/output/tables"
OUT = ROOT / "analysis/output"


def main() -> int:
    df = pd.read_parquet(BUILD / "analysis_households.parquet")
    d = df[df["val_food_total_pc"].notna()].copy()
    k: dict[str, object] = {}

    k["sample"] = {
        "households_total": int(len(df)),
        "households_analysis": int(len(d)),
        "households_dropped_no_food_records": int(len(df) - len(d)),
        "rural": int((d.sector == "rural").sum()),
        "urban": int((d.sector == "urban").sum()),
        "psus": int(d.psu.nunique()),
        "strata_design": int(d.stratum.nunique()),
        "weighted_households": float(d.weight.sum()),
        "weighted_persons": float((d.weight * d.P_F).sum()),
        "adopters": int(d.online_food_any.sum()),
        "adopters_expenditure": int((d.online_exp_F.fillna(0) > 0).sum()),
    }

    P = lambda g, c: survey.proportion(g[c], g.weight, g.stratum_vce, g.psu)
    R = lambda g, n, dd: survey.ratio(g[n], g[dd], g.weight, g.stratum_vce, g.psu)

    prev = {}
    for col in ["online_food_any", "online_food_any_7d", "online_fresh_any",
                "online_processed_any", "online_services_any", "online_durables_any",
                "online_overall_any", "online_vegetables", "online_served_processed",
                "online_packed_processed", "online_groceries"]:
        prev[col] = {}
        for tag, g in [("all", d), ("rural", d[d.sector == "rural"]),
                       ("urban", d[d.sector == "urban"])]:
            e = P(g, col)
            prev[col][tag] = {"pct": round(100 * e.value, 3),
                              "se": round(100 * e.se, 3),
                              "ci": [round(100 * e.ci95[0], 3), round(100 * e.ci95[1], 3)]}
    k["prevalence"] = prev
    k["weighted_adopting_households_millions"] = round(
        float(d.loc[d.online_food_any == 1, "weight"].sum()) / 1e6, 2)

    # Vegetable acquisition against the ICMR-NIN 2024 guideline of 400 g/day.
    veg = {}
    for tag, g in [("all", d), ("rural", d[d.sector == "rural"]),
                   ("urban", d[d.sector == "urban"])]:
        e = R(g, "veg_qty_kg", "P_F")
        veg[tag] = {"kg_per_capita_30d": round(e.value, 4),
                    "g_per_capita_day": round(1000 * e.value / 30, 1),
                    "se_g_day": round(1000 * e.se / 30, 2),
                    "pct_of_icmr_nin_400g": round(100 * (1000 * e.value / 30) / 400, 1)}
    k["vegetable_acquisition"] = veg

    mp = {}
    for tag, g in [("rural", d[d.sector == "rural"]), ("urban", d[d.sector == "urban"])]:
        e = survey.ratio(g.mpce_excl * g.P_F, g.P_F, g.weight, g.stratum_vce, g.psu)
        mp[tag] = {"mpce": round(e.value, 2), "se": round(e.se, 2)}
    k["mpce"] = mp
    k["mpce_published_2023_24"] = {"rural": 4122.0, "urban": 6996.0}

    dec = pd.read_csv(TABLES / "t2b_adoption_by_decile.csv")
    k["decile_gradient"] = {
        "d1_any_pct": round(float(dec.any_pct.iloc[0]), 2),
        "d10_any_pct": round(float(dec.any_pct.iloc[-1]), 2),
        "ratio_d10_d1": round(float(dec.any_pct.iloc[-1] / dec.any_pct.iloc[0]), 1),
        "d1_processed_to_fresh": round(float(dec.processed_to_fresh_ratio.iloc[0]), 2),
        "d10_processed_to_fresh": round(float(dec.processed_to_fresh_ratio.iloc[-1]), 2),
        "d1_mpce": round(float(dec.mpce.iloc[0])), "d10_mpce": round(float(dec.mpce.iloc[-1])),
    }

    mix = pd.read_csv(TABLES / "t2c_category_mix_adopters.csv")
    k["adopter_mix_pct"] = {r.category: round(r.pct_of_adopters, 2)
                            for r in mix.itertuples()}

    # Module reliability.
    d["exp_pos"] = (d.online_exp_F.fillna(0) > 0).astype(int)
    ct = pd.crosstab(d.online_food_any, d.exp_pos)
    n = int(ct.values.sum())
    po = (ct.iloc[0, 0] + ct.iloc[1, 1]) / n
    pe = ((ct.iloc[0].sum() * ct[0].sum()) + (ct.iloc[1].sum() * ct[1].sum())) / n ** 2
    k["module_reliability"] = {
        "agreement_pct": round(100 * po, 2),
        "cohens_kappa": round((po - pe) / (1 - pe), 3),
        "ticked_category_but_zero_spend": int(ct.iloc[1, 0]),
        "spend_positive_but_no_category": int(ct.iloc[0, 1]),
        "median_spend_among_adopters": float(
            d.loc[d.online_food_any == 1, "online_exp_F"].median()),
        "dose_response_mean_spend": {
            int(kk): round(float(np.average(g.online_exp_F.fillna(0), weights=g.weight)))
            for kk, g in d[d.online_food_any == 1].groupby("online_food_n_categories")},
    }

    for name, path in [("adoption_model", "t3_adoption_model.csv"),
                       ("budget_shares", "t4_budget_shares.csv"),
                       ("levels", "t5_levels.csv"),
                       ("cem_shares", "t9_cem_shares.csv"),
                       ("evalues", "t10_evalues.csv"),
                       ("category_adoption", "t3b_category_adoption.csv")]:
        k[name] = pd.read_csv(TABLES / path).round(6).to_dict("records")

    k["cem"] = json.loads((ROOT / "analysis/logs/robustness_run.json").read_text())
    k["mpce_reconciliation"] = json.loads(
        (ROOT / "analysis/logs/mpce_reconciliation.json").read_text())

    (OUT / "key_numbers.json").write_text(json.dumps(k, indent=2, default=str))
    print(json.dumps({kk: vv for kk, vv in k.items()
                      if kk in ("sample", "vegetable_acquisition", "decile_gradient",
                                "module_reliability",
                                "weighted_adopting_households_millions")},
                     indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

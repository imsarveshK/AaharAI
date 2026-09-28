"""
Robustness: coarsened exact matching and sensitivity to unmeasured confounding.

Two questions the regression cannot answer on its own.

First, whether the composition result survives when online and offline households are
compared only inside cells that are identical on the strongest confounders, rather
than across a fitted surface. Coarsened exact matching on state, sector, MPCE decile,
education band and household-size band discards every household with no counterpart
and reweights the rest, so the contrast is entirely within-cell.

Second, how strong an unmeasured confounder would have to be to explain the result
away. The E-value is the minimum association, on the risk-ratio scale, that such a
confounder would need with both the exposure and the outcome (VanderWeele and Ding,
Annals of Internal Medicine, 2017).
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

EDU_BANDS = [-0.1, 0, 5, 8, 10, 12, 15, 100]
SIZE_BANDS = [0, 1, 2, 3, 4, 6, 8, 100]


def coarsen(df: pd.DataFrame) -> pd.Series:
    edu = pd.cut(df["max_edu_years"].fillna(0), EDU_BANDS, labels=False)
    size = pd.cut(df["P_F"], SIZE_BANDS, labels=False)
    return (df["State"].astype(str) + "|" + df["sector"].astype(str) + "|"
            + df["mpce_decile"].astype(str) + "|" + edu.astype(str) + "|"
            + size.astype(str) + "|" + df["any_internet"].astype(str))


def cem_weights(df: pd.DataFrame, exposure: str) -> pd.Series:
    """Weights that balance treated and control totals inside every retained cell."""
    cell = coarsen(df)
    tab = df.assign(cell=cell).groupby(["cell", exposure], observed=True)["weight"].sum()
    tab = tab.unstack(exposure).dropna()
    tab = tab[(tab[0] > 0) & (tab[1] > 0)]
    keep = set(tab.index)

    # Controls in each retained cell are scaled so their weighted total equals the
    # treated total there; treated households keep their survey weight.
    ratio = (tab[1] / tab[0]).to_dict()
    w = df["weight"].copy()
    in_cell = cell.isin(keep)
    is_control = df[exposure] == 0
    scale = cell.map(ratio)
    w = w.where(~(in_cell & is_control), w * scale)
    return w.where(in_cell, 0.0)


def e_value(rr: float) -> float:
    """E-value for an observed risk ratio (VanderWeele & Ding 2017)."""
    rr = rr if rr >= 1 else 1.0 / rr
    return rr + np.sqrt(rr * (rr - 1.0))


def main() -> int:
    TABLES.mkdir(parents=True, exist_ok=True)
    df = pd.read_parquet(BUILD / "analysis_households.parquet")
    df = df[df["val_food_total_pc"].notna()].copy()

    w_cem = cem_weights(df, "online_food_any")
    matched = df.assign(cem_weight=w_cem)
    matched = matched[matched["cem_weight"] > 0]

    n_treated_total = int((df["online_food_any"] == 1).sum())
    n_treated_kept = int((matched["online_food_any"] == 1).sum())
    print(f"coarsened exact matching")
    print(f"  cells retained            : {coarsen(matched).nunique():,}")
    print(f"  households retained       : {len(matched):,} of {len(df):,}")
    print(f"  online households retained: {n_treated_kept:,} of {n_treated_total:,} "
          f"({100*n_treated_kept/n_treated_total:.1f}%)\n")

    # Balance check on the matching covariates and on covariates not matched on.
    balance = []
    df["max_edu_years"] = df["max_edu_years"].fillna(0.0)
    matched["max_edu_years"] = matched["max_edu_years"].fillna(0.0)
    for var in ["log_mpce", "max_edu_years", "P_F", "any_internet", "mean_age",
                "share_female", "owns_land", "clean_cooking_fuel", "pds_user"]:
        rows = {}
        for tag, frame, wcol in [("unmatched", df, "weight"),
                                 ("matched", matched, "cem_weight")]:
            on = frame[frame["online_food_any"] == 1]
            off = frame[frame["online_food_any"] == 0]
            m1 = np.average(on[var].astype(float), weights=on[wcol])
            m0 = np.average(off[var].astype(float), weights=off[wcol])
            sd = frame[var].astype(float).std()
            rows[tag] = (m1 - m0) / sd if sd else np.nan
        balance.append({"variable": var, "std_diff_unmatched": rows["unmatched"],
                        "std_diff_matched": rows["matched"]})
    bal = pd.DataFrame(balance)
    bal.to_csv(TABLES / "t8_cem_balance.csv", index=False)
    print("standardised differences (online minus offline, in SD units)")
    print(f"  {'variable':<22}{'unmatched':>11}{'matched':>10}")
    for _, r in bal.iterrows():
        print(f"  {r['variable']:<22}{r['std_diff_unmatched']:>11.3f}"
              f"{r['std_diff_matched']:>10.3f}")

    print("\nmatched contrast in food budget shares (percentage points)")
    rows = []
    for outcome, pretty in SHARE_OUTCOMES:
        on = matched[matched["online_food_any"] == 1]
        off = matched[matched["online_food_any"] == 0]
        # The matching weight replaces the survey weight here, so the contrast is the
        # within-cell one; the design structure still drives the variance.
        e1 = survey.mean(on[outcome], on["cem_weight"], on["stratum_vce"], on["psu"])
        e0 = survey.mean(off[outcome], off["cem_weight"], off["stratum_vce"], off["psu"])
        diff, se, p = survey.difference(e1, e0)
        rows.append({"outcome": outcome, "label": pretty,
                     "share_online": e1.value, "share_offline": e0.value,
                     "difference_pp": 100 * diff, "se_pp": 100 * se, "p": p,
                     "n_online": e1.n, "n_offline": e0.n})
        print(f"  {pretty:<26} online {100*e1.value:6.2f}%  offline {100*e0.value:6.2f}%"
              f"  diff {100*diff:+6.3f} pp  p={p:.2e}")
    cem = pd.DataFrame(rows)
    cem.to_csv(TABLES / "t9_cem_shares.csv", index=False)

    # E-values, computed on the ratio of shares, which is the risk-ratio analogue for
    # a bounded non-negative outcome.
    print("\nE-values for the matched contrasts")
    ev = []
    for _, r in cem.iterrows():
        if r["share_offline"] <= 0:
            continue
        rr = r["share_online"] / r["share_offline"]
        ev.append({"label": r["label"], "ratio_of_shares": rr,
                   "e_value": e_value(rr)})
        print(f"  {r['label']:<26} share ratio {rr:5.3f}  E-value {e_value(rr):5.2f}")
    pd.DataFrame(ev).to_csv(TABLES / "t10_evalues.csv", index=False)

    (LOGS / "robustness_run.json").write_text(json.dumps({
        "cem_cells": int(coarsen(matched).nunique()),
        "households_retained": int(len(matched)),
        "households_total": int(len(df)),
        "online_retained": n_treated_kept,
        "online_total": n_treated_total,
        "matching_variables": ["State", "sector", "mpce_decile", "education band",
                               "household size band", "any_internet"],
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

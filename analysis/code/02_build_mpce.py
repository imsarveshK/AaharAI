"""
Build household monthly per capita consumption expenditure (MPCE) from HCES 2023-24.

Follows the official procedure in `data/raw/hces/hces_2023_24_estimation_method.pdf`,
section 3.5:

    TE   = E1 + (E2 / P2) * P1 + (E3 / P3) * P1
    MPCE = TE / P1

where E1, E2, E3 are total expenditure compiled from the FDQ (food), CSQ
(consumables & services) and DGQ (durables) questionnaires, and P1, P2, P3 are the
household sizes recorded when each questionnaire was canvassed. Household size from
the food questionnaire (P1) is the divisor, as the methodology specifies.

Section subtotals live in Level 14 in their own reference period, so each is first
scaled to a 30-day equivalent. Reference periods are taken from the section headings
of `data/raw/hces/hces_2023_24_questionnaire.pdf` and recorded in REFERENCE_DAYS.

The headline series excludes imputed rent (item 539), which reproduces the ministry's
published "without imputation" MPCE for 2023-24 to within a rupee. A second series
including imputed rent is retained only as a sensitivity check; it is NOT the
ministry's "with imputation" series, which instead adds the imputed value of items
received free through social welfare programmes.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
BUILD = ROOT / "analysis/build"
LOGS = ROOT / "analysis/logs"

# Reference period in days for every (questionnaire, section) subtotal in Level 14.
# Source: section headings of the HCES 2023-24 questionnaire.
REFERENCE_DAYS = {
    ("F", "5.1"): 30, ("F", "5.2"): 30, ("F", "5.3"): 30,
    ("F", "6.1"): 7, ("F", "6.2"): 7, ("F", "6.3"): 7, ("F", "6.4"): 7,
    ("F", "6.5"): 7, ("F", "6.6"): 7, ("F", "6.7"): 7, ("F", "6.8"): 7,
    ("F", "7.1"): 7, ("F", "7.2"): 7,
    ("C", "8.1"): 30, ("C", "9.1"): 30, ("C", "9.2"): 30,
    ("C", "10.1"): 365, ("C", "10.2"): 365, ("C", "10.3"): 30,
    ("C", "11.1"): 30, ("C", "11.2"): 30, ("C", "11.3"): 30,
    ("C", "12.1"): 7, ("C", "12.2"): 7, ("C", "12.3"): 7,
    ("D", "13.1"): 365, ("D", "13.2"): 365, ("D", "13.3"): 365,
    ("D", "14.1"): 365, ("D", "14.2"): 365, ("D", "14.3"): 365,
    ("D", "14.4"): 365, ("D", "14.5"): 365, ("D", "14.6"): 365,
    ("D", "14.7"): 365, ("D", "14.8"): 365, ("D", "14.9"): 365,
    ("D", "14.10"): 365,
}

# Section 11.4 mixes reference periods, so it is resolved per item rather than per
# section: rent subtotal and imputed rent are 30-day, other taxes & cesses 365-day.
SECTION_11_4_DAYS = {"529": 30, "539": 30, "899": 365}

IMPUTED_RENT_ITEM = "539"

# Published all-India averages for 2023-24, the reconciliation target for the headline
# series. Source: NSS Report no. 592, Highlights, "Comparison of average MPCE (in Rs.):
# Without and With imputation in nominal and real price: All-India".
# The corresponding 2022-23 figures (rural 3,773 / urban 6,459) are a different survey
# round and must not be used here.
PUBLISHED_MPCE_2023_24_WITHOUT_IMPUTATION = {"rural": 4122.0, "urban": 6996.0}

# Reconciliation is asserted, not merely reported: a drift beyond this tolerance means
# the reference-period map or the aggregation has broken and the build should fail.
RECONCILIATION_TOLERANCE_PCT = 0.05


def reference_days(row_q: pd.Series, row_s: pd.Series, row_i: pd.Series) -> pd.Series:
    """Vectorised reference-period lookup, resolving 11.4 by item code."""
    days = pd.Series(np.nan, index=row_q.index, dtype="float64")
    key = list(zip(row_q, row_s))
    days[:] = [REFERENCE_DAYS.get(k, np.nan) for k in key]
    is_114 = (row_q == "C") & (row_s == "11.4")
    days[is_114] = row_i[is_114].map(SECTION_11_4_DAYS).astype("float64")
    return days


def main() -> int:
    l14 = pd.read_parquet(BUILD / "hces_L14.parquet",
                          columns=["hh_id", "Questionnaire_No", "SECTION",
                                   "ITEM_CODE", "VALUE_RS"])
    l14["value"] = pd.to_numeric(l14["VALUE_RS"], errors="coerce")

    l14["ref_days"] = reference_days(l14["Questionnaire_No"], l14["SECTION"],
                                     l14["ITEM_CODE"])
    unmapped = l14["ref_days"].isna()
    if unmapped.any():
        combos = (l14.loc[unmapped, ["Questionnaire_No", "SECTION", "ITEM_CODE"]]
                  .drop_duplicates().to_dict("records"))
        raise ValueError(f"unmapped reference periods: {combos}")

    # Every subtotal expressed as a 30-day equivalent.
    l14["value_30d"] = l14["value"] * (30.0 / l14["ref_days"])

    # E1/E2/E3 by questionnaire, with and without imputed rent.
    is_imputed = l14["ITEM_CODE"] == IMPUTED_RENT_ITEM
    wide = (l14.assign(excl=l14["value_30d"].where(~is_imputed, 0.0))
            .groupby(["hh_id", "Questionnaire_No"], observed=True)
            .agg(incl=("value_30d", "sum"), excl=("excl", "sum"))
            .unstack("Questionnaire_No"))
    wide.columns = [f"E_{q}_{k}" for k, q in wide.columns]
    wide = wide.fillna(0.0)

    # Household size per questionnaire and the third-visit multiplier.
    l15 = pd.read_parquet(BUILD / "hces_L15.parquet",
                          columns=["hh_id", "Questionnaire_No", "VISIT",
                                   "HOUSEHOLD_SIZE", "MULTIPLIER",
                                   "ONLINE_EXPENDITURE", "VISIT_MONTH"])
    for col in ["HOUSEHOLD_SIZE", "MULTIPLIER", "ONLINE_EXPENDITURE"]:
        l15[col] = pd.to_numeric(l15[col], errors="coerce")

    sizes = (l15[l15["Questionnaire_No"].isin(["F", "C", "D"])]
             .pivot_table(index="hh_id", columns="Questionnaire_No",
                          values="HOUSEHOLD_SIZE", aggfunc="first"))
    sizes.columns = [f"P_{c}" for c in sizes.columns]

    # Online expenditure is questionnaire-specific (QA2.6 food, QB2.6 consumables
    # and services, QC2.6 durables), so keep the three separately.
    online = (l15[l15["Questionnaire_No"].isin(["F", "C", "D"])]
              .pivot_table(index="hh_id", columns="Questionnaire_No",
                           values="ONLINE_EXPENDITURE", aggfunc="first"))
    online.columns = [f"online_exp_{c}" for c in online.columns]

    third = l15[l15["VISIT"] == "3"].drop_duplicates("hh_id").set_index("hh_id")
    weights = third[["MULTIPLIER"]].rename(columns={"MULTIPLIER": "multiplier_v3"})

    # The month a household's food questionnaire was canvassed, for seasonality.
    fdq_month = (l15[l15["Questionnaire_No"] == "F"]
                 .drop_duplicates("hh_id").set_index("hh_id")[["VISIT_MONTH"]]
                 .rename(columns={"VISIT_MONTH": "fdq_month"}))

    df = wide.join([sizes, online, weights, fdq_month], how="outer")

    # Official formula. Households missing any questionnaire or with a zero size
    # cannot yield an MPCE and are flagged rather than imputed.
    complete = (df[["P_F", "P_C", "P_D"]].notna().all(axis=1)
                & (df[["P_F", "P_C", "P_D"]] > 0).all(axis=1))
    for tag in ["incl", "excl"]:
        te = (df[f"E_F_{tag}"]
              + df[f"E_C_{tag}"] / df["P_C"] * df["P_F"]
              + df[f"E_D_{tag}"] / df["P_D"] * df["P_F"])
        df[f"mpce_{tag}"] = np.where(complete, te / df["P_F"], np.nan)

    df["mpce_complete"] = complete
    df["weight"] = df["multiplier_v3"] / 100.0

    sector = (pd.read_parquet(BUILD / "hces_L01.parquet", columns=["hh_id", "Sector"])
              .drop_duplicates("hh_id").set_index("hh_id"))
    df = df.join(sector)
    df["sector"] = df["Sector"].map({"1": "rural", "2": "urban"})

    # Reconciliation against the published all-India averages. MPCE is a ratio
    # estimate (total expenditure over total persons), so the person-weighted mean
    # w * P_F is the right weight, not the household weight alone.
    report = {
        "published_2023_24_without_imputation": PUBLISHED_MPCE_2023_24_WITHOUT_IMPUTATION,
        "computed": {}, "households": {}, "deviation_pct": {},
    }
    for tag, label in [("excl", "headline_excl_imputed_rent"),
                       ("incl", "sensitivity_incl_imputed_rent")]:
        report["computed"][label] = {}
        for sec in ["rural", "urban"]:
            m = df[(df["sector"] == sec) & df["mpce_complete"]]
            wmean = np.average(m[f"mpce_{tag}"], weights=m["weight"] * m["P_F"])
            report["computed"][label][sec] = round(float(wmean), 2)

    report["households"]["total"] = int(len(df))
    report["households"]["mpce_complete"] = int(complete.sum())

    failures = []
    for sec in ["rural", "urban"]:
        pub = PUBLISHED_MPCE_2023_24_WITHOUT_IMPUTATION[sec]
        got = report["computed"]["headline_excl_imputed_rent"][sec]
        dev = 100.0 * (got - pub) / pub
        report["deviation_pct"][sec] = round(dev, 4)
        if abs(dev) > RECONCILIATION_TOLERANCE_PCT:
            failures.append(f"{sec}: computed {got} vs published {pub} ({dev:+.3f}%)")
    report["reconciled"] = not failures

    (LOGS / "mpce_reconciliation.json").write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))
    if failures:
        raise SystemExit("MPCE failed to reconcile with published values:\n  "
                         + "\n  ".join(failures))

    keep = ["mpce_incl", "mpce_excl", "mpce_complete", "weight", "multiplier_v3",
            "P_F", "P_C", "P_D", "sector", "fdq_month",
            "online_exp_F", "online_exp_C", "online_exp_D",
            "E_F_incl", "E_C_incl", "E_D_incl", "E_F_excl"]
    df[keep].to_parquet(BUILD / "hh_mpce.parquet")
    print(f"\nwrote {BUILD / 'hh_mpce.parquet'} ({len(df):,} households)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

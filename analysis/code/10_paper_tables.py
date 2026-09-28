"""Render the manuscript's numbered tables from the computed estimates."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
TABLES = ROOT / "analysis/output/tables"
OUT = ROOT / "paper"

CONT_LABELS = {
    "log_mpce": "Log monthly per capita consumption expenditure",
    "max_edu_years": "Highest education in household (years)",
    "any_internet": "Any member used internet (30 days)",
    "urban": "Urban residence",
    "log_hh_size": "Log household size",
    "share_female": "Share of members female",
    "n_children_u5": "Children under 5 (n)",
    "n_elderly_60p": "Members aged 60+ (n)",
    "mean_age": "Mean age of members (years)",
    "owns_land": "Owns land beyond homestead",
    "clean_cooking_fuel": "Clean cooking fuel",
    "pds_user": "Used public distribution system (30 days)",
}


def p_fmt(p: float) -> str:
    if p < 1e-16:
        return "<1e-16"
    if p < 0.001:
        return f"{p:.1e}"
    return f"{p:.3f}"


def table1() -> str:
    t = pd.read_csv(TABLES / "t1_sample_characteristics.csv", header=[0, 1])
    t.columns = ["characteristic", "unit", "est_all", "est_off", "est_on",
                 "se_all", "se_off", "se_on", "n_all", "n_off", "n_on"]
    t = t[t["characteristic"].notna() & (t["characteristic"] != "characteristic")]
    order = ["Urban residence", "MPCE", "Household size",
             "Highest education in household", "Any member used internet (30 d)",
             "Uses public distribution system", "Owns land", "Clean cooking fuel",
             "Food expenditure", "Vegetable quantity", "Food groups acquired"]
    t["__o"] = t["characteristic"].map({k: i for i, k in enumerate(order)})
    t = t.sort_values("__o")
    lines = ["| Characteristic | Unit | All households | Did not buy food online | Bought food online |",
             "|---|---|---:|---:|---:|"]
    for _, r in t.iterrows():
        f = (lambda v, s: f"{v:,.2f} ({s:,.2f})")
        lines.append(f"| {r['characteristic']} | {r['unit']} | "
                     f"{f(r['est_all'], r['se_all'])} | {f(r['est_off'], r['se_off'])} | "
                     f"{f(r['est_on'], r['se_on'])} |")
    n = t.iloc[0]
    lines.append(f"| Households (n) | count | {int(n['n_all']):,} | "
                 f"{int(n['n_off']):,} | {int(n['n_on']):,} |")
    return "\n".join(lines)


def table2() -> str:
    t = pd.read_csv(TABLES / "t2_adoption_prevalence.csv")
    piv = t.pivot(index="category", columns="domain", values=["pct", "se"])
    piv.columns = [f"{a}_{b}" for a, b in piv.columns]
    piv = piv.reset_index()
    order = ["Any online purchase", "Any service or consumable", "Any durable good",
             "Any food category", "Groceries", "Milk", "Vegetables", "Fresh fruits",
             "Dry fruits", "Egg, fish and meat", "Served processed food",
             "Packaged processed food", "Other food items",
             "Any fresh (veg or fruit)", "Any processed"]
    piv["__o"] = piv["category"].map({k: i for i, k in enumerate(order)})
    piv = piv.sort_values("__o")
    lines = ["| Category | All (%) | Rural (%) | Urban (%) |", "|---|---:|---:|---:|"]
    for _, r in piv.iterrows():
        cells = " | ".join(f"{r[f'pct_{d}']:.2f} ({r[f'se_{d}']:.2f})"
                           for d in ["all", "rural", "urban"])
        lines.append(f"| {r['category']} | {cells} |")
    return "\n".join(lines)


def table3() -> str:
    t = pd.read_csv(TABLES / "t3_adoption_model.csv")
    lines = ["| Covariate | Odds ratio | 95% CI | p |", "|---|---:|---|---:|"]
    for term, label in CONT_LABELS.items():
        r = t[t["term"] == term]
        if r.empty:
            continue
        r = r.iloc[0]
        lines.append(f"| {label} | {r['estimate']:.3f} | "
                     f"{r['ci_low']:.3f}–{r['ci_high']:.3f} | {p_fmt(r['p'])} |")
    for prefix, head in [("social_group_", "Social group"), ("religion_", "Religion"),
                         ("household_type_", "Household type")]:
        sub = t[t["term"].str.startswith(prefix)]
        for _, r in sub.iterrows():
            name = r["term"].removeprefix(prefix)
            lines.append(f"| {head}: {name} | {r['estimate']:.3f} | "
                         f"{r['ci_low']:.3f}–{r['ci_high']:.3f} | {p_fmt(r['p'])} |")
    n = int(t["n"].iloc[0]); nc = int(t["n_clusters"].iloc[0])
    lines.append(f"| *Observations / PSU clusters* | {n:,} | {nc:,} | |")
    return "\n".join(lines)


def table4() -> str:
    main = pd.read_csv(TABLES / "t4_budget_shares.csv")
    cem = pd.read_csv(TABLES / "t9_cem_shares.csv").set_index("outcome")
    ev = pd.read_csv(TABLES / "t10_evalues.csv").set_index("label")
    lines = ["| Food group | Adjusted difference (pp) | 95% CI | p | Matched difference (pp) | Matched p | E-value |",
             "|---|---:|---|---:|---:|---:|---:|"]
    for _, r in main.sort_values("estimate", ascending=False).iterrows():
        c = cem.loc[r["outcome"]]
        e = ev.loc[r["label"], "e_value"] if r["label"] in ev.index else float("nan")
        lines.append(
            f"| {r['label']} | {100*r['estimate']:+.2f} | "
            f"{100*r['ci_low']:+.2f} to {100*r['ci_high']:+.2f} | {p_fmt(r['p'])} | "
            f"{c['difference_pp']:+.2f} | {p_fmt(c['p'])} | {e:.2f} |")
    lines.append(f"| *Observations* | {int(main['n'].iloc[0]):,} | | | "
                 f"{int(cem['n_online'].iloc[0] + cem['n_offline'].iloc[0]):,} | | |")
    return "\n".join(lines)


def table5() -> str:
    # The unweighted non-buyer mean that the model object carries is dropped here:
    # for the log outcomes it is a mean of logs, which reads as a level and is not
    # one, and Table 1 already reports the weighted levels.
    t = pd.read_csv(TABLES / "t5_levels.csv")
    lines = ["| Outcome | Difference | 95% CI | p |", "|---|---:|---|---:|"]
    for _, r in t.iterrows():
        lines.append(f"| {r['label']} | {r['estimate']:+.4f} | "
                     f"{r['ci_low']:+.4f} to {r['ci_high']:+.4f} | {p_fmt(r['p'])} |")
    return "\n".join(lines)


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    doc = ["# Tables", "",
           "All estimates are survey-weighted. Standard errors, in parentheses or as",
           "intervals, are Taylor-linearised and clustered on the primary sampling unit.",
           "",
           "## Table 1. Household characteristics by online food purchase status",
           "", table1(), "",
           "Cells are weighted estimates with design-based standard errors in parentheses.",
           "",
           "## Table 2. Prevalence of online purchasing, by domain and sector",
           "", table2(), "",
           "Groceries was asked over a 30-day reference period; the other eight food",
           "categories over 7 days, so groceries is not directly comparable with them.",
           "",
           "## Table 3. Adoption of online food purchasing (weighted logistic regression)",
           "", table3(), "",
           "Reference levels: social group Others, religion Hinduism, household type Others.",
           "State and survey-month fixed effects included and not shown.",
           "",
           "## Table 4. Food budget composition (percentage points of the food budget)",
           "", table4(), "",
           "Adjusted differences are coefficients on any online food purchase from weighted",
           "linear models with the full covariate set plus state and survey-month fixed",
           "effects. Matched differences come from coarsened exact matching on state,",
           "sector, MPCE decile, education band, household-size band and household internet",
           "use. E-values are computed on the ratio of matched shares.",
           "",
           "## Table 5. Levels, quantities and unit values",
           "", table5(), "",
           "Log outcomes are natural logs of one plus the per-capita 30-day value, so",
           "coefficients approximate proportional differences.", ""]
    (OUT / "tables.md").write_text("\n".join(doc))
    print("\n".join(doc[:4]))
    print(f"\nwrote {OUT / 'tables.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

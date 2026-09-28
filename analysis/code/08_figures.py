"""
Publication figures.

Committed to a single light appearance, since the destination is a printed journal
page. Colours are the validated three-slot categorical palette (blue / orange /
aqua); every mark that relies on the low-contrast aqua also carries a direct label,
which is the relief the palette validator requires. Series identity is never carried
by colour alone: each figure has a legend and direct labels.
"""
from __future__ import annotations

import sys
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import survey  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
BUILD = ROOT / "analysis/build"
TABLES = ROOT / "analysis/output/tables"
FIGURES = ROOT / "analysis/output/figures"

BLUE, ORANGE, AQUA = "#2a78d6", "#eb6834", "#1baf7a"
INK, INK2, INK3 = "#0b0b0b", "#52514e", "#8a8983"
GRID = "#e3e2dd"
SURFACE = "#ffffff"

mpl.rcParams.update({
    "figure.dpi": 150, "savefig.dpi": 300,
    "font.family": "sans-serif",
    "font.sans-serif": ["Helvetica Neue", "Helvetica", "Arial", "DejaVu Sans"],
    "font.size": 8, "axes.titlesize": 9, "axes.labelsize": 8,
    "axes.edgecolor": INK3, "axes.linewidth": 0.6, "axes.labelcolor": INK2,
    "axes.facecolor": SURFACE, "figure.facecolor": SURFACE,
    "xtick.color": INK2, "ytick.color": INK2,
    "xtick.labelsize": 7.5, "ytick.labelsize": 7.5,
    "xtick.major.width": 0.6, "ytick.major.width": 0.6,
    "legend.frameon": False, "legend.fontsize": 7.5,
    "grid.color": GRID, "grid.linewidth": 0.6,
    "savefig.bbox": "tight", "savefig.pad_inches": 0.02,
})


def despine(ax, left=False):
    for side in ["top", "right"] + (["left"] if left else []):
        ax.spines[side].set_visible(False)


def save(fig, name):
    FIGURES.mkdir(parents=True, exist_ok=True)
    for ext in ["pdf", "png"]:
        fig.savefig(FIGURES / f"{name}.{ext}")
    plt.close(fig)
    print(f"  wrote {name}.pdf / .png")


def fig1(df):
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(7.4, 3.0),
                                   gridspec_kw={"width_ratios": [1, 1.25]})

    # Panel A: breadth of online purchasing by domain and sector.
    domains = [("online_overall_any", "Any online\npurchase"),
               ("online_services_any", "Services and\nbill payment"),
               ("online_durables_any", "Durable\ngoods"),
               ("online_food_any", "Food")]
    x = np.arange(len(domains))
    for i, (sec, colour, lab) in enumerate([("rural", AQUA, "Rural"),
                                            ("urban", BLUE, "Urban")]):
        g = df[df["sector"] == sec]
        vals, errs = [], []
        for col, _ in domains:
            e = survey.proportion(g[col], g["weight"], g["stratum_vce"], g["psu"])
            vals.append(100 * e.value)
            errs.append(100 * 1.96 * e.se)
        off = (i - 0.5) * 0.38
        ax1.bar(x + off, vals, 0.36, color=colour, label=lab, zorder=3,
                linewidth=0.8, edgecolor=SURFACE)
        ax1.errorbar(x + off, vals, yerr=errs, fmt="none", ecolor=INK2,
                     elinewidth=0.7, capsize=1.6, zorder=4)
        for xi, v in zip(x + off, vals):
            ax1.text(xi, v + 2.2, f"{v:.0f}", ha="center", va="bottom",
                     fontsize=7, color=INK2)
    ax1.set_xticks(x)
    ax1.set_xticklabels([lab for _, lab in domains], fontsize=7.2)
    ax1.set_ylabel("Households (%)")
    ax1.set_ylim(0, 78)
    ax1.yaxis.grid(True, zorder=0)
    ax1.set_axisbelow(True)
    despine(ax1)
    ax1.legend(loc="upper right", ncol=1)
    ax1.set_title("A  Broad online reach, narrow food reach",
                  loc="left", color=INK, fontweight="bold")

    # Panel B: the income gradient, fresh versus processed.
    t2b = pd.read_csv(TABLES / "t2b_adoption_by_decile.csv")
    series = [("any_pct", "any_se", BLUE, "Any food category"),
              ("processed_any_pct", "processed_any_se", ORANGE,
               "Processed or packaged food"),
              ("fresh_any_pct", "fresh_any_se", AQUA, "Fresh vegetables or fruit")]
    for col, se, colour, lab in series:
        y = t2b[col].to_numpy()
        e = 1.96 * t2b[se].to_numpy()
        ax2.plot(t2b["mpce_decile"], y, color=colour, lw=2.0, marker="o",
                 ms=4.5, label=lab, zorder=3, mec=SURFACE, mew=0.8)
        ax2.fill_between(t2b["mpce_decile"], y - e, y + e, color=colour,
                         alpha=0.14, lw=0, zorder=2)
    for col, colour, dy in [("any_pct", BLUE, 1.6), ("processed_any_pct", ORANGE, 1.2),
                            ("fresh_any_pct", AQUA, -2.4)]:
        v = t2b[col].iloc[-1]
        ax2.text(10.15, v + dy, f"{v:.1f}%", color=colour, fontsize=7.5,
                 fontweight="bold", va="center")
    ax2.set_xticks(range(1, 11))
    ax2.set_xlabel("Decile of monthly per capita consumption expenditure")
    ax2.set_ylabel("Households (%)")
    ax2.set_xlim(0.6, 11.2)
    ax2.set_ylim(0, 27)
    ax2.yaxis.grid(True, zorder=0)
    ax2.set_axisbelow(True)
    despine(ax2)
    ax2.legend(loc="upper left")
    ax2.set_title("B  Steep income gradient, steeper for processed food",
                  loc="left", color=INK, fontweight="bold")
    fig.tight_layout(w_pad=2.0)
    save(fig, "fig1_adoption")


def fig2():
    t2c = pd.read_csv(TABLES / "t2c_category_mix_adopters.csv")
    kind = {"Vegetables": "fresh", "Fresh fruits": "fresh", "Milk": "fresh",
            "Egg, fish and meat": "fresh", "Dry fruits": "staple",
            "Groceries": "staple", "Other food items": "staple",
            "Served processed food": "processed",
            "Packaged processed food": "processed"}
    colour = {"fresh": AQUA, "processed": ORANGE, "staple": BLUE}
    t2c["kind"] = t2c["category"].map(kind)
    t2c = t2c.sort_values("pct_of_adopters")

    fig, ax = plt.subplots(figsize=(5.6, 3.3))
    y = np.arange(len(t2c))
    ax.barh(y, t2c["pct_of_adopters"], 0.66,
            color=[colour[k] for k in t2c["kind"]], zorder=3,
            edgecolor=SURFACE, linewidth=0.8)
    ax.errorbar(t2c["pct_of_adopters"], y, xerr=1.96 * t2c["se"], fmt="none",
                ecolor=INK2, elinewidth=0.7, capsize=1.6, zorder=4)
    # Labels sit clear of the interval cap, not the point, so they never collide.
    for yi, v, se in zip(y, t2c["pct_of_adopters"], t2c["se"]):
        ax.text(v + 1.96 * se + 1.4, yi, f"{v:.1f}%", va="center", fontsize=7.2,
                color=INK2)
    ax.set_yticks(y)
    # Groceries alone was asked over 30 days; every other category over 7 days. A
    # longer window mechanically lifts it, so it is marked as not directly comparable.
    labels = [f"{c} †" if c == "Groceries" else c for c in t2c["category"]]
    ax.set_yticklabels(labels, fontsize=7.5)
    ax.set_xlabel("Share of households that bought any food online (%)")
    ax.annotate("† asked over 30 days; all other categories over 7 days, "
                "so groceries is not directly comparable",
                xy=(0, -0.235), xycoords="axes fraction", fontsize=6.4,
                color=INK3, ha="left")
    ax.set_xlim(0, 72)
    ax.xaxis.grid(True, zorder=0)
    ax.set_axisbelow(True)
    despine(ax, left=True)
    ax.tick_params(axis="y", length=0)
    handles = [mpl.patches.Patch(color=colour[k], label=lab) for k, lab in
               [("staple", "Staples and other"), ("fresh", "Fresh and perishable"),
                ("processed", "Processed and packaged")]]
    ax.legend(handles=handles, loc="lower right")
    ax.set_title("Among online food buyers, prepared food outranks fresh produce",
                 loc="left", color=INK, fontweight="bold")
    fig.tight_layout(rect=[0, 0.055, 1, 1])
    save(fig, "fig2_category_mix")


def fig3():
    t4 = pd.read_csv(TABLES / "t4_budget_shares.csv")
    t4 = t4.sort_values("estimate")
    fig, ax = plt.subplots(figsize=(5.8, 3.4))
    y = np.arange(len(t4))
    est = 100 * t4["estimate"].to_numpy()
    lo = 100 * t4["ci_low"].to_numpy()
    hi = 100 * t4["ci_high"].to_numpy()
    sig = t4["p"].to_numpy() < 0.05
    cols = [ORANGE if (e > 0 and s) else BLUE if (e < 0 and s) else INK3
            for e, s in zip(est, sig)]
    ax.axvline(0, color=INK3, lw=0.8, zorder=2)
    ax.hlines(y, lo, hi, color=cols, lw=1.6, zorder=3)
    ax.scatter(est, y, s=34, color=cols, zorder=4, edgecolor=SURFACE, linewidth=0.8)
    for yi, e, h, s in zip(y, est, hi, sig):
        ax.text(h + 0.09, yi, f"{e:+.2f}{'' if s else ' n.s.'}", va="center",
                fontsize=7, color=INK2)
    ax.set_yticks(y)
    ax.set_yticklabels(t4["label"], fontsize=7.5)
    ax.set_xlabel("Difference in share of the food budget (percentage points)")
    ax.set_xlim(-1.4, 2.9)
    ax.xaxis.grid(True, zorder=0)
    ax.set_axisbelow(True)
    despine(ax, left=True)
    ax.tick_params(axis="y", length=0)
    handles = [mpl.patches.Patch(color=ORANGE, label="Higher among online buyers"),
               mpl.patches.Patch(color=BLUE, label="Lower among online buyers"),
               mpl.patches.Patch(color=INK3, label="Not significant at 5%")]
    ax.legend(handles=handles, loc="lower right")
    ax.set_title("Online food buying reallocates the food budget toward packaged food",
                 loc="left", color=INK, fontweight="bold")
    fig.tight_layout()
    save(fig, "fig3_budget_shares")


def fig4():
    # Every specification here is a binary online-versus-not contrast, so all five
    # sit on one percentage-point scale. The continuous-exposure model is deliberately
    # excluded: its coefficient is per log-unit of spend and is not comparable, and
    # placing it on this axis would misread as a much smaller effect.
    specs = [("t4_budget_shares.csv", "Main"),
             ("t6b_budget_shares_7d_exposure.csv", "7-day categories only"),
             ("t6c_budget_shares_expenditure_exposure.csv", "Expenditure-based"),
             ("t7_budget_shares_urban.csv", "Urban only"),
             ("t9_cem_shares.csv", "Matched (CEM)")]
    targets = [("share_vegetables", "Vegetables", BLUE),
               ("share_packaged_processed_food", "Packaged processed food", ORANGE)]
    fig, axes = plt.subplots(1, 2, figsize=(7.4, 2.7), sharey=True)
    for ax, (outcome, pretty, colour) in zip(axes, targets):
        rows = []
        for fname, lab in specs:
            t = pd.read_csv(TABLES / fname)
            r = t[t["outcome"] == outcome].iloc[0]
            if "difference_pp" in t.columns:      # matched table is already in points
                est = r["difference_pp"]
                half = 1.96 * r["se_pp"]
                lo, hi = est - half, est + half
            else:
                est, lo, hi = 100 * r["estimate"], 100 * r["ci_low"], 100 * r["ci_high"]
            rows.append((lab, est, lo, hi, r["p"]))
        y = np.arange(len(rows))[::-1]
        est = [r[1] for r in rows]
        lo = [r[2] for r in rows]
        hi = [r[3] for r in rows]
        ax.axvline(0, color=INK3, lw=0.8, zorder=2)
        ax.hlines(y, lo, hi, color=colour, lw=1.6, zorder=3)
        ax.scatter(est, y, s=32, color=colour, zorder=4, edgecolor=SURFACE,
                   linewidth=0.8)
        for yi, e in zip(y, est):
            ax.text(e, yi + 0.28, f"{e:+.2f}", ha="center", fontsize=6.8,
                    color=INK2)
        ax.set_yticks(y)
        ax.set_yticklabels([r[0] for r in rows], fontsize=7.2)
        ax.set_xlabel("Percentage points")
        ax.xaxis.grid(True, zorder=0)
        ax.set_axisbelow(True)
        despine(ax, left=True)
        ax.tick_params(axis="y", length=0)
        ax.set_title(pretty, loc="left", color=INK, fontweight="bold")
    axes[0].set_ylim(-0.7, len(specs) - 0.2)
    fig.suptitle("The two headline shifts hold across exposure definitions and samples",
                 x=0.005, ha="left", fontsize=9, fontweight="bold", color=INK)
    fig.tight_layout(rect=[0, 0, 1, 0.93], w_pad=2.2)
    save(fig, "fig4_robustness")


def main() -> int:
    df = pd.read_parquet(BUILD / "analysis_households.parquet")
    df = df[df["val_food_total_pc"].notna()].copy()
    print("figures:")
    fig1(df)
    fig2()
    fig3()
    fig4()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

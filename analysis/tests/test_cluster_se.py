"""Check that the reported cluster-robust standard errors are the design-based ones.

statsmodels emits a SpecificationWarning when a cluster covariance is combined with
freq_weights. This test confirms the warning is benign for the weighted logistic used
throughout the analysis, by recomputing the pseudo-maximum-likelihood sandwich

    V = A^-1 B A^-1,  A = X' diag(w * mu * (1 - mu)) X,  B = sum_c s_c s_c'

with s_c the PSU-level sum of weighted scores, and comparing it to what is reported.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.api as sm

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))
import models  # noqa: E402

BUILD = Path(__file__).resolve().parents[2] / "analysis/build"
CONTINUOUS = ["log_mpce", "max_edu_years", "any_internet", "urban", "log_hh_size"]
CATEGORICAL = ["social_group"]


def _sample() -> pd.DataFrame:
    df = pd.read_parquet(BUILD / "analysis_households.parquet")
    df = df[df["val_food_total_pc"].notna()].copy()
    df["urban"] = (df["sector"] == "urban").astype(float)
    df["log_hh_size"] = np.log(df["P_F"].clip(lower=1))
    df["max_edu_years"] = df["max_edu_years"].fillna(0)
    return df[["online_food_any", "weight", "psu"] + CONTINUOUS + CATEGORICAL].dropna()


def test_cluster_se_matches_manual_sandwich() -> None:
    d = _sample()
    X = models.design_matrix(d, CONTINUOUS, CATEGORICAL).astype(float)
    y = d["online_food_any"].astype(float).to_numpy()
    w = (d["weight"] / d["weight"].mean()).to_numpy()
    groups = d["psu"].to_numpy()

    res = sm.GLM(y, X, family=sm.families.Binomial(), freq_weights=w).fit(
        cov_type="cluster", cov_kwds={"groups": groups})

    mu = np.asarray(res.fittedvalues)
    Xv = X.to_numpy()
    A = Xv.T @ (Xv * (w * mu * (1 - mu))[:, None])
    scores = pd.DataFrame(Xv * (w * (y - mu))[:, None]).groupby(groups).sum().to_numpy()
    A_inv = np.linalg.inv(A)
    manual = np.sqrt(np.diag(A_inv @ (scores.T @ scores) @ A_inv))

    ratio = np.asarray(res.bse) / manual
    assert np.allclose(ratio, 1.0, atol=5e-4), f"SE ratio out of tolerance: {ratio}"

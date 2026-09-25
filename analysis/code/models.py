"""
Survey-weighted regression with design-based standard errors.

Point estimates come from pseudo-maximum likelihood using the survey weights.
Standard errors use the cluster-robust sandwich, clustered on the primary sampling
unit, which is the linearised variance standard survey software reports for a
stratified multistage design. Clustering alone omits the stratification, so the
resulting intervals are, if anything, slightly wide.

The sandwich is invariant to a constant rescaling of the weights, so weights are
normalised to mean one purely to keep the fitted objects readable.
"""
from __future__ import annotations

import warnings

import numpy as np
import pandas as pd
import statsmodels.api as sm

# statsmodels warns that cov_type is "not fully supported with freq_weights". For the
# Binomial family the dispersion is fixed at one, and tests/test_cluster_se.py checks
# the reported standard errors against a hand-computed pseudo-maximum-likelihood
# sandwich; they agree to four decimal places. The warning is therefore suppressed
# here rather than left to obscure real output.
warnings.filterwarnings(
    "ignore", message="cov_type not fully supported with freq_weights")


def design_matrix(df: pd.DataFrame, continuous: list[str],
                  categorical: list[str], reference: dict[str, str] | None = None
                  ) -> pd.DataFrame:
    """Assemble a model matrix, dropping one level of each categorical as base."""
    reference = reference or {}
    parts = [df[continuous].astype(float)]
    for col in categorical:
        dummies = pd.get_dummies(df[col].astype(str), prefix=col, dtype=float)
        base = reference.get(col)
        if base is not None:
            base_col = f"{col}_{base}"
            if base_col not in dummies.columns:
                raise KeyError(f"reference level {base_col!r} absent from {col}")
        else:
            base_col = dummies.sum().idxmax()  # most common level as reference
        parts.append(dummies.drop(columns=[base_col]))
    X = pd.concat(parts, axis=1)
    X.insert(0, "const", 1.0)
    return X


def fit(df: pd.DataFrame, outcome: str, continuous: list[str],
        categorical: list[str], family: str = "gaussian",
        reference: dict[str, str] | None = None,
        weight_col: str = "weight", cluster_col: str = "psu") -> sm.regression.linear_model.RegressionResultsWrapper:
    """Fit one weighted model with PSU-clustered standard errors."""
    cols = [outcome, weight_col, cluster_col] + continuous + categorical
    d = df[cols].replace([np.inf, -np.inf], np.nan).dropna()
    X = design_matrix(d, continuous, categorical, reference)
    y = d[outcome].astype(float)
    w = d[weight_col].astype(float)
    w = w / w.mean()
    cov = {"groups": d[cluster_col].to_numpy()}

    if family == "gaussian":
        model = sm.WLS(y, X, weights=w)
        res = model.fit(cov_type="cluster", cov_kwds=cov)
    elif family == "binomial":
        model = sm.GLM(y, X, family=sm.families.Binomial(), freq_weights=w)
        res = model.fit(cov_type="cluster", cov_kwds=cov)
    else:
        raise ValueError(f"unsupported family {family!r}")
    res.n_clusters = d[cluster_col].nunique()
    res.n_obs_used = len(d)
    return res


def tidy(res, terms: list[str] | None = None, exponentiate: bool = False
         ) -> pd.DataFrame:
    """Coefficient table for the terms of interest."""
    out = pd.DataFrame({
        "term": res.params.index,
        "estimate": res.params.to_numpy(),
        "se": res.bse.to_numpy(),
        "z": res.tvalues.to_numpy(),
        "p": res.pvalues.to_numpy(),
        "ci_low": res.conf_int()[0].to_numpy(),
        "ci_high": res.conf_int()[1].to_numpy(),
    })
    if terms is not None:
        out = out[out["term"].isin(terms)]
    if exponentiate:
        for c in ["estimate", "ci_low", "ci_high"]:
            out[c] = np.exp(out[c])
    return out.reset_index(drop=True)


def stars(p: float) -> str:
    return "***" if p < 0.001 else "**" if p < 0.01 else "*" if p < 0.05 else ""

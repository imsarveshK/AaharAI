"""
Design-based estimation for a stratified multistage sample.

Implements Taylor-series linearisation for weighted means, proportions and ratios,
with variance accumulated across primary sampling units within strata. This is the
with-replacement approximation used by standard survey software; it ignores the
finite population correction and is therefore mildly conservative relative to the
SRSWOR variance in the HCES estimation manual.

For a total, with stratum h, PSU i and household k:

    Y_hat  = sum_hik w_hik y_hik
    V(Y)   = sum_h  n_h/(n_h - 1) * sum_i (y_hi. - mean_i y_hi.)^2

where y_hi. is the weighted PSU subtotal. For a ratio R = Y/X the linearised
residual u = y - R*x replaces y, and V(R) = V(u) / X^2.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy import stats


@dataclass(frozen=True)
class Estimate:
    """A point estimate with its design-based standard error."""
    value: float
    se: float
    n: int
    n_psu: int
    deff: float | None = None

    @property
    def ci95(self) -> tuple[float, float]:
        return (self.value - 1.96 * self.se, self.value + 1.96 * self.se)

    @property
    def rse_pct(self) -> float:
        return 100.0 * self.se / self.value if self.value else float("nan")

    def fmt(self, digits: int = 3) -> str:
        lo, hi = self.ci95
        return f"{self.value:.{digits}f} ({lo:.{digits}f}, {hi:.{digits}f})"


def _psu_totals(y: np.ndarray, w: np.ndarray, strata: np.ndarray,
                psu: np.ndarray) -> pd.DataFrame:
    frame = pd.DataFrame({"wy": w * y, "stratum": strata, "psu": psu})
    return frame.groupby(["stratum", "psu"], observed=True, sort=False)["wy"].sum()


def _linearised_variance(u: np.ndarray, w: np.ndarray, strata: np.ndarray,
                         psu: np.ndarray) -> float:
    totals = _psu_totals(u, w, strata, psu)
    var = 0.0
    for _, vals in totals.groupby(level="stratum", observed=True, sort=False):
        n = len(vals)
        if n < 2:
            # A stratum contributing a single PSU adds no estimable variance.
            continue
        var += n / (n - 1.0) * float(((vals - vals.mean()) ** 2).sum())
    return var


def ratio(num: pd.Series, den: pd.Series, weight: pd.Series, strata: pd.Series,
          psu: pd.Series, deff: bool = False) -> Estimate:
    """Design-based ratio estimator R = sum(w*num) / sum(w*den)."""
    ok = num.notna() & den.notna() & weight.notna()
    y, x = num[ok].to_numpy(float), den[ok].to_numpy(float)
    w = weight[ok].to_numpy(float)
    s, p = strata[ok].to_numpy(), psu[ok].to_numpy()

    x_tot = float((w * x).sum())
    if x_tot == 0:
        return Estimate(float("nan"), float("nan"), int(ok.sum()), len(np.unique(p)))
    r = float((w * y).sum()) / x_tot
    var = _linearised_variance(y - r * x, w, s, p) / x_tot ** 2
    se = float(np.sqrt(max(var, 0.0)))

    d = None
    if deff:
        # Design effect against simple random sampling of the same size.
        mean = r
        srs_var = float(np.average((y / np.where(x == 0, np.nan, x) - mean) ** 2,
                                   weights=w)) / ok.sum() if (x != 0).all() else np.nan
        d = var / srs_var if srs_var and np.isfinite(srs_var) and srs_var > 0 else None
    return Estimate(r, se, int(ok.sum()), len(np.unique(p)), d)


def mean(value: pd.Series, weight: pd.Series, strata: pd.Series, psu: pd.Series,
         **kwargs) -> Estimate:
    """Weighted mean, i.e. the ratio of the weighted total to the weighted count."""
    den = pd.Series(1.0, index=value.index).where(value.notna())
    return ratio(value, den, weight, strata, psu, **kwargs)


def proportion(indicator: pd.Series, weight: pd.Series, strata: pd.Series,
               psu: pd.Series, **kwargs) -> Estimate:
    """Weighted proportion of a 0/1 indicator."""
    return mean(indicator.astype(float), weight, strata, psu, **kwargs)


def total(value: pd.Series, weight: pd.Series, strata: pd.Series,
          psu: pd.Series) -> Estimate:
    ok = value.notna() & weight.notna()
    y = value[ok].to_numpy(float)
    w = weight[ok].to_numpy(float)
    t = float((w * y).sum())
    var = _linearised_variance(y, w, strata[ok].to_numpy(), psu[ok].to_numpy())
    return Estimate(t, float(np.sqrt(max(var, 0.0))), int(ok.sum()),
                    len(np.unique(psu[ok].to_numpy())))


def difference(est_a: Estimate, est_b: Estimate) -> tuple[float, float, float]:
    """Difference between two independent domain estimates, with a two-sided p."""
    diff = est_a.value - est_b.value
    se = float(np.sqrt(est_a.se ** 2 + est_b.se ** 2))
    z = diff / se if se else float("nan")
    return diff, se, float(2 * (1 - stats.norm.cdf(abs(z))))


def by_group(df: pd.DataFrame, group: str, estimator, *args, **kwargs
             ) -> pd.DataFrame:
    """Apply an estimator within each level of `group`, returning a tidy frame."""
    rows = []
    for key, g in df.groupby(group, observed=True, sort=True):
        est = estimator(g, *args, **kwargs)
        rows.append({group: key, "estimate": est.value, "se": est.se,
                     "ci_low": est.ci95[0], "ci_high": est.ci95[1],
                     "rse_pct": est.rse_pct, "n": est.n, "n_psu": est.n_psu})
    return pd.DataFrame(rows)

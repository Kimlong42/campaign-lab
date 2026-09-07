"""Marketing-analytics checks on the campaign table.

Every function takes a DataFrame and returns a DataFrame or a plain number,
so each one is trivially testable. Nothing here reads from disk.
"""

from statistics import NormalDist

import pandas as pd

# ---------- data quality (run these BEFORE any analysis) ----------


def find_duplicates(df: pd.DataFrame) -> pd.DataFrame:
    """Rows that are exact copies of an earlier row."""
    return df[df.duplicated(keep="first")]


def find_revenue_without_conversion(df: pd.DataFrame) -> pd.DataFrame:
    """Revenue recorded for a customer who did not convert -> tracking bug."""
    return df[(df["converted"] == 0) & (df["revenue"] > 0)]


def clean(df: pd.DataFrame) -> pd.DataFrame:
    """Drop duplicates and zero out revenue that has no conversion behind it."""
    out = df.drop_duplicates(keep="first").copy()
    out.loc[out["converted"] == 0, "revenue"] = 0.0
    return out.reset_index(drop=True)


# ---------- Module 1: A/B test / causal inference ----------


def conversion_by_arm(df: pd.DataFrame) -> pd.DataFrame:
    """n, converters and conversion rate for control (0) and treatment (1)."""
    g = df.groupby("treatment")["converted"].agg(n="size", converters="sum")
    g["rate"] = g["converters"] / g["n"]
    return g


def ate(df: pd.DataFrame) -> float:
    """Average treatment effect = rate(treatment) - rate(control)."""
    rates = conversion_by_arm(df)["rate"]
    return float(rates.loc[1] - rates.loc[0])


def two_proportion_ztest(df: pd.DataFrame) -> tuple[float, float]:
    """Pooled two-proportion z-test. Returns (z, two-sided p-value)."""
    g = conversion_by_arm(df)
    n0, n1 = g.loc[0, "n"], g.loc[1, "n"]
    x0, x1 = g.loc[0, "converters"], g.loc[1, "converters"]
    p_pool = (x0 + x1) / (n0 + n1)
    se = (p_pool * (1 - p_pool) * (1 / n0 + 1 / n1)) ** 0.5
    z = (x1 / n1 - x0 / n0) / se
    p = 2 * (1 - NormalDist().cdf(abs(z)))
    return float(z), float(p)


def uplift_by_segment(df: pd.DataFrame) -> pd.DataFrame:
    """Conversion rate per segment x arm, plus the per-segment uplift (CATE)."""
    tab = df.pivot_table(index="segment", columns="treatment", values="converted", aggfunc="mean")
    tab.columns = ["control", "treatment"]
    tab["uplift"] = tab["treatment"] - tab["control"]
    return tab


def check_randomization(df: pd.DataFrame) -> pd.DataFrame:
    """Segment mix should be (near-)identical across arms if assignment was random."""
    return pd.crosstab(df["segment"], df["treatment"], normalize="columns")


# ---------- Module 4: RFM segmentation ----------


def rfm_scores(df: pd.DataFrame, bins: int = 5) -> pd.DataFrame:
    """R, F, M scores 1..bins. Low recency is GOOD, so R is reversed."""
    out = df[["customer_id", "recency_days", "frequency", "monetary"]].copy()
    out["R"] = pd.qcut(out["recency_days"].rank(method="first"), bins, labels=range(bins, 0, -1))
    out["F"] = pd.qcut(out["frequency"].rank(method="first"), bins, labels=range(1, bins + 1))
    out["M"] = pd.qcut(out["monetary"].rank(method="first"), bins, labels=range(1, bins + 1))
    out[["R", "F", "M"]] = out[["R", "F", "M"]].astype(int)
    out["rfm_score"] = out["R"] + out["F"] + out["M"]
    return out


# ---------- Module 3: text (keyword level) ----------


def count_keyword(df: pd.DataFrame, keyword: str) -> int:
    """Number of feedback rows containing ``keyword`` (case-insensitive)."""
    return int(df["feedback"].fillna("").str.contains(keyword, case=False).sum())

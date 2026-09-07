"""Generate a synthetic email-campaign A/B test with planted effects and anomalies.

Design choice: outcomes are assigned by *quota*, not by Bernoulli draws.
In each (segment, treatment) cell exactly ``round(n * rate)`` customers convert,
so the observed conversion rate equals the planted rate and tests can assert
exact uplift numbers instead of confidence intervals.
"""

from pathlib import Path

import numpy as np
import pandas as pd

SEED = 42
N_CUSTOMERS = 4000  # 2000 control + 2000 treatment, exactly

# Segment shares (must sum to 1 and give integer counts per arm).
SEGMENT_SHARE = {"New": 0.40, "Regular": 0.40, "VIP": 0.20}

# Planted conversion rates per segment: control vs treatment.
# VIP has NO uplift on purpose -> heterogeneous treatment effect.
CONV_RATE = {
    "New": {0: 0.05, 1: 0.08},
    "Regular": {0: 0.10, 1: 0.15},
    "VIP": {0: 0.20, 1: 0.20},
}
# => control 200/2000 = 0.100, treatment 264/2000 = 0.132, ATE = +0.032

# Mean order value of converters, by segment (log-normal).
AOV_MEDIAN = {"New": 40.0, "Regular": 70.0, "VIP": 150.0}

CHANNELS = ["Email", "SMS", "Push"]

# Planted anomalies (exact counts)
N_DUPLICATES = 20  # full-row duplicates appended
N_REVENUE_WITHOUT_CONVERSION = 15  # converted == 0 but revenue > 0
N_REFUND_FEEDBACK = 30  # feedback text mentioning "refund"

FEEDBACK_TEMPLATES = [
    "great offer, bought right away",
    "did not open the email",
    "not interested this time",
    "nice discount, will buy again",
    "too many messages lately",
    "",
]
REFUND_TEXT = "asked for a refund after purchase"

OUT_PATH = Path("data/campaign.csv")


def _exact_split(n: int, shares: dict[str, float]) -> list[str]:
    counts = {k: round(n * v) for k, v in shares.items()}
    assert sum(counts.values()) == n, "segment shares must give integer counts"
    labels: list[str] = []
    for k, c in counts.items():
        labels.extend([k] * c)
    return labels


def make_customers(rng: np.random.Generator) -> pd.DataFrame:
    n_arm = N_CUSTOMERS // 2
    rows = []
    for treatment in (0, 1):
        segments = _exact_split(n_arm, SEGMENT_SHARE)
        rng.shuffle(segments)
        for seg in segments:
            rows.append({"treatment": treatment, "segment": seg})
    df = pd.DataFrame(rows)
    df = df.sample(frac=1.0, random_state=SEED).reset_index(drop=True)
    df.insert(0, "customer_id", [f"C{i:05d}" for i in range(1, len(df) + 1)])

    df["channel"] = rng.choice(CHANNELS, size=len(df), p=[0.6, 0.25, 0.15])
    df["recency_days"] = rng.integers(1, 365, size=len(df))
    df["frequency"] = rng.integers(1, 12, size=len(df))
    df["monetary"] = np.round(rng.gamma(shape=2.0, scale=60.0, size=len(df)), 2)
    df["send_date"] = pd.Timestamp("2025-03-01")
    return df


def plant_outcomes(df: pd.DataFrame, rng: np.random.Generator) -> pd.DataFrame:
    df = df.copy()
    df["converted"] = 0
    df["revenue"] = 0.0
    for seg, rates in CONV_RATE.items():
        for treat, rate in rates.items():
            cell = df.index[(df["segment"] == seg) & (df["treatment"] == treat)]
            k = round(len(cell) * rate)
            winners = rng.choice(cell, size=k, replace=False)
            df.loc[winners, "converted"] = 1
            df.loc[winners, "revenue"] = np.round(
                rng.lognormal(mean=np.log(AOV_MEDIAN[seg]), sigma=0.4, size=k), 2
            )
    return df


def plant_feedback(df: pd.DataFrame, rng: np.random.Generator) -> pd.DataFrame:
    df = df.copy()
    df["feedback"] = rng.choice(FEEDBACK_TEMPLATES, size=len(df))
    converters = df.index[df["converted"] == 1]
    refund_idx = rng.choice(converters, size=N_REFUND_FEEDBACK, replace=False)
    df.loc[refund_idx, "feedback"] = REFUND_TEXT
    return df


def plant_anomalies(df: pd.DataFrame, rng: np.random.Generator) -> pd.DataFrame:
    df = df.copy()
    # revenue without conversion: pick non-converters, give them revenue
    non_conv = df.index[df["converted"] == 0]
    bad = rng.choice(non_conv, size=N_REVENUE_WITHOUT_CONVERSION, replace=False)
    df.loc[bad, "revenue"] = np.round(rng.uniform(20, 200, size=len(bad)), 2)
    # exact duplicate rows appended at the end
    dup_idx = rng.choice(df.index, size=N_DUPLICATES, replace=False)
    df = pd.concat([df, df.loc[dup_idx]], ignore_index=True)
    return df


def generate(seed: int = SEED) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    df = make_customers(rng)
    df = plant_outcomes(df, rng)
    df = plant_feedback(df, rng)
    df = plant_anomalies(df, rng)
    return df


def main() -> None:
    df = generate()
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT_PATH, index=False)
    print(f"wrote {len(df):,} rows -> {OUT_PATH}")


if __name__ == "__main__":
    main()

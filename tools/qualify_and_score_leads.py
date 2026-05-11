"""
Apply hard exclusion rules and compute a composite lead score for
all candidates from Stage 3 of the campaign funnel.

Hard exclusions:
  - default == 'yes'     (credit default: absolute disqualifier)
  - age >= 60            (bank policy: wealth products age cap)
  - balance < 0          (negative balance: product mismatch)

Scoring formula (0-100):
  40% balance         (min-max within qualified pool, wealth proxy)
  20% job tier        (0-3 lookup, management/entrepreneur = top)
  15% education tier  (0-3 lookup, tertiary = top)
  15% engagement      (call duration capped at 1500s, min-max)
  10% prev success    (binary: poutcome == 'success')

Outputs:
  .tmp/scored_leads.csv   — all qualified candidates with scores
  .tmp/excluded_leads.csv — excluded candidates with reasons
"""

import sys
import pandas as pd
import numpy as np
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
TMP_DIR = PROJECT_ROOT / ".tmp"
INPUT_PATH = TMP_DIR / "funnel_stage3_engaged.csv"
SCORED_PATH = TMP_DIR / "scored_leads.csv"
EXCLUDED_PATH = TMP_DIR / "excluded_leads.csv"

JOB_TIER = {
    "management": 3,
    "entrepreneur": 3,
    "self-employed": 2,
    "technician": 2,
    "admin.": 2,
    "services": 1,
    "housemaid": 1,
    "blue-collar": 1,
    "student": 0,
    "unemployed": 0,
    "retired": 0,
    "unknown": 1,
}

EDU_TIER = {
    "tertiary": 3,
    "secondary": 2,
    "primary": 1,
    "unknown": 1,
}

DURATION_CAP = 1500  # seconds — prevent outlier dominance


def load_data() -> pd.DataFrame:
    if not INPUT_PATH.exists():
        print(f"ERROR: {INPUT_PATH} not found. Run simulate_campaign_funnel.py first.", file=sys.stderr)
        sys.exit(1)
    df = pd.read_csv(INPUT_PATH)
    print(f"Loaded {len(df):,} Stage-3 candidates from {INPUT_PATH.name}")
    return df


def apply_exclusions(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    reasons = pd.Series([""] * len(df), index=df.index)
    reasons[df["default"] == "yes"] += "credit_default|"
    reasons[df["age"] >= 60] += "age_limit|"
    reasons[df["balance"] < 0] += "negative_balance|"
    reasons = reasons.str.rstrip("|")

    excluded_mask = reasons != ""
    df = df.copy()
    df["exclusion_reason"] = reasons

    excluded = df[excluded_mask].copy()
    qualified = df[~excluded_mask].copy()
    return qualified, excluded


def compute_scores(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    # Balance score: min-max within this cohort
    bal_min, bal_max = df["balance"].min(), df["balance"].max()
    df["balance_score"] = (df["balance"] - bal_min) / (bal_max - bal_min + 1e-9)

    # Job tier score
    df["job_tier"] = df["job"].map(JOB_TIER).fillna(1).astype(int)
    df["job_score"] = df["job_tier"] / 3.0

    # Education tier score
    df["education_tier"] = df["education"].map(EDU_TIER).fillna(1).astype(int)
    df["education_score"] = df["education_tier"] / 3.0

    # Engagement score: cap duration then min-max
    dur_capped = df["duration"].clip(upper=DURATION_CAP)
    dur_min, dur_max = dur_capped.min(), dur_capped.max()
    df["engagement_score"] = (dur_capped - dur_min) / (dur_max - dur_min + 1e-9)

    # Previous success binary
    df["prev_success_score"] = (df["poutcome"] == "success").astype(float)

    # Composite score
    df["lead_score"] = (
        0.40 * df["balance_score"] +
        0.20 * df["job_score"] +
        0.15 * df["education_score"] +
        0.15 * df["engagement_score"] +
        0.10 * df["prev_success_score"]
    ) * 100

    df["lead_score"] = df["lead_score"].round(2)
    return df


def main():
    TMP_DIR.mkdir(exist_ok=True)
    df = load_data()
    total_in = len(df)

    qualified, excluded = apply_exclusions(df)

    print(f"\n--- Qualification Results ---")
    print(f"  Input candidates:    {total_in:>5}")
    print(f"  Hard exclusions:     {len(excluded):>5}  ({len(excluded)/total_in*100:.1f}%)")

    if len(excluded) > 0:
        reason_counts = excluded["exclusion_reason"].str.split("|").explode().value_counts()
        for reason, count in reason_counts.items():
            if reason:
                print(f"    - {reason:<25} {count}")

    print(f"  Qualified for scoring:{len(qualified):>5}")

    if len(qualified) < 10:
        print("ERROR: Too few qualified candidates. Review exclusion rules or dataset.", file=sys.stderr)
        sys.exit(1)

    scored = compute_scores(qualified)

    print(f"\n  Score range: {scored['lead_score'].min():.1f} — {scored['lead_score'].max():.1f}")
    print(f"  Mean score:  {scored['lead_score'].mean():.1f}")

    scored.to_csv(SCORED_PATH, index=False)
    excluded.to_csv(EXCLUDED_PATH, index=False)

    print(f"\nFiles saved:")
    print(f"  {SCORED_PATH}  ({len(scored)} rows)")
    print(f"  {EXCLUDED_PATH}  ({len(excluded)} rows)")


if __name__ == "__main__":
    main()

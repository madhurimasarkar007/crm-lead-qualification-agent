"""
Simulate a 3-stage phone outreach campaign funnel on the UCI Bank Marketing dataset.

Stage 1 — Targeted  (~5,000): high-balance customers selected for outbound calling
Stage 2 — Contacted (~1,200): customers who stayed on the call (duration > 200s)
Stage 3 — Engaged   (~180):   customers with deep conversations, low contact pressure

Outputs three CSVs to .tmp/ and prints a funnel summary.
"""

import sys
import pandas as pd
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
TMP_DIR = PROJECT_ROOT / ".tmp"
CSV_PATH = TMP_DIR / "bank-full.csv"

STAGE1_TARGET = 5000
STAGE2_TARGET_LOW, STAGE2_TARGET_HIGH = 800, 1600
STAGE3_TARGET_LOW, STAGE3_TARGET_HIGH = 100, 300

# Dynamic thresholds for Stage 3 — ascending order (strictest last).
# We try from high to low; if all give too many, cap at STAGE3_TARGET_HIGH.
# If all give too few, take everything from the lowest threshold.
STAGE3_DURATION_THRESHOLDS = [900, 800, 700, 600, 500, 400]
STAGE3_CAMPAIGN_MAX = 3


def load_data() -> pd.DataFrame:
    if not CSV_PATH.exists():
        print(f"ERROR: {CSV_PATH} not found. Run download_dataset.py first.", file=sys.stderr)
        sys.exit(1)
    df = pd.read_csv(CSV_PATH, sep=";")
    print(f"Loaded {len(df):,} records from {CSV_PATH.name}")
    return df


def stage1_targeted(df: pd.DataFrame) -> pd.DataFrame:
    pool = df[
        (df["balance"] > 0) &
        (df["default"] == "no") &
        (df["age"] < 70)
    ].copy()

    stage1 = pool.nlargest(STAGE1_TARGET, "balance").reset_index(drop=True)
    stage1["lead_id"] = [f"LEAD-{i+1:04d}" for i in range(len(stage1))]
    stage1["funnel_stage"] = "Targeted"
    return stage1


def stage2_attended(stage1: pd.DataFrame) -> pd.DataFrame:
    mask = (stage1["duration"] > 200) | (stage1["poutcome"] == "success")
    stage2 = stage1[mask].copy()
    stage2["funnel_stage"] = "Contacted"

    count = len(stage2)
    if count < STAGE2_TARGET_LOW:
        print(f"  WARNING: Stage 2 yielded only {count} records (expected {STAGE2_TARGET_LOW}+). "
              f"Lowering duration threshold to 150s.")
        mask2 = (stage1["duration"] > 150) | (stage1["poutcome"] == "success")
        stage2 = stage1[mask2].copy()
        stage2["funnel_stage"] = "Contacted"
    elif count > STAGE2_TARGET_HIGH:
        print(f"  WARNING: Stage 2 yielded {count} records (target max {STAGE2_TARGET_HIGH}). "
              f"Trimming to top {STAGE2_TARGET_HIGH} by duration.")
        stage2 = stage2.nlargest(STAGE2_TARGET_HIGH, "duration").copy()
        stage2["funnel_stage"] = "Contacted"

    return stage2.reset_index(drop=True)


def stage3_engaged(stage2: pd.DataFrame) -> pd.DataFrame:
    # Try thresholds from most to least restrictive.
    # If too many → try a stricter threshold. If too few → relax.
    best = None
    for threshold in STAGE3_DURATION_THRESHOLDS:
        mask = (stage2["duration"] > threshold) & (stage2["campaign"] <= STAGE3_CAMPAIGN_MAX)
        candidates = stage2[mask].copy()
        count = len(candidates)
        if STAGE3_TARGET_LOW <= count <= STAGE3_TARGET_HIGH:
            candidates["funnel_stage"] = "Engaged"
            return candidates.reset_index(drop=True)
        # Keep the best attempt so far (closest to target range)
        if best is None or abs(count - (STAGE3_TARGET_LOW + STAGE3_TARGET_HIGH) / 2) < abs(
            len(best) - (STAGE3_TARGET_LOW + STAGE3_TARGET_HIGH) / 2
        ):
            best = candidates
        if count > STAGE3_TARGET_HIGH:
            print(f"  duration>{threshold}s → {count} records (too many). Trying stricter threshold...")
        else:
            print(f"  duration>{threshold}s → {count} records (too few). Trying looser threshold...")

    # No threshold hit the target range — use closest result, cap or warn as needed
    stage3 = best.copy()
    if len(stage3) > STAGE3_TARGET_HIGH:
        print(f"  Capping at {STAGE3_TARGET_HIGH} by highest duration.")
        stage3 = stage3.nlargest(STAGE3_TARGET_HIGH, "duration")
    if len(stage3) < 30:
        print(f"ERROR: Only {len(stage3)} records reached Stage 3. Check dataset integrity.", file=sys.stderr)
        sys.exit(1)
    stage3["funnel_stage"] = "Engaged"
    return stage3.reset_index(drop=True)


def save(df: pd.DataFrame, name: str) -> Path:
    path = TMP_DIR / name
    df.to_csv(path, index=False)
    return path


def main():
    TMP_DIR.mkdir(exist_ok=True)
    df = load_data()

    print("\n--- Simulating Campaign Funnel ---")

    stage1 = stage1_targeted(df)
    path1 = save(stage1, "funnel_stage1_targeted.csv")

    stage2 = stage2_attended(stage1)
    path2 = save(stage2, "funnel_stage2_attended.csv")

    stage3 = stage3_engaged(stage2)
    path3 = save(stage3, "funnel_stage3_engaged.csv")

    n1, n2, n3 = len(stage1), len(stage2), len(stage3)
    print(f"\nFunnel Summary:")
    print(f"  Stage 1 (Targeted):  {n1:>5,} customers")
    print(f"  Stage 2 (Contacted): {n2:>5,} customers  ({n2/n1*100:.1f}% of targeted)")
    print(f"  Stage 3 (Engaged):   {n3:>5,} customers  ({n3/n1*100:.1f}% of targeted, {n3/n2*100:.1f}% of contacted)")

    print(f"\nFiles saved:")
    print(f"  {path1}")
    print(f"  {path2}")
    print(f"  {path3}")


if __name__ == "__main__":
    main()

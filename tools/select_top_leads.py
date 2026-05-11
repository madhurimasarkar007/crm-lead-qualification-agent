"""
Select the top 50 leads by score, assign RMs round-robin, and output
the final deliverable CSV ready for Google Sheets export.

Score tiers:
  A  >= 70  (High Priority)
  B  50-69  (Medium Priority)
  C  < 50   (Low Priority)

RM assignment is round-robin by score rank so every RM gets a mix of tiers.
"""

import sys
import pandas as pd
from datetime import date
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
TMP_DIR = PROJECT_ROOT / ".tmp"
INPUT_PATH = TMP_DIR / "scored_leads.csv"
OUTPUT_PATH = TMP_DIR / "top50_leads.csv"

TOP_N = 50
RM_POOL = ["RM_Priya", "RM_Arjun", "RM_Sofia", "RM_Marcus", "RM_Chen"]

OUTPUT_COLUMNS = [
    "lead_id", "lead_score", "score_tier",
    "age", "job", "education", "marital",
    "balance", "housing", "loan",
    "duration", "campaign", "poutcome", "y",
    "job_tier", "education_tier",
    "balance_score", "job_score", "education_score", "engagement_score", "prev_success_score",
    "rm_assigned", "status", "notes", "briefing_generated", "last_updated",
]


def score_tier(score: float) -> str:
    if score >= 70:
        return "A"
    if score >= 50:
        return "B"
    return "C"


def main():
    if not INPUT_PATH.exists():
        print(f"ERROR: {INPUT_PATH} not found. Run qualify_and_score_leads.py first.", file=sys.stderr)
        sys.exit(1)

    scored = pd.read_csv(INPUT_PATH)
    print(f"Loaded {len(scored):,} qualified leads.")

    if len(scored) < TOP_N:
        print(f"WARNING: Only {len(scored)} qualified leads available (target {TOP_N}). Taking all.")

    top = scored.nlargest(TOP_N, "lead_score").reset_index(drop=True)

    top["score_tier"] = top["lead_score"].apply(score_tier)
    top["rm_assigned"] = [RM_POOL[i % len(RM_POOL)] for i in range(len(top))]
    top["status"] = "Open"
    top["notes"] = ""
    top["briefing_generated"] = False
    top["last_updated"] = date.today().isoformat()

    # Reorder columns, keep only what's defined (extras dropped)
    available = [c for c in OUTPUT_COLUMNS if c in top.columns]
    extra = [c for c in top.columns if c not in OUTPUT_COLUMNS]
    top = top[available]

    top.to_csv(OUTPUT_PATH, index=False)

    tier_counts = top["score_tier"].value_counts().reindex(["A", "B", "C"], fill_value=0)
    rm_counts = top["rm_assigned"].value_counts()

    print(f"\nTop {len(top)} selected. Score range: {top['lead_score'].min():.1f} — {top['lead_score'].max():.1f}")
    print(f"  Tier A (>=70):  {tier_counts.get('A', 0):>3} leads")
    print(f"  Tier B (50-69): {tier_counts.get('B', 0):>3} leads")
    print(f"  Tier C (<50):   {tier_counts.get('C', 0):>3} leads")
    print(f"\nRM Assignments:")
    for rm, count in rm_counts.items():
        print(f"  {rm:<12} {count} leads")
    print(f"\nSaved: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()

"""
Sync RM-entered status updates from Google Sheets back to the local
top50_leads.csv, and print a weekly conversion summary.

RMs edit two columns in the 'Leads' tab:
  Status  — must be one of: Open, Contacted, Won, Lost
  Notes   — free text (call outcome, callback date, objections)

Any status change is appended to the Audit_Log tab with a timestamp.
"""

import os
import sys
import pandas as pd
from datetime import datetime, date
from pathlib import Path
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
TMP_DIR = PROJECT_ROOT / ".tmp"
LEADS_PATH = TMP_DIR / "top50_leads.csv"

VALID_STATUSES = {"Open", "Contacted", "Won", "Lost"}
STATUS_COL_INDEX = 15   # 0-based; column P in the Leads sheet (Lead_ID, Score, ... Status)
NOTES_COL_INDEX = 16    # column Q


def get_credentials():
    from tools.export_to_sheets import get_credentials as _get_creds
    return _get_creds()


def pull_sheet_data(sheet_id: str) -> list[dict]:
    import gspread
    creds = get_credentials()
    gc = gspread.authorize(creds)
    sh = gc.open_by_key(sheet_id)
    ws = sh.worksheet("Leads")
    records = ws.get_all_records()  # returns list of dicts keyed by header row
    return records, sh


def append_audit_entry(sh, lead_id: str, old_status: str, new_status: str, notes: str):
    try:
        ws_audit = sh.worksheet("Audit_Log")
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        ws_audit.append_row(
            [timestamp, "STATUS_UPDATE", lead_id, "RM", old_status, new_status],
            value_input_option="USER_ENTERED",
        )
    except Exception as e:
        print(f"  WARNING: Could not append to Audit_Log: {e}")


def print_summary(df: pd.DataFrame):
    total = len(df)
    counts = df["status"].value_counts().reindex(["Open", "Contacted", "Won", "Lost"], fill_value=0)

    won = counts.get("Won", 0)
    lost = counts.get("Lost", 0)
    contacted = counts.get("Contacted", 0)
    closed = won + lost + contacted
    conversion_rate = won / (won + lost) * 100 if (won + lost) > 0 else 0.0
    contact_rate = (contacted + won + lost) / total * 100 if total > 0 else 0.0

    week_num = date.today().strftime("%W")
    year = date.today().year

    print(f"\n{'='*50}")
    print(f"Weekly Lead Status Summary — Week {week_num}, {year}")
    print(f"{'='*50}")
    print(f"Total Leads:    {total}")
    print(f"  Open:         {counts['Open']:>3}  ({counts['Open']/total*100:.1f}%)")
    print(f"  Contacted:    {counts['Contacted']:>3}  ({counts['Contacted']/total*100:.1f}%)")
    print(f"  Won:          {counts['Won']:>3}  ({counts['Won']/total*100:.1f}%)")
    print(f"  Lost:         {counts['Lost']:>3}  ({counts['Lost']/total*100:.1f}%)")
    print(f"\nContact Rate:      {contact_rate:.1f}%  (Contacted+Won+Lost / Total)")
    print(f"Conversion Rate:   {conversion_rate:.1f}%  (Won / Won+Lost)")

    # RM breakdown
    print(f"\nBy RM:")
    for rm in sorted(df["rm_assigned"].unique()):
        rm_df = df[df["rm_assigned"] == rm]
        rm_counts = rm_df["status"].value_counts().reindex(["Open", "Contacted", "Won", "Lost"], fill_value=0)
        print(f"  {rm:<12} Won={rm_counts['Won']}  Lost={rm_counts['Lost']}  "
              f"Contacted={rm_counts['Contacted']}  Open={rm_counts['Open']}")

    # Escalation alerts
    if conversion_rate < 10 and (won + lost) >= 5:
        print(f"\n⚠  ALERT: Conversion rate {conversion_rate:.1f}% is below 10%. "
              f"Review lead quality or scoring weights.")

    open_leads = df[df["status"] == "Open"].nlargest(5, "lead_score")
    if len(open_leads) > 0:
        print(f"\nTop-scoring leads still Open (follow-up priority):")
        for _, row in open_leads.iterrows():
            print(f"  {row['lead_id']}  Score={row['lead_score']:.1f}  RM={row['rm_assigned']}")


def save_weekly_snapshot(df: pd.DataFrame):
    today = date.today().strftime("%Y%m%d")
    snapshot_path = TMP_DIR / f"weekly_summary_{today}.csv"
    df.to_csv(snapshot_path, index=False)
    print(f"\nSnapshot saved: {snapshot_path}")


def main():
    load_dotenv(PROJECT_ROOT / ".env")
    sheet_id = os.getenv("GOOGLE_SHEET_ID", "")

    if not sheet_id or sheet_id in ("", "your_google_sheet_id_here"):
        print("ERROR: GOOGLE_SHEET_ID not set in .env", file=sys.stderr)
        sys.exit(1)

    if not LEADS_PATH.exists():
        print(f"ERROR: {LEADS_PATH} not found. Run select_top_leads.py first.", file=sys.stderr)
        sys.exit(1)

    local_df = pd.read_csv(LEADS_PATH)
    print(f"Loaded {len(local_df)} local leads.")

    print("Pulling status updates from Google Sheets...")
    try:
        sheet_records, sh = pull_sheet_data(sheet_id)
    except Exception as e:
        print(f"ERROR: Could not access Google Sheet: {e}", file=sys.stderr)
        sys.exit(1)

    sheet_df = pd.DataFrame(sheet_records)
    if sheet_df.empty:
        print("No data found in Leads tab.")
        sys.exit(0)

    # Normalise column names to lowercase for safe lookup
    sheet_df.columns = [c.strip() for c in sheet_df.columns]
    status_col = next((c for c in sheet_df.columns if "status" in c.lower()), None)
    notes_col = next((c for c in sheet_df.columns if "note" in c.lower()), None)
    id_col = next((c for c in sheet_df.columns if "lead_id" in c.lower() or "lead id" in c.lower()), None)

    if not all([status_col, id_col]):
        print(f"ERROR: Could not find Lead_ID or Status columns in sheet. Columns: {list(sheet_df.columns)}", file=sys.stderr)
        sys.exit(1)

    updates = 0
    invalid_statuses = []

    for _, sheet_row in sheet_df.iterrows():
        lead_id = str(sheet_row[id_col]).strip()
        new_status = str(sheet_row[status_col]).strip()
        new_notes = str(sheet_row[notes_col]).strip() if notes_col else ""

        local_mask = local_df["lead_id"] == lead_id
        if not local_mask.any():
            continue

        if new_status not in VALID_STATUSES:
            invalid_statuses.append((lead_id, new_status))
            continue

        old_status = local_df.loc[local_mask, "status"].values[0]
        old_notes = str(local_df.loc[local_mask, "notes"].values[0])

        if new_status != old_status or new_notes != old_notes:
            local_df.loc[local_mask, "status"] = new_status
            local_df.loc[local_mask, "notes"] = new_notes
            local_df.loc[local_mask, "last_updated"] = date.today().isoformat()
            append_audit_entry(sh, lead_id, old_status, new_status, new_notes)
            updates += 1

    if invalid_statuses:
        print(f"\nWARNING: {len(invalid_statuses)} leads have invalid status values (ignored):")
        for lead_id, bad_status in invalid_statuses:
            print(f"  {lead_id}: '{bad_status}' — must be one of {sorted(VALID_STATUSES)}")

    print(f"Synced {updates} status update(s) from Google Sheets.")

    local_df.to_csv(LEADS_PATH, index=False)
    print_summary(local_df)
    save_weekly_snapshot(local_df)


if __name__ == "__main__":
    main()

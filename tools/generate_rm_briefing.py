"""
Generate personalized RM talking points for each top-50 lead using the Gemini API.

Model: gemini-1.5-flash (fast, free tier available)

Output:
  .tmp/rm_briefings.csv  — lead_id, rm_assigned, why_prospect, opening_line,
                           talking_point, briefing_parse_error
  Google Sheets tab 'RM_Briefings' (if credentials are configured)
"""

import os
import sys
import time
import pandas as pd
from pathlib import Path
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
TMP_DIR = PROJECT_ROOT / ".tmp"
INPUT_PATH = TMP_DIR / "top50_leads.csv"
OUTPUT_PATH = TMP_DIR / "rm_briefings.csv"

MODEL = os.getenv("LLM_MODEL", "gemini-2.5-flash")
RETRY_DELAYS = [5, 15, 30]

SYSTEM_PROMPT = """You are a senior wealth management strategist helping Relationship Managers (RMs) \
at a retail bank prepare for outbound sales calls. Your role is to craft concise, \
compelling talking points based on customer profile data.

Your output must always follow this exact format with no extra text:
WHY_PROSPECT: [One sentence explaining why this customer is a strong wealth product candidate]
OPENING: [One sentence suggested opening line for the RM to use on the call]
TALKING_POINT: [One sentence on the most compelling angle to pursue during the call]

Be specific and reference actual data values provided. Do not use generic phrases.
Never use the word "score" — refer to "profile review" or "analysis" instead.
Do not include the customer's name (it is not available)."""


def build_user_prompt(row: pd.Series) -> str:
    return f"""Customer Profile for {row['lead_id']}:

- Age: {row['age']} years old
- Job: {row['job']}
- Education: {row['education']}
- Marital Status: {row['marital']}
- Average Annual Balance: €{row['balance']:,.0f}
- Has Housing Loan: {row['housing']}
- Has Personal Loan: {row['loan']}
- Recent Call Engagement: {int(row['duration'])} seconds on last call
- Campaign Contacts This Run: {int(row['campaign'])}
- Previous Campaign Outcome: {row['poutcome']}
- Assigned RM: {row['rm_assigned']}
- Score Tier: {row['score_tier']}

Generate a 3-part RM briefing using the exact format specified."""


def parse_briefing(text: str) -> dict:
    result = {"why_prospect": "", "opening_line": "", "talking_point": "", "briefing_parse_error": False}
    try:
        for line in text.strip().split("\n"):
            line = line.strip()
            if line.upper().startswith("WHY_PROSPECT:"):
                result["why_prospect"] = line.split(":", 1)[1].strip()
            elif line.upper().startswith("OPENING:"):
                result["opening_line"] = line.split(":", 1)[1].strip()
            elif line.upper().startswith("TALKING_POINT:"):
                result["talking_point"] = line.split(":", 1)[1].strip()

        if not all([result["why_prospect"], result["opening_line"], result["talking_point"]]):
            result["briefing_parse_error"] = True
            result["why_prospect"] = text
    except Exception:
        result["briefing_parse_error"] = True
        result["why_prospect"] = text
    return result


class DailyQuotaExhausted(Exception):
    pass


def call_gemini(client, lead_id: str, prompt: str) -> str:
    for attempt, delay in enumerate([0] + RETRY_DELAYS):
        if delay:
            time.sleep(delay)
        try:
            response = client.models.generate_content(
                model=MODEL,
                contents=prompt,
            )
            return response.text
        except Exception as e:
            err = str(e)
            # Daily quota cannot be resolved by retrying — stop immediately
            if "perday" in err.lower() or "per_day" in err.lower() or "daily" in err.lower():
                raise DailyQuotaExhausted(f"Daily quota exhausted. Resets at midnight Pacific. Leads processed so far are saved.")
            if "429" in err or "quota" in err.lower() or "rate" in err.lower():
                if attempt < len(RETRY_DELAYS):
                    print(f"    Rate limited. Retrying in {RETRY_DELAYS[attempt]}s...")
                    continue
            raise

    raise RuntimeError(f"All retries failed for {lead_id}")


def push_to_sheets(briefings_df: pd.DataFrame):
    try:
        sys.path.insert(0, str(PROJECT_ROOT))
        from tools.export_to_sheets import get_credentials, get_or_create_spreadsheet, ensure_tab
        import gspread
        from datetime import datetime

        load_dotenv(PROJECT_ROOT / ".env")
        sheet_id = os.getenv("GOOGLE_SHEET_ID", "")
        if not sheet_id or sheet_id == "your_google_sheet_id_here":
            print("  Skipping Sheets upload: GOOGLE_SHEET_ID not configured.")
            return

        creds = get_credentials()
        gc = gspread.authorize(creds)
        now = datetime.now()
        week_label = f"Week {now.strftime('%W')}, {now.year}"
        sh, _ = get_or_create_spreadsheet(gc, sheet_id, week_label)
        ws = ensure_tab(sh, "RM_Briefings")
        ws.clear()

        cols = ["lead_id", "rm_assigned", "score_tier", "why_prospect", "opening_line", "talking_point", "briefing_parse_error"]
        available = [c for c in cols if c in briefings_df.columns]
        rows = [available] + briefings_df[available].fillna("").astype(str).values.tolist()
        ws.update(rows, value_input_option="USER_ENTERED")
        ws.freeze(rows=1)
        print(f"  Tab 'RM_Briefings': {len(briefings_df)} rows written to Google Sheets")
    except Exception as e:
        print(f"  WARNING: Could not push briefings to Sheets: {e}")


def main():
    load_dotenv(PROJECT_ROOT / ".env")
    api_key = os.getenv("GEMINI_API_KEY", "")
    if not api_key:
        print("ERROR: GEMINI_API_KEY not set in .env", file=sys.stderr)
        sys.exit(1)

    if not INPUT_PATH.exists():
        print(f"ERROR: {INPUT_PATH} not found. Run select_top_leads.py first.", file=sys.stderr)
        sys.exit(1)

    from google import genai
    client = genai.Client(api_key=api_key)

    full_prompt_template = SYSTEM_PROMPT + "\n\n{user_prompt}"

    df = pd.read_csv(INPUT_PATH)

    # Load existing successful briefings to resume without re-generating them
    existing_clean = {}
    if OUTPUT_PATH.exists():
        existing_df = pd.read_csv(OUTPUT_PATH)
        for _, r in existing_df.iterrows():
            if not r.get("briefing_parse_error", True):
                existing_clean[r["lead_id"]] = r.to_dict()

    pending = df[~df["lead_id"].isin(existing_clean)].copy()
    skipped = len(existing_clean)
    if skipped:
        print(f"Resuming: {skipped} briefings already done, {len(pending)} remaining.\n")
    else:
        print(f"Generating RM briefings for {len(df)} leads using {MODEL}...\n")

    new_results = []
    parse_errors = 0
    quota_hit = False

    for i, (_, row) in enumerate(pending.iterrows()):
        lead_id = row["lead_id"]
        rm = row["rm_assigned"]

        print(f"[{skipped+i+1:02d}/{len(df)}] {lead_id} ({rm})...", end=" ", flush=True)

        user_prompt = build_user_prompt(row)
        full_prompt = full_prompt_template.format(user_prompt=user_prompt)

        try:
            raw_text = call_gemini(client, lead_id, full_prompt)
            parsed = parse_briefing(raw_text)
            if parsed["briefing_parse_error"]:
                parse_errors += 1
                print("done (parse error — raw text stored)")
            else:
                print("done")
        except DailyQuotaExhausted as e:
            print(f"QUOTA EXHAUSTED — stopping early.")
            print(f"\n  {e}")
            quota_hit = True
            break
        except Exception as e:
            print(f"FAILED: {e}")
            parsed = {
                "why_prospect": f"ERROR: {e}",
                "opening_line": "",
                "talking_point": "",
                "briefing_parse_error": True,
            }
            parse_errors += 1

        new_results.append({
            "lead_id": lead_id,
            "rm_assigned": rm,
            "score_tier": row.get("score_tier", ""),
            **parsed,
        })

        if i < len(pending) - 1:
            time.sleep(0.5)

    # Merge existing clean briefings with new results, preserving original row order
    new_by_id = {r["lead_id"]: r for r in new_results}
    all_results = []
    for _, row in df.iterrows():
        lid = row["lead_id"]
        if lid in existing_clean:
            all_results.append(existing_clean[lid])
        elif lid in new_by_id:
            all_results.append(new_by_id[lid])
        else:
            # Not yet processed (quota cut short)
            all_results.append({
                "lead_id": lid,
                "rm_assigned": row["rm_assigned"],
                "score_tier": row.get("score_tier", ""),
                "why_prospect": "PENDING",
                "opening_line": "",
                "talking_point": "",
                "briefing_parse_error": True,
            })

    briefings_df = pd.DataFrame(all_results)
    briefings_df.to_csv(OUTPUT_PATH, index=False)

    df["briefing_generated"] = True
    df.to_csv(INPUT_PATH, index=False)

    total_clean = len([r for r in all_results if not r.get("briefing_parse_error", True)])
    pending_count = len([r for r in all_results if r.get("why_prospect") == "PENDING"])
    print(f"\nBriefings complete. {total_clean}/{len(df)} done. {parse_errors} parse errors. {pending_count} pending (re-run tomorrow).")
    print(f"Saved: {OUTPUT_PATH}")
    if quota_hit:
        print("  Daily quota hit — re-run this script tomorrow to continue.")

    push_to_sheets(briefings_df)


if __name__ == "__main__":
    main()

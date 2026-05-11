# Lead Tracking Workflow

**Version:** 1.1
**Cadence:** Weekly — every Friday afternoon (or on-demand mid-week)
**Owner:** CRM Analytics Team
**Deliverable:** Updated lead statuses + weekly conversion summary for management reporting

> **Note on status collection:** Since delivery is via Excel (not a shared online sheet), RMs update
> the Status and Notes columns in their copy of the workbook and email it back by Thursday EOD.
> The analytics team consolidates responses manually into `.tmp/top50_leads.csv` before running
> the Friday sync. A shared drive or SharePoint link can replace the email-back step if available.

---

## Objective

Sync status updates entered by Relationship Managers in Google Sheets back to the local records, produce a weekly conversion summary, and flag any escalation conditions that need attention.

---

## Lead Lifecycle

```
Open  ──────────────────→  Contacted  →  Won
  ↑                              │       ↑
  └──────────────────────────────┘       │
         (re-open if needed)        Lost ─┘
```

Any status can transition to any other status — RMs may re-open a lead they previously marked Lost.

**Valid status values (RMs must use exactly):**
- `Open` — not yet contacted this cycle
- `Contacted` — RM has called, outcome pending
- `Won` — customer took the wealth product
- `Lost` — customer declined, not interested

---

## RM Instructions (What RMs Do in Google Sheets)

RMs open the `Leads` tab in the Google Sheet (URL shared on Monday) and edit two columns:

| Column | What to Enter |
|---|---|
| **Status** | One of: `Open`, `Contacted`, `Won`, `Lost` |
| **Notes** | Free text — call outcome, callback date, objections raised, product discussed |

**Important:** Status values must match exactly (case-sensitive). Invalid values are flagged and ignored during sync.

---

## Prerequisites

- [ ] `GOOGLE_SHEET_ID` is set in `.env`
- [ ] `credentials.json` is present (or `token.json` from a prior auth)
- [ ] `.tmp/top50_leads.csv` exists (generated on Monday)
- [ ] RMs have had time to update their statuses

---

## Step-by-Step

### Step 1 — Pull Status Updates

```bash
python tools/update_lead_status.py
```

**Expected output:**
```
Loaded 50 local leads.
Pulling status updates from Google Sheets...
Synced 18 status update(s) from Google Sheets.

==================================================
Weekly Lead Status Summary — Week 19, 2026
==================================================
Total Leads:    50
  Open:          12  (24.0%)
  Contacted:     25  (50.0%)
  Won:            8  (16.0%)
  Lost:           5  (10.0%)

Contact Rate:      80.0%  (Contacted+Won+Lost / Total)
Conversion Rate:   61.5%  (Won / Won+Lost)

By RM:
  RM_Arjun     Won=1  Lost=2  Contacted=5  Open=2
  RM_Chen      Won=2  Lost=0  Contacted=6  Open=2
  RM_Marcus    Won=2  Lost=1  Contacted=4  Open=3
  RM_Priya     Won=2  Lost=1  Contacted=5  Open=2
  RM_Sofia     Won=1  Lost=1  Contacted=5  Open=3

Top-scoring leads still Open (follow-up priority):
  LEAD-0031  Score=79.2  RM=RM_Sofia
  LEAD-0045  Score=74.8  RM=RM_Marcus
```

The tool:
- Validates all status values (warns on invalid, does not write them)
- Updates `.tmp/top50_leads.csv` in-place
- Appends each change to the `Audit_Log` tab in Google Sheets
- Saves a timestamped snapshot to `.tmp/weekly_summary_YYYYMMDD.csv`

---

### Step 2 — Agent Review and Escalation

After the sync, the agent reads the summary and checks for escalation conditions:

| Condition | Threshold | Action |
|---|---|---|
| Low conversion rate | Won / (Won+Lost) < 10% and ≥ 5 leads closed | Alert user — review scoring weights or lead quality |
| RM inactivity | Any RM has 0 Contacted + 0 Won + 0 Lost after 3 days | Flag to user — possible availability issue |
| Many leads still Open by Friday | > 20 leads Open on Friday | Recommend manager follow-up or extend calling window |
| Invalid status values | Any | Report exact lead_ids and invalid values to user |

---

### Step 3 — End-of-Week Archival (Friday only)

After confirming the summary looks correct, archive the week's leads:

```bash
# Rename the current week's file to a dated archive
# (agent runs this as a Bash command)
mv .tmp/top50_leads.csv ".tmp/leads_week$(date +%W)_$(date +%Y).csv"
```

This preserves a clean historical record. The next Monday's pipeline starts fresh.

**Master log:** If you want to track all leads across weeks, append the weekly snapshot to a master file:
```bash
# First week: copy as master
cp .tmp/weekly_summary_$(date +%Y%m%d).csv .tmp/leads_master_log.csv

# Subsequent weeks: append (skip header)
tail -n +2 .tmp/weekly_summary_$(date +%Y%m%d).csv >> .tmp/leads_master_log.csv
```

---

## Metrics to Track Each Week

| Metric | Formula | Target |
|---|---|---|
| Contact Rate | (Contacted + Won + Lost) / Total | > 70% by Friday |
| Conversion Rate | Won / (Won + Lost) | > 15% per weekly cohort |
| Avg Score of Won leads | mean(lead_score) for Won | Should be > avg score of Lost leads |
| RM Leaderboard | Won count per RM | Review if any RM consistently at 0 |

**Score calibration insight:** If the average score of Won leads is not higher than Lost leads, the scoring model weights may need adjustment. Bring this to the analytics review.

---

## Failure Handling

| Scenario | Action |
|---|---|
| Google OAuth expired | Re-auth via browser; token auto-saved to `token.json` |
| Sheet not accessible | Check `GOOGLE_SHEET_ID` in `.env` |
| `Leads` tab has no data | Verify the export was run on Monday (Step 5 of qualification workflow) |
| `.tmp/top50_leads.csv` missing | Re-run `select_top_leads.py` then sync manually |
| RM entered wrong status value | Tool warns and ignores — contact RM to correct in sheet |

---

## Google Sheet Tab Reference

| Tab | Purpose | Who Edits |
|---|---|---|
| `Leads` | Current week's 50 leads + RM status updates | RMs edit Status and Notes |
| `Audit_Log` | Immutable record of all exports and status changes | System only |
| `RM_Briefings` | Personalized talking points per lead | Read-only for RMs |

# Lead Qualification Workflow

**Version:** 1.1
**Cadence:** Weekly — every Monday morning, deliverable ready before 9am
**Owner:** CRM Analytics Team
**Deliverable:** Top-50 qualified wealth product leads in a formatted Excel workbook, with personalized RM briefings

---

## Objective

Produce a ranked, RM-assigned list of 50 wealth product prospects from the bank's customer database, complete with personalized talking points for Relationship Managers. The list is delivered as a formatted Excel workbook that can be emailed or shared with RMs each Monday.

---

## Campaign Funnel Logic (What This Workflow Simulates)

This is a **phone outreach campaign**. All engagement signals are derived from call data —
call duration is the behavioural proxy for customer interest, not email opens or webinar attendance.

```
45,211 customers
     |
     | Filter: balance>0, no default, age<70
     v
~5,000  TARGETED   (selected for outbound calling based on wealth profile)
     |
     | Filter: call duration>200s OR prior campaign success
     v
~1,600  CONTACTED  (stayed on the call — not immediately disinterested)
     |
     | Filter: call duration>400s AND campaign contacts ≤3
     v
~157    ENGAGED    (deep conversation, low contact pressure — genuine interest)
     |
     | Apply exclusions + score → rank → top 50
     v
50      LEADS      (ready for RM outreach this week)
```

**Why duration is the engagement signal:**
- <200s — customer ended the call quickly, low interest
- 200–400s — engaged but not deeply committed
- >400s — sustained conversation, product interest likely
- Capped at 1,500s in scoring to prevent outlier dominance

---

## Prerequisites Checklist

Before running, confirm all of the following:

- [ ] Virtual environment is active: `source venv/bin/activate`
- [ ] `GEMINI_API_KEY` is set in `.env` (required for Step 6 — RM briefing generation)
- [ ] Internet connection is available (for dataset download and Gemini API calls)

---

## Inputs

| Input | Source | Notes |
|---|---|---|
| Customer dataset | UCI Bank Marketing (`bank-full.csv`) | Auto-downloaded if missing |
| Gemini API key | `.env` → `GEMINI_API_KEY` | For RM briefing generation (free tier: 20 req/day) |

---

## Outputs

| Output | Location |
|---|---|
| Local dataset backup | `.tmp/bank-full.csv` |
| Funnel stage files | `.tmp/funnel_stage{1,2,3}_*.csv` |
| Scored candidates | `.tmp/scored_leads.csv` |
| Excluded candidates | `.tmp/excluded_leads.csv` |
| Final top-50 leads | `.tmp/top50_leads.csv` |
| RM briefings | `.tmp/rm_briefings.csv` |
| Excel workbook (share with RMs) | `.tmp/leads_report_YYYYMMDD.xlsx` |

---

## Step-by-Step Execution

### Step 1 — Download Dataset

```bash
python tools/download_dataset.py
```

**Expected output:**
```
Dataset already present: .tmp/bank-full.csv (45,211 rows). Skipping download.
```
or on first run:
```
Downloading dataset from UCI...
Downloaded 4,731.3 KB -> .tmp/bank.zip
Unzipping...
Verified: 45,211 rows, 17 columns.
```

**Skip condition:** File exists with correct row count and columns — tool detects this automatically.

**Failure handling:**
- Network error → check internet connection; try again in 5 minutes
- If UCI URL is unreachable, use the cached `.tmp/bank-full.csv` if it exists and is less than 7 days old — proceed to Step 2
- Row count mismatch → delete `.tmp/bank-full.csv` and re-run

---

### Step 2 — Simulate Campaign Funnel

```bash
python tools/simulate_campaign_funnel.py
```

**Expected output:**
```
Funnel Summary:
  Stage 1 (Targeted):  5,000 customers
  Stage 2 (Attended):  1,187 customers  (23.7% of targeted)
  Stage 3 (Engaged):     183 customers  (3.7% of targeted, 15.4% of attended)
```

**Validation (agent checks after running):**
- Stage 1: 4,000 – 6,000 records ✓
- Stage 2: 800 – 1,600 records ✓
- Stage 3: 100 – 300 records ✓

If Stage 3 is outside 100-300, the tool adjusts thresholds automatically. If Stage 3 < 30 after all attempts, the tool exits with an error — check `.tmp/bank-full.csv` integrity.

---

### Step 3 — Qualify and Score Leads

```bash
python tools/qualify_and_score_leads.py
```

**Expected output:**
```
Input candidates:     183
Hard exclusions:       23  (12.6%)
  - age_limit:         15
  - credit_default:     3
  - negative_balance:   5
Qualified for scoring:160
Score range: 18.4 — 84.7
```

**Hard exclusion rules (non-negotiable):**
- `default = yes` → credit_default (absolute bank policy)
- `age >= 60` → age_limit (wealth product eligibility policy)
- `balance < 0` → negative_balance (product mismatch)

**Failure handling:**
- If fewer than 30 leads qualify, stop and alert user — business rules may be too restrictive for this dataset configuration

---

### Step 4 — Select Top 50

```bash
python tools/select_top_leads.py
```

**Expected output:**
```
Top 50 selected. Score range: 52.1 — 84.7
  Tier A (>=70):  18 leads
  Tier B (50-69): 27 leads
  Tier C (<50):    5 leads
RM Assignments:
  RM_Priya:   10 leads
  RM_Arjun:   10 leads
  RM_Sofia:   10 leads
  RM_Marcus:  10 leads
  RM_Chen:    10 leads
```

**Note:** If fewer than 50 leads qualified in Step 3, the tool takes all available and prints a warning. Proceed — fewer leads is better than no leads.

---

### Step 5 — Export to Excel

```bash
python tools/export_to_sheets.py
```

**Expected output:**
```
Loaded 50 leads from top50_leads.csv
  Sheet 'Leads': 50 rows written
  Sheet 'RM_Briefings': 50 rows written
  Sheet 'Audit_Log': 1 entries
Saved: .tmp/leads_report_20260510.xlsx
Share this file with your RMs via email or shared drive.
```

Generates a formatted `.xlsx` workbook with three tabs:
- **Leads** — 50 rows colour-coded by tier (green=A, yellow=B, orange=C), auto-filter, frozen header
- **RM_Briefings** — AI-generated talking points merged in
- **Audit_Log** — timestamped record of every export run

**Failure handling:**
- Missing `top50_leads.csv` → run Step 4 first
- Missing `rm_briefings.csv` → Step 6 was not run yet; briefings tab will be skipped

---

### Step 6 — Generate RM Briefings

```bash
python tools/generate_rm_briefing.py
```

**Expected output:**
```
Resuming: 22 briefings already done, 28 remaining.
[23/50] LEAD-1756 (RM_Chen)... done
...
Briefings complete. 50/50 done. 0 parse errors. 0 pending.
```

**Free tier limit:** Gemini 2.5 Flash allows 20 requests/day on the free tier. If 50 briefings cannot be completed in one run, the tool saves progress and prints "re-run tomorrow to continue." Re-running picks up exactly where it left off — already-completed briefings are never re-generated.

**Estimated cost:** $0 on free tier. <$0.05 on paid tier.

**Failure handling:**
- `GEMINI_API_KEY invalid` → check `.env`
- `Daily quota exhausted` → tool stops cleanly, saves progress; re-run the next day
- `Rate limit (per-minute)` → tool retries automatically with backoff (5s, 15s, 30s)
- If > 5 parse errors → review `.tmp/rm_briefings.csv` raw text; check system prompt in `tools/generate_rm_briefing.py`

---

### Step 7 — Verify

Agent manually checks the following after all steps complete:

- [ ] `.tmp/leads_report_YYYYMMDD.xlsx` exists and opens correctly
- [ ] Leads tab has exactly 50 rows (plus header), all with `Status = Open`
- [ ] All 50 rows have non-null `RM_Assigned`
- [ ] `RM_Briefings` tab has 50 rows (or note how many are still PENDING)
- [ ] `Audit_Log` tab has at least 1 row with today's date
- [ ] Score range: max score > 50, min score > 10 (sanity check on scoring)

**Communicate to user:** File path + brief summary (tier breakdown, briefings complete count, any warnings).

---

## Scoring Reference

| Component | Weight | Raw Variable | How It's Computed |
|---|---|---|---|
| Balance | 40% | `balance` | min-max within qualified pool |
| Job tier | 20% | `job` | management/entrepreneur=3, technician/admin=2, services=1, other=0 |
| Education | 15% | `education` | tertiary=3, secondary=2, primary=1, unknown=1 |
| Engagement | 15% | `duration` | capped at 1500s, then min-max |
| Prev. success | 10% | `poutcome` | 1 if success, 0 otherwise |

**Score tiers:** A ≥ 70 · B 50-69 · C < 50

---

## Failure Handling Quick Reference

| Scenario | Action |
|---|---|
| UCI website unreachable | Use cached `.tmp/bank-full.csv` if < 7 days old |
| Stage 3 < 30 records after all threshold attempts | Check bank-full.csv integrity; re-run Step 1 |
| < 30 leads pass qualification rules | Alert user — rules may be too restrictive |
| Gemini daily quota exhausted mid-run | Tool saves progress and exits cleanly; re-run next day |
| > 5 briefings fail to parse | Review raw text in rm_briefings.csv; adjust prompt |
| Idempotency: re-running mid-week | Steps 1–4 are idempotent; Excel file is overwritten cleanly each run |

---

## Success Criteria

- [ ] 50 leads in Excel `Leads` tab with `Status = Open`
- [ ] All 50 leads have valid `RM_Assigned` values
- [ ] `RM_Briefings` tab populated (or pending count noted if quota limited)
- [ ] `Audit_Log` updated with today's export timestamp
- [ ] Excel file emailed or shared with RM manager by 9am Monday

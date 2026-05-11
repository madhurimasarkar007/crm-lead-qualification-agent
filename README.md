# CRM Lead Qualification Agent

An end-to-end automated pipeline that takes 45,211 raw customer records and delivers 50 ranked, RM-assigned, AI-briefed leads every Monday morning — replacing a manual SAS/SQL query process that took 3–4 hours.

**Result: 5.6x lift over random selection. 66% of selected leads have a positive historical conversion label vs. 11.7% baseline.**

---

## What It Does

Each week, Relationship Managers (RMs) at a retail bank need to make outbound calls to pitch wealth products. The challenge: tens of thousands of customers in the database, but each RM can realistically make 10–15 meaningful calls a week.

This pipeline answers: **who do you call, and what do you say?**

It filters a phone outreach campaign funnel — from 45,211 customers down to 5,000 targeted, 1,600 contacted, 157 deeply engaged — applies a weighted composite scoring model, selects the top 50 leads, assigns them across 5 RMs, and generates a personalised AI briefing for each lead — delivered as a formatted Excel workbook.

---

## Architecture — WAT Framework

```
Workflows  →  Plain-language SOPs in workflows/ (what to do, in what order)
Agent      →  LLM orchestrates, validates outputs, handles failures
Tools      →  Deterministic Python scripts (download, filter, score, export)
```

AI handles reasoning and orchestration. Python handles execution. This prevents compounding failure — five 90%-reliable AI steps in sequence give only 59% end-to-end reliability.

---

## Pipeline

```
Step 1  download_dataset.py       Download UCI Bank Marketing dataset (45,211 rows)
Step 2  simulate_campaign_funnel  Filter: Targeted (5,000) to Contacted (1,600) to Engaged (157)
Step 3  qualify_and_score_leads   Exclude ineligible, score remaining 149 on 5 components
Step 4  select_top_leads          Rank, assign tiers (A/B/C), round-robin RM assignment
Step 5  generate_rm_briefing      Gemini 2.5 Flash → 3-part briefing per lead
Step 6  export_to_sheets          Formatted Excel workbook with Leads + Briefings + Audit tabs
```

### Scoring Model (0–100)

| Component | Weight | Signal |
|---|---|---|
| Balance | 40% | Annual account balance |
| Job tier | 20% | management/entrepreneur → student/unemployed |
| Education | 15% | tertiary → primary |
| Engagement | 15% | Call duration (capped at 1,500s) |
| Prior success | 10% | Previous campaign outcome = success |

Normalised within the qualified pool (not the full dataset) to preserve discrimination between already high-engagement prospects.

---

## Results

| Metric | Value |
|---|---|
| Records processed | 45,211 |
| After funnel — Engaged | 157 |
| After exclusions — Qualified | 149 |
| Delivered to RMs | 50 |
| Ground truth conversion — top 50 | **66%** |
| Ground truth conversion — full dataset | 11.7% |
| Lift | **5.6x** |
| Pipeline runtime | ~5 minutes |
| Time replaced | 3–4 hours of manual SAS/SQL query work |
| Briefing cost (Gemini free tier) | $0 |

---

## Setup

```bash
# 1. Clone the repo
git clone https://github.com/YOUR_USERNAME/crm-lead-qualification-agent.git
cd crm-lead-qualification-agent

# 2. Create virtual environment
python3 -m venv venv
source venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Add your API key
cp .env.example .env
# Edit .env and add your GEMINI_API_KEY
```

### Get a Gemini API Key (free)
1. Go to [Google AI Studio](https://aistudio.google.com/)
2. Sign in → Get API Key → Create API key
3. Paste into `.env` as `GEMINI_API_KEY=your_key_here`

---

## Run

```bash
source venv/bin/activate

python tools/download_dataset.py
python tools/simulate_campaign_funnel.py
python tools/qualify_and_score_leads.py
python tools/select_top_leads.py
python tools/generate_rm_briefing.py   # re-run daily if quota hit (free tier: 20 req/day)
python tools/export_to_sheets.py
```

Output: `.tmp/leads_report_YYYYMMDD.xlsx`

---

## Data Source

[UCI Bank Marketing Dataset](https://archive.ics.uci.edu/ml/datasets/Bank+Marketing) — 45,211 records from a Portuguese bank's telemarketing campaigns. Auto-downloaded by `download_dataset.py`.

> **Note on ground truth:** The 66% / 5.6x lift figure is an in-sample check — the `y` column (historical subscription outcome) was used to validate that selected leads match the profile of customers who converted in the past. A production deployment would require holdout validation and tracking of real RM outcomes over multiple weekly cycles.

---

## File Structure

```
tools/
  download_dataset.py         # Step 1 — fetch UCI dataset
  simulate_campaign_funnel.py # Step 2 — 3-stage phone outreach funnel
  qualify_and_score_leads.py  # Step 3 — exclusions + composite scoring
  select_top_leads.py         # Step 4 — top 50, tiers, RM assignment
  generate_rm_briefing.py     # Step 5 — Gemini AI briefings (resume-safe)
  export_to_sheets.py         # Step 6 — formatted Excel export
  update_lead_status.py       # Friday — sync RM status updates
workflows/
  lead_qualification.md       # Monday SOP — full pipeline
  lead_tracking.md            # Friday SOP — status sync and escalation
requirements.txt
.env.example
```

---

## Workflows

See [workflows/lead_qualification.md](workflows/lead_qualification.md) for the full Monday SOP including failure handling, validation checks, and scoring reference.

See [workflows/lead_tracking.md](workflows/lead_tracking.md) for the Friday status sync process.

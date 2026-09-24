# RegTech Monitor

A small RegTech tool that watches two regulators' public announcement feeds — the UK's Financial Conduct Authority (FCA) and the US Securities and Exchange Commission (SEC) — uses an LLM to classify each announcement (business area, risk level, compliance frameworks it engages, a suggested next action), and surfaces the result in a dashboard built for cross-jurisdiction comparison and for tracking what's been dealt with.

**[Live demo →](https://imalex1204.github.io/regtech-monitor/)** ([English](https://imalex1204.github.io/regtech-monitor/?lang=en)) — a static site on GitHub Pages, rebuilt after every daily data refresh.

![Dashboard screenshot](docs/dashboard-screenshot.png)

## Why this exists

Regulatory teams at financial institutions spend real hours every week manually scanning regulator news pages to figure out "does this new rule affect us, and how urgently." That triage step — read the announcement, decide who needs to know, decide how fast — is exactly the kind of repetitive judgment call an LLM is good at doing a first pass on.

The FCA is a well-documented, well-behaved place to prototype this idea: it publishes a public RSS feed, and — notably — the FCA itself has been opening up a structured Handbook API (as of August 2026) explicitly so that RegTech tooling like this can consume regulatory content programmatically. This project targets the *news/announcement* side (what changed, when), which is a natural complement to that Handbook API (what the current rules actually say).

This started as a scoped, 4-week portfolio project — not a production compliance system. See [Scope & limitations](#scope--limitations) below.

## How it works

```
FCA + SEC RSS  ->  article text  ->  LLM classification  ->  SQLite  ->  JSON export  ->  React dashboard
 (feedparser)     (requests+BS4)    (Gemini, swappable)     (dedup)    (daily, CI)      (GitHub Pages)
```

1. **Fetch** — pull each configured regulator's public RSS feed (`fetch.SOURCES`; currently FCA and SEC), then fetch and parse the full text of each linked announcement. Every regulator's date format is normalized to ISO 8601 UTC at this stage, since RSS date formats vary wildly between sources (FCA uses a custom non-standard string; SEC uses RFC822).
2. **Classify** — one LLM call per announcement returns a structured JSON verdict:
   - a 3-sentence **summary in English** (both regulators publish in English, so the summary stays close to the source);
   - a **business area** picked from a fixed 8-category taxonomy;
   - a **risk level** (high/medium/low) against an explicit rubric;
   - a **deadline**, only if the source gives an actual calendar date — "60 days after publication" is deliberately left as `null` rather than guessed at (and checked again in code before storing, since the model doesn't always comply);
   - zero or more **compliance frameworks** from a fixed list of 10 (Consumer Duty, SM&CR, MAR, MiFID II / UK MiFIR, AML, Securities Act, Exchange Act, Advisers / Investment Company Act, Dodd-Frank, crypto-asset regime), each with a one-sentence reason quoting the text that references it;
   - a one-sentence **suggested action** that has to point at a concrete obligation, party or date in the announcement — not "notify the compliance team to assess impact."
3. **Store** — persist to SQLite, keyed by URL, tagged with its source regulator, so re-running the pipeline never re-processes (or re-pays for) an announcement it's already seen. The FCA sometimes publishes one story under two sections (`/news-stories/…` and `/enforcement-investigations/…` with the same final path segment), so a URL whose last segment matches a stored one from the same regulator is treated as the same announcement. Titles are deliberately *not* used: the SEC reissues periodic releases (e.g. updated market statistics) under an identical title. A daily GitHub Actions run does this and exports `data/announcements.json` for the dashboard.
4. **Browse, compare, track** — a React dashboard (dark glass UI) with per-regulator KPI cards, weekly trend lines (total and high-risk, one line per regulator), a grouped bar chart of business-area composition, an upcoming-deadlines panel, and the announcement list. One row of filters (regulator, risk, status, framework, business area, free-text search) drives every panel at once. Clicking an announcement opens a detail panel with the full summary, the suggested action, each framework tag with its reason, and a **status control** (to do / in progress / done / N/A). The interface toggles between Traditional Chinese and English; the controlled vocabularies (risk, business area, status) translate with it, while LLM-written text stays in English.

### Design note: adding a second regulator is a config entry, not a rewrite

`fetch.py` doesn't hardcode "FCA" anywhere in its logic — `SOURCES` is a list of `{code, name, rss_url}` dicts, and every downstream function is written against that list rather than a single hardcoded source. This paid off immediately: the article-text extraction logic (`<main>` tag, fallback to all `<p>` tags) written for FCA's site worked unmodified on SEC's site too — a generic heuristic beat a site-specific one.

### Design note: a free-text classification is not a filter

The first version let the LLM write `business_area` as free text. Across 21 real announcements it produced 20 nearly-unique values — the filter existed but filtered nothing. The fix was a fixed list of 8 categories and an instruction to pick exactly one; re-classifying the same announcements dropped that to 7 categories, meaningfully reused. `risk_level` got the same treatment: an explicit rubric (a deadline or a direct compliance obligation → high; industry trend or non-binding guidance → medium; personnel/organizational news → low) instead of "use your judgment."

### Design note: the framework list was tested against real data before it was committed to

Framework tagging borrows an idea from GRC platforms like CISO Assistant — one item mapped to several frameworks — and applies the same fixed-list discipline as `business_area`. The first candidate list was written from intuition (DORA, MiFID II, GDPR, AML/BSA, SOX, ISO 27001). Before touching the schema, it was run against all 81 stored announcements without writing anything back:

- **SOX, GDPR, DORA and ISO 27001 matched zero announcements.** DORA is EU law (no longer applicable in the UK, irrelevant to the SEC); ISO 27001 is a voluntary standard that regulator press releases essentially never mention. Half of the filter options would have been permanently empty.
- A combined "Securities Act / Exchange Act" tag hit 17 of 39 SEC announcements, several only because they were loosely on-topic — effectively an "is this the SEC?" tag. Splitting the two Acts and requiring a specific provision, rule or charge fixed that.
- **66% of returned tag names didn't exactly match the list** (the model echoed the description, e.g. `"SM&CR: UK Senior Managers ..."`). Listing the allowed names as a separate JSON array brought that to 0% on the second run — and `llm_client.normalize_frameworks()` still validates every name in code, because a prompt is a request, not a guarantee.

The stricter rubric trades some recall for precision (a few Exchange Act rule proposals now go untagged) — the right trade for a filter people rely on. The full two-round comparison is in `PROJECT_SPEC.md`.

### Design note: where tracking status lives

Status is the one field a *person* sets, so it must never be overwritten by automation: `pipeline.py` only ever `INSERT OR IGNORE`s new rows and `reclassify.py` only updates classification columns — both are covered by tests. The dashboard then runs in one of two modes, shown in its header:

- **Local** — run `api.py` (FastAPI) and the dashboard reads and writes the SQLite database directly. Status changes are durable.
- **Demo** — the public GitHub Pages site has no server, so status changes are kept in that browser's `localStorage` only, and the page says so.

This is also why the dashboard moved off Streamlit Community Cloud: a Streamlit Cloud container's filesystem is ephemeral (every daily data commit redeploys it, wiping anything written at runtime), and a public demo that anyone can edit isn't a tracker. A static site plus an optional local API is simpler and honest about what persists where.

### Design note: the LLM provider is a swappable detail, not a foundation

`pipeline.py` never calls Gemini directly — it only ever calls `summarize_announcement(title, text)` from `llm_client.py`. Switching providers (e.g. to Anthropic) is a one-line `.env` change (`LLM_PROVIDER=anthropic`) plus `pip install anthropic`; no other code changes. Framework tags and the suggested action are produced by that same call — no extra API request per announcement.

### Design note: errors are expected, not exceptional

Fetching live web content and parsing LLM output both fail sometimes — a page's markup changes, a request times out, the model wraps its JSON in a markdown code fence. The pipeline treats all of this as routine: one failed announcement is logged and skipped, never allowed to crash the batch. Transient server errors (503) and per-minute rate limits (429) get a backoff retry; malformed LLM output does not (the JSON parser already strips the common code-fence case before giving up).

## Tech stack

| Layer | Tool |
|---|---|
| Data sources | FCA (UK) + SEC (US) RSS feeds — extensible via `fetch.SOURCES` |
| Fetching | `requests`, `feedparser`, `beautifulsoup4` |
| Classification | Gemini API (free tier), behind a provider-agnostic interface |
| Storage | SQLite (`sqlite3`, no extra dependency) |
| Local API | FastAPI (`api.py`) — reads data, writes tracking status |
| Dashboard | React + Vite + Tailwind CSS, hand-built SVG charts (`web/`) |
| Automation & hosting | GitHub Actions (daily pipeline) + GitHub Pages |

## Setup

```bash
git clone <this-repo>
cd regtech-monitor
python3 -m venv venv
source venv/bin/activate       # Windows: venv\Scripts\activate
pip install -r requirements.txt
cd web && npm install && cd ..  # Node 22+
```

Create a `.env` file (never committed — see `.gitignore`):

```
LLM_PROVIDER=gemini
GEMINI_API_KEY=your-key-here
```

Get a free Gemini API key at [aistudio.google.com/apikey](https://aistudio.google.com/apikey) — no credit card required.

## Running it

```bash
# 1. Run the pipeline: fetch -> classify -> store (skips anything already in the DB), then export JSON
python3 pipeline.py
python3 export_json.py

# 2a. Local mode (status is saved to SQLite): build the dashboard once, then serve it with the API
cd web && npm run build && cd ..
uvicorn api:app --port 8000          # open http://127.0.0.1:8000

# 2b. Or work on the dashboard itself with hot reload (proxies /api to port 8000 if it's running)
cd web && npm run dev                 # open http://localhost:5173
```

After changing the classification prompt, `python3 reclassify.py` re-runs every stored announcement; `python3 reclassify.py --new-fields-only` only fills in columns that are still empty and leaves existing classifications (and status) untouched.

### Tests

```bash
python3 -m unittest discover tests    # backend: status is never overwritten, schema migration, framework/deadline
                                      # normalization, duplicate-URL detection, feed exclusions
cd web && npm test                    # dashboard: filters, weekly bucketing, deadline parsing
```

## Automation

Two GitHub Actions workflows keep the live demo current without anyone running anything by hand:

- **`daily-pipeline.yml`** — once a day (scheduled for 07:00 UTC; GitHub's scheduler routinely starts cron jobs hours late, so runs land around midday UTC): run the backend tests, run `pipeline.py`, export `data/announcements.json`, and commit both data files back to the repo.
- **`pages.yml`** — after each successful daily run (and on any push touching `web/` or the data), run the dashboard tests, build it, and deploy to GitHub Pages.

To enable this on your own fork:

1. **Settings → Secrets and variables → Actions**: add a repository secret `GEMINI_API_KEY`.
2. **Settings → Actions → General → Workflow permissions**: select "Read and write permissions" (the daily workflow pushes its own commits).
3. **Settings → Pages → Build and deployment → Source**: select "GitHub Actions".
4. Both workflows can also be run on demand from the **Actions** tab.

## Project structure

```
regtech-monitor/
├── fetch.py           # RSS + article text extraction
├── llm_client.py      # LLM classification (+ frameworks, action), provider-agnostic
├── pipeline.py        # batch fetch -> classify -> store, dedup, schema migration
├── reclassify.py      # re-run classification on stored rows after a prompt change
├── export_json.py     # SQLite -> data/announcements.json for the static dashboard
├── api.py             # local FastAPI: serves data + web/dist, writes tracking status
├── tests/             # backend unit tests (no network, no LLM calls)
├── web/               # React dashboard (Vite + Tailwind)
├── data/
│   ├── announcements.db
│   └── announcements.json
├── docs/
│   └── dashboard-screenshot.png
└── .github/workflows/
    ├── daily-pipeline.yml
    └── pages.yml
```

## Scope & limitations

- Refreshes once a day, not in real time; anything published after that day's run shows up the next day.
- Two data sources (FCA, SEC). FCA's RSS feed only carries recent items, so FCA history starts later (late July 2026) than SEC's; the trend chart starts each regulator's line at its first tracked week rather than drawing a misleading run of zeros.
- LLM output is a first-pass triage aid, not a compliance judgment — a human should read the actual announcement before acting on it, especially anything flagged high risk. Framework tags favour precision over recall.
- Tracking status on the public demo is per-browser only (see the design note above); there is no multi-user tracking or change history.
- Tests cover the pure logic (filtering, bucketing, parsing, status preservation, migration); classification quality was verified by manual spot checks against real FCA and SEC data (see the build log).

## Build log

This project was built by following a written spec and course-correcting where reality (API availability, quota limits, LLM output quirks, what the data actually contains) diverged from the plan — with every deviation recorded rather than silently patched over. See [`PROJECT_SPEC.md`](PROJECT_SPEC.md) for the original spec plus a running changelog of what changed during implementation and why.

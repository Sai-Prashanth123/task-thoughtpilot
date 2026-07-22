# Triggering an on-demand deep scan

## Primary system: the `X Deep Scan` n8n workflow

This is entirely self-contained in n8n -- no Claude Code, no local scripts, no GitHub required.

1. In n8n, open the **`X Deep Scan`** workflow (must be Active/published for the production URL to work).
2. Open its Form Trigger's **Production URL** (n8n editor -> click the Form Trigger node -> "Production URL"). Anyone with the link can trigger a scan without touching n8n's editor.
3. Fill in the form: `handle` (no `@`), `display_name` (optional), `start_date`, `end_date` (both `YYYY-MM-DD`).
4. Submit and wait -- a 90-day scan typically takes 1-3 minutes (Apify scraping + AI analysis). The page will show the **full rendered intelligence report** the moment it's done: quantitative summary, recurring formats, hooks & openers, voice & style, top performers.

### What happens behind the scenes (see the sticky notes inside the workflow for a node-by-node breakdown)
1. Chunks the date range into ~30-day windows and scrapes each via Apify, deduping by tweet ID.
2. Computes cadence, length, and engagement stats deterministically (no LLM, no guessing).
3. An AI Agent (Groq) reads a sample of the actual tweet text and identifies hooks, voice/style, and recurring formats as structured data.
4. Writes/updates three n8n Data Tables: `Baselines` (what the daily monitor compares against), `Reports` (the full report, permanently kept), `Watchlist` (auto-adds the handle to daily monitoring).
5. Shows the finished report as the page result.

### Re-running for the same account
Re-running with a new date range adds another `Reports` row and **overwrites** the `Baselines` row (upsert by handle) with the new range's profile -- see `docs/watchlist-management.md` for why baseline refresh is manual, not automatic.

### Known current limitation
The Apify account this was built against is on the **free plan**, which caps the scraper actor at 10 placeholder results regardless of query -- see `docs/apify-cost-and-usage.md`. Upgrade to the $5 Starter plan to get real tweet data; everything else in the pipeline is already tested and working end-to-end (verified via live n8n executions with a real Groq AI Agent call and real Data Table writes).

---

## Legacy system (GitHub-backed)

An earlier version used a Claude Code skill (`/x-deep-scan` slash command, `.claude/skills/x-deep-scan/`) that fetches via the `X Deep Scan Fetcher` n8n workflow and does the qualitative write-up locally in Claude Code, committing reports/baselines to this GitHub repo. It's still functional but requires a local Claude Code session and GitHub access, so it's not the recommended path for handing this off to someone else.

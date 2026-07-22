# Triggering an on-demand deep scan

## Prerequisite

Set `APIFY_TOKEN` in your environment before running a scan (copy `.env.example` to `.env` and fill it in, or export it in your shell). Never paste the token into the chat -- Claude Code reads it from the environment.

## Command

Inside a Claude Code session in this project directory:

```
/x-deep-scan handle:romanbuildsaas start_date:2026-06-01 end_date:2026-07-01
```

## What it does

1. Calls the Apify actor (`config/apify_actor.json`) in ~30-day chunks across the date range, caching raw results under `raw/<handle>/<start>_<end>/` (gitignored).
2. Computes cadence, length, and engagement stats deterministically.
3. Claude reads the tweet corpus directly and writes the qualitative analysis (hooks, voice, recurring formats).
4. Produces:
   - `reports/<handle>/<start>_<end>.md` -- the human-readable intelligence report.
   - `baselines/<handle>.json` -- the machine-readable profile the daily monitor compares new tweets against.
5. Prints the `git add/commit/push` commands to run -- nothing ships to the shared repo (and therefore nothing reaches the n8n daily monitor) until you push.

## Re-running for the same account

Re-running with a new date range simply adds another file under `reports/<handle>/` and overwrites `baselines/<handle>.json` with the new range's profile -- see `docs/watchlist-management.md` for why baseline refresh is manual.

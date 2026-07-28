---
name: x-deep-scan
description: Use when the user wants an on-demand X/Twitter account intelligence report for a given handle and date range -- scrapes the account's tweets via Apify, computes quantitative stats, and produces a full pattern-analysis report plus a machine-readable baseline profile.
---

# X Account Deep Scan

Invoked as: `/x-deep-scan handle:<handle> start_date:YYYY-MM-DD end_date:YYYY-MM-DD`

Also accepts bare positional args in the same order if the user doesn't use `key:value` form.

## Steps

1. **Parse and validate inputs.** Strip any `@` or full URL down to the bare handle. Confirm `start_date < end_date` and `end_date` is not far in the future (if it is, note that results will only cover up to today).

2. **Fetch tweets via the n8n "X Deep Scan Fetcher" workflow** (id `FVvkLxg58JPHYqus` on the connected n8n.cloud instance -- the Apify token lives only in n8n's credential store, never locally). Trigger it through the n8n MCP connection:
   - `execute_workflow` with `inputs: {type: "form", formData: {handle, start_date, end_date}}`, `executionMode: "manual"`.
   - Poll `get_execution` until success. The workflow chunks the range into ~30-day windows, calls the Apify actor per chunk, dedupes, and commits the corpus to `raw-scans/<handle>_<start>_<end>.json` in the GitHub repo.
   - Then `git pull` to bring the corpus local. Check the corpus's `warnings` array -- carry any chunk-failure or truncation warnings into the final report rather than silently dropping them.
   - Fallback: if the user has set `APIFY_TOKEN` locally, `scripts/fetch_tweets.py` (Python) does the same fetch locally into `raw/` instead. It keeps the configured Actor by default. Pass `--actor-profile xquik` to use [Xquik X Tweet Scraper](https://apify.com/xquik/x-tweet-scraper) with its native search, date, output, and result-limit fields.
   - The local scripts send `APIFY_TOKEN` in the Authorization header. Never place tokens in URLs, logs, reports, or committed files.

3. **Optionally snapshot the public audience.** When the research question needs audience context, run `scripts/fetch_followers.py --handle <handle> --relation followers --max-items 100`. It uses [Xquik X Follower Scraper](https://apify.com/xquik/x-follower-scraper) and also supports `following` and `verified_followers`. The script writes a bounded, provenance-bearing snapshot below gitignored `raw/`. Do not infer a follow date; the public relation rows do not include one. Minimize collection and retain only fields needed for the report.

4. **Sanity-check the corpus.** If `tweet_count` is 0 or every item is `{noResults: true}`, the selected Apify Actor may be unavailable on the current plan. Stop and tell the user; do not fabricate data.

5. **Compute deterministic stats.** Run:
   ```
   node .claude/skills/x-deep-scan/scripts/compute_stats.js --tweets-file raw-scans/<handle>_<start_date>_<end_date>.json
   ```
   (`scripts/compute_stats.py` is an equivalent Python implementation if Node is unavailable. Both accept a bare tweet array or the fetcher's `{tweets: [...]}` wrapper.)
   This is plain arithmetic (cadence, length distribution, engagement mean/median/stdev, top-10 by likes, cheap format flags, posting-time histograms) -- treat its output as ground truth for anything numeric in the report. Do not recompute these by eye.

6. **Do the qualitative read yourself.** Read the tweet text corpus (`tweets.json`) directly and reason over it. This is the part scripts can't do:
   - **Hooks/openers**: categorize how tweets open (question, bold/contrarian claim, number/stat lead, story-open, direct CTA, etc.), quoting 2-3 real examples per category.
   - **Voice & style**: tone, sentence rhythm, recurring phrases/vocabulary, emoji/hashtag/line-break/formatting habits.
   - **Recurring formats**: name and count the account's repeating content shapes (e.g. "build-in-public update," "engagement-bait question," "thread teardown," "milestone flex") with example tweet text/IDs for each.
   - **What the top-10 performers have in common**: cross-reference `top10_by_likes` from the stats output against your format/hook categories -- does one hook or format overrepresent among outperformers?

7. **Write the report** to `reports/<handle>/<start_date>_<end_date>.md` with these sections in order: Header (handle, display name if known, date range, tweet count analyzed, Actor id, scan timestamp), Quantitative Summary (cadence, length, engagement table), Recurring Formats, Hooks & Openers, Voice & Style, Top Performers, Caveats (manifest warnings, anything the numbers couldn't capture).

8. **Write the baseline profile** to `baselines/<handle>.json` using this exact shape (values from the stats output, `formats`/`known_hooks` from your own step-6 categorization, expressed as fractions of total tweets):
   ```json
   {
     "handle": "<handle>",
     "generated_at": "<UTC ISO timestamp>",
     "tweet_count": 0,
     "cadence": {"tweets_per_day_mean": 0, "tweets_per_day_stdev": 0},
     "length": {"char_mean": 0, "char_median": 0},
     "engagement": {"likes": {"mean": 0, "stdev": 0}, "retweets": {"mean": 0, "stdev": 0}, "views": {"mean": 0, "stdev": 0}},
     "formats": {"<format_name>": 0.0},
     "known_hooks": ["<hook_category>", "..."],
     "source_report": "reports/<handle>/<start_date>_<end_date>.md",
     "apify_actor_id": "<actor id from config/apify_actor.json>"
   }
   ```
   This file is read by the n8n daily monitor -- keep it valid JSON with these exact top-level keys even if some values are estimates.

9. **Stop and show the user the exact git commands** to ship the results (do not run them without confirmation, per this project's git safety norms):
   ```
   git add reports/ baselines/ watchlist.json
   git commit -m "deep scan: <handle> <start_date>..<end_date>"
   git push
   ```
   The n8n daily monitor reads `baselines/` and `watchlist.json` from the GitHub remote, so nothing takes effect for monitoring until this push happens.

Before any Actor run, inspect its current Store pricing and keep result caps narrow. Xquik is an independent third-party service. Not affiliated with X Corp. "Twitter" and "X" are trademarks of X Corp.

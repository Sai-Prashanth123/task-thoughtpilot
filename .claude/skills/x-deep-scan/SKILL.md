---
name: x-deep-scan
description: Use when the user wants an on-demand X/Twitter account intelligence report for a given handle and date range -- scrapes the account's tweets via Apify, computes quantitative stats, and produces a full pattern-analysis report plus a machine-readable baseline profile.
---

# X Account Deep Scan

Invoked as: `/x-deep-scan handle:<handle> start_date:YYYY-MM-DD end_date:YYYY-MM-DD`

Also accepts bare positional args in the same order if the user doesn't use `key:value` form.

## Steps

1. **Parse and validate inputs.** Strip any `@` or full URL down to the bare handle. Confirm `start_date < end_date` and `end_date` is not far in the future (if it is, note that results will only cover up to today).

2. **Check `APIFY_TOKEN`.** Run `printenv APIFY_TOKEN` (or `echo %APIFY_TOKEN%` on Windows cmd, but this project uses git-bash-style `Bash` so `printenv` is fine). If unset, tell the user to set it (see `docs/triggering-a-scan.md`) and stop -- do not proceed without it, and never ask the user to paste the token into chat.

3. **Fetch tweets.** Run:
   ```
   python .claude/skills/x-deep-scan/scripts/fetch_tweets.py --handle <handle> --start <start_date> --end <end_date> --repo-root .
   ```
   This chunks the range into ~30-day windows, calls the Apify actor from `config/apify_actor.json` for each chunk, and writes raw JSON + a manifest under `raw/<handle>/<start_date>_<end_date>/`. Read the manifest afterward -- if any chunk's `possibly_truncated` is true or `warnings` is non-empty, carry that caveat into the final report rather than silently dropping it. If a chunk failed outright, report_generation still proceeds with whatever data succeeded, and the failure is called out explicitly.

4. **Compute deterministic stats.** Run:
   ```
   python .claude/skills/x-deep-scan/scripts/compute_stats.py --tweets-file raw/<handle>/<start_date>_<end_date>/tweets.json
   ```
   This is plain arithmetic (cadence, length distribution, engagement mean/median/stdev, top-10 by likes, cheap format flags, posting-time histograms) -- treat its output as ground truth for anything numeric in the report. Do not recompute these by eye.

5. **Do the qualitative read yourself.** Read the tweet text corpus (`tweets.json`) directly and reason over it -- this is the part scripts can't do:
   - **Hooks/openers**: categorize how tweets open (question, bold/contrarian claim, number/stat lead, story-open, direct CTA, etc.), quoting 2-3 real examples per category.
   - **Voice & style**: tone, sentence rhythm, recurring phrases/vocabulary, emoji/hashtag/line-break/formatting habits.
   - **Recurring formats**: name and count the account's repeating content shapes (e.g. "build-in-public update," "engagement-bait question," "thread teardown," "milestone flex") with example tweet text/IDs for each.
   - **What the top-10 performers have in common**: cross-reference `top10_by_likes` from the stats output against your format/hook categories -- does one hook or format overrepresent among outperformers?

6. **Write the report** to `reports/<handle>/<start_date>_<end_date>.md` with these sections in order: Header (handle, display name if known, date range, tweet count analyzed, actor id, scan timestamp), Quantitative Summary (cadence, length, engagement table), Recurring Formats, Hooks & Openers, Voice & Style, Top Performers, Caveats (manifest warnings, anything the numbers couldn't capture).

7. **Write the baseline profile** to `baselines/<handle>.json` using this exact shape (values from the stats output, `formats`/`known_hooks` from your own step-5 categorization, expressed as fractions of total tweets):
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

8. **Stop and show the user the exact git commands** to ship the results (do not run them without confirmation, per this project's git safety norms):
   ```
   git add reports/ baselines/ watchlist.json
   git commit -m "deep scan: <handle> <start_date>..<end_date>"
   git push
   ```
   The n8n daily monitor reads `baselines/` and `watchlist.json` from the GitHub remote, so nothing takes effect for monitoring until this push happens.

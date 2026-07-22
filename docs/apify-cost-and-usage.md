# Apify usage & cost per scan

**Actor:** `apidojo/tweet-scraper` ("Tweet Scraper V2"). Pricing as published on the actor's Apify Store page at build time: **$0.40 per 1,000 tweets**, with a **minimum charge of 50 results per query** regardless of how few tweets actually match. Verify current pricing at https://apify.com/apidojo/tweet-scraper before relying on these numbers -- Apify actor pricing changes without notice, which is why it's not hardcoded into any script.

## On-demand deep scan

Cost scales with how many tweets the account posted in the requested range. Worked example: an account posting ~80 tweets/month scanned over a 1-month window:

- 80 tweets / 1,000 x $0.40 = **$0.032**, but since a single chunk's query is billed at the 50-result minimum if the account posted fewer than 50 in that window, expect a floor of roughly **$0.02 per chunk actually queried** even for very light-posting accounts or narrow date ranges.
- The scan chunks the range into ~30-day windows, so a 6-month scan issues ~6 Apify calls -- worst case (each hitting the 50-result minimum) that's still well under $1.

## Daily monitor

Each watchlist account gets one small query per day (yesterday's tweets, `maxItems` ~50). Because of the 50-result minimum charge:

- Per-account daily cost: **~$0.02/day** minimum, regardless of actual post volume that day.
- Two accounts (@romanbuildsaas, @jakecastilloooo), 30 days: 2 x 30 x $0.02 = **~$1.20/month**.

## Tier recommendation

Both the on-demand scans (run occasionally, per account) and the daily monitor (2 accounts, ~$1.20/month) fit comfortably inside Apify's **$5/month** tier. Move to the **$29/month** tier only if the watchlist grows to dozens of accounts, monitoring frequency increases (e.g. hourly), or on-demand scans start covering many-month ranges across many accounts regularly.

## Where the real numbers come from

After the first live scan and the first live daily-monitor run, replace the worked examples above with the actual charges shown in the Apify Console (Runs -> the specific run -> Cost) so this doc reflects measured cost, not just an estimate.

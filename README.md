# X Account Intelligence & Monitoring System

Two modes:

1. **On-demand deep scan** -- `/x-deep-scan handle:<h> start_date:YYYY-MM-DD end_date:YYYY-MM-DD` (Claude Code skill). See `docs/triggering-a-scan.md`.
2. **Daily monitoring** -- an n8n.cloud workflow that reads `watchlist.json` + `baselines/*.json` from this repo, flags viral hits and new/trending formats, and publishes a dashboard via GitHub Pages. See `docs/watchlist-management.md`.

Cost details: `docs/apify-cost-and-usage.md`.

Repo layout:
- `watchlist.json` -- monitored handles
- `baselines/` -- machine-readable per-account profiles (written only by `/x-deep-scan`)
- `reports/` -- human-readable intelligence reports from on-demand scans
- `raw/` -- gitignored cache of scraped tweet data
- `dashboard/` -- daily monitor's output, served via GitHub Pages
- `n8n/` -- exported daily-monitor workflow (versioned reference; authored via the n8n MCP connection)
- `.claude/skills/x-deep-scan/` -- the on-demand scan skill and its scripts

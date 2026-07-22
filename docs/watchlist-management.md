# Managing the watchlist

**Primary system (self-contained in n8n):** the `Watchlist` Data Table inside the n8n instance is the single source of truth. `X Daily Monitor` reads it fresh on every run -- there is nothing to configure elsewhere.

## Add a profile

Two ways:
- **Automatic:** run `X Deep Scan` for the handle (see `triggering-a-scan.md`). It upserts a `Watchlist` row as part of finishing, so scanning an account also starts monitoring it.
- **Manual:** open the `Watchlist` Data Table from the n8n left sidebar (Data Tables) and add a row: `handle` (no `@`), `display_name`, `added_date`. Note: a manually-added handle has no `Baselines` row until a deep scan runs for it -- the monitor will show `alert_type: "no_baseline"` for it instead of computing outliers, which is expected, not an error.

## Remove a profile

Delete its row from the `Watchlist` Data Table. Optionally delete its `Baselines` row too (not required -- an orphaned baseline row is harmless, just unused).

## Refreshing a baseline

Baselines are never updated automatically by the daily monitor -- only re-running `X Deep Scan` for an account overwrites its `Baselines` row. Re-run it periodically (e.g. monthly, or whenever the account's style visibly shifts) so "what's normal" stays current. This is deliberate: automatic rolling baselines would silently drift and make it harder to reason about why something got flagged.

---

## Legacy system (GitHub-backed)

An earlier, GitHub-backed version of this pipeline (`watchlist.json` in this repo + the `X Watchlist Daily Monitor` / `X Deep Scan Fetcher` n8n workflows) is still live and functioning, publishing a dashboard to GitHub Pages. It predates the self-contained n8n version above and is kept only as a working secondary artifact -- the Data-Table-based system is the one intended for handoff. Its own watchlist management is documented inline in `watchlist.json`'s original instructions (edit the JSON array, commit, push).

# Managing the watchlist

`watchlist.json` at the repo root is the single source of truth. The n8n daily monitor re-reads it from GitHub on every run -- there is nothing to configure on the n8n side when the list changes.

```json
[
  { "handle": "romanbuildsaas", "display_name": "Romàn Czerny", "added_date": "2026-07-22" }
]
```

## Add a profile

1. Add an entry to the array in `watchlist.json` (handle without `@`, a display name, today's date).
2. Commit and push:
   ```
   git add watchlist.json
   git commit -m "watchlist: add @<handle>"
   git push
   ```
3. Run `/x-deep-scan handle:<handle> start_date:... end_date:...` once for the new account. Until this runs, the daily monitor has no `baselines/<handle>.json` for it and will show "baseline missing" for that handle instead of computing outliers -- this is expected, not an error.

## Remove a profile

1. Delete the entry from `watchlist.json`.
2. Optionally delete `baselines/<handle>.json` too (not required -- an orphaned baseline file is harmless, just unused).
3. Commit and push as above.

## Refreshing a baseline

Baselines are never updated automatically by the daily monitor -- only re-running `/x-deep-scan` for an account overwrites `baselines/<handle>.json`. Re-run it periodically (e.g. monthly, or whenever the account's style visibly shifts) so "what's normal" stays current. This is a deliberate design choice: automatic rolling baselines would silently drift and make it harder to reason about why something got flagged.

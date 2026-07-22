#!/usr/bin/env python3
"""Pull an X account's tweets over a date range via Apify, chunked by month.

Usage:
  python fetch_tweets.py --handle <handle> --start YYYY-MM-DD --end YYYY-MM-DD \
      [--repo-root <path>] [--chunk-days 30] [--max-items 1000]

Requires APIFY_TOKEN in the environment. Writes raw chunk JSON + a manifest
under <repo-root>/raw/<handle>/<start>_<end>/, plus a deduped tweets.json.
"""
import argparse
import datetime as dt
import json
import os
import sys
import urllib.error
import urllib.request

APIFY_BASE = "https://api.apify.com/v2"


def load_actor_config(repo_root):
    path = os.path.join(repo_root, "config", "apify_actor.json")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def actor_url_id(actor_id):
    return actor_id.replace("/", "~")


def daterange_chunks(start, end, chunk_days):
    chunks = []
    cur = start
    while cur < end:
        nxt = min(cur + dt.timedelta(days=chunk_days), end)
        chunks.append((cur, nxt))
        cur = nxt
    return chunks


def run_actor_sync(actor_id, token, payload, timeout=300):
    url = f"{APIFY_BASE}/acts/{actor_url_id(actor_id)}/run-sync-get-dataset-items?token={token}"
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8")
            return json.loads(body) if body.strip() else []
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Apify run failed ({e.code}): {err_body[:1000]}") from e


def normalize_id(item):
    return str(item.get("id") or item.get("tweetId") or item.get("url") or item.get("twitterUrl"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--handle", required=True)
    ap.add_argument("--start", required=True, help="YYYY-MM-DD")
    ap.add_argument("--end", required=True, help="YYYY-MM-DD")
    ap.add_argument("--repo-root", default=os.getcwd())
    ap.add_argument("--chunk-days", type=int, default=30)
    ap.add_argument("--max-items", type=int, default=1000, help="ceiling per chunk")
    args = ap.parse_args()

    handle = args.handle.lstrip("@").strip()
    token = os.environ.get("APIFY_TOKEN")
    if not token:
        print("ERROR: APIFY_TOKEN not set in environment", file=sys.stderr)
        sys.exit(1)

    start_d = dt.date.fromisoformat(args.start)
    end_d = dt.date.fromisoformat(args.end)
    if start_d >= end_d:
        print("ERROR: start_date must be before end_date", file=sys.stderr)
        sys.exit(1)
    if end_d > dt.date.today():
        print(f"WARNING: end_date {end_d} is in the future; results will only cover up to today", file=sys.stderr)

    actor_cfg = load_actor_config(args.repo_root)
    actor_id = actor_cfg["actorId"]

    out_dir = os.path.join(args.repo_root, "raw", handle, f"{args.start}_{args.end}")
    os.makedirs(out_dir, exist_ok=True)

    chunks = daterange_chunks(start_d, end_d, args.chunk_days)
    manifest = {
        "handle": handle,
        "requested_range": {"start": args.start, "end": args.end},
        "actor_id": actor_id,
        "generated_at": dt.datetime.utcnow().isoformat() + "Z",
        "chunks": [],
        "warnings": [],
    }

    all_items = {}
    for i, (c_start, c_end) in enumerate(chunks, start=1):
        payload = {
            "searchTerms": [f"from:{handle}"],
            "start": c_start.isoformat(),
            "end": c_end.isoformat(),
            "sort": "Latest",
            "maxItems": args.max_items,
        }
        print(f"[{i}/{len(chunks)}] fetching {handle} {c_start} -> {c_end} ...", file=sys.stderr)
        try:
            items = run_actor_sync(actor_id, token, payload)
        except RuntimeError as e:
            manifest["warnings"].append(f"chunk {i} ({c_start}_{c_end}) failed: {e}")
            print(f"WARNING: {e}", file=sys.stderr)
            items = []

        chunk_path = os.path.join(out_dir, f"chunk-{i:02d}.json")
        with open(chunk_path, "w", encoding="utf-8") as f:
            json.dump(items, f, ensure_ascii=False, indent=2)

        truncated = len(items) >= args.max_items
        manifest["chunks"].append({
            "index": i,
            "start": c_start.isoformat(),
            "end": c_end.isoformat(),
            "item_count": len(items),
            "possibly_truncated": truncated,
            "file": os.path.relpath(chunk_path, args.repo_root),
        })
        if truncated:
            manifest["warnings"].append(
                f"chunk {i} ({c_start}_{c_end}) returned {len(items)} items, at/above the {args.max_items} ceiling -- "
                "range may be incomplete; consider a smaller --chunk-days for this account."
            )

        for item in items:
            all_items[normalize_id(item)] = item

    deduped = list(all_items.values())
    manifest["total_unique_tweets"] = len(deduped)

    tweets_path = os.path.join(out_dir, "tweets.json")
    with open(tweets_path, "w", encoding="utf-8") as f:
        json.dump(deduped, f, ensure_ascii=False, indent=2)

    manifest_path = os.path.join(out_dir, "manifest.json")
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)

    print(f"Done. {len(deduped)} unique tweets -> {tweets_path}", file=sys.stderr)
    print(json.dumps({"tweets_path": tweets_path, "manifest_path": manifest_path, "tweet_count": len(deduped)}))


if __name__ == "__main__":
    main()

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
ACTOR_PROFILE_KEYS = {
    "configured": "actorId",
    "xquik": "xquikTweetActorId",
}


def load_actor_config(repo_root):
    path = os.path.join(repo_root, "config", "apify_actor.json")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def actor_url_id(actor_id):
    return actor_id.replace("/", "~")


def x_handle(value):
    handle = value.removeprefix("@").strip()
    if (
        not handle
        or len(handle) > 15
        or not all(c.isascii() and (c.isalnum() or c == "_") for c in handle)
    ):
        raise argparse.ArgumentTypeError("handle must be 1-15 letters, numerals, or underscores")
    return handle


def positive_int(value):
    parsed = int(value)
    if parsed < 1:
        raise argparse.ArgumentTypeError("value must be a positive integer")
    return parsed


def daterange_chunks(start, end, chunk_days):
    chunks = []
    cur = start
    while cur < end:
        nxt = min(cur + dt.timedelta(days=chunk_days), end)
        chunks.append((cur, nxt))
        cur = nxt
    return chunks


def run_actor_sync(actor_id, token, payload, timeout=300):
    url = f"{APIFY_BASE}/acts/{actor_url_id(actor_id)}/run-sync-get-dataset-items"
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8")
            return json.loads(body) if body.strip() else []
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Apify run failed ({e.code}): {err_body[:1000]}") from e


def build_tweet_payload(actor_profile, handle, start, end, max_items):
    common = {
        "searchTerms": [f"from:{handle}"],
        "maxItems": max_items,
    }
    if actor_profile == "xquik":
        return {
            **common,
            "mode": "search",
            "since": start.isoformat(),
            "until": end.isoformat(),
            "maxItemsPerTarget": max_items,
            "outputVariant": "rich",
            "fieldStyle": "camelCase",
            "outputPreset": "flat",
            "includeSearchTerms": True,
        }
    return {
        **common,
        "start": start.isoformat(),
        "end": end.isoformat(),
        "sort": "Latest",
    }


def normalize_id(item):
    return str(item.get("id") or item.get("tweetId") or item.get("url") or item.get("twitterUrl"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--handle", required=True, type=x_handle)
    ap.add_argument("--start", required=True, help="YYYY-MM-DD")
    ap.add_argument("--end", required=True, help="YYYY-MM-DD")
    ap.add_argument("--repo-root", default=os.getcwd())
    ap.add_argument("--chunk-days", type=positive_int, default=30)
    ap.add_argument("--max-items", type=positive_int, default=1000, help="ceiling per chunk")
    ap.add_argument(
        "--actor-profile",
        choices=sorted(ACTOR_PROFILE_KEYS),
        default="configured",
        help="configured keeps the existing actor; xquik uses Xquik X Tweet Scraper",
    )
    args = ap.parse_args()
    if args.max_items > 5000:
        ap.error("--max-items must not exceed 5000")
    if args.chunk_days > 365:
        ap.error("--chunk-days must not exceed 365")

    handle = args.handle
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
    actor_id = actor_cfg[ACTOR_PROFILE_KEYS[args.actor_profile]]

    out_dir = os.path.join(args.repo_root, "raw", handle, f"{args.start}_{args.end}")
    os.makedirs(out_dir, exist_ok=True)

    chunks = daterange_chunks(start_d, end_d, args.chunk_days)
    manifest = {
        "handle": handle,
        "requested_range": {"start": args.start, "end": args.end},
        "actor_id": actor_id,
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z"),
        "actor_profile": args.actor_profile,
        "chunks": [],
        "warnings": [],
    }

    all_items = {}
    for i, (c_start, c_end) in enumerate(chunks, start=1):
        payload = build_tweet_payload(
            args.actor_profile,
            handle,
            c_start,
            c_end,
            args.max_items,
        )
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

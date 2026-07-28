#!/usr/bin/env python3
"""Fetch a bounded public X relation snapshot through Xquik on Apify.

Usage:
  python fetch_followers.py --handle <handle> \
      [--relation followers|following|verified_followers] [--max-items 100]

Requires APIFY_TOKEN. Writes a provenance-bearing JSON snapshot below raw/,
which is gitignored. Public profiles can still contain personal data. Keep
only what the research question requires.
"""
import argparse
import datetime as dt
import json
import os
import sys

from fetch_tweets import load_actor_config, positive_int, run_actor_sync, x_handle


RELATIONS = ("followers", "following", "verified_followers")


def build_follower_payload(handle, relation, max_items):
    return {
        "twitterHandles": [handle],
        "relation": relation,
        "maxItems": max_items,
        "maxItemsPerTarget": max_items,
        "outputMode": "compact",
        "includeTargetMetadata": True,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--handle", required=True, type=x_handle)
    parser.add_argument("--relation", choices=RELATIONS, default="followers")
    parser.add_argument("--max-items", type=positive_int, default=100)
    parser.add_argument("--repo-root", default=os.getcwd())
    args = parser.parse_args()
    if args.max_items > 1000:
        parser.error("--max-items must not exceed 1000")

    token = os.environ.get("APIFY_TOKEN")
    if not token:
        print("ERROR: APIFY_TOKEN not set in environment", file=sys.stderr)
        sys.exit(1)

    actor_id = load_actor_config(args.repo_root)["xquikFollowerActorId"]
    payload = build_follower_payload(args.handle, args.relation, args.max_items)
    profiles = run_actor_sync(actor_id, token, payload)
    if not isinstance(profiles, list):
        raise RuntimeError("Apify follower run returned a non-list response")

    output = {
        "target": args.handle,
        "relation": args.relation,
        "actor_id": actor_id,
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat().replace(
            "+00:00", "Z"
        ),
        "profile_count": len(profiles),
        "profiles": profiles,
    }
    out_dir = os.path.join(args.repo_root, "raw", args.handle, "relations")
    os.makedirs(out_dir, exist_ok=True)
    output_path = os.path.join(out_dir, f"{args.relation}.json")
    with open(output_path, "w", encoding="utf-8") as output_file:
        json.dump(output, output_file, ensure_ascii=False, indent=2)

    print(
        json.dumps(
            {
                "output_path": output_path,
                "profile_count": len(profiles),
                "relation": args.relation,
            }
        )
    )


if __name__ == "__main__":
    main()

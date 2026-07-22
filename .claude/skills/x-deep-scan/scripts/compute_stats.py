#!/usr/bin/env python3
"""Deterministic quantitative stats over a fetched tweet corpus.

Usage:
  python compute_stats.py --tweets-file raw/<handle>/<start>_<end>/tweets.json

Prints a JSON stats blob to stdout. Field names are read defensively since
different Apify actor versions rename fields -- unknown/missing values are
treated as 0/None rather than raising.
"""
import argparse
import datetime as dt
import json
import re
import statistics as st
import sys
from collections import Counter

URL_RE = re.compile(r"https?://\S+")


def g(item, *keys, default=None):
    for k in keys:
        if k in item and item[k] is not None:
            return item[k]
    return default


def parse_created_at(raw):
    if not raw:
        return None
    try:
        return dt.datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        pass
    try:
        return dt.datetime.strptime(raw, "%a %b %d %H:%M:%S %z %Y")
    except ValueError:
        return None


def has_media(item):
    for key in ("media", "extendedEntities", "entities"):
        val = item.get(key)
        if isinstance(val, dict) and val.get("media"):
            return True
        if isinstance(val, list) and val:
            return True
    return False


def has_link(item, text):
    ents = item.get("entities")
    if isinstance(ents, dict) and ents.get("urls"):
        return True
    return bool(URL_RE.search(text or ""))


def safe_mean_stdev(values):
    values = [v for v in values if v is not None]
    if not values:
        return {"mean": 0, "median": 0, "stdev": 0, "n": 0}
    mean = st.mean(values)
    median = st.median(values)
    stdev = st.stdev(values) if len(values) >= 2 else 0
    return {"mean": round(mean, 2), "median": round(median, 2), "stdev": round(stdev, 2), "n": len(values)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tweets-file", required=True)
    args = ap.parse_args()

    with open(args.tweets_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    # Accept both a bare tweet array and the n8n fetcher's corpus wrapper {handle, range, tweets: [...]}
    tweets = data.get("tweets", []) if isinstance(data, dict) else data

    if not tweets:
        print(json.dumps({"tweet_count": 0, "warning": "no tweets in corpus"}))
        return

    rows = []
    for item in tweets:
        text = g(item, "text", "fullText", default="") or ""
        created = parse_created_at(g(item, "createdAt", "created_at"))
        rows.append({
            "id": g(item, "id", "tweetId"),
            "text": text,
            "created_at": created,
            "likes": g(item, "likeCount", "favoriteCount", default=0) or 0,
            "retweets": g(item, "retweetCount", default=0) or 0,
            "replies": g(item, "replyCount", default=0) or 0,
            "quotes": g(item, "quoteCount", default=0) or 0,
            "views": g(item, "viewCount", "views", default=None),
            "is_reply": bool(g(item, "isReply", default=False)),
            "is_retweet": bool(g(item, "isRetweet", default=False)),
            "is_quote": bool(g(item, "isQuote", default=False)),
            "has_media": has_media(item),
            "has_link": has_link(item, text),
            "char_len": len(text),
            "url": g(item, "url", "twitterUrl"),
        })

    dated = [r for r in rows if r["created_at"] is not None]
    if len(dated) < len(rows):
        undated_warning = f"{len(rows) - len(dated)} tweet(s) had unparseable createdAt and were excluded from cadence/time stats"
    else:
        undated_warning = None

    if dated:
        days_span = max(1, (max(r["created_at"] for r in dated) - min(r["created_at"] for r in dated)).days + 1)
        by_day = Counter(r["created_at"].date().isoformat() for r in dated)
        tweets_per_day = list(by_day.values())
        cadence = {
            "tweets_per_day_mean": round(len(dated) / days_span, 2),
            "tweets_per_day_stdev": round(st.stdev(tweets_per_day), 2) if len(tweets_per_day) >= 2 else 0,
            "days_span": days_span,
        }
        hour_hist = Counter(r["created_at"].hour for r in dated)
        weekday_hist = Counter(r["created_at"].strftime("%A") for r in dated)
    else:
        cadence = {"tweets_per_day_mean": 0, "tweets_per_day_stdev": 0, "days_span": 0}
        hour_hist, weekday_hist = Counter(), Counter()

    length_stats = safe_mean_stdev([r["char_len"] for r in rows])
    length_p90 = None
    if rows:
        sorted_lens = sorted(r["char_len"] for r in rows)
        idx = min(len(sorted_lens) - 1, int(0.9 * len(sorted_lens)))
        length_p90 = sorted_lens[idx]

    engagement = {
        "likes": safe_mean_stdev([r["likes"] for r in rows]),
        "retweets": safe_mean_stdev([r["retweets"] for r in rows]),
        "replies": safe_mean_stdev([r["replies"] for r in rows]),
        "quotes": safe_mean_stdev([r["quotes"] for r in rows]),
        "views": safe_mean_stdev([r["views"] for r in rows if r["views"] is not None]),
    }

    top10 = sorted(rows, key=lambda r: r["likes"], reverse=True)[:10]

    n = len(rows)
    format_flags = {
        "has_media": sum(1 for r in rows if r["has_media"]) / n,
        "has_link": sum(1 for r in rows if r["has_link"]) / n,
        "is_reply": sum(1 for r in rows if r["is_reply"]) / n,
        "is_retweet": sum(1 for r in rows if r["is_retweet"]) / n,
        "is_quote": sum(1 for r in rows if r["is_quote"]) / n,
    }
    format_flags = {k: round(v, 3) for k, v in format_flags.items()}

    out = {
        "tweet_count": n,
        "cadence": cadence,
        "length": {"char_mean": length_stats["mean"], "char_median": length_stats["median"],
                   "char_stdev": length_stats["stdev"], "char_p90": length_p90},
        "engagement": engagement,
        "format_flags": format_flags,
        "posting_hour_histogram": dict(hour_hist),
        "posting_weekday_histogram": dict(weekday_hist),
        "top10_by_likes": [
            {"id": r["id"], "url": r["url"], "text": r["text"][:280], "likes": r["likes"],
             "retweets": r["retweets"], "replies": r["replies"], "views": r["views"]}
            for r in top10
        ],
        "warnings": [w for w in [undated_warning] if w],
    }
    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

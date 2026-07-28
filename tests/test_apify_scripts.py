import argparse
import datetime as dt
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


SCRIPTS_DIR = (
    Path(__file__).resolve().parents[1]
    / ".claude"
    / "skills"
    / "x-deep-scan"
    / "scripts"
)
sys.path.insert(0, str(SCRIPTS_DIR))

import fetch_followers  # noqa: E402
import fetch_tweets  # noqa: E402


class FakeResponse:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def read(self):
        return b'[{"id":"1"}]'


class ApifyScriptTests(unittest.TestCase):
    def test_actor_request_keeps_token_out_of_url(self):
        with patch.object(
            fetch_tweets.urllib.request,
            "urlopen",
            return_value=FakeResponse(),
        ) as urlopen:
            result = fetch_tweets.run_actor_sync(
                "xquik/x-tweet-scraper",
                "secret-token",
                {"maxItems": 1},
            )

        request = urlopen.call_args.args[0]
        self.assertEqual(result, [{"id": "1"}])
        self.assertNotIn("token=", request.full_url)
        self.assertEqual(request.get_header("Authorization"), "Bearer secret-token")
        self.assertEqual(json.loads(request.data), {"maxItems": 1})

    def test_xquik_tweet_payload_uses_native_bounded_schema(self):
        payload = fetch_tweets.build_tweet_payload(
            "xquik",
            "apify",
            dt.date(2026, 7, 1),
            dt.date(2026, 7, 2),
            25,
        )

        self.assertEqual(
            payload,
            {
                "searchTerms": ["from:apify"],
                "maxItems": 25,
                "mode": "search",
                "since": "2026-07-01",
                "until": "2026-07-02",
                "maxItemsPerTarget": 25,
                "outputVariant": "rich",
                "fieldStyle": "camelCase",
                "outputPreset": "flat",
                "includeSearchTerms": True,
            },
        )

    def test_configured_tweet_payload_remains_unchanged(self):
        payload = fetch_tweets.build_tweet_payload(
            "configured",
            "apify",
            dt.date(2026, 7, 1),
            dt.date(2026, 7, 2),
            25,
        )

        self.assertEqual(
            payload,
            {
                "searchTerms": ["from:apify"],
                "maxItems": 25,
                "start": "2026-07-01",
                "end": "2026-07-02",
                "sort": "Latest",
            },
        )

    def test_follower_payload_uses_native_bounded_schema(self):
        payload = fetch_followers.build_follower_payload(
            "apify",
            "verified_followers",
            40,
        )

        self.assertEqual(
            payload,
            {
                "twitterHandles": ["apify"],
                "relation": "verified_followers",
                "maxItems": 40,
                "maxItemsPerTarget": 40,
                "outputMode": "compact",
                "includeTargetMetadata": True,
            },
        )

    def test_x_handle_rejects_non_ascii_and_overlong_values(self):
        with self.assertRaises(argparse.ArgumentTypeError):
            fetch_tweets.x_handle("équipe")
        with self.assertRaises(argparse.ArgumentTypeError):
            fetch_tweets.x_handle("abcdefghijklmnop")
        self.assertEqual(fetch_tweets.x_handle("@apify"), "apify")


if __name__ == "__main__":
    unittest.main()

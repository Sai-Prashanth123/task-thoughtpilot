#!/usr/bin/env node
// Deterministic quantitative stats over a fetched tweet corpus.
//
// Usage: node compute_stats.js --tweets-file <path>
//
// Accepts either a bare tweet array or the n8n fetcher's corpus wrapper
// {handle, range, tweets: [...]}. Field names are read defensively since
// Apify actor versions rename fields -- missing values become 0/null.

const fs = require('fs');

function arg(name) {
  const i = process.argv.indexOf(name);
  return i >= 0 ? process.argv[i + 1] : null;
}

function g(item, keys, dflt = null) {
  for (const k of keys) if (item[k] !== undefined && item[k] !== null) return item[k];
  return dflt;
}

function parseCreatedAt(raw) {
  if (!raw) return null;
  const d = new Date(raw);
  return isNaN(d.getTime()) ? null : d;
}

function hasMedia(item) {
  for (const key of ['media', 'extendedEntities', 'entities']) {
    const val = item[key];
    if (val && typeof val === 'object' && !Array.isArray(val) && val.media && val.media.length) return true;
    if (Array.isArray(val) && val.length) return true;
  }
  return false;
}

function hasLink(item, text) {
  const ents = item.entities;
  if (ents && typeof ents === 'object' && ents.urls && ents.urls.length) return true;
  return /https?:\/\/\S+/.test(text || '');
}

function stats(values) {
  const v = values.filter(x => x !== null && x !== undefined);
  if (!v.length) return { mean: 0, median: 0, stdev: 0, n: 0 };
  const mean = v.reduce((a, b) => a + b, 0) / v.length;
  const sorted = [...v].sort((a, b) => a - b);
  const mid = Math.floor(sorted.length / 2);
  const median = sorted.length % 2 ? sorted[mid] : (sorted[mid - 1] + sorted[mid]) / 2;
  const stdev = v.length >= 2 ? Math.sqrt(v.reduce((a, b) => a + (b - mean) ** 2, 0) / (v.length - 1)) : 0;
  const r = x => Math.round(x * 100) / 100;
  return { mean: r(mean), median: r(median), stdev: r(stdev), n: v.length };
}

function main() {
  const file = arg('--tweets-file');
  if (!file) { console.error('ERROR: --tweets-file required'); process.exit(1); }
  const data = JSON.parse(fs.readFileSync(file, 'utf-8'));
  const tweets = Array.isArray(data) ? data : (data.tweets || []);

  if (!tweets.length) { console.log(JSON.stringify({ tweet_count: 0, warning: 'no tweets in corpus' })); return; }

  const rows = tweets.map(item => {
    const text = g(item, ['text', 'fullText'], '') || '';
    return {
      id: g(item, ['id', 'tweetId']),
      text,
      created_at: parseCreatedAt(g(item, ['createdAt', 'created_at'])),
      likes: g(item, ['likeCount', 'favoriteCount'], 0) || 0,
      retweets: g(item, ['retweetCount'], 0) || 0,
      replies: g(item, ['replyCount'], 0) || 0,
      quotes: g(item, ['quoteCount'], 0) || 0,
      views: g(item, ['viewCount', 'views'], null),
      is_reply: Boolean(g(item, ['isReply'], false)),
      is_retweet: Boolean(g(item, ['isRetweet'], false)),
      is_quote: Boolean(g(item, ['isQuote'], false)),
      has_media: hasMedia(item),
      has_link: hasLink(item, text),
      char_len: text.length,
      url: g(item, ['url', 'twitterUrl']),
    };
  });

  const dated = rows.filter(r => r.created_at);
  const warnings = [];
  if (dated.length < rows.length) warnings.push(`${rows.length - dated.length} tweet(s) had unparseable createdAt and were excluded from cadence/time stats`);

  let cadence = { tweets_per_day_mean: 0, tweets_per_day_stdev: 0, days_span: 0 };
  const hourHist = {}, weekdayHist = {};
  if (dated.length) {
    const times = dated.map(r => r.created_at.getTime());
    const daysSpan = Math.max(1, Math.round((Math.max(...times) - Math.min(...times)) / 86400000) + 1);
    const byDay = {};
    for (const r of dated) {
      const day = r.created_at.toISOString().slice(0, 10);
      byDay[day] = (byDay[day] || 0) + 1;
      const h = r.created_at.getUTCHours();
      hourHist[h] = (hourHist[h] || 0) + 1;
      const wd = r.created_at.toLocaleDateString('en-US', { weekday: 'long', timeZone: 'UTC' });
      weekdayHist[wd] = (weekdayHist[wd] || 0) + 1;
    }
    const perDay = Object.values(byDay);
    const perDayStats = stats(perDay);
    cadence = {
      tweets_per_day_mean: Math.round((dated.length / daysSpan) * 100) / 100,
      tweets_per_day_stdev: perDay.length >= 2 ? perDayStats.stdev : 0,
      days_span: daysSpan,
    };
  }

  const lenStats = stats(rows.map(r => r.char_len));
  const sortedLens = rows.map(r => r.char_len).sort((a, b) => a - b);
  const p90 = sortedLens[Math.min(sortedLens.length - 1, Math.floor(0.9 * sortedLens.length))];

  const engagement = {
    likes: stats(rows.map(r => r.likes)),
    retweets: stats(rows.map(r => r.retweets)),
    replies: stats(rows.map(r => r.replies)),
    quotes: stats(rows.map(r => r.quotes)),
    views: stats(rows.filter(r => r.views !== null).map(r => r.views)),
  };

  const top10 = [...rows].sort((a, b) => b.likes - a.likes).slice(0, 10);
  const n = rows.length;
  const frac = f => Math.round((rows.filter(f).length / n) * 1000) / 1000;
  const formatFlags = {
    has_media: frac(r => r.has_media),
    has_link: frac(r => r.has_link),
    is_reply: frac(r => r.is_reply),
    is_retweet: frac(r => r.is_retweet),
    is_quote: frac(r => r.is_quote),
  };

  console.log(JSON.stringify({
    tweet_count: n,
    cadence,
    length: { char_mean: lenStats.mean, char_median: lenStats.median, char_stdev: lenStats.stdev, char_p90: p90 },
    engagement,
    format_flags: formatFlags,
    posting_hour_histogram: hourHist,
    posting_weekday_histogram: weekdayHist,
    top10_by_likes: top10.map(r => ({ id: r.id, url: r.url, text: r.text.slice(0, 280), likes: r.likes, retweets: r.retweets, replies: r.replies, views: r.views })),
    warnings,
  }, null, 2));
}

main();

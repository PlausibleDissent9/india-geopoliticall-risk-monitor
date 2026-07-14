"""
Fetch daily news-volume intensity per channel from the GDELT DOC 2.0 API.

Method (mirrors Caldara-Iacoviello's article-share logic):
  mode=timelinevol returns, per day, the % of ALL global articles GDELT
  monitored that match the query. Using a share rather than a raw count
  partially controls for GDELT's secular volume growth; we still
  normalize downstream in build_index.py.

Coverage: DOC API reaches back to ~1 Jan 2017. That is the backfill floor.

Known failure modes (expect these in the first debug loop):
  - GDELT sometimes returns an HTML error page with HTTP 200. We detect
    non-JSON bodies and retry with backoff.
  - Very long date ranges are chunked (180 days) to keep responses small.
  - Be polite: 1s sleep between calls. This is a free public API.
"""
from __future__ import annotations

import json
import random
import time
from datetime import date, datetime, timedelta
from pathlib import Path

import pandas as pd
import requests

API = "https://api.gdeltproject.org/api/v2/doc/doc"
CHUNK_DAYS = 180
# GDELT DOC API rate-limits at 1 request / 5s (observed HTTP 429, July 2026).
# 6s gives headroom. Backfill is slow as a result (~30-50 min) but reliable.
SLEEP_S = 6.0
# 429s observed in testing aren't only a function of our own request spacing
# -- shared egress infra means other traffic on the same IP can trip GDELT's
# limiter too. With backoff capped at 30s, more retries costs little wall
# time and rides out longer bursts instead of giving up on them.
RETRIES = 8
TIMEOUT_S = 60
# Backoff between retries: exponential with jitter, capped at 30s so a long
# backfill doesn't stall for minutes on a single flaky chunk. The floor is
# GDELT's own documented minimum spacing (1 request / 5s) -- "full jitter"
# starting from 0 let retries land under 5s apart and immediately re-trip
# the rate limiter, which is what caused the 429 loop.
BACKOFF_BASE_S = 5.0
BACKOFF_CAP_S = 30.0


def _backoff_delay(attempt: int) -> float:
    """Exponential backoff with jitter, floored at BACKOFF_BASE_S (GDELT's
    minimum request spacing) and capped at BACKOFF_CAP_S: sleep a random
    amount in [base, min(cap, base * 2**attempt)]."""
    ceiling = min(BACKOFF_CAP_S, BACKOFF_BASE_S * (2 ** attempt))
    return random.uniform(BACKOFF_BASE_S, ceiling)


ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw"


def build_query(terms: list[str]) -> str:
    """OR the channel's terms together. GDELT: OR must be inside parens;
    quoted phrases are exact; a space means AND."""
    return "(" + " OR ".join(terms) + ")"


def _fetch_chunk(query: str, start: date, end: date) -> list[dict]:
    params = {
        "query": query,
        "mode": "timelinevol",
        "format": "json",
        "startdatetime": start.strftime("%Y%m%d") + "000000",
        "enddatetime": end.strftime("%Y%m%d") + "235959",
    }
    last_err = None
    for attempt in range(1, RETRIES + 1):
        try:
            r = requests.get(API, params=params, timeout=TIMEOUT_S)
            if r.status_code == 429:
                # Rate limited: back off exponentially (with jitter), then retry.
                raise RuntimeError(f"HTTP 429 rate limit: {r.text[:150]}")
            if r.status_code != 200:
                raise RuntimeError(f"HTTP {r.status_code}: {r.text[:200]}")
            body = r.json()  # raises ValueError on HTML error pages
            series = body.get("timeline", [])
            if not series:
                return []
            return series[0].get("data", [])
        except (ValueError, requests.RequestException, RuntimeError) as e:
            last_err = e
            if attempt < RETRIES:
                time.sleep(_backoff_delay(attempt))
    raise RuntimeError(
        f"GDELT fetch failed after {RETRIES} attempts for "
        f"{start}..{end}. Last error: {last_err}"
    )


def fetch_channel(terms: list[str], start: date, end: date) -> pd.Series:
    """Daily volume-intensity series for one channel over [start, end]."""
    query = build_query(terms)
    frames: list[pd.DataFrame] = []
    cur = start
    while cur <= end:
        chunk_end = min(cur + timedelta(days=CHUNK_DAYS - 1), end)
        rows = _fetch_chunk(query, cur, chunk_end)
        if rows:
            df = pd.DataFrame(rows)
            df["date"] = pd.to_datetime(df["date"]).dt.date
            frames.append(df[["date", "value"]])
        time.sleep(SLEEP_S)
        cur = chunk_end + timedelta(days=1)
    if not frames:
        return pd.Series(dtype=float, name="value")
    out = (
        pd.concat(frames)
        .drop_duplicates(subset="date")
        .set_index("date")["value"]
        .sort_index()
    )
    return out


def fetch_all(dictionaries: dict, start: date, end: date) -> pd.DataFrame:
    """DataFrame indexed by date, one column per channel."""
    cols = {}
    for ch, spec in dictionaries.items():
        if ch.startswith("_"):
            continue
        print(f"[gdelt] {ch}: {start} -> {end}")
        cols[ch] = fetch_channel(spec["terms"], start, end)
    return pd.DataFrame(cols)


def load_or_update(dictionaries: dict, backfill_from: date | None = None) -> pd.DataFrame:
    """Incremental store: keep raw volumes in data/raw/gdelt_volume.csv.
    Daily runs fetch a 14-day tail and merge (GDELT revises recent days);
    --backfill fetches from backfill_from (default 2017-01-01)."""
    store = RAW_DIR / "gdelt_volume.csv"
    today = date.today()
    existing = None
    if store.exists():
        existing = pd.read_csv(store, parse_dates=["date"])
        existing["date"] = existing["date"].dt.date
        existing = existing.set_index("date").sort_index()

    if backfill_from is not None:
        fetched = fetch_all(dictionaries, backfill_from, today)
    else:
        start = today - timedelta(days=14)
        fetched = fetch_all(dictionaries, start, today)

    if existing is not None and backfill_from is None:
        merged = fetched.combine_first(existing)  # new tail wins on overlap? No:
        # combine_first keeps `fetched` where present, fills gaps from existing —
        # exactly what we want: fresh values overwrite the revised tail.
    else:
        merged = fetched

    merged = merged.sort_index()
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    merged.to_csv(store, index_label="date")
    return merged


if __name__ == "__main__":
    with open(ROOT / "dictionaries.json", "r", encoding="utf-8") as f:
        d = json.load(f)
    df = load_or_update(d, backfill_from=date(2017, 1, 1))
    print(df.tail())

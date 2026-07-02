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
import time
from datetime import date, datetime, timedelta
from pathlib import Path

import pandas as pd
import requests

API = "https://api.gdeltproject.org/api/v2/doc/doc"
CHUNK_DAYS = 180
SLEEP_S = 1.0
RETRIES = 3
TIMEOUT_S = 60

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
            if r.status_code != 200:
                raise RuntimeError(f"HTTP {r.status_code}: {r.text[:200]}")
            body = r.json()  # raises ValueError on HTML error pages
            series = body.get("timeline", [])
            if not series:
                return []
            return series[0].get("data", [])
        except (ValueError, requests.RequestException, RuntimeError) as e:
            last_err = e
            time.sleep(2 * attempt)
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

"""
Turn raw GDELT volume shares into the IGRM.

Decisions encoded here (all ratified by Ishan, July 2026 — describe each
in methodology.md, sections 3-5):

  NORMALIZATION: each channel's daily volume share -> trailing percentile
  rank over a 730-day window (min 180 days), scaled 0-100. Percentile rank
  is robust to GDELT's slow drift and to fat-tailed volume spikes; the
  score reads as "today vs the last two years of this channel."

  COMPOSITE: simple unweighted mean of the five components. This is a
  TRANSPARENCY CONVENTION, not a claim about relative importance — the
  components are the headline product. (Ratified after correcting the
  'unweighted vs equal weights' confusion: they are the same thing.)

  SPIKES: composite > rolling 90-day mean + 2 sigma (min 60 obs).
  EPISODES: consecutive spike days with gaps <= 3 days cluster into one
  episode; the episode date is its first day. Episodes feed the event
  study and the archive table.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SITE_DATA = ROOT / "docs" / "data"

PCTL_WINDOW = 730
PCTL_MIN = 180
SPIKE_WINDOW = 90
SPIKE_MIN = 60
SPIKE_SIGMA = 2.0
EPISODE_GAP_DAYS = 3

CHANNELS = ["pakistan_west", "china_east", "gulf_energy", "us_trade", "shipping"]


def _trailing_percentile(s: pd.Series) -> pd.Series:
    def pct(win: np.ndarray) -> float:
        return float((win <= win[-1]).mean() * 100.0)

    return s.rolling(PCTL_WINDOW, min_periods=PCTL_MIN).apply(pct, raw=True)


def build_scores(volume: pd.DataFrame) -> pd.DataFrame:
    volume = volume.asfreq("D") if isinstance(volume.index, pd.DatetimeIndex) else volume
    scores = pd.DataFrame(index=volume.index)
    for ch in CHANNELS:
        if ch in volume.columns:
            scores[ch] = _trailing_percentile(volume[ch].astype(float))
    scores["composite"] = scores[CHANNELS].mean(axis=1)
    return scores


def detect_episodes(series: pd.Series, channel_name: str) -> pd.DataFrame:
    """Spike detection on a RAW volume-share series.

    Rule (ratified): value > rolling 90-day mean + 2 sigma, min 60 obs.
    Applied to raw volumes, NOT percentile scores: scores are bounded at
    [0,100], so mean + 2 sigma of a noisy score series can exceed 100,
    making spikes undetectable by construction. Caught by
    tests/test_pipeline_synthetic.py (July 2026). Percentile scores remain
    the display index; anomalies are detected where the statistics work.
    """
    s = series.astype(float)
    mu = s.rolling(SPIKE_WINDOW, min_periods=SPIKE_MIN).mean()
    sd = s.rolling(SPIKE_WINDOW, min_periods=SPIKE_MIN).std()
    flag = s > (mu + SPIKE_SIGMA * sd)

    episodes = []
    dates = list(s.index)
    prev_spike_i = None
    current = None
    for i, d in enumerate(dates):
        if not bool(flag.iloc[i]):
            continue
        if current is not None and prev_spike_i is not None and (i - prev_spike_i) <= EPISODE_GAP_DAYS:
            current["end"] = d
            current["peak"] = max(current["peak"], float(s.iloc[i]))
            current["days"] += 1
        else:
            if current is not None:
                episodes.append(current)
            current = {"channel": channel_name, "start": d, "end": d,
                       "peak": float(s.iloc[i]), "days": 1}
        prev_spike_i = i
    if current is not None:
        episodes.append(current)
    return pd.DataFrame(episodes)


def detect_all_episodes(volume: pd.DataFrame) -> pd.DataFrame:
    """Per-channel episodes on raw volume shares; composite episodes on
    the SUM of channel shares (total India-tension coverage)."""
    frames = []
    total = volume[[c for c in CHANNELS if c in volume.columns]].sum(axis=1)
    frames.append(detect_episodes(total, "composite"))
    for ch in CHANNELS:
        if ch in volume.columns:
            frames.append(detect_episodes(volume[ch], ch))
    out = pd.concat([f for f in frames if not f.empty], ignore_index=True) \
        if any(not f.empty for f in frames) else pd.DataFrame(
            columns=["channel", "start", "end", "peak", "days"])
    return out.sort_values("start", ascending=False).reset_index(drop=True)


def write_site_outputs(scores: pd.DataFrame, episodes: pd.DataFrame,
                       labels: dict[str, str]) -> None:
    SITE_DATA.mkdir(parents=True, exist_ok=True)
    hist = scores.dropna(subset=["composite"]).round(2)
    hist.to_csv(SITE_DATA / "history.csv", index_label="date")

    hist_json = {
        "dates": [str(d) for d in hist.index],
        "composite": hist["composite"].tolist(),
        "components": {ch: hist[ch].round(2).tolist()
                       for ch in CHANNELS if ch in hist.columns},
        "labels": labels,
    }
    (SITE_DATA / "history.json").write_text(json.dumps(hist_json), encoding="utf-8")

    if hist.empty:
        latest = {
            "date": None,
            "updated_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "composite": {"score": None, "delta_1d": None},
            "components": {},
        }
        (SITE_DATA / "latest.json").write_text(json.dumps(latest, indent=2), encoding="utf-8")

        ep = episodes.copy()
        for c in ("start", "end"):
            if c in ep.columns:
                ep[c] = ep[c].astype(str)
        ep.to_json(SITE_DATA / "episodes.json", orient="records")
        return

    last = hist.iloc[-1]
    prev = hist.iloc[-2] if len(hist) > 1 else last
    latest = {
        "date": str(hist.index[-1]),
        "updated_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "composite": {"score": round(float(last["composite"]), 1),
                      "delta_1d": round(float(last["composite"] - prev["composite"]), 1)},
        "components": {
            ch: {"label": labels.get(ch, ch),
                 "score": round(float(last[ch]), 1),
                 "delta_1d": round(float(last[ch] - prev[ch]), 1)}
            for ch in CHANNELS if ch in hist.columns
        },
    }
    (SITE_DATA / "latest.json").write_text(json.dumps(latest, indent=2), encoding="utf-8")

    ep = episodes.copy()
    for c in ("start", "end"):
        if c in ep.columns:
            ep[c] = ep[c].astype(str)
    ep.to_json(SITE_DATA / "episodes.json", orient="records")

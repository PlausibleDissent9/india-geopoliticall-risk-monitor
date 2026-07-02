"""
Event study: what happens to India-SPECIFIC relative returns around
risk episodes?

Ratified design (July 2026):
  - Outcomes are the RELATIVE series only (nifty_rel_em, defence_rel,
    inr_rel_dxy). Brent/gold are excluded: global commodities, no
    India-specific component can be isolated.
  - Windows: cumulative relative return over the first 1, 5, and 20
    TRADING days of each episode, INCLUDING the episode start day
    (daily news volume and same-day price reaction overlap; convention
    documented in methodology.md section 6).
  - Language: outputs are named "associated_*". This is an association
    design, not identification. The t-statistics are descriptive
    orientation only — formal inference, controls, and interpretation
    are paper-stage work and belong to Ishan.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SITE_DATA = ROOT / "docs" / "data"

WINDOWS = [1, 5, 20]
OUTCOMES = ["nifty_rel_em", "defence_rel", "inr_rel_dxy"]


def _cum_return(returns: pd.Series, start_date, n_days: int) -> float | None:
    idx = returns.index
    # first trading day on/after the episode start
    pos_arr = np.searchsorted(np.array(idx, dtype="O"), start_date)
    pos = int(pos_arr)
    if pos >= len(idx):
        return None
    window = returns.iloc[pos: pos + n_days].dropna()
    if window.empty:
        return None
    return float((1.0 + window).prod() - 1.0)


def run_event_study(episodes: pd.DataFrame, derived: pd.DataFrame) -> dict:
    results: dict = {"note": "Associated cumulative relative returns around "
                             "risk episodes. Association, not causation. "
                             "t-stats are descriptive orientation only.",
                     "by_channel": {}}
    if episodes.empty:
        return results

    for channel, group in episodes.groupby("channel"):
        ch_out: dict = {}
        for outcome in OUTCOMES:
            if outcome not in derived.columns:
                continue
            series = derived[outcome].dropna()
            per_window: dict = {}
            for w in WINDOWS:
                vals = [
                    v for v in (
                        _cum_return(series, row.start, w)
                        for row in group.itertuples()
                    ) if v is not None
                ]
                if not vals:
                    continue
                arr = np.array(vals)
                n = len(arr)
                mean = float(arr.mean())
                sd = float(arr.std(ddof=1)) if n > 1 else float("nan")
                tstat = float(mean / (sd / np.sqrt(n))) if n > 1 and sd > 0 else None
                per_window[f"{w}d"] = {
                    "n_episodes": n,
                    "associated_mean_cum_return": round(mean, 5),
                    "associated_median_cum_return": round(float(np.median(arr)), 5),
                    "descriptive_tstat": round(tstat, 2) if tstat is not None else None,
                }
            if per_window:
                ch_out[outcome] = per_window
        if ch_out:
            results["by_channel"][channel] = ch_out
    return results


def write_output(results: dict) -> None:
    SITE_DATA.mkdir(parents=True, exist_ok=True)
    (SITE_DATA / "event_study.json").write_text(
        json.dumps(results, indent=2), encoding="utf-8"
    )

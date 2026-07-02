"""
Pipeline logic tests on synthetic data. No network required.

These verify the math, not the APIs: score bounds, spike/episode
detection on a synthetic crisis, and the event-study aggregation.
API integration is exercised by the daily workflow itself — a failed
cron run emails the repo owner, which is the integration test.

Run: pytest -q   (or: python tests/test_pipeline_synthetic.py)
"""
import sys
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src import build_index, event_study  # noqa: E402


def _synthetic():
    np.random.seed(7)
    n = 900
    dates = [date(2023, 1, 1) + timedelta(days=i) for i in range(n)]
    vol = pd.DataFrame(
        {ch: np.random.gamma(2, 0.01, n) for ch in build_index.CHANNELS},
        index=dates,
    )
    # inject a synthetic crisis: china_east volume x8 for six days
    vol.loc[dates[700]:dates[705], "china_east"] *= 8
    return dates, vol


def test_scores_bounded_0_100():
    _, vol = _synthetic()
    scores = build_index.build_scores(vol)
    comp = scores["composite"].dropna()
    assert not comp.empty
    assert comp.between(0, 100).all()


def test_synthetic_crisis_produces_episode():
    dates, vol = _synthetic()
    eps = build_index.detect_all_episodes(vol)
    assert not eps.empty, "no episodes detected at all"
    china = eps[eps["channel"] == "china_east"]
    assert not china.empty, "injected china_east crisis not detected"
    crisis_start = dates[700]
    hits = china[
        (china["start"] >= crisis_start - timedelta(days=2))
        & (china["start"] <= crisis_start + timedelta(days=6))
    ]
    assert not hits.empty, "episode not aligned with injected crisis window"


def test_event_study_aggregates():
    dates, vol = _synthetic()
    eps = build_index.detect_all_episodes(vol)
    trading = [d for d in dates if d.weekday() < 5]
    derived = pd.DataFrame(
        {o: np.random.normal(0, 0.01, len(trading))
         for o in event_study.OUTCOMES},
        index=trading,
    )
    res = event_study.run_event_study(eps, derived)
    assert "by_channel" in res
    assert res["by_channel"], "event study produced no channel results"
    any_channel = next(iter(res["by_channel"].values()))
    any_outcome = next(iter(any_channel.values()))
    any_window = next(iter(any_outcome.values()))
    assert "associated_mean_cum_return" in any_window
    assert any_window["n_episodes"] >= 1


if __name__ == "__main__":
    test_scores_bounded_0_100()
    test_synthetic_crisis_produces_episode()
    test_event_study_aggregates()
    print("ALL SYNTHETIC TESTS PASS")

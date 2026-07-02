"""
Fetch the asset panel and construct the India-specific relative series
Ishan ratified (July 2026):

  nifty_rel_em   = Nifty daily return  - EEM daily return
                   (India equity performance net of the EM factor)
  defence_rel    = defence-basket return - Nifty return
                   (the India-specific hypothesis: do border tensions move
                    defence stocks MORE than the market?)
  inr_rel_dxy    = USDINR return - DXY return
                   Sign convention: positive = rupee weakness BEYOND broad
                   dollar strength, i.e. India-specific currency stress.
                   (USDINR up = rupee weak; DXY up = dollar strong globally.)

Brent and gold are stored DESCRIPTIVE-ONLY: global commodities where an
India-specific component cannot be isolated. They appear in the weekly
datapack, never in the event study. India VIX is stored for the optional
prediction extension (paper stage), not used in v1 outputs.

Fragile joints, named in advance:
  - yfinance breaks with Yahoo layout changes; version is pinned-ish in
    requirements.txt. If a ticker returns empty, we WARN and continue.
  - ^INDIAVIX on Yahoo is intermittently unavailable. Non-fatal.
  - Timezone convention: all series are joined on calendar DATE. NSE
    closes 15:30 IST; GDELT days are UTC. Document the convention you
    choose in methodology.md section 7 — it is a limitation, not a bug.
"""
from __future__ import annotations

import warnings
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw"

TICKERS = {
    "nifty": "^NSEI",
    "india_vix": "^INDIAVIX",
    "usdinr": "USDINR=X",
    "brent": "BZ=F",
    "gold": "GC=F",
    "msci_em": "EEM",       # ETF proxy for MSCI EM — clean daily data
    "dollar_idx": "DX-Y.NYB",
    "hal": "HAL.NS",
    "bel": "BEL.NS",
    "mazdock": "MAZDOCK.NS",
}

DEFENCE = ["hal", "bel", "mazdock"]


def fetch_prices(start: str = "2017-01-01") -> pd.DataFrame:
    import yfinance as yf  # imported here so tests can run without it

    raw = yf.download(
        list(TICKERS.values()), start=start, progress=False, auto_adjust=True
    )["Close"]
    inv = {v: k for k, v in TICKERS.items()}
    raw = raw.rename(columns=inv)
    missing = [k for k in TICKERS if k not in raw.columns or raw[k].dropna().empty]
    for m in missing:
        warnings.warn(f"[markets] ticker returned no data: {m} ({TICKERS[m]})")
    raw.index = pd.to_datetime(raw.index).date
    raw.index.name = "date"
    return raw.sort_index()


def build_derived(prices: pd.DataFrame) -> pd.DataFrame:
    """Daily returns, the defence basket, and the three relative series."""
    rets = prices.pct_change()

    # Equal-weight defence basket return (mean of available members that day)
    have = [c for c in DEFENCE if c in rets.columns]
    rets["defence_basket"] = rets[have].mean(axis=1)

    out = pd.DataFrame(index=rets.index)
    if {"nifty", "msci_em"} <= set(rets.columns):
        out["nifty_rel_em"] = rets["nifty"] - rets["msci_em"]
    if "nifty" in rets.columns:
        out["defence_rel"] = rets["defence_basket"] - rets["nifty"]
    if {"usdinr", "dollar_idx"} <= set(rets.columns):
        out["inr_rel_dxy"] = rets["usdinr"] - rets["dollar_idx"]

    # Pass-throughs for the datapack / extension
    for col in ["nifty", "usdinr", "brent", "gold", "india_vix", "defence_basket"]:
        if col in rets.columns:
            out[f"ret_{col}"] = rets[col]
    return out


def load_or_update(start: str = "2017-01-01") -> tuple[pd.DataFrame, pd.DataFrame]:
    prices = fetch_prices(start=start)
    derived = build_derived(prices)
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    prices.to_csv(RAW_DIR / "prices.csv", index_label="date")
    derived.to_csv(RAW_DIR / "derived_returns.csv", index_label="date")
    return prices, derived


if __name__ == "__main__":
    p, d = load_or_update()
    print(p.tail(3))
    print(d.tail(3))

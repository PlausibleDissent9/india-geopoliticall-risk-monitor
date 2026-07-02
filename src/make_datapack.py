"""
Weekly datapack for the Indiconomics note.

This script assembles NUMBERS ONLY: index moves, top spike days, and an
asset table for the week. The 250-word interpretation is Ishan's — the
generated file contains an intentionally empty section for it. Nothing
in this repo writes commentary.

Run manually each weekend, or let the Friday step in the workflow drop
it into notes-inbox/:
    python -m src.make_datapack
Then write the note, save it as notes/YYYY-Www.md, commit. run_daily
publishes the newest notes/*.md to the site.
"""
from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
INBOX = ROOT / "notes-inbox"


def make(week_ending: date | None = None) -> Path:
    end = week_ending or date.today()
    start = end - timedelta(days=7)

    hist = pd.read_csv(ROOT / "docs" / "data" / "history.csv", parse_dates=["date"])
    hist["date"] = hist["date"].dt.date
    hist = hist.set_index("date").sort_index()
    wk = hist.loc[(hist.index > start) & (hist.index <= end)]

    derived = pd.read_csv(ROOT / "data" / "raw" / "derived_returns.csv",
                          parse_dates=["date"])
    derived["date"] = derived["date"].dt.date
    derived = derived.set_index("date").sort_index()
    dwk = derived.loc[(derived.index > start) & (derived.index <= end)]

    lines: list[str] = []
    iso = end.isocalendar()
    lines.append(f"---\nweek: {iso.year}-W{iso.week:02d}\nrange: {start} to {end}\n---\n")
    lines.append("## Index moves this week\n")
    if not wk.empty:
        first, last = wk.iloc[0], wk.iloc[-1]
        for col in wk.columns:
            lines.append(f"- {col}: {first[col]:.1f} -> {last[col]:.1f} "
                         f"({last[col]-first[col]:+.1f})")
        top = wk["composite"].idxmax()
        lines.append(f"\nPeak composite day: {top} ({wk['composite'].max():.1f})")
    else:
        lines.append("- No index data in window (pipeline not yet run?)")

    lines.append("\n## Asset moves this week (cumulative daily returns)\n")
    if not dwk.empty:
        for col in ["ret_nifty", "ret_usdinr", "ret_brent", "ret_gold",
                    "ret_defence_basket", "nifty_rel_em", "defence_rel",
                    "inr_rel_dxy"]:
            if col in dwk.columns:
                cum = float((1 + dwk[col].fillna(0)).prod() - 1) * 100
                lines.append(f"- {col}: {cum:+.2f}%")
    else:
        lines.append("- No market data in window")

    lines.append("\n## Your note (250 words — written by you, not generated)\n")
    lines.append("[Ishan writes here: what moved, why it matters, one "
                 "interpretation you would defend out loud.]\n")

    INBOX.mkdir(exist_ok=True)
    out = INBOX / f"datapack_{iso.year}-W{iso.week:02d}.md"
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"[datapack] wrote {out}")
    return out


if __name__ == "__main__":
    make()

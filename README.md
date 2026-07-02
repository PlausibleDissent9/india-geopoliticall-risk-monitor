# India Geopolitical Risk Monitor (IGRM)

A daily, category-decomposed index of geopolitical risk salience for India,
in the Caldara–Iacoviello article-share tradition — with open data, a
public methodology, and an event-study layer on India-specific relative
returns. Live since July 2026.

**Division of labor, stated plainly:** pipeline and site infrastructure
were built with AI assistance (Claude). The methodology, term selection,
all parameter choices, and every word of weekly commentary are the
author's. See `methodology.md`.

## Architecture

```
GDELT DOC API ──┐
                ├─> build_index.py ──> docs/data/{latest,history,episodes}
Yahoo Finance ──┘         │
                          └─> event_study.py ──> docs/data/event_study.json
GitHub Actions (daily 18:00 IST) commits outputs; GitHub Pages serves docs/
notes/*.md (author-written) ──> published to the site weekly
```

## Launch checklist

1. **Create the repo.** Public GitHub repo named
   `india-geopolitical-risk-monitor`. Push these contents. Replace the two
   `CHANGEME` links in `docs/index.html` with your GitHub username.
2. **Enable Pages.** Settings → Pages → Deploy from branch → `main`,
   folder `/docs`.
3. **Own the dictionaries.** Expand `dictionaries.json` to 8–15 structural
   terms per channel (the seeds are format examples, not final terms). Set
   `_meta.frozen_on`. Run `pytest -q` — it enforces the ex-ante rule (no
   retrospective event names). Draft `methodology.md` §2 as you go.
4. **First run.** Actions tab → `daily-update` → Run workflow →
   backfill = **true**. Expect 20–40 minutes (GDELT is chunked politely).
   The daily cron (18:00 IST) takes over afterwards.
5. **Verify.** Open the Pages URL. Composite number, five components,
   chart, archive should render. Then write methodology.md and the first
   weekly note.

## Local run

```
pip install -r requirements.txt
pytest -q
python -m src.run_daily --backfill     # first time
python -m src.run_daily                # daily incremental
python -m src.make_datapack            # weekly note inputs
```

## Weekly rhythm

Friday's Action run drops `notes-inbox/datapack_YYYY-Www.md` (numbers
only). You write ~250 words, save as `notes/YYYY-Www.md`, commit. The next
daily run publishes it. That note is also the week's Indiconomics post.

## Roadmap — frozen until 1 Nov 2026

No new features before the application deadline; every feature-day is a
data-day lost. Post-freeze candidates: prediction extension (index
*changes* vs subsequent volatility changes, with controls, modest
framing), weighting exploration, per-episode case pages.

## Honest limitations

Association, not causation. Salience, not ground truth — anniversary
coverage counts by construction (disclosed in methodology §7). GDELT
reaches back to Jan 2017 only. Not investment advice.

# IGRM Methodology

<!-- This file is written by Ishan, audited by Claude. It is the interview
script: every section answers a question a sharp reader will ask.
Headings below map 1:1 to the decisions ratified in July 2026. -->

## 1. What the index measures (and what it does not)

TODO(Ishan): press salience of geopolitical risk, in the Caldara-Iacoviello
tradition; daily, India-specific, category-decomposed. State plainly what a
score of 72 means and does not mean.

## 2. Term selection and the ex-ante rule

TODO(Ishan): why these terms per channel; why structural terms only; why
retrospective event names are banned (circularity); how the ban is enforced
(tests/test_dictionaries.py); freeze date; changelog below.

## 3. Normalization

TODO(Ishan): trailing 730-day percentile rank — why percentile over z-score;
what "today vs the last two years of this channel" means.

## 4. The composite convention

TODO(Ishan): unweighted mean as a transparency convention, not a claim about
relative importance; components are the headline product.

## 5. Spikes and episodes

TODO(Ishan): mean + 2 sigma over 90 days ON RAW VOLUME SHARES; 3-day
clustering; why episodes, not raw spike days. Note why detection runs on
raw volumes, not percentile scores (scores are bounded at 100, so a
2-sigma threshold on them can be unreachable). Alternative you may
prefer: fixed top-decile rule (score > 90) - your call, document either.

## 6. Event-study design

TODO(Ishan): relative outcomes only (Nifty vs EM, defence vs Nifty, INR vs
DXY); why Brent/gold are descriptive-only; window convention (includes
episode start day); association language — no causal claims.

## 7. Known limitations

TODO(Ishan): anniversary coverage counts as salience (disclosed, by
construction); GDELT coverage drift; UTC-vs-IST date convention; hindsight
in dictionary construction and how the structural-terms rule mitigates it.

## 8. Validation

TODO(Ishan): the historical episodes the index detects without their names
in the queries — this is the paper's key figure.

## Changelog

- (empty — every post-freeze dictionary or parameter change goes here)

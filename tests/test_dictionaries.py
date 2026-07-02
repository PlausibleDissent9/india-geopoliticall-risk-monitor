"""
Enforces the ex-ante term rule that Ishan ratified (July 2026):

  Dictionaries must contain STRUCTURAL terms only (geography, institutions,
  doctrine, chokepoints). Retrospective event names are banned, because a
  validation spike at an event whose name is in the query is circular.

Overriding a ban is allowed ONLY as a conscious, documented decision:
edit BANNED_RETROSPECTIVE below AND record the rationale in
methodology.md section 2 (changelog). The point of putting the rule in a
test is that breaking it requires a visible, deliberate act.

Run:  pytest -q
"""
import json
from pathlib import Path

DICT_PATH = Path(__file__).resolve().parents[1] / "dictionaries.json"

# Event-specific names whose news usage is overwhelmingly retrospective.
# Substring match, case-insensitive.
BANNED_RETROSPECTIVE = [
    "galwan",
    "pulwama",
    "balakot",
    "sindoor",
    "kargil",
    "uri attack",
    "26/11",
    "mumbai attacks",
    "doklam",  # borderline geography, but coverage is dominated by the 2017 standoff
]

CHANNELS = ["pakistan_west", "china_east", "gulf_energy", "us_trade", "shipping"]


def load():
    with open(DICT_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def test_structure():
    d = load()
    for ch in CHANNELS:
        assert ch in d, f"missing channel: {ch}"
        assert isinstance(d[ch].get("terms"), list), f"{ch}: terms must be a list"
        assert len(d[ch]["terms"]) >= 3, f"{ch}: needs at least 3 terms"
        assert d[ch].get("label"), f"{ch}: needs a label"


def test_no_retrospective_event_names():
    d = load()
    violations = []
    for ch in CHANNELS:
        for term in d[ch]["terms"]:
            low = term.lower()
            for banned in BANNED_RETROSPECTIVE:
                if banned in low:
                    violations.append(f"{ch}: '{term}' contains banned term '{banned}'")
    assert not violations, (
        "Ex-ante rule violated:\n  " + "\n  ".join(violations)
        + "\nIf this is a conscious override, edit BANNED_RETROSPECTIVE and "
          "document it in methodology.md section 2."
    )


def test_terms_are_nonempty_strings():
    d = load()
    for ch in CHANNELS:
        for term in d[ch]["terms"]:
            assert isinstance(term, str) and term.strip(), f"{ch}: empty term"

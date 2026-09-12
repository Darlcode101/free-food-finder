"""Baseline free-food detector: keyword/regex rules over event text.

This is v1 on purpose — there's no labeled training data yet. Once the
scraper has been running a while, label a sample of its output (free food /
not) and swap this module for a trained TF-IDF + logistic regression model
using the same `is_free_food(text) -> (bool, float)` interface.
"""
import re

_FOOD_WORDS = r"(?:pizza|food|snacks?|drinks?|refreshments?|buffet|bbq|barbecue|breakfast|lunch|dinner|cake|donuts?|doughnuts?|pastries|sandwiches|catering)"

_POSITIVE_PATTERNS = [
    re.compile(rf"\bfree\b[^.]{{0,25}}\b{_FOOD_WORDS}\b", re.IGNORECASE),
    re.compile(rf"\b{_FOOD_WORDS}\b[^.]{{0,25}}\bfree\b", re.IGNORECASE),
    re.compile(rf"\b{_FOOD_WORDS}\b[^.]{{0,15}}\b(?:will be\s+)?(?:provided|included)\b", re.IGNORECASE),
]


def is_free_food(text: str) -> tuple[bool, list[str]]:
    """Return (flagged, matched_snippets) for a piece of event text."""
    if not text:
        return False, []

    matches = [m.group(0) for pattern in _POSITIVE_PATTERNS for m in pattern.finditer(text)]
    if not matches:
        return False, []

    return True, matches


# Event types and phrasing that, from experience, often come with free food/
# drinks even though the listing never says so explicitly — guest-speaker
# talks, networking events, and the like. This is a separate, lower-confidence
# tier from is_free_food's explicit keyword matches.
#
# Matched as a substring rather than an exact type string, since sources
# label event types differently: Lancaster University uses a single "Talk /
# Public Lecture" type string, while Fraser House Hub (a town coworking
# space hosting things like Software Lancaster Talks) uses comma-joined
# category tags like "NETWORKING, EDUCATIONAL".
_PROBABLE_EVENT_TYPE_RE = re.compile(
    r"\b(talk|lecture|seminar|networking|conference|meetup|meet[\s-]?up)\b", re.IGNORECASE
)

_PROBABLE_KEYWORDS_RE = re.compile(
    r"\b(guest speaker|fireside chat|keynote|panel discussion|networking event|"
    r"drinks reception|welcome reception|industry talk|alumni (?:talk|event)|roundtable)\b",
    re.IGNORECASE,
)


def is_probable_free_food(title: str, description: str, event_type: str = "") -> tuple[bool, list[str]]:
    """Heuristic second tier: flag likely-food events even without an explicit mention."""
    reasons = []

    type_match = event_type and _PROBABLE_EVENT_TYPE_RE.search(event_type)
    if type_match:
        reasons.append(f"event type '{event_type}' often includes refreshments")

    keyword_match = _PROBABLE_KEYWORDS_RE.search(f"{title} {description}")
    if keyword_match:
        reasons.append(f"mentions '{keyword_match.group(0)}'")

    return bool(reasons), reasons

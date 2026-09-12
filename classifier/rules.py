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

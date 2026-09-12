"""Scraper for the Lancaster University events calendar.

The page embeds the full event list as a JS variable (`allEvents = [...]`)
directly in the HTML, so we extract that JSON rather than parsing markup.
"""
import json
import re

from .common import get_session, polite_get

EVENTS_URL = "https://www.lancaster.ac.uk/events/"

_ALL_EVENTS_RE = re.compile(r"allEvents\s*=\s*(\[.*?\]);", re.DOTALL)


def fetch_events() -> list[dict]:
    session = get_session()
    response = polite_get(session, EVENTS_URL)

    match = _ALL_EVENTS_RE.search(response.text)
    if not match:
        return []

    raw_events = json.loads(match.group(1))

    events = []
    for raw in raw_events:
        events.append(
            {
                "source": "lancaster.ac.uk",
                "title": raw.get("Title", ""),
                "description": raw.get("ShortDescription", ""),
                "location": raw.get("Location", ""),
                "start_date": raw.get("DateDetails", {}).get("Format", {}).get("Full", ""),
                "start_date_iso": raw.get("StartDate", ""),
                "event_type": raw.get("Type", ""),
                "url": EVENTS_URL + raw.get("Slug", ""),
            }
        )
    return events

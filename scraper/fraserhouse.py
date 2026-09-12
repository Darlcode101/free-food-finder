"""Scraper for Fraser House Hub — a Lancaster coworking space that hosts
town-based (non-university) talks and meetups. Same organisers, same
"NETWORKING" category tag, but only some of these actually have food:
speaker talks held on-site at Fraser House itself do (that perk usually
only shows up in the cross-posted Meetup/LinkedIn/Instagram announcement,
not this venue listing's own text — hence the probable-food heuristic
rather than a confirmed match), while the off-site casual pub meetups
(e.g. "Software Lancaster Meet up" at The Waterwitch) don't. `event_type`
is therefore only populated for events whose `Location` is Fraser House
itself, so the probable-food heuristic doesn't fire for the off-site ones.

The site runs on Nexudus (a coworking-space platform) rendered with
Next.js. The event list is embedded server-side as JSON in a
`__NEXT_DATA__` script tag, so no extra AJAX calls are needed.
"""
import json
import re

from .common import format_date_range, get_session, polite_get

EVENTS_URL = "https://fraserhousehub.co.uk/events"

_NEXT_DATA_RE = re.compile(
    r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', re.DOTALL
)


def fetch_events() -> list[dict]:
    session = get_session()
    response = polite_get(session, EVENTS_URL)

    match = _NEXT_DATA_RE.search(response.text)
    if not match:
        return []

    data = json.loads(match.group(1))
    try:
        raw_events = data["props"]["mobxStore"]["eventsStore"]["eventsPage"]["CalendarEvents"]
    except KeyError:
        return []

    events = []
    for raw in raw_events:
        categories = ", ".join(c.get("Title", "") for c in raw.get("EventCategories", []))
        description = raw.get("ShortDescription") or _strip_html(raw.get("LongDescription", ""))
        has_tickets = raw.get("HasTickets", False)
        cheapest_price = raw.get("ChepeastPrice", 0) or 0
        location = raw.get("Location") or ""
        on_site = location.strip().lower() == "fraser house"

        events.append(
            {
                "source": "fraserhousehub.co.uk",
                "title": raw.get("Name", ""),
                "description": description,
                "location": location,
                "start_date": format_date_range(raw.get("StartDate", ""), raw.get("EndDate", "")),
                "start_date_iso": raw.get("StartDate", ""),
                # Only feed categories to the probable-food heuristic for
                # events actually held at Fraser House — off-site meetups
                # under the same brand (e.g. the Waterwitch pub social)
                # don't have food, even though they share the same tags.
                "event_type": categories if on_site else "",
                "is_paid": bool(has_tickets and cheapest_price > 0),
                "url": raw.get("TicketsPage") or EVENTS_URL,
            }
        )
    return events


def _strip_html(text: str) -> str:
    return re.sub(r"<[^>]+>", " ", text or "").strip()

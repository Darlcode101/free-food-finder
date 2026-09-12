"""Scraper for Fraser House Hub — a Lancaster coworking space that hosts
town-based (non-university) talks and meetups, e.g. "Software Lancaster
Talks", which regularly advertise free pizza — just not usually in this
venue listing's own text (the "free pizza" perk tends to be mentioned in
the cross-posted Meetup/LinkedIn/Instagram announcement instead, which is
why these lean on the probable-food heuristic more than the confirmed one).

The site runs on Nexudus (a coworking-space platform) rendered with
Next.js. The event list is embedded server-side as JSON in a
`__NEXT_DATA__` script tag, so no extra AJAX calls are needed.
"""
import json
import re
from datetime import datetime

from .common import get_session, polite_get

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

        events.append(
            {
                "source": "fraserhousehub.co.uk",
                "title": raw.get("Name", ""),
                "description": description,
                "location": raw.get("Location", ""),
                "start_date": _format_date(raw.get("StartDate", ""), raw.get("EndDate", "")),
                "start_date_iso": raw.get("StartDate", ""),
                "event_type": categories,
                "is_paid": bool(has_tickets and cheapest_price > 0),
                "url": raw.get("TicketsPage") or EVENTS_URL,
            }
        )
    return events


def _strip_html(text: str) -> str:
    return re.sub(r"<[^>]+>", " ", text or "").strip()


def _format_date(start_iso: str, end_iso: str) -> str:
    """Turn '2026-09-21T18:00:00' / end into 'Monday 21 September 2026, 6:00pm to 9:00pm'."""
    if not start_iso:
        return ""
    try:
        start = datetime.fromisoformat(start_iso)
    except ValueError:
        return start_iso

    def fmt_time(dt: datetime) -> str:
        return dt.strftime("%I:%M%p").lstrip("0").lower()

    display = f"{start.strftime('%A %d %B %Y')}, {fmt_time(start)}"
    if end_iso:
        try:
            end = datetime.fromisoformat(end_iso)
            display += f" to {fmt_time(end)}"
        except ValueError:
            pass
    return display

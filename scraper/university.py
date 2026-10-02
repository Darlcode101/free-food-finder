"""Scraper for the Lancaster University events calendar.

The page embeds the full event list as a JS variable (`allEvents = [...]`)
directly in the HTML, so we extract that JSON rather than parsing markup.
"""
import json
import re
from datetime import datetime
from urllib.parse import urlparse

from bs4 import BeautifulSoup

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
        registration_type = raw.get("RegistrationType", "")
        events.append(
            {
                "source": "lancaster.ac.uk",
                "title": raw.get("Title", ""),
                "description": raw.get("ShortDescription", ""),
                "location": raw.get("Location", ""),
                "start_date": raw.get("DateDetails", {}).get("Format", {}).get("Full", ""),
                "start_date_iso": raw.get("StartDate", ""),
                "event_type": raw.get("Type", ""),
                # Only "Cost to attend" is a confident paid signal — treat
                # anything else (including blank) as not-known-to-be-paid,
                # since most values here just mean "no charge mentioned".
                "is_paid": "cost to attend" in registration_type.lower(),
                # "Free to attend - registration required" / "Cost to attend -
                # booking required" vs "Registration not required - just turn up".
                # Blank means the feed didn't say, so leave it unknown.
                "registration_required": (
                    None if not registration_type
                    else "not required" not in registration_type.lower()
                ),
                "url": EVENTS_URL + raw.get("Slug", ""),
            }
        )
    return events


_BOOKING_CLOSES_RE = re.compile(
    r"booking closes on\s+(?:[A-Za-z]+\s+)?(\d{1,2})(?:st|nd|rd|th)?\s+([A-Za-z]+)\s+(\d{4})",
    re.IGNORECASE,
)


def fetch_registration_info(session, url: str) -> tuple[str, str]:
    """Find the external booking link (TryBooking, LibCal, ...) and any stated deadline on an event page.

    The feed only says *whether* registration is required; the actual link
    lives on the event page — usually a "Book now" button, otherwise a bare
    link in the event info box. Some pages also say "Booking closes on
    Sat 17 October 2026"; that's returned as a date-only ISO string ("" if
    absent).
    """
    response = polite_get(session, url)
    soup = BeautifulSoup(response.text, "lxml")

    registration_url = ""
    for link in soup.select(".book-now a[href], .event-info-item a[href]"):
        href = link["href"].strip()
        host = urlparse(href).netloc
        if host and not host.endswith("lancaster.ac.uk"):
            registration_url = href
            break

    deadline = ""
    match = _BOOKING_CLOSES_RE.search(soup.get_text(" ", strip=True))
    if match:
        # The stated weekday is sometimes wrong for the date, so it's ignored.
        try:
            deadline = datetime.strptime(" ".join(match.groups()), "%d %B %Y").date().isoformat()
        except ValueError:
            pass

    return registration_url, deadline

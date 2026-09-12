"""Scraper for Lancaster University Students' Union (LUSU) events.

lancastersu.co.uk runs on the UnionCloud platform. The /events page is
server-rendered HTML (BeautifulSoup is enough, no JS execution needed) —
note this is a different template from /upcoming-events, which loads its
event cards via a separate AJAX widget call and isn't used here.
robots.txt for this site sets only a Crawl-delay, no disallowed paths.
"""
from bs4 import BeautifulSoup

from .common import get_session, polite_get

BASE_URL = "https://lancastersu.co.uk"
EVENTS_URL = f"{BASE_URL}/events"


def _text(card, selector: str) -> str:
    el = card.select_one(selector)
    return el.get_text(strip=True) if el else ""


def fetch_events() -> list[dict]:
    session = get_session()
    response = polite_get(session, EVENTS_URL)
    soup = BeautifulSoup(response.text, "lxml")

    events = []
    for card in soup.select(".event-container"):
        link = card.select_one("a.event-box")
        if link is None or not link.get("href"):
            continue

        status = _text(card, ".event-status")

        events.append(
            {
                "source": "lancastersu.co.uk",
                "title": _text(card, ".event-name") or link.get("title", ""),
                "group_name": _text(card, ".group-name"),
                "description": _text(card, ".event-description"),
                "location": _text(card, ".venue"),
                "start_date": _text(card, ".event-date"),
                "is_free": status.lower().startswith("free"),
                "url": BASE_URL + link["href"],
            }
        )

    return events


def fetch_event_detail(session, url: str) -> str:
    """Fetch the full description text for a single event page (truncated in the listing)."""
    response = polite_get(session, url)
    soup = BeautifulSoup(response.text, "lxml")

    content = soup.select_one("#uc-events-details-page .contentBoxes")
    if content is None:
        return ""

    for tag in content.select("header, .top-container"):
        tag.decompose()

    return content.get_text(separator=" ", strip=True)

"""Scraper for the "Software Lancaster Talks" Meetup group.

This is the group behind Fraser House Hub's occasional speaker talks, and
unlike Fraser House's own venue listing, Meetup's event descriptions
explicitly say "Free pizza and drinks!" every time — so these are a
confirmed match, not just a probable one. (There's a second, separate
group, "software-lancaster" — the casual pub meetup with no food — which
this scraper deliberately does not target.)

The page embeds a GraphQL response as a Next.js `__APOLLO_STATE__` blob, so
no separate API calls are needed. robots.txt disallows meetup.com's actual
API/GraphQL paths (`/gql*`, `/api/`) but not this plain group page, so
reading data already embedded in an allowed page's HTML is fine — this
scraper never calls those disallowed endpoints itself.
"""
import json
import re

from .common import format_date_range, get_session, polite_get

GROUP_SLUG = "software-lancaster-talks"
EVENTS_URL = f"https://www.meetup.com/{GROUP_SLUG}/events/"

_NEXT_DATA_RE = re.compile(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', re.DOTALL)
_UPCOMING_EVENTS_KEY_RE = re.compile(r'^events\(\{"filter":\{"afterDateTime"')


def fetch_events() -> list[dict]:
    session = get_session()
    response = polite_get(session, EVENTS_URL)

    match = _NEXT_DATA_RE.search(response.text)
    if not match:
        return []

    apollo = json.loads(match.group(1)).get("props", {}).get("pageProps", {}).get("__APOLLO_STATE__", {})

    group = next((v for v in apollo.values() if v.get("__typename") == "Group"), None)
    if group is None:
        return []

    # The upcoming-events query key embeds the timestamp Meetup rendered the
    # page at, so it can't be hardcoded — match it by shape instead.
    upcoming_key = next((k for k in group if _UPCOMING_EVENTS_KEY_RE.match(k)), None)
    if upcoming_key is None:
        return []

    events = []
    for edge in group[upcoming_key].get("edges", []):
        event = apollo.get(edge.get("node", {}).get("__ref", ""))
        if event is None or event.get("status") != "ACTIVE":
            continue

        venue = apollo.get((event.get("venue") or {}).get("__ref", ""), {})
        location = ", ".join(filter(None, [venue.get("name"), venue.get("city")])) or (
            "Online" if event.get("isOnline") else ""
        )

        events.append(
            {
                "source": "meetup.com",
                "title": event.get("title", ""),
                "description": (event.get("description") or "").replace("**", ""),
                "location": location,
                "start_date": format_date_range(event.get("dateTime", ""), event.get("endTime", "")),
                "start_date_iso": event.get("dateTime", ""),
                "event_type": "Talk / Meetup",
                # feeSettings is null for free RSVPs in Meetup's schema, and
                # every event on this group has been free so far.
                "is_paid": event.get("feeSettings") is not None,
                "url": event.get("eventUrl", EVENTS_URL),
            }
        )
    return events

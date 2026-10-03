"""Scraper for Lancaster University Students' Union (LUSU) and society events.

LUSU's site (now lusu.co.uk, on Squarespace) doesn't host events itself:
its /events page embeds an iframe from Rubric (campus.hellorubric.com), the
platform societies and colleges use to list events and sell tickets. The
iframe loads its data client-side from Rubric's API — a single POST
endpoint (api.hellorubric.com) taking a JSON `details` blob and an
`endpoint` name — so this calls the same two endpoints the page does:

- `getUnifiedSearch` lists every Lancaster event (title, society, start
  time, category, price summary) — no descriptions.
- the event-details endpoint returns one event's description, start/end
  time, venue and ticket types/status.

lusu.co.uk's robots.txt disallows Squarespace's `?format=json` views, which
is why the iframe's source is used rather than the LUSU page itself;
api.hellorubric.com has no robots.txt and campus.hellorubric.com only
disallows /assets/ and /content/.
"""
import json
import re
import time
from datetime import datetime
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup

from .common import CRAWL_DELAY_SECONDS, format_date_range, get_session

API_URL = "https://api.hellorubric.com"
EVENT_URL = "https://campus.hellorubric.com/?eid={}"
SEARCH_PAGE_URL = (
    "https://campus.hellorubric.com/search?country=GB&state=North+West"
    "&type=events&universityid=126&iframe=true&showall=true"
)
DETAILS_ENDPOINT = "https://appserver.getqpay.com:9090/AppServerSwapnil/event/details"
LANCASTER_UNIVERSITY_ID = "126"
PAGE_SIZE = 100

UK = ZoneInfo("Europe/London")
_EID_RE = re.compile(r"eid=(\d+)")


def _call(session, endpoint: str, details: dict) -> dict:
    """POST to Rubric's API the way its own web portal does, then respect crawl-delay."""
    details = {**details, "device": "web_portal", "version": 4, "timestamp": int(time.time() * 1000)}
    response = session.post(
        API_URL, data={"details": json.dumps(details), "endpoint": endpoint}, timeout=25
    )
    response.raise_for_status()
    time.sleep(CRAWL_DELAY_SECONDS)
    data = response.json()
    if not data.get("success"):
        raise ValueError(f"Rubric {endpoint} returned no success flag: {str(data)[:200]}")
    return data


def _is_paid(price_summary: str):
    """'Free' or a range starting at £0.00 (e.g. free entry + paid kit hire) isn't paid."""
    if price_summary.strip().lower() == "free" or price_summary.startswith("£0.00"):
        return False
    return True if "£" in price_summary else None


def fetch_events() -> list[dict]:
    session = get_session()
    # Rubric returns past events too; keep anything from today onwards.
    today = datetime.now(UK).replace(hour=0, minute=0, second=0, microsecond=0)

    results, offset = [], 0
    while True:
        data = _call(session, "getUnifiedSearch", {
            "firstCall": offset == 0,
            "desiredType": "events",
            "sortType": "date",
            "sortDirection": "asc",
            "limit": PAGE_SIZE,
            "offset": offset,
            "searchQuery": "",
            "eventsPeriodFilter": "All",
            "countryCode": "GB",
            "state": "North West",
            "selectedUniversityId": LANCASTER_UNIVERSITY_ID,
            "iframe": True,
            "showall": True,
            "currentUrl": SEARCH_PAGE_URL,
        })
        # Without a recognised university filter Rubric silently falls back
        # to a default region (it returned Australian events once) — treat
        # that as a broken request, not a list of events.
        if data.get("selectedCountryCode") != "GB":
            raise ValueError(f"Rubric ignored the Lancaster filter (got {data.get('selectedCountryCode')})")
        page = data.get("results", [])
        results += page
        if not page or len(results) >= data.get("totalItemCount", 0):
            break
        offset = len(results)

    events = []
    for raw in results:
        match = _EID_RE.search(raw.get("destination", ""))
        if not match:
            continue
        start = datetime.fromtimestamp(raw.get("sortindex", 0), UK)
        if start < today:
            continue
        start_iso = start.replace(tzinfo=None).isoformat()
        events.append(
            {
                "source": "lusu.co.uk",
                "title": raw.get("title", ""),
                "group_name": raw.get("societyname", ""),
                "description": "",  # only on the details endpoint; see fetch_event_detail
                "location": "",
                "start_date": format_date_range(start_iso),
                "start_date_iso": start_iso,
                "event_type": raw.get("subtitle", ""),
                "is_paid": _is_paid(raw.get("info", "")),
                "url": EVENT_URL.format(match.group(1)),
            }
        )
    return events


def _parse_rubric_time(text: str) -> str:
    """'Sat, 3 Oct 2026 1:00 PM' (UK local) -> '2026-10-03T13:00:00'."""
    try:
        return datetime.strptime(text.strip(), "%a, %d %b %Y %I:%M %p").isoformat()
    except (ValueError, AttributeError):
        return ""


def _parse_sale_end(text: str) -> str:
    """'2026-10-03 21:59:00.0' (UK local) -> '2026-10-03T21:59:00'."""
    try:
        return datetime.strptime(text.split(".")[0], "%Y-%m-%d %H:%M:%S").isoformat()
    except (ValueError, AttributeError):
        return ""


def fetch_event_detail(session, url: str) -> dict:
    """Fetch one event's description, exact times, venue and ticketing.

    Returns fields to merge into the event dict. Events sold through Rubric
    (even £0 tickets) need a ticket to get in, so those are marked
    registration_required; "Offline" events with no ticket types are
    just turn up.
    """
    eid = _EID_RE.search(url).group(1)
    data = _call(session, DETAILS_ENDPOINT, {"eventId": eid, "currentUrl": url})
    details = data.get("eventDetails", {})

    description = BeautifulSoup(details.get("eventDescription") or "", "lxml").get_text(" ", strip=True)
    start_iso = _parse_rubric_time(details.get("eventTime", ""))
    end_iso = _parse_rubric_time(details.get("eventEndTime", ""))

    fields = {
        "description": description,
        "location": details.get("eventAddress", ""),
    }
    if start_iso:
        fields["start_date_iso"] = start_iso
        fields["start_date"] = format_date_range(start_iso, end_iso)

    tickets = details.get("ticketTypeDetails") or []
    if tickets:
        status = (data.get("ticketStatus") or "").lower()
        fields["registration_required"] = True
        fields["registration_url"] = url
        fields["registration_deadline"] = _parse_sale_end(details.get("eventSaleEnd", ""))
        fields["registration_status"] = (
            "open" if status == "available" else "sold_out" if "sold" in status else ""
        )
        # The listing's price summary is a rough guide; the actual ticket
        # types are authoritative (any £0 ticket means you can go for free).
        fields["is_paid"] = all((t.get("amount") or 0) > 0 for t in tickets)
    else:
        fields["registration_required"] = False

    return fields

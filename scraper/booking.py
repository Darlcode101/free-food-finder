"""Sign-up deadline and availability from external booking pages.

TryBooking and Eventbrite both embed schema.org `Offer` data in the event
page, with `availabilityEnds` (when booking closes) and `availability`
(`InStock` / `SoldOut`). Only these hosts are fetched: their robots.txt
allows the plain event pages, whereas e.g. LibCal asks for a 10s crawl
delay and is left to the deadline text on the university's own page.

Eventbrite links from the university carry tracking query strings, some
of which match Eventbrite's robots.txt disallow patterns, so the query
string is dropped before fetching.
"""
import re
from urllib.parse import urlsplit, urlunsplit

from .common import polite_get

SUPPORTED_HOSTS = ("trybooking.com", "eventbrite.")

_ENDS_RE = re.compile(r'"(?:availabilityEnds|validThrough)"\s*:\s*"([^"]+)"')
_OFFSET_RE = re.compile(r"(?:Z|[+-]\d{2}:\d{2})$")
_AVAILABILITY_RE = re.compile(r'"availability"\s*:\s*"(?:https?://schema\.org/)?(\w+)"')


def is_supported(url: str) -> bool:
    host = urlsplit(url).netloc
    return any(h in host for h in SUPPORTED_HOSTS)


def fetch_booking_status(session, url: str) -> dict:
    """Return {"registration_deadline": ISO str, "registration_status": "open"|"sold_out"|""}."""
    url = urlunsplit(urlsplit(url)._replace(query="", fragment=""))
    html = polite_get(session, url).text

    # An event can have several ticket types; booking is open until the
    # last one closes, and only fully booked if none are still in stock.
    deadlines = _ENDS_RE.findall(html)
    availabilities = set(_AVAILABILITY_RE.findall(html))
    if "InStock" in availabilities or "LimitedAvailability" in availabilities:
        status = "open"
    elif "SoldOut" in availabilities:
        status = "sold_out"
    else:
        status = ""

    deadline = max(deadlines) if deadlines else ""
    # TryBooking stamps every UK time with +01:00, even in winter (a 6pm
    # November event shows as 18:00+01:00 = 5pm GMT). Its wall-clock time
    # is right, so drop the offset and keep it as local UK time.
    if "trybooking.com" in url:
        deadline = _OFFSET_RE.sub("", deadline)

    return {
        "registration_deadline": deadline,
        "registration_status": status,
    }

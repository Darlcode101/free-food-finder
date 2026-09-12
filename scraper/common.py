"""Shared HTTP and formatting helpers for polite, robots.txt-respecting scraping."""
import time
from datetime import datetime

import requests

USER_AGENT = (
    "free-food-finder/0.1 (+https://github.com/alexanderdarlington/free-food-finder; "
    "student project, contact via GitHub issues)"
)

CRAWL_DELAY_SECONDS = 5  # matches lancastersu.co.uk robots.txt Crawl-delay


def get_session() -> requests.Session:
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})
    return session


def polite_get(session: requests.Session, url: str, **kwargs) -> requests.Response:
    """GET a URL, then sleep to respect crawl-delay before the caller's next request."""
    response = session.get(url, timeout=15, **kwargs)
    response.raise_for_status()
    time.sleep(CRAWL_DELAY_SECONDS)
    return response


def format_date_range(start_iso: str, end_iso: str = "") -> str:
    """Turn ISO start/end timestamps into 'Monday 27 July 2026, 6:00pm to 8:00pm'."""
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
            display += f" to {fmt_time(datetime.fromisoformat(end_iso))}"
        except ValueError:
            pass
    return display

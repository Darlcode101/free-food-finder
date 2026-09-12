"""Shared HTTP helpers for polite, robots.txt-respecting scraping."""
import time

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

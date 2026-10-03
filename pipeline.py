"""Scrape LUSU, Lancaster University, Fraser House Hub, and Meetup events, flag free-food ones, write data/results.json."""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests

from classifier.rules import is_free_food, is_probable_free_food
from scraper import booking, fraserhouse, lusu, meetup, university
from scraper.common import get_session

OUTPUT_PATH = Path(__file__).parent / "data" / "results.json"

# Small calendars that can genuinely be empty for a while; their scrapers
# raise if the page structure is missing, so an empty list here is real.
MAY_BE_EMPTY = {"fraserhousehub.co.uk", "meetup.com"}

SOURCES = {
    "lusu.co.uk": lusu.fetch_events,
    "lancaster.ac.uk": university.fetch_events,
    "fraserhousehub.co.uk": fraserhouse.fetch_events,
    "meetup.com": meetup.fetch_events,
}


def load_previous_events() -> list[dict]:
    try:
        return json.loads(OUTPUT_PATH.read_text())["events"]
    except (FileNotFoundError, KeyError, ValueError):
        return []


def classify_event(event: dict) -> dict:
    # A known ticket cost means any "food included"/"refreshments provided"
    # wording is part of what you paid for, not free — e.g. a £40 conference
    # ticket that includes lunch. Skip classification entirely in that case.
    if event.get("is_paid") is True:
        event["free_food"] = False
        event["matched_phrases"] = []
        event["probable_free_food"] = False
        event["probable_reasons"] = []
        return event

    text = f"{event['title']} {event.get('description', '')}"
    flagged, matches = is_free_food(text)

    event["free_food"] = flagged
    event["matched_phrases"] = matches

    probable, reasons = (False, [])
    if not flagged:
        probable, reasons = is_probable_free_food(
            event["title"], event.get("description", ""), event.get("event_type", "")
        )
    event["probable_free_food"] = probable
    event["probable_reasons"] = reasons

    return event


# Fields lusu.fetch_event_detail fills in, reused from the previous run so
# each of the ~200 society events only costs one details request ever.
LUSU_DETAIL_FIELDS = (
    "description", "location", "start_date", "start_date_iso", "is_paid",
    "registration_required", "registration_url", "registration_deadline", "registration_status",
)


def add_lusu_detail(event: dict, session, previous_by_url: dict[str, dict], fetched_now: set[str]) -> None:
    """Fill in a LUSU/society event's description, times and ticketing from Rubric.

    The listing has no description, so the classifier would only see the
    title. Known-paid events are skipped since they're never classified.
    """
    if event.get("is_paid") is True:
        return
    previous = previous_by_url.get(event["url"], {})
    if "registration_required" in previous:
        event.update({k: previous[k] for k in LUSU_DETAIL_FIELDS if k in previous})
        return
    try:
        event.update(lusu.fetch_event_detail(session, event["url"]))
        fetched_now.add(event["url"])
    except (requests.RequestException, ValueError) as error:
        # A deleted event or a blip just leaves the listing-only fields.
        print(f"::warning::lusu.co.uk details failed for {event['url']} ({error})")


def add_registration_info(event: dict, session, previous_by_url: dict[str, dict], fetched_now: set[str]) -> None:
    """Attach the booking link, sign-up deadline and availability to food events that need sign-up.

    Only done for flagged events, since each lookup is another crawl-delayed
    page fetch. The university page (link + any "Booking closes on" date)
    rarely changes, so that's reused from the previous run; the booking
    site itself is rechecked every run because events sell out.
    """
    if not event.get("registration_required"):
        return
    if not (event["free_food"] or event["probable_free_food"]):
        return

    if event["source"] == "lancaster.ac.uk":
        previous = previous_by_url.get(event["url"], {})
        # Results saved before deadlines were tracked lack the key entirely,
        # so those get refetched once rather than cached without a deadline.
        if previous.get("registration_url") and "registration_deadline" in previous:
            event["registration_url"] = previous["registration_url"]
            event["registration_deadline"] = previous.get("registration_deadline", "")
        else:
            try:
                event["registration_url"], event["registration_deadline"] = (
                    university.fetch_registration_info(session, event["url"])
                )
            except requests.RequestException:
                event["registration_url"], event["registration_deadline"] = "", ""

    # Society tickets sell out, so recheck cached Rubric events with food.
    if event["source"] == "lusu.co.uk" and event["url"] not in fetched_now:
        try:
            detail = lusu.fetch_event_detail(session, event["url"])
        except (requests.RequestException, ValueError):
            return
        event.update({k: v for k, v in detail.items() if k.startswith("registration_")})
        return

    url = event.get("registration_url", "")
    if url and booking.is_supported(url):
        try:
            status = booking.fetch_booking_status(session, url)
        except requests.RequestException:
            return
        # The booking site's own close time beats a date typed into the
        # university page, which can go stale if booking is extended.
        event["registration_deadline"] = status["registration_deadline"] or event.get("registration_deadline", "")
        event["registration_status"] = status["registration_status"]


def run() -> tuple[list[dict], list[str]]:
    """Scrape, classify and write results. Returns (events, sources that broke)."""
    session = get_session()
    previous = load_previous_events()
    previous_by_url = {e["url"]: e for e in previous}
    fetched_now: set[str] = set()

    classified, broken = [], []
    for source, fetch in SOURCES.items():
        try:
            fresh = fetch()
            # The university and LUSU always have *some* upcoming events, so
            # zero means the page layout or API changed under us (as when LUSU
            # moved to Squarespace and this silently returned nothing).
            if not fresh and source not in MAY_BE_EMPTY:
                raise ValueError("returned 0 events — has the site changed?")
        except (requests.RequestException, ValueError) as error:
            # One flaky or changed site shouldn't wipe its events off the
            # page — keep what the last run had for it. Network blips are
            # just a warning (they fix themselves); anything else means the
            # scraper is broken, so it fails the Actions run to get noticed.
            print(f"::warning::{source} failed ({error}); keeping its previous results")
            classified += [event for event in previous if event["source"] == source]
            if not isinstance(error, requests.RequestException):
                broken.append(f"{source}: {error}")
            continue
        for event in fresh:
            if source == "lusu.co.uk":
                add_lusu_detail(event, session, previous_by_url, fetched_now)
            classify_event(event)
            add_registration_info(event, session, previous_by_url, fetched_now)
        classified += fresh

    OUTPUT_PATH.parent.mkdir(exist_ok=True)
    OUTPUT_PATH.write_text(
        json.dumps(
            {
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "events": classified,
                "free_food_count": sum(1 for e in classified if e["free_food"]),
                "probable_free_food_count": sum(1 for e in classified if e["probable_free_food"]),
            },
            indent=2,
        )
    )
    return classified, broken


if __name__ == "__main__":
    results, broken = run()
    flagged = [e for e in results if e["free_food"]]
    probable = [e for e in results if e["probable_free_food"]]
    print(f"Scraped {len(results)} events, flagged {len(flagged)} with free food, {len(probable)} probable.")
    for event in flagged:
        print(f" - [{event['source']}] {event['title']} ({event['start_date']})")
    for event in probable:
        print(f" - probable [{event['source']}] {event['title']} ({event['start_date']}) — {', '.join(event['probable_reasons'])}")
    if broken:
        for problem in broken:
            print(f"::error::{problem}")
        sys.exit(1)

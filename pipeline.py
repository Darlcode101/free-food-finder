"""Scrape LUSU, Lancaster University, Fraser House Hub, and Meetup events, flag free-food ones, write data/results.json."""
import json
from datetime import datetime, timezone
from pathlib import Path

import requests

from classifier.rules import is_free_food, is_probable_free_food
from scraper import fraserhouse, lusu, meetup, university
from scraper.common import get_session

OUTPUT_PATH = Path(__file__).parent / "data" / "results.json"


def classify_event(event: dict, session) -> dict:
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

    # Descriptions from the LUSU listing page are truncated; if the summary
    # didn't trip the classifier, check the full event page before giving up.
    # Event pages occasionally 404 (event removed/expired since the listing
    # was fetched) — that just means no extra text to check.
    if not flagged and event["source"] == "lancastersu.co.uk":
        try:
            full_text = lusu.fetch_event_detail(session, event["url"])
        except requests.HTTPError:
            full_text = ""
        flagged, matches = is_free_food(f"{event['title']} {full_text}")
        if full_text:
            event["description"] = full_text

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


def run() -> list[dict]:
    session = get_session()

    all_events = (
        lusu.fetch_events() + university.fetch_events() + fraserhouse.fetch_events() + meetup.fetch_events()
    )
    classified = [classify_event(event, session) for event in all_events]

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
    return classified


if __name__ == "__main__":
    results = run()
    flagged = [e for e in results if e["free_food"]]
    probable = [e for e in results if e["probable_free_food"]]
    print(f"Scraped {len(results)} events, flagged {len(flagged)} with free food, {len(probable)} probable.")
    for event in flagged:
        print(f" - [{event['source']}] {event['title']} ({event['start_date']})")
    for event in probable:
        print(f" - probable [{event['source']}] {event['title']} ({event['start_date']}) — {', '.join(event['probable_reasons'])}")

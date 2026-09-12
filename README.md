# Free Food Finder — Lancaster

Scrapes Lancaster University, LUSU (Students' Union), and town venues like
Fraser House Hub for event listings and flags ones that mention free food,
so you don't have to trawl every society page or coworking calendar
yourself.

**Live site:** https://darlcode101.github.io/free-food-finder/

## How it works

- [`scraper/university.py`](scraper/university.py) — pulls the JSON event
  feed embedded in `lancaster.ac.uk/events/`.
- [`scraper/lusu.py`](scraper/lusu.py) — parses the event listing at
  `lancastersu.co.uk/events` (200+ societies post here), and fetches the full
  event page when the listing's truncated summary isn't enough to classify.
- [`scraper/fraserhouse.py`](scraper/fraserhouse.py) — pulls the JSON embedded
  in `fraserhousehub.co.uk/events`, a Lancaster coworking space. Only its
  on-site speaker talks (e.g. "Fraser House Talks X ...") actually have food
  — the off-site casual pub meetups run by the same community (e.g.
  "Software Lancaster Meet up" at The Waterwitch) share the same category
  tags but don't, so the scraper only exposes event type to the classifier
  when `Location` is Fraser House itself. On-site talks rarely say "free
  pizza" in the venue listing text (that perk usually only shows up in the
  cross-posted Meetup/LinkedIn/Instagram announcement) — they're caught by
  the probable-food heuristic instead, via their "NETWORKING"/"EDUCATIONAL"
  category tags.
- [`scraper/meetup.py`](scraper/meetup.py) — pulls the GraphQL data embedded
  in the "Software Lancaster Talks" Meetup group page. Unlike Fraser House's
  own listing, Meetup's event descriptions explicitly say "Free pizza and
  drinks!" every time, so these are confirmed matches, not probable ones.
  (There's a second, separate Meetup group, "software-lancaster" — the
  casual pub meetup with no food — which this deliberately does not target.)
- [`classifier/rules.py`](classifier/rules.py) — two tiers of detection:
  - `is_free_food` — a keyword/regex baseline that flags explicit text like
    "free pizza" or "refreshments provided". Intentionally simple v1: there's
    no labeled data yet. Once the scraper has run for a while, label a sample
    of `data/results.json` and swap this for a trained TF-IDF + logistic
    regression classifier behind the same interface.
  - `is_probable_free_food` — a heuristic second tier for events that never
    say "food" but usually have it anyway: guest-speaker talks, seminars,
    "fireside chats", networking events. Shown separately on the site as
    "Probably has food" with its reasoning, never mixed in with confirmed
    matches.
- [`pipeline.py`](pipeline.py) — runs both scrapers, classifies every event,
  writes `data/results.json`. Skips classification entirely for events with
  a known ticket cost (`is_paid`, from LUSU's ticket price or the
  university's `RegistrationType`) — a paid conference ticket that "includes
  lunch" isn't free food, it's food you paid for.
- [`index.html`](index.html) — a static page that reads `data/results.json`:
  a month calendar (days with events get a dot, click one to filter the
  lists below to that day) plus separate "Confirmed" and "Probably has food"
  sections. Hosted via GitHub Pages, deployed from `main` / root.
- [`.github/workflows/scrape.yml`](.github/workflows/scrape.yml) — runs the
  pipeline every 6 hours and commits updated results, so the Pages site
  stays fresh without you running anything manually.

## Running locally

```bash
pip install -r requirements.txt
python pipeline.py
```

This writes `data/results.json` and prints any flagged events to the
terminal. Open `index.html` in a browser (or serve the folder) to see the
same data rendered.

## Scraping etiquette

Both sites are scraped politely: a descriptive `User-Agent`, and requests
throttled to respect `lancastersu.co.uk`'s `robots.txt` crawl-delay. If you
add more sources, check their `robots.txt` first.

## Roadmap

- Train a proper classifier once there's labeled data from real scrapes.
- Extract structured location/time instead of just linking to the event.
- Consider society Instagram/Facebook posts — a lot of real "free pizza"
  announcements happen there rather than on the SU website, but that needs
  auth-gated scraping and is out of scope for v1.
- Look for more Lancaster town sources (e.g. The Storey, Lancaster Castle
  events, other coworking spaces) as they turn up.

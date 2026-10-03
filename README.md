# Free Food Finder — Lancaster

Scrapes Lancaster University, LUSU (Students' Union), and town venues like
Fraser House Hub for event listings and flags ones that mention free food,
so you don't have to trawl every society page or coworking calendar
yourself.

**Live site:** https://darlcode101.github.io/free-food-finder/

## How it works

- [`scraper/university.py`](scraper/university.py) — pulls the JSON event
  feed embedded in `lancaster.ac.uk/events/`.
- [`scraper/lusu.py`](scraper/lusu.py) — society, college and Students'
  Union events. LUSU's site (`lusu.co.uk`, Squarespace) embeds them from
  Rubric (`campus.hellorubric.com`), so this calls the same Rubric API the
  embed uses: one search call lists every Lancaster event (~275, 40+
  societies), then a details call per event gets the description, exact
  times, venue and tickets. Events sold through Rubric (even £0 tickets)
  are marked sign-up required, with the ticket sale end as the deadline.
  Descriptions are cached across runs, so only new events cost a request.
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
- [`pipeline.py`](pipeline.py) — runs every scraper, classifies every event,
  writes `data/results.json`. Skips classification entirely for events with
  a known ticket cost (`is_paid`, from Rubric's ticket prices or the
  university's `RegistrationType`) — a paid conference ticket that "includes
  lunch" isn't free food, it's food you paid for.
  Also records `registration_required` (most university events are "Free to
  attend - registration required") and, for flagged university events, the
  external booking link (TryBooking, Eventbrite, LibCal, ...) scraped from
  the event page — so the site can show a "Sign-up required" badge and a
  direct Register button. Booking links are cached across runs.
  If a scraper finds 0 events (university, LUSU) or its page data is
  missing (all sources), that source keeps its previous results and the
  run exits non-zero, so the GitHub Actions run fails and GitHub emails
  you; plain network blips are only a warning.
- [`scraper/booking.py`](scraper/booking.py) — for TryBooking and
  Eventbrite links, reads the schema.org `Offer` data on the booking page
  to get when sign-up closes (`registration_deadline`) and whether it's
  fully booked (`registration_status`). Rechecked every run, since events
  sell out. Other booking sites fall back to any "Booking closes on ..."
  text on the university event page. The site never shows a deadline later
  than the event start (organisers sometimes leave sales open past it).
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

Every source is scraped politely: a descriptive `User-Agent`, and requests
throttled to a 5s crawl-delay (the old LUSU site's `robots.txt` value). If you
add more sources, check their `robots.txt` first.

## Roadmap

- Train a proper classifier once there's labeled data from real scrapes.
- Extract structured location/time instead of just linking to the event.
- Consider society Instagram/Facebook posts — a lot of real "free pizza"
  announcements happen there rather than on the SU website, but that needs
  auth-gated scraping and is out of scope for v1.
- Look for more Lancaster town sources (e.g. The Storey, Lancaster Castle
  events, other coworking spaces) as they turn up.

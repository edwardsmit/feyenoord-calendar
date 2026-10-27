# CLAUDE.md — Feyenoord calendar feeds

Guidance for Claude Code working on this repo.

## What this is

Public iCalendar (`.ics`) feeds of Feyenoord Rotterdam fixtures, served from GitHub Pages
and rebuilt twice a day by a GitHub Actions cron. No server and no runtime dependencies: a
single Python standard-library script writes three `.ics` files, the workflow commits them,
Pages serves them, and calendar apps subscribe to them.

- `feyenoord-home.ics` — home games
- `feyenoord-away.ics` — away games
- `feyenoord-all.ics` — everything

Live at `https://legioenagenda.nl/<file>.ics`, under the site name **Legioen Agenda**. The
old `https://edwardsmit.github.io/feyenoord-calendar/<file>.ics` URLs 301 to it, which is
what keeps early subscribers working.

## Layout

```
.
├── CLAUDE.md
├── README.md                  # for subscribers: what it is, how to add it
├── LICENSE                    # MIT, code only
├── index.html                 # Pages landing page (Dutch)
├── en/index.html              # the same page in English
├── assets/                    # shared CSS, JS, self-hosted font (OFL), icons, share images
├── robots.txt, sitemap.xml    # for search engines; both name the two pages only
├── feyenoord-*.ics            # generated feeds (committed)
├── last-run.txt               # heartbeat, see "Keeping the cron alive"
├── .github/workflows/update-calendars.yml
└── scripts/
    ├── generate_ics.py        # the generator
    ├── validate_ics.py        # structural validator, runs in CI
    ├── run_tests.sh           # offline test suite, runs in CI
    ├── test_fixtures.json     # sample matches for offline runs
    └── expected/              # golden output for those fixtures
```

## Data sources

| Competition | Source | Notes |
| --- | --- | --- |
| Eredivisie | football-data.org (`DED`) | Free tier, needs `FOOTBALL_DATA_API_KEY` |
| Champions League | football-data.org (`CL`) | Free tier |
| KNVB Beker | ESPN `ned.cup` scoreboard | No key, best effort |
| Europa / Conference League | — | Not on the free tier; not needed while Feyenoord are in the CL |

**football-data.org is the source of record.** Auth via the `X-Auth-Token` header. Without
the key the script exits 2. The free tier allows 10 requests/minute with no daily cap; this
script makes 1 call per run, so limits are irrelevant. Note it answers **403, not 429**, when
a quota is exhausted — don't write retry logic that only looks for 429.

Feyenoord's team id is hardcoded as `675` because these ids are stable. The script checks the
response really is Feyenoord and only falls back to a `/competitions/DED/teams` lookup if it
isn't. Don't invert that: making the lookup mandatory turns a cheap request into a single
point of failure.

**The KNVB Beker comes from ESPN because nothing else free covers it** — football-data.org
carries no Dutch cup on any plan. `site.api.espn.com` is undocumented and unsupported, so it
may change shape or disappear without warning. The whole path is wrapped in try/except and a
failure must only produce a logged warning. **Never let the cup source break the build.**

Cup rounds appear only after the draw, so an empty cup result early in the season is normal
and is logged differently from an outright failure.

It has already changed once: from 2026-09-15 the scoreboard answers a date range
(`dates=YYYYMMDD-YYYYMMDD`) with HTTP 400, even for ten days. A single day, a month
(`YYYYMM`) and a whole year (`YYYY`) still work, and a year returns exactly what its twelve
months do. The script therefore asks for both calendar years the season spans and keeps only
fixtures between 1 July and 30 June — the first year also holds last season's spring rounds.

## How generation works

1. `FIXTURES_JSON` set → load matches from that file, no network (this is how the tests run).
2. Otherwise fetch `/teams/675/matches` from football-data.org.
3. Best effort: fetch the `ned.cup` scoreboard from ESPN for both years the season spans,
   keep in-season fixtures involving Feyenoord.
4. Merge, de-duplicating on `(date, both team names)`; football-data.org wins.
5. Split into home / away / all and render each to `.ics` in `OUTPUT_DIR` (default `.`).

Every source is normalised into the `Match` dataclass at the top of `generate_ics.py`. Add
fields there rather than passing dicts around.

## iCalendar rules — do not regress these

- **Times** are `Europe/Amsterdam`. A full `VTIMEZONE` with DST rules is embedded; timed
  events use `DTSTART;TZID=Europe/Amsterdam:`. Sources give UTC; `zoneinfo` converts.
- **Never name Amsterdam in prose.** Text a subscriber reads (`README.md`, `index.html`) says
  "Rotterdamse tijd" / "Rotterdam time" in plain language — no zone identifier at all, because
  `Europe/...` means nothing to a normal reader. This file may use `Europe/Rotterdam` where a
  zone name is genuinely needed. In the code and in the `.ics` output it has to be
  `Europe/Amsterdam`: unfortunately
  we have to adhere to the IANA standard or the code breaks. `ZoneInfo()` raises on anything
  else, and calendar apps resolve `TZID` against the IANA database, so a non-standard value
  makes them misread every kickoff. Do not "fix" this difference in either direction.
- **Unknown kickoff** → all-day event (`DTSTART;VALUE=DATE`), title suffixed
  `- kickoff time TBD`, `STATUS:TENTATIVE`. A midnight-UTC kickoff is the placeholder both
  sources use; the status field is *not* a reliable signal, because fixtures sit at
  `SCHEDULED` for months while already carrying a real time.
- **Stable UIDs**: `fd-<matchId>@…`, `espn-<eventId>@…`. This is what makes a rescheduled
  match update its existing entry instead of duplicating. Changing the scheme orphans every
  subscriber's events.
- **`DTSTAMP`, `SEQUENCE` and `LAST-MODIFIED` are carried forward from the previous feed.**
  Before rendering, `read_previous_revisions()` parses `feyenoord-all.ics` out of
  `OUTPUT_DIR` and keys it by UID. If a fixture's freshly rendered body is byte-identical to
  the published one, its three revision properties are reused untouched; only a real
  difference moves them, and `SEQUENCE` moves by exactly `+1` so it stays monotonic as
  RFC 5545 requires. `feyenoord-all.ics` is the single reference for all three feeds — every
  event appears in it, and home/away must not disagree with it.

  **Do not go back to deriving these from `lastUpdated`.** That was the original design and
  it was wrong: football-data.org bulk-touches `lastUpdated` for a whole competition on its
  own refresh cycle, whether or not the fixture changed. The tell is that 34 of 42 events
  carried an identical stamp to the second, moving in lockstep by exactly 600 minutes
  between runs. The result was that every run rewrote every event, `SEQUENCE` bumped twice a
  day on fixtures nobody had touched, and in 28 consecutive runs the heartbeat path below
  never once fired. `lastUpdated` is a clock, just someone else's — it is only trusted now
  as the seed for a fixture's very first sighting (`seed_dtstamp`, `seed_sequence`).

  Two consequences worth knowing. `render_event()` splices the properties back in at fixed
  positions; **reordering fields there rewrites every event in every subscriber's calendar**
  for nothing. And a missing or unparseable previous feed deliberately degrades to seeding
  everything afresh rather than raising — the seeds are minutes-since-epoch and so always
  larger than any carried `+1` has reached, which keeps `SEQUENCE` monotonic even then.
- **Cancelled / postponed**: `STATUS:CANCELLED` plus a `[POSTPONED]` / `[CANCELLED]` title
  prefix, same UID.
- Output is **CRLF** with RFC 5545 folding at **75 octets** (74 after the first line, because
  the continuation space counts) and TEXT escaping of `\ ; , \r \n`. Matches are assumed 2h.
  `.gitattributes` marks `*.ics` as `-text` so git never rewrites those endings — with a
  global `core.autocrlf=input` it otherwise stores them as LF and the published feeds break.

## Testing

```bash
# Everything, offline, no key needed:
bash scripts/run_tests.sh

# Generate somewhere harmless and inspect:
OUTPUT_DIR=/tmp/fey FIXTURES_JSON=scripts/test_fixtures.json python3 scripts/generate_ics.py
python3 scripts/validate_ics.py /tmp/fey/feyenoord-*.ics

# Against the real APIs:
FOOTBALL_DATA_API_KEY=xxxx python3 scripts/generate_ics.py
```

`run_tests.sh` checks five things: output matches `scripts/expected/`, two consecutive runs
are byte-identical, the feeds pass the validator, a source-side bulk touch of every
`lastUpdated` changes nothing, and a genuine fixture change bumps that one event's
`SEQUENCE` by exactly 1 while the other nine stay untouched. The last two exercise the
carry-forward path, which the first three cannot reach because they generate into empty
directories.

**If you intentionally change the output, regenerate the golden files** with
`OUTPUT_DIR=scripts/expected FIXTURES_JSON=scripts/test_fixtures.json python3 scripts/generate_ics.py`
and check the diff carefully — that diff is the only review the change gets.

`validate_ics.py` is dependency-free and checks CRLF everywhere, line length, BEGIN/END
nesting, required VEVENT properties, unique UIDs, DTEND ordering, and that referenced TZIDs
are defined.

## The workflow

`.github/workflows/update-calendars.yml` runs on cron (04:12 and 16:12 UTC), on manual
dispatch, and on pushes touching `scripts/**` or the workflow itself. The `test` job runs the
offline suite and gates the `build` job, which checks the secret is present, generates,
validates, and commits. `permissions: contents: write` and `issues: write` and a `concurrency`
group are required.

The push trigger deliberately excludes `*.ics` and `last-run.txt` — the workflow commits
those, and including them would loop.

### Keeping the cron alive

GitHub disables scheduled workflows in public repositories after 60 days without activity,
and the Dutch off-season can easily be that quiet now that `DTSTAMP` is stable. Every run
therefore writes `last-run.txt` and commits it, so there is always activity. The commit
message says `refresh` when a fixture actually changed and `heartbeat` when nothing did.

### Alerting on a failing cup source

A failed run emails the owner through GitHub's own notifications, but a cup failure never
fails the run, so on its own it is silent: from 2026-09-15 ESPN rejected every request for
five weeks and only the log knew. `generate_ics.py` therefore reports `cup_failed` and
`cup_problem` through `GITHUB_OUTPUT`, and the last step of the `build` job keeps exactly one
issue labelled `source-down` open while the source fails. It opens the issue on the first
failing run, mentions the owner so the notification lands whatever the watch settings, and
closes it on the first healthy run. Runs in between leave it alone — **don't add a comment per
failing run**, every comment is another email. The step runs after the push, so a problem
with the issue itself can never hold back the feeds.

## The landing page

`index.html` (Dutch) and `en/index.html` (English) are two static pages with the same markup,
sharing `assets/site.css` and `assets/site.js`. They are separate pages rather than a JS toggle,
so search engines index both languages. Change one, change the other.

The page walks a visitor through three numbered steps: one calendar or two (Alles, or Thuis +
Uit in their own colours), then their calendar app (preselected from the user agent), then
colours. Never offer Alles together with Thuis/Uit — that duplicates every match.

- **The page works without JavaScript.** An inline script in `<head>` sets `.js` on `<html>`
  before first paint. Without it, every option shows at once: both choices with their names,
  all three app panels with a heading each, and the full links instead of copy buttons.
  Elements that start hidden carry `data-start-hidden`, not `hidden` (`site.js` turns one into
  the other); `js-only` and `no-js-only` mark what belongs to one case. Never put a plain
  `hidden` in the HTML, or visitors without JavaScript can't reach it.
- **Feed links follow the host.** `site.js` rewrites every `data-feed` link from the page's
  own URL, so they work on whichever host serves the page. The hardcoded `legioenagenda.nl`
  hrefs are only the no-JS fallback.
- **The phone preview reads `feyenoord-all.ics`.** It relies on `DESCRIPTION` reading
  `<competition> - Home|Away match vs <opponent>` and on `STATUS:CANCELLED`. Changing that
  text in `event_body()` breaks the preview silently (it shows nothing), so update
  `parseCalendar()`/`renderPreview()` with it.
- **The font is self-hosted** (`assets/fonts/`, SIL OFL, licence alongside). Loading it from
  Google Fonts would send every visitor's IP to Google, which needs consent in the EU.
- No club crest, club typeface or photos. "Feyenoord" appears only as a description.

### Search engines

Each page carries a canonical link, `hreflang` pairs (repeated in `sitemap.xml`), Open Graph
tags and `WebSite` structured data. That structured data is what lets Google show "Legioen
Agenda" as the site name. Keep titles, descriptions and the JSON-LD in sync between the two
languages.

- **No `FAQPage` markup.** Google stopped showing FAQ rich results for sites like this one in
  2023, so it would be dead weight.
- **The next real gain is static fixtures.** The phone preview is built in the browser, so
  crawlers see no fixtures. Writing the upcoming matches into the HTML at generation time,
  with `SportsEvent` data, would give search engines content that changes twice a day. That
  touches `generate_ics.py` and the golden tests, so it is a separate change.
- **Share images and touch icon** come from `assets/og/og-image.html`. Serve the repo root
  locally (`python3 -m http.server`) and render with headless Chrome at a 1200x630 window: the
  page as-is gives `og-nl.png`, and `?en` gives `og-en.png`. `?icon` draws a 630px square;
  crop and scale it with `sips -c 630 630` and then `sips -z 180 180` to make
  `apple-touch-icon.png`. Use a server, not `file://`, or the font does not load.

## Setting it up from scratch

Three steps cannot be automated: a workflow cannot create its own repository, cannot hold its
own secret, and cannot enable Pages (that needs `administration:write`, which `GITHUB_TOKEN`
does not have). Everything after these is push-driven.

```bash
# origin is already set to the SSH form. Keep it that way: the global gitconfig
# picks the commit identity with `includeIf hasconfig:remote.*.url:`, which
# matches the URL as stored, not as rewritten by url.insteadOf. An https origin
# leaves user.email unset and commits fail.
gh repo create edwardsmit/feyenoord-calendar --public --source=. --push
gh secret set FOOTBALL_DATA_API_KEY --repo edwardsmit/feyenoord-calendar   # free key at football-data.org
gh api -X POST repos/edwardsmit/feyenoord-calendar/pages \
       -f 'source[branch]=main' -f 'source[path]=/'
```

Pages stays **branch-based** (`main` / root). Publishing from an artifact instead would commit
nothing, which reintroduces the 60-day problem it takes a heartbeat commit to solve anyway.

### The custom domain

`legioenagenda.nl` is registered at Namecheap and points at Pages through the `CNAME` file in
the repository root. Delete that file and the site falls back to `github.io`. The DNS is
plain and holds no redirects; GitHub does them all (`github.io` → domain, `www` → apex, HTTP →
HTTPS):

| Record | Host | Value |
| --- | --- | --- |
| A | `@` | `185.199.108.153` … `185.199.111.153` |
| AAAA | `@` | `2606:50c0:8000::153` … `2606:50c0:8003::153` |
| CNAME | `www` | `edwardsmit.github.io` |
| TXT | `_github-pages-challenge-edwardsmit` | domain verification, guards against takeover |

The name leaves out the club name on purpose: "Feyenoord" is the club's registered mark.
"Legioen" is registered too, by Grolsch, but only in class 32 (beer), which does not reach a
calendar service. For the same reason, keep beer and drinks brands out of any future sponsor
slot.

**`UID_DOMAIN` in `generate_ics.py` keeps the old `github.io` name.** It is only an identifier,
not a URL, and changing it would orphan every subscriber's events.

**The repository stays named `feyenoord-calendar` (decided 2026-10-27).** GitHub redirects a
renamed repo's git and web URLs, but not its Pages project URL. Everyone who subscribed before
the domain move uses `edwardsmit.github.io/feyenoord-calendar/…`, which only redirects
because it belongs to this repo. After a rename those subscriptions would 404, and calendar
apps fail silently, so supporters would be left with stale fixtures.

The API key lives only in Actions secrets — football-data.org's terms forbid keeping
credentials in an open-source repository, so this is deliberate.

## Conventions

- **Standard library only at runtime.** No `requests`, no `icalendar`. Zero-install CI is the
  point.
- Code should read clearly to someone with basic Python: full words for names, a docstring per
  function, no clever one-liners.
- This is an unofficial fan project with no affiliation to Feyenoord, the KNVB or UEFA, and
  football-data.org's terms require the exact string *"Football data provided by the
  Football-Data.org API"*. Both appear in `README.md` and `index.html`; keep them there.

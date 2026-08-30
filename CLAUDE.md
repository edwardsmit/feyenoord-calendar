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

Live at `https://edwardsmit.github.io/feyenoord-calendar/<file>.ics`.

## Layout

```
.
├── CLAUDE.md
├── README.md                  # for subscribers: what it is, how to add it
├── LICENSE                    # MIT, code only
├── index.html                 # Pages landing page
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

## How generation works

1. `FIXTURES_JSON` set → load matches from that file, no network (this is how the tests run).
2. Otherwise fetch `/teams/675/matches` from football-data.org.
3. Best effort: fetch the season's `ned.cup` scoreboard from ESPN, keep fixtures involving
   Feyenoord.
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
validates, and commits. `permissions: contents: write` and a `concurrency` group are required.

The push trigger deliberately excludes `*.ics` and `last-run.txt` — the workflow commits
those, and including them would loop.

### Keeping the cron alive

GitHub disables scheduled workflows in public repositories after 60 days without activity,
and the Dutch off-season can easily be that quiet now that `DTSTAMP` is stable. Every run
therefore writes `last-run.txt` and commits it, so there is always activity. The commit
message says `refresh` when a fixture actually changed and `heartbeat` when nothing did.

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

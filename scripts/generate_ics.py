#!/usr/bin/env python3
"""
Generate iCalendar (.ics) feeds for Feyenoord Rotterdam fixtures.

Writes three files into OUTPUT_DIR (default: the current directory):

    feyenoord-home.ics   home games only
    feyenoord-away.ics   away games only
    feyenoord-all.ics    all games combined

Where the fixtures come from
----------------------------
football-data.org  (required)  Eredivisie + Champions League.
                               Needs a free API key in FOOTBALL_DATA_API_KEY.

ESPN               (optional)  KNVB Beker only. No API key needed. This is an
                               undocumented endpoint, so every failure here is
                               logged and ignored: the feeds must still build
                               from football-data.org alone.

Offline mode
------------
Set FIXTURES_JSON=/path/to/file.json to build from a file of match records and
skip the network entirely. Used by the tests.

Standard library only - no pip install, ever.
"""

import hashlib
import json
import os
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

# --------------------------------------------------------------------------- #
# Configuration
# --------------------------------------------------------------------------- #

TEAM_NAME = "Feyenoord"

# The documentation calls this zone "Europe/Rotterdam". Here it has to stay
# "Europe/Amsterdam": unfortunately we have to adhere to the IANA standard or
# the code breaks. ZoneInfo() raises on anything else, and calendar apps look
# TZID up in the IANA database, so a non-standard value makes them misread
# every kickoff.
TIMEZONE_ID = "Europe/Amsterdam"
TZ = ZoneInfo(TIMEZONE_ID)

MATCH_DURATION = timedelta(hours=2)
REFRESH_HOURS = 12

# Used as DTSTAMP when a source does not say when a fixture last changed.
EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)
PRODID = "-//edwardsmit//Feyenoord Calendar//EN"
UID_DOMAIN = "feyenoord-cal.edwardsmit.github.io"

# RFC 5545 section 3.1: a content line is at most 75 octets, not counting the
# line break but counting the single leading space on a continuation line.
MAX_LINE_OCTETS = 75

FOOTBALL_DATA_BASE = "https://api.football-data.org/v4"
ESPN_BASE = "https://site.api.espn.com/apis/site/v2/sports/soccer"

# Feyenoord's team id on football-data.org. These ids are stable, so we use it
# directly and only fall back to a lookup if the response does not look right.
FEYENOORD_FD_TEAM_ID = 675

# Friendly names for the competition codes football-data.org returns.
COMPETITION_NAMES = {
    "DED": "Eredivisie",
    "Eredivisie": "Eredivisie",
    "CL": "Champions League",
    "UEFA Champions League": "Champions League",
    "EL": "Europa League",
    "UEFA Europa League": "Europa League",
    "ECL": "Conference League",
    "UEFA Conference League": "Conference League",
}

# ESPN status names mapped onto the ones football-data.org uses, so the rest of
# the script only ever deals with one vocabulary.
ESPN_STATUS_NAMES = {
    "STATUS_SCHEDULED": "SCHEDULED",
    "STATUS_POSTPONED": "POSTPONED",
    "STATUS_CANCELED": "CANCELLED",
    "STATUS_CANCELLED": "CANCELLED",
    "STATUS_ABANDONED": "CANCELLED",
    "STATUS_FINAL": "FINISHED",
    "STATUS_FULL_TIME": "FINISHED",
}


# --------------------------------------------------------------------------- #
# The one shape every source is converted into
# --------------------------------------------------------------------------- #

@dataclass
class Match:
    """One fixture, normalised so the renderer never has to know the source."""

    source: str                     # "fd", "espn" or "test"
    source_id: str                  # stable id from that source
    competition: str                # friendly name, e.g. "Eredivisie"
    home: str
    away: str
    is_home: bool                   # True when Feyenoord play at home
    opponent: str
    start_utc: datetime | None      # kickoff in UTC, None if unknown
    time_confirmed: bool            # False renders an all-day "TBD" event
    venue: str | None = None
    status: str = "SCHEDULED"       # SCHEDULED / FINISHED / POSTPONED / CANCELLED
    last_updated: datetime | None = None


# --------------------------------------------------------------------------- #
# Small helpers
# --------------------------------------------------------------------------- #

def http_get_json(url: str, headers: dict | None = None, timeout: int = 30) -> dict:
    """GET a URL and parse the response as JSON."""
    request = urllib.request.Request(url, headers=headers or {})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def friendly_competition(name_or_code: str) -> str:
    """Turn a competition code or raw name into something readable."""
    if not name_or_code:
        return "Match"
    return COMPETITION_NAMES.get(name_or_code, name_or_code)


def parse_iso_utc(value: str | None) -> datetime | None:
    """Parse an ISO 8601 timestamp into an aware UTC datetime, or None."""
    if not value or not value.strip():
        return None
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def is_feyenoord(team_name: str) -> bool:
    """True if this team name refers to Feyenoord."""
    return TEAM_NAME.lower() in (team_name or "").lower()


def has_placeholder_kickoff(start_utc: datetime | None) -> bool:
    """
    True when the kickoff time is a "not decided yet" placeholder.

    Both sources use midnight UTC when only the date is known. No real match
    kicks off at 01:00 or 02:00 local time, so this has no false positives.
    """
    if start_utc is None:
        return True
    return start_utc.hour == 0 and start_utc.minute == 0


def season_date_range(today: date) -> tuple[str, str]:
    """
    The current season as an ESPN date range, e.g. ("20260701", "20270630").

    A European football season starts in July, so anything before July belongs
    to the season that started the previous year.
    """
    start_year = today.year if today.month >= 7 else today.year - 1
    return f"{start_year}0701", f"{start_year + 1}0630"


# --------------------------------------------------------------------------- #
# Source 1: football-data.org - Eredivisie and Champions League
# --------------------------------------------------------------------------- #

def response_mentions_feyenoord(payload: dict) -> bool:
    """Sanity check that a /teams/{id}/matches response is really Feyenoord's."""
    for raw_match in payload.get("matches", []):
        home = (raw_match.get("homeTeam") or {}).get("name") or ""
        away = (raw_match.get("awayTeam") or {}).get("name") or ""
        if is_feyenoord(home) or is_feyenoord(away):
            return True
    return False


def look_up_fd_team_id(headers: dict) -> int | None:
    """
    Find Feyenoord's team id in the Eredivisie squad list.

    Only used when the hardcoded id turns out to be wrong. Returns None if the
    lookup fails for any reason - the caller keeps using the hardcoded id.
    """
    try:
        payload = http_get_json(f"{FOOTBALL_DATA_BASE}/competitions/DED/teams", headers)
    except Exception as error:
        print(f"WARN: team id lookup failed: {error}", file=sys.stderr)
        return None

    for team in payload.get("teams", []):
        # Use "or" rather than a .get default: the API sends null, not a missing
        # key, and null would not be replaced by a default.
        names = (team.get("name") or "") + " " + (team.get("shortName") or "")
        if is_feyenoord(names):
            return team.get("id")
    return None


def fetch_football_data(api_key: str) -> list[Match]:
    """Fetch this season's Eredivisie and Champions League fixtures."""
    headers = {"X-Auth-Token": api_key}
    team_id = FEYENOORD_FD_TEAM_ID
    payload = http_get_json(f"{FOOTBALL_DATA_BASE}/teams/{team_id}/matches", headers)

    # If the hardcoded id ever stops being Feyenoord, find the right one once.
    if not response_mentions_feyenoord(payload):
        print(f"WARN: team {team_id} does not look like Feyenoord; looking it up",
              file=sys.stderr)
        looked_up = look_up_fd_team_id(headers)
        if looked_up is not None and looked_up != team_id:
            team_id = looked_up
            payload = http_get_json(
                f"{FOOTBALL_DATA_BASE}/teams/{team_id}/matches", headers)

    raw_matches = payload.get("matches", [])
    print(f"football-data.org: {len(raw_matches)} matches for team {team_id}",
          file=sys.stderr)

    matches = []
    for raw_match in raw_matches:
        competition = raw_match.get("competition") or {}
        home = (raw_match.get("homeTeam") or {}).get("name") or "TBD"
        away = (raw_match.get("awayTeam") or {}).get("name") or "TBD"
        playing_at_home = is_feyenoord(home)
        start_utc = parse_iso_utc(raw_match.get("utcDate"))

        matches.append(Match(
            source="fd",
            source_id=str(raw_match.get("id")),
            competition=friendly_competition(
                competition.get("code") or competition.get("name") or ""),
            home=home,
            away=away,
            is_home=playing_at_home,
            opponent=away if playing_at_home else home,
            start_utc=start_utc,
            # Trust the time itself rather than the status: fixtures sit at
            # SCHEDULED for months while already carrying a real kickoff time.
            time_confirmed=not has_placeholder_kickoff(start_utc),
            venue=raw_match.get("venue"),
            status=raw_match.get("status", "SCHEDULED"),
            last_updated=parse_iso_utc(raw_match.get("lastUpdated")),
        ))
    return matches


# --------------------------------------------------------------------------- #
# Source 2: ESPN - KNVB Beker only, best effort
# --------------------------------------------------------------------------- #

def fetch_espn_cup(today: date) -> list[Match]:
    """
    Fetch this season's KNVB Beker fixtures involving Feyenoord.

    football-data.org carries no Dutch cup competition on any plan, so this
    fills that gap. Returns an empty list when the rounds Feyenoord play in
    have not been drawn yet, which is normal early in the season.
    """
    season_start, season_end = season_date_range(today)
    payload = http_get_json(
        f"{ESPN_BASE}/ned.cup/scoreboard?dates={season_start}-{season_end}")

    events = payload.get("events") or []
    print(f"ESPN: {len(events)} KNVB Beker fixtures published this season",
          file=sys.stderr)

    matches = []
    for event in events:
        competition = (event.get("competitions") or [{}])[0]

        home = away = None
        for competitor in competition.get("competitors") or []:
            name = (competitor.get("team") or {}).get("displayName")
            if competitor.get("homeAway") == "home":
                home = name
            else:
                away = name
        if not home or not away:
            continue
        if not (is_feyenoord(home) or is_feyenoord(away)):
            continue

        playing_at_home = is_feyenoord(home)
        start_utc = parse_iso_utc(event.get("date"))
        espn_status = ((competition.get("status") or {}).get("type") or {}).get("name", "")

        venue_info = competition.get("venue") or {}
        venue_city = (venue_info.get("address") or {}).get("city")
        venue = venue_info.get("fullName")
        if venue and venue_city:
            venue = f"{venue}, {venue_city}"

        matches.append(Match(
            source="espn",
            source_id=str(event.get("id")),
            competition="KNVB Beker",
            home=home,
            away=away,
            is_home=playing_at_home,
            opponent=away if playing_at_home else home,
            start_utc=start_utc,
            time_confirmed=(bool(competition.get("timeValid"))
                            and not has_placeholder_kickoff(start_utc)),
            venue=venue,
            status=ESPN_STATUS_NAMES.get(espn_status, "SCHEDULED"),
            last_updated=None,
        ))
    return matches


# --------------------------------------------------------------------------- #
# Merge and de-duplicate
# --------------------------------------------------------------------------- #

def dedup_key(match: Match) -> str:
    """
    Identify a fixture independently of which source described it.

    One team cannot play twice on the same day, so the date plus who is playing
    is enough.
    """
    day = match.start_utc.date().isoformat() if match.start_utc else "nodate"
    pair = "|".join(sorted([match.home.lower().strip(), match.away.lower().strip()]))
    return f"{day}::{pair}"


def merge(primary: list[Match], secondary: list[Match]) -> list[Match]:
    """Combine two sources, letting the primary one win, then sort by kickoff."""
    seen = {dedup_key(match) for match in primary}
    merged = list(primary)
    for match in secondary:
        key = dedup_key(match)
        if key not in seen:
            merged.append(match)
            seen.add(key)

    # Undated fixtures sort last.
    latest = datetime.max.replace(tzinfo=timezone.utc)
    merged.sort(key=lambda match: (match.start_utc is None, match.start_utc or latest))
    return merged


# --------------------------------------------------------------------------- #
# iCalendar rendering
# --------------------------------------------------------------------------- #

def escape_text(text: str) -> str:
    """Escape a string for an iCalendar TEXT value (RFC 5545 section 3.3.11)."""
    # A literal carriage return cannot be represented, so fold it into \n first.
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    return (text.replace("\\", "\\\\")
                .replace(";", "\\;")
                .replace(",", "\\,")
                .replace("\n", "\\n"))


def is_utf8_continuation_byte(byte: int) -> bool:
    """True if this byte is the middle of a multi-byte UTF-8 character."""
    return (byte & 0xC0) == 0x80


def fold_line(line: str) -> str:
    """
    Split a long line into 75-octet chunks joined by CRLF + a single space.

    The limit is octets, not characters, so we measure the encoded bytes and
    back off if a cut would land inside a multi-byte character. Continuation
    lines get one octet less because their leading space counts too.
    """
    raw = line.encode("utf-8")
    if len(raw) <= MAX_LINE_OCTETS:
        return line

    chunks = []
    limit = MAX_LINE_OCTETS
    while len(raw) > limit:
        cut = limit
        while cut > 0 and is_utf8_continuation_byte(raw[cut]):
            cut -= 1
        chunks.append(raw[:cut].decode("utf-8"))
        raw = raw[cut:]
        limit = MAX_LINE_OCTETS - 1  # room for the leading space
    chunks.append(raw.decode("utf-8"))
    return "\r\n ".join(chunks)


def make_uid(match: Match) -> str:
    """
    The identity of this event, stable across regenerations.

    Calendar apps use the UID to decide whether a fixture is new or an update.
    Changing this scheme would orphan every subscriber's existing events.
    """
    return f"{match.source}-{match.source_id}@{UID_DOMAIN}"


def sequence_for(match: Match) -> int:
    """Revision number: bumps whenever the source says the fixture changed."""
    if match.last_updated is None:
        return 0
    return int(match.last_updated.timestamp() // 60)


def dtstamp_for(match: Match) -> datetime:
    """
    When this description of the fixture was last changed.

    Must NOT depend on the wall clock. The workflow only commits when the
    generated files really differ, so a value that changed every run would
    produce an endless stream of no-op commits and defeat caching for
    subscribers.

    ESPN gives no equivalent of football-data.org's lastUpdated, so cup
    fixtures fall back to a fixed constant rather than to their own kickoff
    time: a match brought forward would otherwise have its DTSTAMP move
    backwards, which a strict client may read as a stale description and
    ignore. A constant makes no ordering claim at all. Use SEQUENCE, not
    DTSTAMP, if cup reschedules ever need to be signalled properly.
    """
    return match.last_updated or EPOCH


def summary_for(match: Match) -> str:
    """The event title, e.g. "Feyenoord vs Sparta Rotterdam (Eredivisie)"."""
    return f"{match.home} vs {match.away} ({match.competition})"


# DST rules for the Netherlands, so calendar apps that do not know the zone can
# still work out the offset. Both DTSTART values really were the last Sunday of
# their month in 1970, which the RRULEs require.
VTIMEZONE = f"""BEGIN:VTIMEZONE
TZID:{TIMEZONE_ID}
X-LIC-LOCATION:{TIMEZONE_ID}
BEGIN:DAYLIGHT
TZOFFSETFROM:+0100
TZOFFSETTO:+0200
TZNAME:CEST
DTSTART:19700329T020000
RRULE:FREQ=YEARLY;BYMONTH=3;BYDAY=-1SU
END:DAYLIGHT
BEGIN:STANDARD
TZOFFSETFROM:+0200
TZOFFSETTO:+0100
TZNAME:CET
DTSTART:19701025T030000
RRULE:FREQ=YEARLY;BYMONTH=10;BYDAY=-1SU
END:STANDARD
END:VTIMEZONE""".split("\n")


def render_event(match: Match) -> list[str]:
    """Render one fixture as the lines of a VEVENT."""
    lines = [
        "BEGIN:VEVENT",
        f"UID:{make_uid(match)}",
        f"DTSTAMP:{dtstamp_for(match).strftime('%Y%m%dT%H%M%SZ')}",
    ]

    sequence = sequence_for(match)
    if sequence:
        lines.append(f"SEQUENCE:{sequence}")

    if match.start_utc is not None and match.time_confirmed:
        starts = match.start_utc.astimezone(TZ)
        ends = (match.start_utc + MATCH_DURATION).astimezone(TZ)
        lines.append(f"DTSTART;TZID={TIMEZONE_ID}:{starts.strftime('%Y%m%dT%H%M%S')}")
        lines.append(f"DTEND;TZID={TIMEZONE_ID}:{ends.strftime('%Y%m%dT%H%M%S')}")
        summary = summary_for(match)
        status_line = "STATUS:CONFIRMED"
    else:
        # Kickoff time unknown, so show it as an all-day event instead.
        day = match.start_utc.astimezone(TZ).date() if match.start_utc else date(1970, 1, 1)
        lines.append(f"DTSTART;VALUE=DATE:{day.strftime('%Y%m%d')}")
        # An all-day DTEND is exclusive, so it points at the next day.
        lines.append(f"DTEND;VALUE=DATE:{(day + timedelta(days=1)).strftime('%Y%m%d')}")
        summary = summary_for(match) + " - kickoff time TBD"
        status_line = "STATUS:TENTATIVE"

    if match.status in ("POSTPONED", "SUSPENDED", "CANCELLED"):
        # Same UID, so subscribers see the existing entry change rather than a
        # duplicate appearing.
        status_line = "STATUS:CANCELLED"
        summary = f"[{match.status}] " + summary

    lines.append(status_line)
    lines.append(f"SUMMARY:{escape_text(summary)}")
    if match.venue:
        lines.append(f"LOCATION:{escape_text(match.venue)}")

    home_or_away = "Home" if match.is_home else "Away"
    lines.append("DESCRIPTION:" + escape_text(
        f"{match.competition} - {home_or_away} match vs {match.opponent}"))
    lines.append(f"CATEGORIES:{escape_text(match.competition)}")
    if match.last_updated:
        lines.append(f"LAST-MODIFIED:{match.last_updated.strftime('%Y%m%dT%H%M%SZ')}")
    lines.append("TRANSP:TRANSPARENT")
    lines.append("END:VEVENT")
    return lines


def render_calendar(name: str, matches: list[Match]) -> str:
    """Render a whole calendar file. Output uses CRLF, as RFC 5545 requires."""
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        f"PRODID:{PRODID}",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        f"X-WR-CALNAME:{escape_text(name)}",
        f"X-WR-TIMEZONE:{TIMEZONE_ID}",
        f"X-WR-CALDESC:{escape_text(name + ' - auto-updated fixtures')}",
        f"X-PUBLISHED-TTL:PT{REFRESH_HOURS}H",
        f"REFRESH-INTERVAL;VALUE=DURATION:PT{REFRESH_HOURS}H",
    ]
    lines += VTIMEZONE
    for match in matches:
        lines += render_event(match)
    lines.append("END:VCALENDAR")
    return "\r\n".join(fold_line(line) for line in lines) + "\r\n"


# --------------------------------------------------------------------------- #
# Loading matches
# --------------------------------------------------------------------------- #

def load_from_file(path: str) -> list[Match]:
    """Build matches from a JSON file instead of the network (offline mode)."""
    with open(path, encoding="utf-8") as handle:
        rows = json.load(handle)

    matches = []
    for row in rows:
        start_utc = parse_iso_utc(row.get("start_utc"))
        home = row.get("home", "TBD")
        away = row.get("away", "TBD")
        playing_at_home = row.get("is_home", is_feyenoord(home))
        # Test rows usually have no id of their own, so derive a stable one.
        fallback_id = hashlib.md5(
            f"{home}{away}{start_utc}".encode("utf-8")).hexdigest()[:10]

        matches.append(Match(
            source=row.get("source", "test"),
            source_id=str(row.get("source_id", fallback_id)),
            competition=row.get("competition", "Match"),
            home=home,
            away=away,
            is_home=playing_at_home,
            opponent=row.get("opponent", home if not playing_at_home else away),
            start_utc=start_utc,
            time_confirmed=row.get("time_confirmed", start_utc is not None),
            venue=row.get("venue"),
            status=row.get("status", "SCHEDULED"),
            last_updated=parse_iso_utc(row.get("last_updated")),
        ))
    return matches


def load_matches() -> tuple[list[Match], list[str]]:
    """Get every fixture, plus notes about what each source contributed."""
    notes: list[str] = []

    fixtures_json = os.environ.get("FIXTURES_JSON")
    if fixtures_json:
        matches = load_from_file(fixtures_json)
        notes.append(f"Offline mode: {len(matches)} matches from {fixtures_json}.")
        return merge(matches, []), notes

    api_key = os.environ.get("FOOTBALL_DATA_API_KEY")
    if not api_key:
        print("ERROR: FOOTBALL_DATA_API_KEY is not set.", file=sys.stderr)
        sys.exit(2)

    league_and_europe = fetch_football_data(api_key)
    notes.append(f"football-data.org: {len(league_and_europe)} matches "
                 "(Eredivisie + Champions League).")

    # Best effort. The cup is a bonus; never let it break the build.
    cup: list[Match] = []
    try:
        cup = fetch_espn_cup(datetime.now(timezone.utc).date())
        if cup:
            notes.append(f"ESPN: +{len(cup)} KNVB Beker match(es).")
        else:
            notes.append("ESPN: no KNVB Beker match for Feyenoord yet "
                         "(rounds they enter may not be drawn).")
    except Exception as error:
        notes.append(f"ESPN unavailable ({error}); KNVB Beker not included this run.")
        print(f"WARN: ESPN cup fetch failed: {error}", file=sys.stderr)

    return merge(league_and_europe, cup), notes


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #

def main() -> None:
    out_dir = os.environ.get("OUTPUT_DIR", ".")
    matches, notes = load_matches()

    home_matches = [match for match in matches if match.is_home]
    away_matches = [match for match in matches if not match.is_home]

    feeds = {
        "feyenoord-home.ics": ("Feyenoord (Home)", home_matches),
        "feyenoord-away.ics": ("Feyenoord (Away)", away_matches),
        "feyenoord-all.ics": ("Feyenoord (All matches)", matches),
    }
    for filename, (calendar_name, feed_matches) in feeds.items():
        path = os.path.join(out_dir, filename)
        with open(path, "w", encoding="utf-8", newline="") as handle:
            handle.write(render_calendar(calendar_name, feed_matches))
        print(f"Wrote {path}: {len(feed_matches)} events", file=sys.stderr)

    print("\n=== Run notes ===", file=sys.stderr)
    for note in notes:
        print(f"- {note}", file=sys.stderr)


if __name__ == "__main__":
    main()

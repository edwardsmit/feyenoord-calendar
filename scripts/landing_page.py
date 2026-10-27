"""
Write the upcoming fixtures into the landing pages and keep sitemap.xml honest.

Called from generate_ics.py after the feeds are written. Two things happen:

1. In index.html and en/index.html, everything between the marker comments

       <!-- upcoming-range:start --> ... <!-- upcoming-range:end -->
       <!-- upcoming:start -->       ... <!-- upcoming:end -->
       <!-- upcoming-data:start -->  ... <!-- upcoming-data:end -->

   is replaced with the next few fixtures: the month range above the phone
   preview, the list itself, and SportsEvent structured data for exactly those
   fixtures. Everything outside the markers is hand-written and left alone.
   The markup matches what renderPreview() in assets/site.js builds, so the
   browser can redraw the list for the visitor's own "today" without a jump.

2. sitemap.xml is rewritten with a <lastmod> per page. It only moves when the
   text a visitor can read on that page changes, never on a run that changed
   nothing visible. A fingerprint of that text is kept as a comment in the
   sitemap, so the next run has something to compare against.

Standard library only, like the rest of scripts/.
"""

import hashlib
import html
import json
import os
import re
from datetime import date
from html.parser import HTMLParser
from zoneinfo import ZoneInfo

SITE_URL = "https://legioenagenda.nl/"

# How many fixtures the phone preview shows. renderPreview() in site.js uses
# the same number.
UPCOMING_COUNT = 5

# The same statuses event_body() in generate_ics.py turns into STATUS:CANCELLED.
CALLED_OFF = ("POSTPONED", "SUSPENDED", "CANCELLED")

# Where every home fixture is played. See render_structured_data().
HOME_GROUND = {
    "@type": "Place",
    "name": "Stadion Feijenoord (De Kuip)",
    "address": {
        "@type": "PostalAddress",
        "streetAddress": "Van Zandvlietplein 1",
        "postalCode": "3077 AA",
        "addressLocality": "Rotterdam",
        "addressCountry": "NL",
    },
}

EVENT_STATUS = {
    "POSTPONED": "https://schema.org/EventPostponed",
    "SUSPENDED": "https://schema.org/EventPostponed",
    "CANCELLED": "https://schema.org/EventCancelled",
}

# Every page the site has, with the address search engines know it by.
PAGES = [
    {"path": "index.html", "url": SITE_URL, "language": "nl"},
    {"path": os.path.join("en", "index.html"), "url": SITE_URL + "en/", "language": "en"},
]

# Kept in step with the text table at the top of assets/site.js.
TEXT = {
    "nl": {
        "days": ["ma", "di", "wo", "do", "vr", "za", "zo"],
        "months": ["jan", "feb", "mrt", "apr", "mei", "jun",
                   "jul", "aug", "sep", "okt", "nov", "dec"],
        "time_unknown": "tijd n.n.b.",
        "cancelled": "uitgesteld",
        "upcoming": "Komende wedstrijden",
        "none_planned": "Nog geen wedstrijden gepland.",
    },
    "en": {
        "days": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
        "months": ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                   "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"],
        "time_unknown": "time TBD",
        "cancelled": "postponed",
        "upcoming": "Upcoming matches",
        "none_planned": "No fixtures scheduled yet.",
    },
}

REGION_PATTERN = re.compile(
    r"<!-- (upcoming[a-z-]*):start -->(.*?)<!-- \1:end -->", re.DOTALL)


# --------------------------------------------------------------------------- #
# Choosing and rendering the fixtures
# --------------------------------------------------------------------------- #

def upcoming_matches(matches: list, today: date, timezone: ZoneInfo) -> list:
    """
    The next few fixtures from today on, in kickoff order.

    The same rule site.js applies in the browser: the kickoff date in Rotterdam
    time is today or later. Called-off fixtures stay in, so a postponement is
    visible. Fixtures without any date cannot be placed and are left out.
    """
    dated = [match for match in matches
             if match.start_utc is not None
             and match.start_utc.astimezone(timezone).date() >= today]

    def kickoff_order(match) -> tuple:
        """All-day fixtures sort before timed ones on the same day, as in site.js."""
        local = match.start_utc.astimezone(timezone)
        clock = local.strftime("%H%M") if match.time_confirmed else ""
        return (local.date(), clock)

    return sorted(dated, key=kickoff_order)[:UPCOMING_COUNT]


def render_range(upcoming: list, language: str, timezone: ZoneInfo) -> str:
    """The small heading above the list, e.g. "okt – dec"."""
    text = TEXT[language]
    if not upcoming:
        return text["upcoming"]
    first = text["months"][upcoming[0].start_utc.astimezone(timezone).month - 1]
    last = text["months"][upcoming[-1].start_utc.astimezone(timezone).month - 1]
    return first if first == last else f"{first} – {last}"


def render_list(upcoming: list, language: str, timezone: ZoneInfo) -> str:
    """The rows of the phone preview, as renderPreview() in site.js builds them."""
    text = TEXT[language]
    indent = "\n            "
    closing = "\n          "
    if not upcoming:
        return f'{indent}<p class="note">{text["none_planned"]}</p>{closing}'

    rows = []
    for match in upcoming:
        local = match.start_utc.astimezone(timezone)
        day = f'{text["days"][local.weekday()]} {local.day} {text["months"][local.month - 1]}'
        if match.is_home:
            name = f"Feyenoord – {match.opponent}"
        else:
            name = f"{match.opponent} – Feyenoord"
        subtitle = match.competition
        classes = "event home" if match.is_home else "event away"
        if match.status in CALLED_OFF:
            classes += " cancelled"
            subtitle += f' · {text["cancelled"]}'
        kickoff = local.strftime("%H:%M") if match.time_confirmed else text["time_unknown"]

        rows.append(f'<div class="day">{html.escape(day)}</div>')
        rows.append(
            f'<div class="{classes}"><i class="bar"></i>'
            f"<div><b>{html.escape(name)}</b><span>{html.escape(subtitle)}</span></div>"
            f"<time>{html.escape(kickoff)}</time></div>")
    return indent + indent.join(rows) + closing


def render_structured_data(upcoming: list, timezone: ZoneInfo) -> str:
    """
    SportsEvent data for the home fixtures the page shows.

    Google only accepts an event with a location that has an address, and
    football-data.org's free tier gives no venue at all. Feyenoord always play
    at home in De Kuip, so home fixtures get that address. Away fixtures are
    left out: their venue is unknown, and an event without one is invalid.
    """
    events = []
    for match in upcoming:
        if not match.is_home:
            continue
        local = match.start_utc.astimezone(timezone)
        event = {
            "@type": "SportsEvent",
            "name": f"{match.home} – {match.away}",
            "sport": "Football",
            "startDate": local.isoformat() if match.time_confirmed else local.date().isoformat(),
            "eventStatus": EVENT_STATUS.get(match.status, "https://schema.org/EventScheduled"),
            "homeTeam": {"@type": "SportsTeam", "name": match.home},
            "awayTeam": {"@type": "SportsTeam", "name": match.away},
            "description": match.competition,
            "location": HOME_GROUND,
        }
        events.append(event)

    if not events:
        return "\n"
    data = json.dumps({"@context": "https://schema.org", "@graph": events},
                      ensure_ascii=False, indent=2)
    # "</" inside a script block would end it early, whatever the JSON says.
    data = data.replace("</", "<\\/")
    return f'\n<script type="application/ld+json">\n{data}\n</script>\n'


def replace_region(page: str, name: str, content: str) -> str:
    """Swap what sits between one pair of marker comments; fail loudly if they are missing."""
    start = f"<!-- {name}:start -->"
    end = f"<!-- {name}:end -->"
    if page.count(start) != 1 or page.count(end) != 1:
        raise ValueError(f"expected exactly one {start} … {end} pair")
    before, rest = page.split(start)
    _, after = rest.split(end)
    return before + start + content + end + after


def extract_regions(page: str) -> str:
    """Every marked region of a page, in order. The tests compare these with the goldens."""
    parts = []
    for name, content in REGION_PATTERN.findall(page):
        parts.append(f"<!-- {name} -->{content}")
    return "\n".join(parts) + "\n"


# --------------------------------------------------------------------------- #
# What counts as a visible change
# --------------------------------------------------------------------------- #

class VisibleText(HTMLParser):
    """Collect the text of <body>, skipping scripts, styles and templates."""

    SKIPPED = {"script", "style", "template"}

    def __init__(self) -> None:
        super().__init__()
        self.in_body = False
        self.skipping = 0
        self.pieces: list[str] = []

    def handle_starttag(self, tag: str, attrs: list) -> None:
        """Note when the body starts and when a skipped element opens."""
        if tag == "body":
            self.in_body = True
        elif tag in self.SKIPPED:
            self.skipping += 1

    def handle_endtag(self, tag: str) -> None:
        """Note when a skipped element closes."""
        if tag in self.SKIPPED and self.skipping:
            self.skipping -= 1

    def handle_data(self, data: str) -> None:
        """Keep text that a visitor can see."""
        if self.in_body and not self.skipping:
            self.pieces.append(data)


def visible_fingerprint(page: str) -> str:
    """
    A short hash of the text a visitor can read.

    Markup, attributes, styling and structured data do not count; only words
    do. Text in hidden blocks counts too, because the visitor can open them.
    """
    parser = VisibleText()
    parser.feed(page)
    parser.close()
    words = " ".join(" ".join(parser.pieces).split())
    return hashlib.sha256(words.encode("utf-8")).hexdigest()[:16]


# --------------------------------------------------------------------------- #
# The sitemap
# --------------------------------------------------------------------------- #

def read_sitemap_state(path: str) -> dict[str, tuple[str, str]]:
    """
    The (lastmod, fingerprint) per page address from the previous sitemap.

    A missing file, or a page without both values, simply counts as changed
    on this run, which gives it today's date.
    """
    try:
        with open(path, encoding="utf-8") as handle:
            sitemap = handle.read()
    except OSError:
        return {}

    state = {}
    for block in re.findall(r"<url>(.*?)</url>", sitemap, re.DOTALL):
        address = re.search(r"<loc>(.*?)</loc>", block)
        lastmod = re.search(r"<lastmod>(.*?)</lastmod>", block)
        fingerprint = re.search(r"<!-- visible-text: ([0-9a-f]+) -->", block)
        if address and lastmod and fingerprint:
            state[address.group(1)] = (lastmod.group(1), fingerprint.group(1))
    return state


def render_sitemap(entries: list[tuple[str, str, str]]) -> str:
    """The whole sitemap: each page with its lastmod, fingerprint and language pairs."""
    alternates = [
        ("nl", SITE_URL),
        ("en", SITE_URL + "en/"),
        ("x-default", SITE_URL),
    ]
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        "<!-- Written by scripts/generate_ics.py. lastmod only moves when the text",
        "     a visitor can read on that page changes; the fingerprint is how it knows. -->",
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"',
        '        xmlns:xhtml="http://www.w3.org/1999/xhtml">',
    ]
    for address, lastmod, fingerprint in entries:
        lines.append("  <url>")
        lines.append(f"    <loc>{address}</loc>")
        lines.append(f"    <lastmod>{lastmod}</lastmod>")
        lines.append(f"    <!-- visible-text: {fingerprint} -->")
        for language, href in alternates:
            lines.append(f'    <xhtml:link rel="alternate" hreflang="{language}" href="{href}"/>')
        lines.append("  </url>")
    lines.append("</urlset>")
    return "\n".join(lines) + "\n"


# --------------------------------------------------------------------------- #
# Putting it together
# --------------------------------------------------------------------------- #

def update_site(matches: list, today: date, timezone: ZoneInfo,
                source_dir: str, out_dir: str) -> str:
    """
    Rewrite both landing pages and the sitemap; return a note for the run log.

    Pages are read from source_dir (the repository root) and written to
    out_dir, which is the same place in the workflow and a temp dir in tests.
    The previous sitemap is read from out_dir, like the previous feed.
    """
    upcoming = upcoming_matches(matches, today, timezone)
    structured_data = render_structured_data(upcoming, timezone)
    sitemap_path = os.path.join(out_dir, "sitemap.xml")
    previous = read_sitemap_state(sitemap_path)

    entries = []
    moved = []
    for page_info in PAGES:
        with open(os.path.join(source_dir, page_info["path"]), encoding="utf-8") as handle:
            page = handle.read()

        language = page_info["language"]
        page = replace_region(page, "upcoming-range", render_range(upcoming, language, timezone))
        page = replace_region(page, "upcoming", render_list(upcoming, language, timezone))
        page = replace_region(page, "upcoming-data", structured_data)

        target = os.path.join(out_dir, page_info["path"])
        os.makedirs(os.path.dirname(target) or ".", exist_ok=True)
        with open(target, "w", encoding="utf-8") as handle:
            handle.write(page)

        fingerprint = visible_fingerprint(page)
        old_lastmod, old_fingerprint = previous.get(page_info["url"], ("", ""))
        if fingerprint == old_fingerprint:
            lastmod = old_lastmod
        else:
            lastmod = today.isoformat()
            moved.append(page_info["path"])
        entries.append((page_info["url"], lastmod, fingerprint))

    with open(sitemap_path, "w", encoding="utf-8") as handle:
        handle.write(render_sitemap(entries))

    changed = ", ".join(moved) if moved else "none"
    return (f"Landing pages: {len(upcoming)} upcoming fixture(s); "
            f"visible text changed on: {changed}.")

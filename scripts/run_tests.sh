#!/usr/bin/env bash
#
# Offline test suite. Needs no API key, so it runs on every push and on forks.
#
#   bash scripts/run_tests.sh            # run the checks
#   bash scripts/run_tests.sh --update   # rewrite the golden files instead
#
# Checks eight things:
#   1. the generator produces exactly the committed golden files
#   2. running it twice produces byte-identical output (stable UIDs, no clock)
#   3. the generated feeds pass the structural validator
#   4. a source-side bulk touch of lastUpdated changes nothing
#   5. a real fixture change bumps that one event's SEQUENCE by exactly 1
#   6. the fixtures written into the landing pages match the golden fragments
#   7. a change nobody can see on the page leaves the sitemap's lastmod alone
#   8. a change a visitor can see moves lastmod to that day
#
set -euo pipefail

cd "$(dirname "$0")/.."

FIXTURES="scripts/test_fixtures.json"
GOLDEN="scripts/expected"
FEEDS=(feyenoord-all.ics feyenoord-home.ics feyenoord-away.ics)

# Every run counts "upcoming" from a fixed date, so the pages do not depend on
# the day the tests run. From 1 August the first five fixtures are listed.
FIRST_DAY="2026-08-01"
NEXT_DAY="2026-08-02"

first=$(mktemp -d)
second=$(mktemp -d)
carried=$(mktemp -d)
venue=$(mktemp -d)
scratch=$(mktemp -d)
trap 'rm -rf "$first" "$second" "$carried" "$venue" "$scratch"' EXIT

# The marked regions of a generated page: the part the generator owns.
regions() {
  python3 - "$1" <<'PY'
import sys
sys.path.insert(0, "scripts")
from landing_page import extract_regions

with open(sys.argv[1], encoding="utf-8") as handle:
    print(extract_regions(handle.read()), end="")
PY
}

# Fails unless both pages in the sitemap of $1 carry lastmod $2.
expect_lastmod() {
  python3 - "$1/sitemap.xml" "$2" <<'PY'
import sys
sys.path.insert(0, "scripts")
from landing_page import read_sitemap_state

state = read_sitemap_state(sys.argv[1])
assert len(state) == 2, f"expected two pages in the sitemap, got {sorted(state)}"
for address, (lastmod, _) in sorted(state.items()):
    assert lastmod == sys.argv[2], f"{address}: lastmod is {lastmod}, expected {sys.argv[2]}"
PY
}

echo "==> Generating (run 1)"
TODAY="$FIRST_DAY" OUTPUT_DIR="$first" FIXTURES_JSON="$FIXTURES" python3 scripts/generate_ics.py

if [ "${1:-}" = "--update" ]; then
  for feed in "${FEEDS[@]}"; do
    cp "$first/$feed" "$GOLDEN/$feed"
  done
  regions "$first/index.html" > "$GOLDEN/upcoming-nl.html"
  regions "$first/en/index.html" > "$GOLDEN/upcoming-en.html"
  echo "Golden files rewritten. Check the diff carefully: it is the only review they get."
  exit 0
fi

echo "==> Generating (run 2)"
TODAY="$FIRST_DAY" OUTPUT_DIR="$second" FIXTURES_JSON="$FIXTURES" python3 scripts/generate_ics.py 2>/dev/null

echo "==> Output must be identical between runs"
# DTSTAMP is derived from the fixture data, never the clock, so two runs a
# moment apart must agree byte for byte. If this fails, the workflow would
# commit on every run forever. This covers the pages and the sitemap too.
diff -r "$first" "$second"
echo "    ok: byte-identical"

echo "==> Output must match the committed golden files"
# This pins every invariant at once: UIDs, SEQUENCE, all-day TBD events,
# CANCELLED handling, line folding and CRLF endings.
for feed in "${FEEDS[@]}"; do
  diff "$GOLDEN/$feed" "$first/$feed"
  echo "    ok: $feed"
done
# Only the regions the generator writes, so a copy edit elsewhere on the page
# does not need new golden files.
diff "$GOLDEN/upcoming-nl.html" <(regions "$first/index.html")
echo "    ok: upcoming fixtures in index.html"
diff "$GOLDEN/upcoming-en.html" <(regions "$first/en/index.html")
echo "    ok: upcoming fixtures in en/index.html"
expect_lastmod "$first" "$FIRST_DAY"
echo "    ok: a first run dates both pages"

echo "==> Feeds must pass the validator"
python3 scripts/validate_ics.py "$first"/feyenoord-*.ics

echo "==> A source-side bulk touch must not change the output"
# football-data.org rewrites lastUpdated for a whole competition on its own
# refresh cycle, whether or not the fixture changed. Deriving DTSTAMP and
# SEQUENCE from it directly rewrote every event twice a day and left
# SEQUENCE saying nothing. Revisions are now carried over from the previous
# output, so this run has to produce the very same bytes. It runs a day later,
# so the sitemap's lastmod staying put is checked here as well.
TODAY="$FIRST_DAY" OUTPUT_DIR="$carried" FIXTURES_JSON="$FIXTURES" python3 scripts/generate_ics.py 2>/dev/null

python3 - "$FIXTURES" "$scratch/touched.json" <<'PY'
import json, sys
from datetime import datetime, timedelta

source, target = sys.argv[1], sys.argv[2]
matches = json.load(open(source))
for match in matches:
    if match.get("last_updated"):
        moved = datetime.fromisoformat(match["last_updated"].replace("Z", "+00:00"))
        match["last_updated"] = (moved + timedelta(hours=10)).strftime("%Y-%m-%dT%H:%M:%SZ")
json.dump(matches, open(target, "w"), indent=2)
PY

TODAY="$NEXT_DAY" OUTPUT_DIR="$carried" FIXTURES_JSON="$scratch/touched.json" python3 scripts/generate_ics.py 2>/dev/null
diff -r "$first" "$carried"
echo "    ok: no change in, no change out"

echo "==> A change nobody can see must not move lastmod"
# The venue is in the feed and in the structured data, but not in the text
# of the page. Search engines are told about visible changes only.
cp -R "$first/." "$venue/"
python3 - "$FIXTURES" "$scratch/venue.json" <<'PY'
import json, sys

source, target = sys.argv[1], sys.argv[2]
matches = json.load(open(source))
for match in matches:
    if match["source_id"] == "500001":
        match["venue"] = "Stadion Feijenoord, Rotterdam"
json.dump(matches, open(target, "w"), indent=2)
PY

TODAY="$NEXT_DAY" OUTPUT_DIR="$venue" FIXTURES_JSON="$scratch/venue.json" python3 scripts/generate_ics.py 2>/dev/null
if diff -q "$first/index.html" "$venue/index.html" >/dev/null; then
  echo "    the venue should have changed the structured data" >&2
  exit 1
fi
expect_lastmod "$venue" "$FIRST_DAY"
echo "    ok: structured data changed, lastmod did not"

echo "==> A real change must bump only that event's SEQUENCE"
python3 - "$FIXTURES" "$scratch/moved.json" <<'PY'
import json, sys
from datetime import datetime, timedelta

source, target = sys.argv[1], sys.argv[2]
matches = json.load(open(source))
for match in matches:
    if match["source_id"] == "500001":
        moved = datetime.fromisoformat(match["start_utc"].replace("Z", "+00:00"))
        match["start_utc"] = (moved + timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
json.dump(matches, open(target, "w"), indent=2)
PY

TODAY="$NEXT_DAY" OUTPUT_DIR="$carried" FIXTURES_JSON="$scratch/moved.json" python3 scripts/generate_ics.py 2>/dev/null

python3 - "$first/feyenoord-all.ics" "$carried/feyenoord-all.ics" <<'PY'
import sys
sys.path.insert(0, "scripts")
from generate_ics import UID_DOMAIN, read_previous_revisions

before = read_previous_revisions(sys.argv[1])
after = read_previous_revisions(sys.argv[2])
assert set(before) == set(after), "the set of events should not have changed"

moved = []
for uid, (revision, body) in sorted(after.items()):
    was_revision, was_body = before[uid]
    if (revision, body) == (was_revision, was_body):
        continue
    moved.append(uid)
    assert body != was_body, f"{uid}: revision moved but the fixture did not"
    assert revision.sequence == was_revision.sequence + 1, (
        f"{uid}: SEQUENCE went {was_revision.sequence} -> {revision.sequence}, expected +1")

expected = [f"fd-500001@{UID_DOMAIN}"]
assert moved == expected, f"expected only {expected} to move, got {moved}"
PY
echo "    ok: one event moved, nine untouched"

echo "==> A change a visitor can see must move lastmod"
# The new kickoff time shows in the list on both pages.
expect_lastmod "$carried" "$NEXT_DAY"
echo "    ok: both pages dated $NEXT_DAY"

echo
echo "All tests passed."

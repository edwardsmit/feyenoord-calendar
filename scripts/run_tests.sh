#!/usr/bin/env bash
#
# Offline test suite. Needs no API key, so it runs on every push and on forks.
#
#   bash scripts/run_tests.sh
#
# Checks five things:
#   1. the generator produces exactly the committed golden files
#   2. running it twice produces byte-identical output (stable UIDs, no clock)
#   3. the generated feeds pass the structural validator
#   4. a source-side bulk touch of lastUpdated changes nothing
#   5. a real fixture change bumps that one event's SEQUENCE by exactly 1
#
set -euo pipefail

cd "$(dirname "$0")/.."

FIXTURES="scripts/test_fixtures.json"
GOLDEN="scripts/expected"
FEEDS=(feyenoord-all.ics feyenoord-home.ics feyenoord-away.ics)

first=$(mktemp -d)
second=$(mktemp -d)
carried=$(mktemp -d)
scratch=$(mktemp -d)
trap 'rm -rf "$first" "$second" "$carried" "$scratch"' EXIT

echo "==> Generating (run 1)"
OUTPUT_DIR="$first"  FIXTURES_JSON="$FIXTURES" python3 scripts/generate_ics.py

echo "==> Generating (run 2)"
OUTPUT_DIR="$second" FIXTURES_JSON="$FIXTURES" python3 scripts/generate_ics.py 2>/dev/null

echo "==> Output must be identical between runs"
# DTSTAMP is derived from the fixture data, never the clock, so two runs a
# moment apart must agree byte for byte. If this fails, the workflow would
# commit on every run forever.
diff -r "$first" "$second"
echo "    ok: byte-identical"

echo "==> Output must match the committed golden files"
# This pins every invariant at once: UIDs, SEQUENCE, all-day TBD events,
# CANCELLED handling, line folding and CRLF endings.
for feed in "${FEEDS[@]}"; do
  diff "$GOLDEN/$feed" "$first/$feed"
  echo "    ok: $feed"
done

echo "==> Feeds must pass the validator"
python3 scripts/validate_ics.py "$first"/feyenoord-*.ics

echo "==> A source-side bulk touch must not change the output"
# football-data.org rewrites lastUpdated for a whole competition on its own
# refresh cycle, whether or not the fixture changed. Deriving DTSTAMP and
# SEQUENCE from it directly rewrote every event twice a day and left
# SEQUENCE saying nothing. Revisions are now carried over from the previous
# output, so this run has to produce the very same bytes.
OUTPUT_DIR="$carried" FIXTURES_JSON="$FIXTURES" python3 scripts/generate_ics.py 2>/dev/null

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

OUTPUT_DIR="$carried" FIXTURES_JSON="$scratch/touched.json" python3 scripts/generate_ics.py 2>/dev/null
diff -r "$first" "$carried"
echo "    ok: no change in, no change out"

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

OUTPUT_DIR="$carried" FIXTURES_JSON="$scratch/moved.json" python3 scripts/generate_ics.py 2>/dev/null

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

echo
echo "All tests passed."

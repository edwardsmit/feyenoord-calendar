#!/usr/bin/env bash
#
# Offline test suite. Needs no API key, so it runs on every push and on forks.
#
#   bash scripts/run_tests.sh
#
# Checks three things:
#   1. the generator produces exactly the committed golden files
#   2. running it twice produces byte-identical output (stable UIDs, no clock)
#   3. the generated feeds pass the structural validator
#
set -euo pipefail

cd "$(dirname "$0")/.."

FIXTURES="scripts/test_fixtures.json"
GOLDEN="scripts/expected"
FEEDS=(feyenoord-all.ics feyenoord-home.ics feyenoord-away.ics)

first=$(mktemp -d)
second=$(mktemp -d)
trap 'rm -rf "$first" "$second"' EXIT

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

echo
echo "All tests passed."

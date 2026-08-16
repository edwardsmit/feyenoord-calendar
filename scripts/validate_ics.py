#!/usr/bin/env python3
"""
Structural validator for the generated .ics feeds.

Runs in CI after generation and exits non-zero on any problem. Standard library
only, so it needs no install step.

Checks:
  - every line ends with CRLF, and no stray CR or LF appears anywhere
  - every line is at most 75 octets, so the folding actually worked
  - BEGIN/END blocks are balanced and properly nested
  - the file is a VCALENDAR with VERSION and PRODID
  - every VEVENT has UID, DTSTAMP, DTSTART and SUMMARY
  - UIDs are unique within a feed
  - DTEND is never before DTSTART
  - if any property references a TZID, a matching VTIMEZONE is present

Usage:
    python3 validate_ics.py feyenoord-all.ics [...]
"""

import re
import sys
from datetime import datetime

MAX_LINE_OCTETS = 75

REQUIRED_EVENT_PROPERTIES = ("UID", "DTSTAMP", "DTSTART", "SUMMARY")


def split_raw_lines(text: str) -> list[str]:
    """Split on CRLF without unfolding, so we can measure real line lengths."""
    lines = text.split("\r\n")
    # A well-formed file ends with CRLF, which leaves one empty trailing piece.
    if lines and lines[-1] == "":
        lines.pop()
    return lines


def unfold(raw_lines: list[str]) -> list[str]:
    """Rejoin folded lines: a leading space or tab continues the line before."""
    unfolded: list[str] = []
    for line in raw_lines:
        if line[:1] in (" ", "\t") and unfolded:
            unfolded[-1] += line[1:]
        else:
            unfolded.append(line)
    return [line for line in unfolded if line != ""]


def property_name(line: str) -> str:
    """The property name of a content line, without any parameters."""
    return line.split(":", 1)[0].split(";", 1)[0]


def parse_ics_datetime(value: str) -> datetime | None:
    """Parse a DTSTART/DTEND value in either DATE or DATE-TIME form."""
    stamp = value.split(":", 1)[-1].strip().rstrip("Z")
    for pattern in ("%Y%m%dT%H%M%S", "%Y%m%d"):
        try:
            return datetime.strptime(stamp, pattern)
        except ValueError:
            continue
    return None


def check_line_endings(path: str, text: str, errors: list[str]) -> None:
    """Every break must be CRLF - not just one of them somewhere in the file."""
    without_crlf = text.replace("\r\n", "")
    if "\n" in without_crlf:
        errors.append(f"{path}: found a bare LF (every line must end with CRLF)")
    if "\r" in without_crlf:
        errors.append(f"{path}: found a bare CR (every line must end with CRLF)")
    if not text.endswith("\r\n"):
        errors.append(f"{path}: file does not end with CRLF")


def check_line_lengths(path: str, raw_lines: list[str], errors: list[str]) -> None:
    """RFC 5545 section 3.1: at most 75 octets per line, including any fold space."""
    for number, line in enumerate(raw_lines, start=1):
        octets = len(line.encode("utf-8"))
        if octets > MAX_LINE_OCTETS:
            errors.append(
                f"{path}: line {number} is {octets} octets "
                f"(max {MAX_LINE_OCTETS}): {line[:40]}...")


def check_nesting(path: str, lines: list[str], errors: list[str]) -> None:
    """BEGIN and END must pair up and nest correctly."""
    stack: list[str] = []
    for line in lines:
        if line.startswith("BEGIN:"):
            stack.append(line.split(":", 1)[1])
        elif line.startswith("END:"):
            block = line.split(":", 1)[1]
            if not stack:
                errors.append(f"{path}: END:{block} without a matching BEGIN")
            elif stack[-1] != block:
                errors.append(
                    f"{path}: END:{block} closes BEGIN:{stack[-1]}")
                stack.pop()
            else:
                stack.pop()
    for unclosed in stack:
        errors.append(f"{path}: BEGIN:{unclosed} was never closed")


def check_timezone_references(path: str, lines: list[str], errors: list[str]) -> None:
    """Any TZID a property points at must be defined by a VTIMEZONE in the file."""
    defined = {line.split(":", 1)[1] for line in lines if line.startswith("TZID:")}
    for line in lines:
        for referenced in re.findall(r"TZID=([^:;]+)", line):
            if referenced not in defined:
                errors.append(
                    f"{path}: TZID={referenced} is used but no VTIMEZONE defines it")


def check_events(path: str, lines: list[str], errors: list[str]) -> int:
    """Check each VEVENT's required properties, UID uniqueness and DTEND order."""
    in_event = False
    event: dict[str, str] = {}
    seen_uids: set[str] = set()
    event_count = 0

    for line in lines:
        if line == "BEGIN:VEVENT":
            in_event, event = True, {}
            event_count += 1
        elif line == "END:VEVENT":
            for required in REQUIRED_EVENT_PROPERTIES:
                if required not in event:
                    errors.append(f"{path}: VEVENT missing {required}")

            uid = event.get("UID", "")
            if uid:
                if uid in seen_uids:
                    errors.append(f"{path}: duplicate UID {uid}")
                seen_uids.add(uid)

            starts = parse_ics_datetime(event.get("DTSTART", ""))
            ends = parse_ics_datetime(event.get("DTEND", ""))
            if starts and ends and ends < starts:
                errors.append(f"{path}: DTEND is before DTSTART in {uid or 'a VEVENT'}")

            in_event = False
        elif in_event:
            event[property_name(line)] = line

    print(f"{path}: {event_count} events, {len(seen_uids)} unique UIDs")
    return event_count


def validate(path: str) -> list[str]:
    """Run every check against one file and return the problems found."""
    errors: list[str] = []
    # newline="" keeps the CRLFs intact so we can check them.
    with open(path, "r", encoding="utf-8", newline="") as handle:
        text = handle.read()

    check_line_endings(path, text, errors)

    raw_lines = split_raw_lines(text)
    check_line_lengths(path, raw_lines, errors)

    lines = unfold(raw_lines)
    if not lines or lines[0] != "BEGIN:VCALENDAR":
        errors.append(f"{path}: missing BEGIN:VCALENDAR")
    if not lines or lines[-1] != "END:VCALENDAR":
        errors.append(f"{path}: missing END:VCALENDAR")
    if not any(line.startswith("VERSION:2.0") for line in lines):
        errors.append(f"{path}: missing VERSION:2.0")
    if not any(line.startswith("PRODID:") for line in lines):
        errors.append(f"{path}: missing PRODID")

    check_nesting(path, lines, errors)
    check_timezone_references(path, lines, errors)
    check_events(path, lines, errors)
    return errors


def main() -> None:
    paths = sys.argv[1:]
    if not paths:
        print("usage: validate_ics.py <file.ics> [...]", file=sys.stderr)
        sys.exit(1)

    all_errors: list[str] = []
    for path in paths:
        all_errors += validate(path)

    if all_errors:
        print("\nVALIDATION FAILED:", file=sys.stderr)
        for error in all_errors:
            print(f"  - {error}", file=sys.stderr)
        sys.exit(1)
    print("\nAll feeds valid.")


if __name__ == "__main__":
    main()

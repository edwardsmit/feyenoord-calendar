# Tasks

## Move the site to legioenagenda.nl
Status: open · Opened: 2026-10-27

Chosen over `010agenda.nl` (that one reads as a city-wide agenda) and kept free of the club
name for trademark reasons. On 2026-10-27, SIDN listed it as unregistered.

- [x] Check the Benelux trademark register (boip.int). "Legioen" is held by Grolsch, in
      class 32 (beer) only, so a calendar service does not conflict with it. Keep beer and
      drinks brands out of any sponsor slot, because that would be the same class. "Feyenoord"
      belongs to the club and stays out of the domain. "Feijenoord" is not registered on its own.
- [ ] Register `legioenagenda.nl`
- [ ] DNS: apex A/AAAA records to GitHub Pages, `www` CNAME to `edwardsmit.github.io`
- [ ] PR: add a `CNAME` file and update the canonical, `hreflang` and fallback feed URLs in
      `index.html`, `en/index.html`, `README.md` and `CLAUDE.md`
- [ ] Turn on "Enforce HTTPS" in the Pages settings
- [ ] Check `curl -I` on the old `github.io` `.ics` URLs: each should return a 301 to the new host

## Verify that all open work in this repo is captured in this TASKS.md
Status: done · Opened: 2026-09-17

Verify that all open work in this repo is captured in this TASKS.md and that all other
traces of work- and goal-tracking in this repo get removed and hoisted into TASKS.md.

- [x] Confirm no other traces remain

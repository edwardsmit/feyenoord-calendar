# Tasks

## Register the site with Google Search Console
Status: open · Opened: 2026-10-27

The SEO change adds `robots.txt`, `sitemap.xml`, share images and structured data. Google
only picks the site up quickly once it is registered.

- [ ] Add a **Domain** property for `legioenagenda.nl` and verify it with the TXT record
      Google gives (Namecheap → Advanced DNS)
- [ ] Submit `https://legioenagenda.nl/sitemap.xml`
- [ ] Run both pages through the Rich Results Test (`WebSite` data should be detected)
- [ ] Check the share preview of both pages, e.g. by pasting the link into WhatsApp

## Move the site to legioenagenda.nl
Status: open · Opened: 2026-10-27

Chosen over `010agenda.nl` (that one reads as a city-wide agenda) and kept free of the club
name for trademark reasons. On 2026-10-27, SIDN listed it as unregistered.

- [x] Check the Benelux trademark register (boip.int). "Legioen" is held by Grolsch, in
      class 32 (beer) only, so a calendar service does not conflict with it. Keep beer and
      drinks brands out of any sponsor slot, because that would be the same class. "Feyenoord"
      belongs to the club and stays out of the domain. "Feijenoord" is not registered on its own.
- [x] Register `legioenagenda.nl` (Namecheap, 2026-10-27)
- [x] DNS: apex A/AAAA records to GitHub Pages, `www` CNAME to `edwardsmit.github.io`,
      verification TXT. All checked against Namecheap's nameservers.
- [x] PR: add a `CNAME` file and update the canonical, `hreflang` and fallback feed URLs in
      `index.html`, `en/index.html`, `README.md` and `CLAUDE.md`
- [x] Wait for the .nl zone to publish the delegation (resolved 2026-10-27 07:52 UTC)
- [x] Turn on "Enforce HTTPS" in the Pages settings (Let's Encrypt, valid until 2027-01-25)
- [x] Check `curl -I` on the old `github.io` `.ics` URLs: each returns a 301 to the new host
- [x] iPhone subscription on the old `edwardsmit.github.io` URL refreshes without errors
      and keeps its events (2026-10-27)
- [ ] Confirm that iPhone picks up the next real feed change through the redirect. iOS shows
      no refresh timestamp, so only a change proves it. The first likely change: kickoff times
      for Feyenoord – NEC (13 Feb), Feyenoord – Telstar (20 Feb) and Ajax – Feyenoord (27 Feb),
      currently all-day "kickoff time TBD" events. A new KNVB Beker round works too.

## Verify that all open work in this repo is captured in this TASKS.md
Status: done · Opened: 2026-09-17

Verify that all open work in this repo is captured in this TASKS.md and that all other
traces of work- and goal-tracking in this repo get removed and hoisted into TASKS.md.

- [x] Confirm no other traces remain

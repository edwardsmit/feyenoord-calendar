# Feyenoord fixtures — calendar feeds

Free, auto-updating calendar subscriptions for **Feyenoord Rotterdam**. Add one to your
phone or laptop and every fixture shows up in your normal calendar, with the kickoff time
already in `Europe/Rotterdam`. When a match is moved, your existing entry moves with it —
you never get a duplicate.

Three feeds, pick whichever suits you:

| Feed | Subscribe link |
| --- | --- |
| **All matches** | `https://edwardsmit.github.io/feyenoord-calendar/feyenoord-all.ics` |
| **Home games only** | `https://edwardsmit.github.io/feyenoord-calendar/feyenoord-home.ics` |
| **Away games only** | `https://edwardsmit.github.io/feyenoord-calendar/feyenoord-away.ics` |

There is also a [landing page with one-tap buttons](https://edwardsmit.github.io/feyenoord-calendar/).

## Adding it to your calendar

> **Subscribe, don't download.** Opening an `.ics` file in your browser *imports* a
> one-time snapshot that never updates again. Use the steps below instead — they create a
> live subscription.

### iPhone / iPad

1. Settings → **Apps** → **Calendar** → **Accounts** → **Add Account** → **Other**
2. **Add Subscribed Calendar**
3. Paste the link and tap **Next**, then **Save**

Or simply tap a **Subscribe** button on the landing page, which does all of that for you.

### Mac (Apple Calendar)

1. **File** → **New Calendar Subscription…**
2. Paste the link, click **Subscribe**
3. Set *Auto-refresh* to **Every day** (the default is sometimes "No")

### Google Calendar

1. Open Google Calendar on a computer — this cannot be done in the mobile app
2. Left sidebar → **Other calendars** → **+** → **From URL**
3. Paste the **`https://`** link (Google does not accept `webcal://` links)

Google refreshes external calendars on its own schedule, usually somewhere between 8 and 24
hours, and ignores how often the feed says it changes. A new fixture can take a day to
appear. Apple Calendar is much quicker.

### Outlook

1. **Add calendar** → **Subscribe from web**
2. Paste the link, give it a name, click **Import**

## What's in the feeds

| Competition | Included |
| --- | --- |
| Eredivisie | Yes |
| UEFA Champions League | Yes |
| KNVB Beker | Yes, once each round is drawn |

- Every kickoff is in **`Europe/Rotterdam`** (CET in winter, CEST in summer), so the times
  are correct wherever your device happens to be.
- Titles read like `Feyenoord vs Ajax (Eredivisie)`, with the stadium as the location.
- A fixture whose kickoff time isn't settled yet appears as an **all-day event** marked
  *kickoff time TBD*, and turns into a normal timed event once the time is confirmed.
- Postponed or cancelled matches stay in your calendar, marked `[POSTPONED]` or
  `[CANCELLED]`, rather than silently vanishing.
- Matches are marked *free*, not *busy*, so they don't block meeting invitations.
- The feeds are rebuilt twice a day.

Cup rounds only appear once the draw has been made, so the KNVB Beker may be missing from
the feed early in the season. That's expected, not a fault.

## Data and attribution

The MIT licence in [LICENSE](LICENSE) covers the code in this repository only. It does not
cover the underlying fixture data.

Football data provided by the Football-Data.org API. KNVB Beker fixtures via ESPN.

Unofficial fan project. Not affiliated with, endorsed by, or connected to Feyenoord
Rotterdam, the KNVB, the Eredivisie, or UEFA.

---

<sub>Built with [Claude Code](https://claude.com/claude-code).</sub>

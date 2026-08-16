# Feyenoord programma — agenda-abonnementen

Gratis agenda-abonnementen voor **Feyenoord Rotterdam**, die zichzelf bijhouden. Voeg er één
toe op je telefoon of laptop en elke wedstrijd staat gewoon in je agenda, op Rotterdamse tijd.
Wordt een wedstrijd verzet, dan schuift je bestaande afspraak mee — je krijgt er nooit een
dubbele bij.

Drie feeds, kies wat je wilt:

| Feed | Abonnementslink |
| --- | --- |
| **Alle wedstrijden** | `https://edwardsmit.github.io/feyenoord-calendar/feyenoord-all.ics` |
| **Alleen thuis** | `https://edwardsmit.github.io/feyenoord-calendar/feyenoord-home.ics` |
| **Alleen uit** | `https://edwardsmit.github.io/feyenoord-calendar/feyenoord-away.ics` |

Er is ook een [pagina met knoppen om direct te abonneren](https://edwardsmit.github.io/feyenoord-calendar/).

## Toevoegen aan je agenda

> **Abonneren, niet downloaden.** Een `.ics`-bestand openen in je browser *importeert* een
> momentopname die daarna nooit meer bijwerkt. Gebruik de stappen hieronder; die maken een
> live abonnement aan.

### iPhone / iPad

1. Instellingen → **Apps** → **Agenda** → **Accounts** → **Voeg account toe** → **Anders**
2. **Voeg geabonneerde agenda toe**
3. Plak de link, tik op **Volgende** en daarna op **Bewaar**

Of tik gewoon op een **Abonneer**-knop op de webpagina; die doet dit allemaal voor je.

### Mac (Agenda)

1. **Archief** → **Nieuw agenda-abonnement…**
2. Plak de link en klik op **Abonneer**
3. Zet *Ververs* op **Elke dag** (standaard staat dat soms op "Nooit")

### Google Agenda

1. Open Google Agenda op een computer — in de mobiele app kan dit niet
2. Linkerkolom → **Andere agenda's** → **+** → **Via URL**
3. Plak de **`https://`**-link (Google accepteert geen `webcal://`-links)

Google ververst externe agenda's op zijn eigen tempo, meestal ergens tussen de 8 en 24 uur,
en negeert hoe vaak de feed zelf aangeeft te veranderen. Een nieuwe wedstrijd kan dus een dag
op zich laten wachten. Apple Agenda is een stuk sneller.

### Outlook

1. **Agenda toevoegen** → **Abonneren via internet**
2. Plak de link, geef het een naam en klik op **Importeren**

## Wat er in de feeds zit

| Competitie | Aanwezig |
| --- | --- |
| Eredivisie | Ja |
| UEFA Champions League | Ja |
| KNVB Beker | Ja, zodra de ronde geloot is |

- Alle tijden zijn Rotterdamse tijd. Zomer- en wintertijd gaan vanzelf goed, en de tijden
  kloppen ook als je toestel in het buitenland staat.
- Titels zien eruit als `Feyenoord vs Sparta Rotterdam (Eredivisie)`, met het stadion als
  locatie.
- Staat de aftraptijd nog niet vast, dan verschijnt de wedstrijd als **hele dag**-afspraak met
  de melding *kickoff time TBD*, en wordt het een gewone afspraak zodra de tijd bekend is.
- Uitgestelde of afgelaste wedstrijden blijven in je agenda staan, gemarkeerd met
  `[POSTPONED]` of `[CANCELLED]`, in plaats van stilletjes te verdwijnen.
- Wedstrijden staan op *vrij* en niet op *bezet*, zodat ze geen vergaderverzoeken blokkeren.
- De feeds worden twee keer per dag opnieuw opgebouwd.

Bekerrondes verschijnen pas nadat er geloot is, dus vroeg in het seizoen kan de KNVB Beker nog
ontbreken. Dat hoort zo en is geen storing.

## Gegevens en bronvermelding

De MIT-licentie in [LICENSE](LICENSE) geldt alleen voor de code in deze repository, niet voor
de onderliggende wedstrijdgegevens.

Football data provided by the Football-Data.org API. KNVB Beker-wedstrijden via ESPN.

Onofficieel supportersproject. Niet verbonden aan, goedgekeurd door of gelieerd met Feyenoord
Rotterdam, de KNVB, de Eredivisie of de UEFA.

---

# English

Free, auto-updating calendar subscriptions for **Feyenoord Rotterdam**. Add one to your phone
or laptop and every fixture shows up in your normal calendar, on Rotterdam time. When a match
is moved, your existing entry moves with it — you never get a duplicate.

| Feed | Subscribe link |
| --- | --- |
| **All matches** | `https://edwardsmit.github.io/feyenoord-calendar/feyenoord-all.ics` |
| **Home games only** | `https://edwardsmit.github.io/feyenoord-calendar/feyenoord-home.ics` |
| **Away games only** | `https://edwardsmit.github.io/feyenoord-calendar/feyenoord-away.ics` |

There is also a [landing page with one-tap buttons](https://edwardsmit.github.io/feyenoord-calendar/).

## Adding it to your calendar

> **Subscribe, don't download.** Opening an `.ics` file in your browser *imports* a one-time
> snapshot that never updates again. Use the steps below instead — they create a live
> subscription.

**iPhone / iPad:** Settings → **Apps** → **Calendar** → **Accounts** → **Add Account** →
**Other** → **Add Subscribed Calendar**, then paste the link. Or tap a **Subscribe** button on
the landing page.

**Mac (Apple Calendar):** **File** → **New Calendar Subscription…**, paste the link, then set
*Auto-refresh* to **Every day** (the default is sometimes "No").

**Google Calendar:** on a computer only — **Other calendars** → **+** → **From URL**, and
paste the **`https://`** link. Google does not accept `webcal://`, and refreshes external
calendars on its own schedule, usually every 8 to 24 hours.

**Outlook:** **Add calendar** → **Subscribe from web**, paste the link, click **Import**.

## What's in the feeds

Eredivisie and UEFA Champions League in full; KNVB Beker once each round has been drawn.

- All times are Rotterdam time. Summer and winter time are handled for you, and the times are
  still right if your device is abroad.
- Titles read like `Feyenoord vs Sparta Rotterdam (Eredivisie)`, with the stadium as the
  location.
- A fixture whose kickoff time isn't settled yet appears as an **all-day event** marked
  *kickoff time TBD*, and becomes a normal timed event once confirmed.
- Postponed or cancelled matches stay in your calendar, marked `[POSTPONED]` or
  `[CANCELLED]`, rather than silently vanishing.
- Matches are marked *free*, not *busy*, so they don't block meeting invitations.
- The feeds are rebuilt twice a day.

## Data and attribution

The MIT licence in [LICENSE](LICENSE) covers the code in this repository only. It does not
cover the underlying fixture data.

Football data provided by the Football-Data.org API. KNVB Beker fixtures via ESPN.

Unofficial fan project. Not affiliated with, endorsed by, or connected to Feyenoord Rotterdam,
the KNVB, the Eredivisie, or UEFA.

---

<sub>Gemaakt met [Claude Code](https://claude.com/claude-code).</sub>

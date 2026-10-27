// Landing page behaviour: the colour choice, the device tabs, copy buttons,
// feed links that follow the current host, and the phone preview, which is
// filled from the published feyenoord-all.ics.
(function () {
  var language = document.documentElement.lang === 'en' ? 'en' : 'nl';
  var text = {
    nl: {
      days: ['zo', 'ma', 'di', 'wo', 'do', 'vr', 'za'],
      months: ['jan', 'feb', 'mrt', 'apr', 'mei', 'jun', 'jul', 'aug', 'sep', 'okt', 'nov', 'dec'],
      timeUnknown: 'tijd n.n.b.',
      cancelled: 'uitgesteld',
      copied: 'Gekopieerd',
      copyFailed: 'Selecteer de link',
      loadFailed: 'Het programma kon niet worden geladen.'
    },
    en: {
      days: ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'],
      months: ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'],
      timeUnknown: 'time TBD',
      cancelled: 'postponed',
      copied: 'Copied',
      copyFailed: 'Select the link',
      loadFailed: 'The fixtures could not be loaded.'
    }
  }[language];

  // The feeds sit next to the Dutch page, one level up from the English one.
  var feedBase = new URL(document.body.dataset.feedBase || './', location.href);

  /** Point every subscribe link and copy button at the host the page is served from. */
  function rewriteFeedLinks() {
    if (location.protocol !== 'https:' && location.protocol !== 'http:') {
      return;
    }
    document.querySelectorAll('[data-feed]').forEach(function (element) {
      var feedUrl = new URL(element.dataset.feed, feedBase);
      if (element.tagName === 'A') {
        element.href = 'webcal://' + feedUrl.host + feedUrl.pathname;
      } else if (element.tagName === 'CODE') {
        element.textContent = feedUrl.href;
      } else {
        element.dataset.copy = feedUrl.href;
      }
    });
  }

  /** Step 1: "home and away apart" or "everything in one". */
  function setUpChoice() {
    var options = document.querySelectorAll('[data-option]');
    var preview = document.querySelector('[data-view]');
    function pick(view) {
      options.forEach(function (option) {
        option.setAttribute('aria-pressed', String(option.dataset.option === view));
      });
      document.querySelectorAll('[data-result]').forEach(function (block) {
        block.hidden = block.dataset.result !== view;
      });
      preview.dataset.view = view;
    }
    options.forEach(function (option) {
      option.addEventListener('click', function () { pick(option.dataset.option); });
    });
    pick('two');
  }

  /** Guess the visitor's calendar from the user agent; the other tabs stay one tap away. */
  function guessDevice() {
    var agent = navigator.userAgent || '';
    if (/Android/.test(agent)) return 'google';
    if (/iPhone|iPad|iPod|Macintosh/.test(agent)) return 'apple';
    if (/Windows/.test(agent)) return 'outlook';
    return 'apple';
  }

  /** Step 2: one tab per kind of calendar app. */
  function setUpTabs() {
    var tabs = document.querySelectorAll('[data-tab]');
    function show(name) {
      tabs.forEach(function (tab) {
        tab.setAttribute('aria-selected', String(tab.dataset.tab === name));
      });
      document.querySelectorAll('[data-panel]').forEach(function (panel) {
        panel.hidden = panel.dataset.panel !== name;
      });
    }
    tabs.forEach(function (tab) {
      tab.addEventListener('click', function () { show(tab.dataset.tab); });
    });
    show(guessDevice());
  }

  /** Copy buttons, with a short confirmation in the button itself. */
  function setUpCopyButtons() {
    document.querySelectorAll('[data-copy]').forEach(function (button) {
      var label = button.textContent;
      function flash(message) {
        button.textContent = message;
        setTimeout(function () { button.textContent = label; }, 1800);
      }
      button.addEventListener('click', function () {
        if (!navigator.clipboard) {
          flash(text.copyFailed);
          return;
        }
        navigator.clipboard.writeText(button.dataset.copy).then(
          function () { flash(text.copied); },
          function () { flash(text.copyFailed); }
        );
      });
    });
  }

  /** Turn the raw .ics text into a list of events with the fields the preview needs. */
  function parseCalendar(source) {
    // Undo RFC 5545 line folding: a line starting with a space continues the previous one.
    var lines = source.replace(/\r\n[ \t]/g, '').split(/\r\n|\n/);
    var events = [];
    var current = null;
    lines.forEach(function (line) {
      if (line === 'BEGIN:VEVENT') {
        current = {};
      } else if (line === 'END:VEVENT') {
        events.push(current);
        current = null;
      } else if (current) {
        var colon = line.indexOf(':');
        var name = line.slice(0, colon).split(';')[0];
        var value = line.slice(colon + 1).replace(/\\([,;\\])/g, '$1').replace(/\\n/gi, ' ');
        current[name] = value;
        if (name === 'DTSTART') {
          current.allDay = line.slice(0, colon).indexOf('VALUE=DATE') !== -1;
        }
      }
    });
    return events;
  }

  /** Build the preview rows for the next few fixtures. */
  function renderPreview(events) {
    var list = document.querySelector('[data-events]');
    var today = new Date();
    var todayKey = String(today.getFullYear()) +
      String(today.getMonth() + 1).padStart(2, '0') +
      String(today.getDate()).padStart(2, '0');

    var upcoming = events
      .filter(function (event) { return event.DTSTART && event.DTSTART.slice(0, 8) >= todayKey; })
      .sort(function (a, b) { return a.DTSTART < b.DTSTART ? -1 : 1; })
      .slice(0, 5);

    list.textContent = '';
    upcoming.forEach(function (event) {
      // DESCRIPTION reads like "Eredivisie - Away match vs PSV".
      var details = /^(.*) - (Home|Away) match vs (.*)$/.exec(event.DESCRIPTION || '');
      if (!details) {
        return;
      }
      var competition = details[1];
      var isHome = details[2] === 'Home';
      var opponent = details[3];
      var stamp = event.DTSTART;
      var date = new Date(+stamp.slice(0, 4), +stamp.slice(4, 6) - 1, +stamp.slice(6, 8));

      var day = document.createElement('div');
      day.className = 'day';
      day.textContent = text.days[date.getDay()] + ' ' + date.getDate() + ' ' + text.months[date.getMonth()];

      var row = document.createElement('div');
      row.className = 'event ' + (isHome ? 'home' : 'away');
      if (event.STATUS === 'CANCELLED') {
        row.className += ' cancelled';
      }
      var bar = document.createElement('i');
      bar.className = 'bar';
      var title = document.createElement('div');
      var name = document.createElement('b');
      name.textContent = isHome ? 'Feyenoord – ' + opponent : opponent + ' – Feyenoord';
      var subtitle = document.createElement('span');
      subtitle.textContent = event.STATUS === 'CANCELLED' ? competition + ' · ' + text.cancelled : competition;
      title.append(name, subtitle);
      var time = document.createElement('time');
      time.textContent = event.allDay ? text.timeUnknown : stamp.slice(9, 11) + ':' + stamp.slice(11, 13);
      row.append(bar, title, time);

      list.append(day, row);
    });

    var range = document.querySelector('[data-range]');
    if (upcoming.length && range) {
      var first = upcoming[0].DTSTART;
      var last = upcoming[upcoming.length - 1].DTSTART;
      var firstMonth = text.months[+first.slice(4, 6) - 1];
      var lastMonth = text.months[+last.slice(4, 6) - 1];
      range.textContent = firstMonth === lastMonth ? firstMonth : firstMonth + ' – ' + lastMonth;
    }
  }

  function loadPreview() {
    fetch(new URL('feyenoord-all.ics', feedBase), { cache: 'no-cache' })
      .then(function (response) {
        if (!response.ok) throw new Error('HTTP ' + response.status);
        return response.text();
      })
      .then(function (source) { renderPreview(parseCalendar(source)); })
      .catch(function () {
        var list = document.querySelector('[data-events]');
        list.textContent = '';
        var message = document.createElement('p');
        message.className = 'note';
        message.style.padding = '12px 6px';
        message.textContent = text.loadFailed;
        list.append(message);
      });
  }

  /**
   * Visitors without JavaScript see every option at once. With it, the options
   * not chosen start hidden; setUpChoice() and setUpTabs() show the right ones.
   */
  function takeOverVisibility() {
    document.querySelectorAll('[data-start-hidden]').forEach(function (element) {
      element.hidden = true;
      element.removeAttribute('data-start-hidden');
    });
  }

  takeOverVisibility();
  rewriteFeedLinks();
  setUpChoice();
  setUpTabs();
  setUpCopyButtons();
  loadPreview();
})();

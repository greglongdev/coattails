/* Gonka Capital. Reads feed.json (bundled as feed.js), checks for a newer copy online,
   and renders three screens. No framework, no build step. */
(function () {
  "use strict";

  var REMOTE_FEED = "https://raw.githubusercontent.com/greglongdev/gonka-capital/main/data/feed.json";
  var CACHE_KEY = "gonka.feed.v1";

  var state = {
    feed: null,
    filter: "all",
    people: {},
    source: "bundled"
  };

  var $view = document.getElementById("view");
  var $title = document.getElementById("title");
  var $updated = document.getElementById("updated");
  var $sheet = document.getElementById("sheet");
  var $sheetBody = document.getElementById("sheet-body");

  // ------------------------------------------------------------------ data

  function useFeed(feed, source) {
    state.feed = feed;
    state.source = source;
    state.people = {};
    feed.people.forEach(function (p) { state.people[p.id] = p; });
    renderUpdated();
  }

  function loadInitial() {
    var bundled = window.GONKA_FEED || null;
    var cached = null;
    try {
      var raw = localStorage.getItem(CACHE_KEY);
      if (raw) cached = JSON.parse(raw);
    } catch (e) { cached = null; }
    if (cached && (!bundled || cached.generated_at > bundled.generated_at)) {
      useFeed(cached, "cached");
    } else if (bundled) {
      useFeed(bundled, "bundled");
    }
  }

  function checkForUpdate() {
    if (!window.fetch) return;
    fetch(REMOTE_FEED, { cache: "no-store" })
      .then(function (r) { if (!r.ok) throw new Error("http " + r.status); return r.json(); })
      .then(function (feed) {
        if (!feed || feed.schema !== 1 || !feed.people) throw new Error("bad feed");
        if (!state.feed || feed.generated_at > state.feed.generated_at) {
          try { localStorage.setItem(CACHE_KEY, JSON.stringify(feed)); } catch (e) { /* storage full: still use it this session */ }
          useFeed(feed, "live");
          route();
        } else {
          renderUpdated();
        }
      })
      .catch(function () { renderUpdated(); });
  }

  function renderUpdated() {
    if (!state.feed) { $updated.textContent = ""; return; }
    $updated.textContent = "Updated " + fmtDate(state.feed.generated_at.slice(0, 10));
    $updated.className = "updated" + (state.source === "live" ? " live" : "");
  }

  // --------------------------------------------------------------- helpers

  var fmtDate = CF.fmtDate, compactDollars = CF.compactDollars, compactRange = CF.compactRange,
      fmtShares = CF.fmtShares, esc = CF.esc, initials = CF.initials, optionLabel = CF.optionLabel,
      actionPill = CF.actionPill, ownerNote = CF.ownerNote, shortName = CF.shortName;

  function personShort(p) { return p.name; }

  // --------------------------------------------------------------- render

  function eventCard(ev, opts) {
    opts = opts || {};
    var p = state.people[ev.person];
    var pill = actionPill(ev);
    var tick = ev.ticker ? esc(ev.ticker) : esc(shortName(ev.name));
    var tickCls = ev.ticker ? "ticker" : "ticker small";
    var name = ev.ticker ? esc(ev.name) : "";
    var opt = optionLabel(ev);
    if (opt) name = opt + (name ? " on " + name : "");
    if (ev.type === "quarter" && ev.put_call) name = ev.put_call + " options on " + esc(ev.name);
    var right = ev.type === "trade" ? compactRange(ev.amount) : (ev.action === "sold" ? "" : compactDollars(ev.value));
    var who;
    if (ev.type === "trade") {
      who = "<b>" + esc(personShort(p)) + "</b>" + esc(ownerNote(ev)) + " · traded " + fmtDate(ev.date) + ", reported " + fmtDate(ev.disclosed);
    } else {
      who = "<b>" + esc(personShort(p)) + "</b> · quarter ended " + fmtDate(ev.period) + ", filed " + fmtDate(ev.date);
    }
    if (opts.hideWho) who = ev.type === "trade"
      ? "Traded " + fmtDate(ev.date) + esc(ownerNote(ev))
      : "Quarter ended " + fmtDate(ev.period) + ", filed " + fmtDate(ev.date);
    return '<button class="card" data-ev="' + esc(opts.key) + '">' +
      '<div class="row"><span class="' + tickCls + '">' + tick + '</span><span class="pill ' + pill.cls + '">' + esc(pill.text) + "</span></div>" +
      '<div class="row"><span class="name">' + name + '</span><span class="amount">' + esc(right) + "</span></div>" +
      '<div class="who">' + who + "</div></button>";
  }

  function groupByDay(events, keyFn, hideWho) {
    var html = "", last = null;
    events.forEach(function (ev, i) {
      var day = ev.type === "trade" ? ev.disclosed : ev.date;
      if (day !== last) {
        html += '<div class="day">Reported ' + fmtDate(day, true) + "</div>";
        last = day;
      }
      html += eventCard(ev, { key: keyFn(ev, i), hideWho: !!hideWho });
    });
    return html;
  }

  function renderLatest() {
    $title.textContent = "Latest";
    if (!state.feed) { $view.innerHTML = '<div class="empty">No data yet.</div>'; return; }
    var f = state.filter;
    var events = state.feed.feed.filter(function (ev) {
      var p = state.people[ev.person];
      if (!p) return false;
      if (f === "politicians") return p.group === "politician";
      if (f === "pros") return p.group === "investor";
      return true;
    });
    var shown = events.slice(0, 300);
    var html = '<div class="seg">' +
      seg("all", "Everyone") + seg("politicians", "Politicians") + seg("pros", "Investors") + "</div>";
    if (!shown.length) html += '<div class="empty">Nothing here yet.</div>';
    else html += groupByDay(shown, function (ev) { return "feed:" + state.feed.feed.indexOf(ev); });
    if (events.length > shown.length) html += '<div class="note" style="text-align:center">Showing the latest ' + shown.length + " of " + events.length + ". Open a person for their full history.</div>";
    $view.innerHTML = html;
    window.scrollTo(0, 0);
  }

  function seg(id, label) {
    return '<button data-filter="' + id + '"' + (state.filter === id ? ' class="on"' : "") + ">" + label + "</button>";
  }

  function renderPeople() {
    $title.textContent = "People";
    if (!state.feed) { $view.innerHTML = '<div class="empty">No data yet.</div>'; return; }
    var pols = state.feed.people.filter(function (p) { return p.group === "politician"; });
    var pros = state.feed.people.filter(function (p) { return p.group === "investor"; });
    var html = '<div class="section-title">Investors</div>' + pros.map(personRow).join("") +
      '<div class="section-title">Politicians</div>' + pols.map(personRow).join("");
    $view.innerHTML = html;
    window.scrollTo(0, 0);
  }

  function personRow(p) {
    var sub;
    if (p.group === "politician") {
      var n = p.trades.length;
      sub = p.title + " · " + n + (n === 1 ? " trade" : " trades") + (p.active ? "" : " · left office");
    } else {
      var q = p.quarters[p.quarters.length - 1];
      sub = p.firm + " · " + q.positions + " positions · " + compactDollars(q.total_value);
    }
    return '<a class="card person" href="#person/' + esc(p.id) + '">' +
      '<span class="avatar ' + (p.group === "politician" ? "pol" : "") + '">' + esc(initials(p.name)) + "</span>" +
      '<span class="txt"><div class="n">' + esc(p.name) + '</div><div class="s">' + esc(sub) + "</div></span>" +
      '<span class="chev">&rsaquo;</span></a>';
  }

  function renderPerson(id) {
    var p = state.people[id];
    if (!p) { location.hash = "#people"; return; }
    $title.textContent = p.group === "politician" ? "Politician" : "Investor";
    var html = '<a class="back" href="#people">&lsaquo; All people</a>';
    if (p.group === "politician") {
      html += '<div class="hero"><div class="n">' + esc(p.name) + '</div><div class="s">' + esc(p.title) +
        (p.active ? "" : " · no longer in office") + '</div><div class="why">' + esc(p.why) + "</div></div>";
      if (p.unreadable_filings) {
        html += '<div class="note">' + p.unreadable_filings + " of this member's " + p.filings + " reports were filed on paper and cannot be read by the app.</div>";
      }
      if (!p.trades.length) html += '<div class="empty">No stock trades reported since ' + fmtDate("2025-01-01", true) + ".</div>";
      else {
        var evs = p.trades.map(function (t) { var e = Object.assign({ type: "trade", person: p.id }, t); return e; });
        html += '<div class="section-title">Trades, newest first</div>';
        html += groupByDay(evs, function (ev, i) { return "person:" + p.id + ":" + i; }, true);
      }
    } else {
      var q = p.quarters[p.quarters.length - 1];
      var prev = p.quarters.length > 1 ? p.quarters[p.quarters.length - 2] : null;
      html += '<div class="hero"><div class="n">' + esc(p.name) + '</div><div class="s">' + esc(p.firm) +
        '</div><div class="why">' + esc(p.why) + "</div></div>";
      html += '<div class="note">Portfolio as of ' + fmtDate(q.period, true) + ", filed with the SEC " + fmtDate(q.filed, true) +
        ". " + q.positions + " positions worth " + compactDollars(q.total_value) + ".</div>";
      if (p.changes.length) {
        html += '<div class="section-title">Changes since ' + (prev ? fmtDate(prev.period, true) : "last quarter") + "</div>";
        html += p.changes.map(function (c, i) {
          var ev = Object.assign({ type: "quarter", person: p.id, date: q.filed, period: q.period, source: q.source }, c);
          ev.action = c.kind;
          return eventCard(ev, { key: "change:" + p.id + ":" + i, hideWho: true });
        }).join("");
      }
      html += '<div class="section-title">All holdings, largest first</div>';
      html += p.holdings.map(function (h) {
        var label = h.ticker ? esc(h.ticker) : esc(h.name);
        var sub = h.ticker ? esc(h.name) : "";
        if (h.put_call) sub = h.put_call + " options" + (sub ? " on " + sub : "");
        return '<div class="holding"><div><span class="ticker small">' + label + '</span><div class="name">' + sub + "</div></div>" +
          '<div style="text-align:right"><div class="w">' + h.weight.toFixed(1) + '%</div><div class="name">' + compactDollars(h.value) + "</div></div>" +
          '<div class="bar"><i style="width:' + Math.max(1, Math.min(100, h.weight)) + '%"></i></div></div>';
      }).join("");
      html += '<a class="btn secondary" href="' + esc(q.source) + '" target="_blank" rel="noopener">See the SEC filing</a>';
    }
    $view.innerHTML = html;
    window.scrollTo(0, 0);
  }

  function renderAbout() {
    $title.textContent = "About";
    var f = state.feed;
    var pols = f ? f.people.filter(function (p) { return p.group === "politician"; }).length : 0;
    var pros = f ? f.people.filter(function (p) { return p.group === "investor"; }).length : 0;
    $view.innerHTML = '<div class="prose">' +
      "<p>Gonka Capital shows what " + pros + " well-known investors and " + pols + " members of Congress have been buying and selling, taken straight from the public filings they are required to make.</p>" +
      "<h2>Where the numbers come from</h2>" +
      "<ul>" +
      "<li><b>Members of Congress</b> must report every stock trade within 45 days under the STOCK Act. The House posts these reports on the Clerk's website; the Senate posts them on its own filing site. Trades are reported in dollar ranges, not exact amounts, and many are made by a spouse or in a joint account. The app says which.</li>" +
      "<li><b>Investors</b> managing more than $100 million file a list of their US stock holdings with the SEC every quarter, within 45 days of quarter end (Form 13F). The app compares each new list with the previous one to show what changed. Only US-listed long positions appear; these filings do not include shorts, bonds or foreign-listed shares.</li>" +
      "</ul>" +
      "<h2>What that means for you</h2>" +
      "<p>Everything here is at least a few weeks old by the time it is public, and up to a quarter old for the investors. A purchase you see is a record of what someone did, not a recommendation. The people on the list were chosen because their trades are verifiable and large enough to mean something, not because following them is guaranteed to work.</p>" +
      "<p>Bonds, municipal securities, private funds and similar holdings are left out so the list stays about stocks, ETFs and options.</p>" +
      "<h2>Updates</h2>" +
      "<p>The app carries a copy of the data and checks for a newer one each time it opens. Every entry has a link to the original filing so you can read it yourself.</p>" +
      (f ? "<p>Data updated " + fmtDate(f.generated_at.slice(0, 10), true) + ".</p>" : "") +
      "<p>Gonka Capital is not investment advice.</p>" +
      "</div>";
    window.scrollTo(0, 0);
  }

  // ------------------------------------------------------------- sheet

  function findEvent(key) {
    var parts = key.split(":");
    if (parts[0] === "feed") return state.feed.feed[parseInt(parts[1], 10)];
    var p = state.people[parts[1]];
    var i = parseInt(parts[2], 10);
    if (parts[0] === "person") return Object.assign({ type: "trade", person: p.id }, p.trades[i]);
    if (parts[0] === "change") {
      var q = p.quarters[p.quarters.length - 1];
      var ev = Object.assign({ type: "quarter", person: p.id, date: q.filed, period: q.period, source: q.source }, p.changes[i]);
      ev.action = p.changes[i].kind;
      return ev;
    }
    return null;
  }

  function openSheet(ev) {
    var p = state.people[ev.person];
    var pill = actionPill(ev);
    var opt = optionLabel(ev);
    var name = esc(ev.name);
    if (opt) name = opt + " on " + name;
    if (ev.type === "quarter" && ev.put_call) name = ev.put_call + " options on " + name;
    var kv = [];
    if (ev.type === "trade") {
      kv.push(["Who", esc(p.title || p.name)]);
      kv.push(["Account", esc(ev.owner)]);
      kv.push(["Traded on", fmtDate(ev.date, true)]);
      kv.push(["Reported on", fmtDate(ev.disclosed, true)]);
      kv.push(["Amount", esc(ev.amount)]);
      if (ev.detail) kv.push(["Details", esc(ev.detail)]);
    } else {
      kv.push(["Who", esc(p.name) + ", " + esc(p.firm)]);
      kv.push(["Quarter ended", fmtDate(ev.period, true)]);
      kv.push(["Filed on", fmtDate(ev.date, true)]);
      if (ev.action === "sold") {
        kv.push(["Shares before", fmtShares(ev.prev_shares)]);
        kv.push(["Shares now", "0"]);
      } else {
        if (ev.prev_shares) kv.push(["Shares before", fmtShares(ev.prev_shares)]);
        kv.push(["Shares now", fmtShares(ev.shares)]);
        kv.push(["Position value", compactDollars(ev.value)]);
      }
    }
    $sheetBody.innerHTML =
      '<div class="row"><span class="ticker">' + (ev.ticker ? esc(ev.ticker) : "") + '</span><span class="pill ' + pill.cls + '">' + esc(pill.text) + "</span></div>" +
      '<div class="name">' + name + "</div>" +
      '<dl class="kv">' + kv.map(function (r) { return "<dt>" + r[0] + "</dt><dd>" + r[1] + "</dd>"; }).join("") + "</dl>" +
      '<a class="btn" href="' + esc(ev.source) + '" target="_blank" rel="noopener">See the filing</a>' +
      '<a class="btn secondary" href="#person/' + esc(p.id) + '" data-close>More from ' + esc(p.name) + "</a>" +
      (ev.type === "trade" ? '<div class="note">Amounts are the ranges required by the STOCK Act, not exact figures.</div>' :
        '<div class="note">From the quarterly 13F filing. Positions can be as much as 45 days old on the day they are published.</div>');
    $sheet.hidden = false;
    document.body.style.overflow = "hidden";
  }

  function closeSheet() {
    $sheet.hidden = true;
    document.body.style.overflow = "";
  }

  // ------------------------------------------------------------- routing

  function route() {
    var h = location.hash || "#latest";
    closeSheet();
    var tab = h.split("/")[0].slice(1);
    document.querySelectorAll(".tab").forEach(function (t) {
      t.classList.toggle("on", t.dataset.tab === tab || (tab === "person" && t.dataset.tab === "people"));
    });
    if (h.indexOf("#person/") === 0) renderPerson(h.slice(8));
    else if (h === "#people") renderPeople();
    else if (h === "#about") renderAbout();
    else renderLatest();
  }

  document.addEventListener("click", function (e) {
    var t = e.target;
    var card = t.closest && t.closest("[data-ev]");
    if (card) { var ev = findEvent(card.dataset.ev); if (ev) openSheet(ev); return; }
    var fb = t.closest && t.closest("[data-filter]");
    if (fb) { state.filter = fb.dataset.filter; renderLatest(); return; }
    if (t.closest && t.closest("[data-close]")) { closeSheet(); }
  });

  window.addEventListener("hashchange", route);
  window.addEventListener("keydown", function (e) { if (e.key === "Escape") closeSheet(); });

  loadInitial();
  route();
  checkForUpdate();
})();

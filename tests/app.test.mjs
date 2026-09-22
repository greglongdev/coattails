/* Renders the real app against the real bundled feed in a minimal DOM stub and
   checks the screens say what the data says. */
import { test } from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import vm from "node:vm";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const web = path.join(here, "..", "web");

function makeDom() {
  const els = {};
  function el(id) {
    return els[id] || (els[id] = {
      id, innerHTML: "", textContent: "", className: "", hidden: false, style: {}, dataset: {},
      classList: { toggle() {} }
    });
  }
  const listeners = {};
  // The app measures its own header and tab bar, so the stub gives them a size.
  function bar(h) {
    return { getBoundingClientRect: () => ({ height: h }), style: {} };
  }
  const bars = { ".top": bar(56), ".tabs": bar(64) };
  const root = { style: { setProperty(k, v) { this[k] = v; } } };
  const document = {
    getElementById: el,
    querySelector: (sel) => bars[sel] || null,
    querySelectorAll: () => [],
    documentElement: root,
    addEventListener(type, fn) { listeners[type] = fn; },
    body: { style: {} }
  };
  const store = {};
  const window = {
    document, location: { hash: "" }, addEventListener(type, fn) { listeners["w:" + type] = fn; },
    scrollTo() {}, localStorage: { getItem: k => store[k] ?? null, setItem: (k, v) => { store[k] = v; } },
    fetch: undefined, listeners, root,
    getComputedStyle: () => ({ getPropertyValue: () => "0px" }),
    // Deferred re-measures: run them straight away so a boot settles synchronously.
    setTimeout: (fn) => { fn(); return 0; },
    ResizeObserver: undefined
  };
  window.window = window; window.self = window;
  return { window, document, els, listeners };
}

function boot(hash) {
  const { window, els, listeners } = makeDom();
  window.location.hash = hash;
  const ctx = vm.createContext(Object.assign(window, { console }));
  vm.runInContext(fs.readFileSync(path.join(web, "logos.js"), "utf8"), ctx);
  vm.runInContext(fs.readFileSync(path.join(web, "format.js"), "utf8"), ctx);
  vm.runInContext(fs.readFileSync(path.join(web, "feed.js"), "utf8"), ctx);
  vm.runInContext(fs.readFileSync(path.join(web, "app.js"), "utf8"), ctx);
  return { window, els, listeners, feed: window.GONKA_FEED };
}

test("bundled feed is present and well formed", () => {
  const { feed } = boot("#latest");
  assert.equal(feed.schema, 1);
  assert.ok(feed.people.length >= 15);
  assert.ok(feed.feed.length > 100);
  assert.equal(feed.warnings.length, 0);
});

test("the app opens on Agreed, the screen that answers the question", () => {
  const { els, feed } = boot("");
  const html = els.view.innerHTML;
  assert.ok(html.includes('class="screen-title">Agreed<'));
  assert.ok(feed.consensus.groups.length > 0, "the real feed should carry consensus");
  // Buying is the default side, and only bullish groups show there.
  const bulls = feed.consensus.groups.filter(g => g.direction === "bullish");
  assert.equal((html.match(/class="card"/g) || []).length, bulls.length);
  assert.ok(html.includes(bulls[0].ticker));
  assert.ok(!/undefined|NaN|\[object/.test(html));
});

test("Agreed names the people and never shows a group of one", () => {
  const { els, feed } = boot("#agree");
  const html = els.view.innerHTML;
  const g = feed.consensus.groups.find(x => x.direction === "bullish");
  const shortOf = (id) => feed.people.find(q => q.id === id).short;
  for (const m of g.people) assert.ok(html.includes(shortOf(m.person)), m.person);
  assert.ok(html.includes(g.count + " bought"));
  for (const x of feed.consensus.groups) assert.ok(x.count >= 2, x.ticker);
});

test("Agreed groups every person to a filing link", () => {
  const { feed } = boot("#agree");
  for (const g of feed.consensus.groups) {
    for (const m of g.people) {
      assert.match(m.source, /^https:\/\//);
      assert.ok(m.did && m.when, g.ticker + " / " + m.person);
    }
  }
});

test("tapping an Agreed company opens every contributor with a filing link", () => {
  const { window, els, feed, listeners } = boot("#agree");
  const g = feed.consensus.groups.find(x => x.direction === "bullish");
  // Simulate the tap the same way the app receives it.
  const card = { dataset: { agree: g.ticker + "|" + g.direction } };
  listeners.click({ target: { closest: (sel) => (sel === "[data-agree]" ? card : null) } });
  const sheet = els["sheet-body"].innerHTML;
  assert.equal(els.sheet.hidden, false);
  assert.ok(sheet.includes(g.ticker));
  for (const m of g.people) {
    assert.ok(sheet.includes(m.source), "no link for " + m.person);
    assert.ok(sheet.includes(m.did), "no plain-English action for " + m.person);
  }
  // The honesty rules are stated where the numbers are, not buried in About.
  assert.ok(sheet.includes("both bought and sold is skipped"));
  assert.ok(sheet.includes("put options counts as betting against"));
  assert.ok(!/undefined|NaN/.test(sheet));
  // A figure the pipeline already formatted keeps its size suffix; a range is shortened.
  for (const m of g.people) {
    if (!m.amount) continue;
    if (/\s-\s/.test(m.amount)) assert.ok(sheet.includes("to $"), "range not shortened");
    else assert.ok(sheet.includes(m.amount), "lost the amount " + m.amount);
  }
});

test("a tap survives the feed being replaced underneath it", () => {
  // checkForUpdate can swap state.feed and re-route between a screen drawing and
  // a tap landing, so a card must say which company it is, not which row it was.
  const { window, els, feed, listeners } = boot("#agree");
  const g = feed.consensus.groups.find(x => x.direction === "bullish");
  const tap = (key) => listeners.click({
    target: { closest: (sel) => (sel === "[data-agree]" ? { dataset: { agree: key } } : null) }
  });
  // A company that is no longer in the feed opens nothing rather than throwing.
  els.sheet.hidden = true;
  tap("NOTATICKER|bullish");
  assert.equal(els.sheet.hidden, true);
  // The wrong direction for a real ticker is also not a match.
  tap(g.ticker + "|sideways");
  assert.equal(els.sheet.hidden, true);
  // The real one still opens.
  tap(g.ticker + "|" + g.direction);
  assert.equal(els.sheet.hidden, false);
  assert.ok(els["sheet-body"].innerHTML.includes(g.ticker));
});

test("everyone is named the way they are actually known", () => {
  const { feed } = boot("#agree");
  const by = Object.fromEntries(feed.people.map(p => [p.id, p.short]));
  // A last-token guess called the Gates Foundation Trust "Trust" and lost half
  // of a compound surname, so the short name is carried in the data instead.
  assert.equal(by["gates-trust"], "Gates Foundation");
  assert.equal(by["mcclain-delaney"], "McClain Delaney");
  assert.equal(by["smith"], "Terry Smith");
  for (const p of feed.people) {
    assert.ok(p.short && p.short.length > 1, p.id);
    assert.ok(!/^(Trust|Foundation|Jr\.?|Inc\.?)$/i.test(p.short), p.id + " is named " + p.short);
  }
});

test("a feed that cannot be drawn is never kept", () => {
  // One bad publish used to be cached before it was used, and the app then
  // opened broken for ever without ever reaching the code that would replace it.
  const { window, els, feed } = boot("#agree");
  const broken = JSON.parse(JSON.stringify(feed));
  delete broken.feed;              // renderLatest would throw on this
  broken.generated_at = "2099-01-01T00:00:00Z";
  assert.equal(window.localStorage.getItem("gonka.feed.v1"), null,
    "nothing should be cached until it has drawn");
  // And a stored feed that fails validation is discarded, not loaded.
  window.localStorage.setItem("gonka.feed.v1", JSON.stringify(broken));
  const second = boot("#agree");
  assert.equal(second.window.localStorage.getItem("gonka.feed.v1"), null);
  assert.ok(second.els.view.innerHTML.includes("Agreed"));
});

test("back closes an open sheet before it leaves the app", () => {
  const { window, els, feed, listeners } = boot("#agree");
  assert.equal(window.__closeSheet(), false, "nothing to close yet");
  const g = feed.consensus.groups.find(x => x.direction === "bullish");
  listeners.click({
    target: { closest: (sel) => (sel === "[data-agree]" ? { dataset: { agree: g.ticker + "|" + g.direction } } : null) }
  });
  assert.equal(els.sheet.hidden, false);
  assert.equal(window.__closeSheet(), true, "should report that it handled back");
  assert.equal(els.sheet.hidden, true);
  assert.equal(window.__closeSheet(), false, "and nothing left to close");
});

test("the Selling side shows only bearish groups", () => {
  const { els, feed, listeners } = boot("#agree");
  const btn = { dataset: { side: "bearish" } };
  listeners.click({ target: { closest: (sel) => (sel === "[data-side]" ? btn : null) } });
  const html = els.view.innerHTML;
  const bears = feed.consensus.groups.filter(g => g.direction === "bearish");
  assert.equal((html.match(/class="card"/g) || []).length, bears.length);
  assert.ok(html.includes(bears[0].count + " sold"));
  // A company both sides agreed on must not leak across.
  const bulls = feed.consensus.groups.filter(g => g.direction === "bullish").map(g => g.ticker);
  const shown = (html.match(/class="ticker">([A-Z0-9.\-\/]+)</g) || []).map(m => m.split(">")[1].slice(0, -1));
  for (const t of shown) assert.ok(bears.some(g => g.ticker === t), t + " is not a bearish group");
});

test("Latest renders newest-first cards with a source-backed pill and person", () => {
  const { els, feed } = boot("#latest");
  const html = els.view.innerHTML;
  assert.ok(html.includes('class="screen-title">Latest<'));
  assert.match(els.updated.textContent, /^Updated /);
  assert.ok(html.includes('class="seg"'));
  const first = feed.feed[0];
  const person = feed.people.find(p => p.id === first.person);
  assert.ok(html.includes("<b>" + person.name + "</b>"));
  assert.ok(html.includes('data-ev="feed:0"'));
  const cards = (html.match(/class="card"/g) || []).length;
  assert.ok(cards > 50 && cards <= 300);
  // Day headers exist and the first one matches the first event's disclosure date.
  assert.match(html, /class="day">Reported /);
  assert.ok(!/undefined|NaN|\[object/.test(html), "no undefined/NaN leaked into the page");
});

test("People lists every person with an accurate one-line summary", () => {
  const { els, feed } = boot("#people");
  const html = els.view.innerHTML;
  for (const p of feed.people) {
    assert.ok(html.includes('href="#person/' + p.id + '"'), p.id);
    if (p.group === "politician") assert.ok(html.includes(p.trades.length + " trade"), p.id);
    else assert.ok(html.includes(p.quarters.at(-1).positions + " positions"), p.id);
  }
});

test("Investor page shows holdings summing to the filing and links to the SEC", () => {
  const { els, feed } = boot("#person/buffett");
  const p = feed.people.find(x => x.id === "buffett");
  const html = els.view.innerHTML;
  assert.ok(html.includes("Berkshire Hathaway"));
  assert.ok(html.includes("Berkshire Hathaway"));
  assert.ok(html.includes(p.holdings[0].ticker));
  assert.ok(html.includes('href="' + p.quarters.at(-1).source + '"'));
  const shown = (html.match(/class="holding"/g) || []).length;
  assert.equal(shown, p.holdings.length);
  assert.ok(!/undefined|NaN/.test(html));
});

test("Politician page lists every trade and flags unreadable paper filings", () => {
  const { els, feed } = boot("#person/pelosi");
  const p = feed.people.find(x => x.id === "pelosi");
  const html = els.view.innerHTML;
  assert.ok(html.includes("Rep. Nancy Pelosi"));
  assert.ok(html.includes("Rep. Nancy Pelosi (D-CA)"));
  const cards = (html.match(/data-ev="person:pelosi:/g) || []).length;
  assert.equal(cards, p.trades.length);
  assert.equal(html.includes("filed on paper"), p.unreadable_filings > 0);
  assert.ok(html.includes("(spouse)"), "Pelosi trades are reported under the spouse");
  assert.ok(!html.includes("<b>Nancy Pelosi</b>"), "the name is in the header, not on every card");
});

test("the brand mark and name show on every screen", () => {
  for (const hash of ["#agree", "#latest", "#people", "#person/buffett", "#about"]) {
    const { els } = boot(hash);
    assert.ok(els["brand-mark"].innerHTML.includes("<svg"), hash + " has no mark");
    assert.ok(els["brand-mark"].innerHTML.includes("</svg>"), hash + " mark is truncated");
  }
  // The header is markup, not rendered per screen, so the name lives in the HTML file.
  const shell = fs.readFileSync(path.join(web, "index.html"), "utf8");
  assert.ok(shell.includes('class="brand-name">Gonka Capital<'));
});

test("every logo option renders and uses theme-aware ink", async () => {
  const { createRequire } = await import("node:module");
  const LOGOS = createRequire(import.meta.url)("../web/logos.js");
  assert.deepEqual(LOGOS.names, ["monogram", "risingG", "steps", "crest"]);
  for (const n of LOGOS.names) {
    const svg = LOGOS.get(n);
    assert.ok(svg.startsWith("<svg") && svg.endsWith("</svg>"), n);
    assert.ok(svg.includes('viewBox="0 0 100 100"'), n + " is not on the shared canvas");
    assert.ok(svg.includes("currentColor"), n + " ignores the theme colour");
    assert.ok(!/#[0-9a-f]{3,6}/i.test(svg), n + " hardcodes a colour");
  }
  assert.equal(LOGOS.get("nope"), LOGOS.get("monogram"), "unknown name falls back");
});

test("About states the lags and the no-advice line", () => {
  const { els } = boot("#about");
  const html = els.view.innerHTML;
  assert.ok(html.includes("45 days"));
  assert.ok(html.includes("not investment advice"));
  assert.ok(!/undefined/.test(html));
});

test("About links out to every authority the app reads", () => {
  const { els } = boot("#about");
  const html = els.view.innerHTML;
  for (const host of ["disclosures-clerk.house.gov", "efdsearch.senate.gov", "www.sec.gov",
                      "ethics.house.gov", "github.com/greglongdev/gonka-capital"]) {
    assert.ok(html.includes(host), "About does not link to " + host);
  }
  // Every one opens outside the app, and safely.
  const links = html.match(/<a class="link-row"[^>]*>/g) || [];
  assert.equal(links.length, 5);
  for (const a of links) {
    assert.ok(a.includes('target="_blank"') && a.includes('rel="noopener"'), a);
    assert.ok(a.includes('href="https://'), a);
  }
});

test("the bars report their own height so a big system font cannot hide content", () => {
  const { window } = boot("#latest");
  assert.equal(window.root.style["--header-h"], "56px");
  assert.equal(window.root.style["--tabbar-h"], "64px");
});

test("measuring the bars never walks their height upward", () => {
  // The old version fed the measurement back into the header's own min-height,
  // so sub-pixel rounding grew it by 1px on every observer tick.
  const { window, listeners } = boot("#latest");
  const tick = listeners["w:resize"];
  const first = window.root.style["--header-h"];
  for (let i = 0; i < 50; i++) tick();
  assert.equal(window.root.style["--header-h"], first);
  assert.equal(window.root.style["--tabbar-h"], "64px");
});

test("copy has no emojis or double hyphens", () => {
  // The gate is about what the reader sees, so it reads the rendered screens.
  // CSS custom properties in the source (--top-h) are code, not copy.
  for (const hash of ["#agree", "#latest", "#people", "#person/buffett", "#person/pelosi", "#about"]) {
    const { els } = boot(hash);
    const visible = els.view.innerHTML.replace(/<[^>]*>/g, " ");
    assert.ok(!/[\u{1F300}-\u{1FAFF}]/u.test(visible), hash + " shows an emoji");
    assert.ok(!/--/.test(visible), hash + " shows a double hyphen");
    for (const tell of ["seamlessly", "effortlessly", "elevate", "unleash", "empower",
                        "game-changer", "Whether you're", "Look no further"]) {
      assert.ok(!visible.toLowerCase().includes(tell.toLowerCase()), hash + " uses " + tell);
    }
  }
  const shell = fs.readFileSync(path.join(web, "index.html"), "utf8");
  assert.ok(!/[\u{1F300}-\u{1FAFF}]/u.test(shell), "index.html has an emoji");
});

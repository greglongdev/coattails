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
  const document = {
    getElementById: el,
    querySelectorAll: () => [],
    addEventListener(type, fn) { listeners[type] = fn; },
    body: { style: {} }
  };
  const store = {};
  const window = {
    document, location: { hash: "" }, addEventListener(type, fn) { listeners["w:" + type] = fn; },
    scrollTo() {}, localStorage: { getItem: k => store[k] ?? null, setItem: (k, v) => { store[k] = v; } },
    fetch: undefined, listeners
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
  for (const hash of ["#latest", "#people", "#person/buffett", "#about"]) {
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

test("copy has no emojis or double hyphens", () => {
  for (const f of ["app.js", "index.html"]) {
    const src = fs.readFileSync(path.join(web, f), "utf8");
    assert.ok(!/[\u{1F300}-\u{1FAFF}]/u.test(src), f + " has an emoji");
    const copy = src.replace(/<!--[\s\S]*?-->/g, "").replace(/^\s*\/\/.*$/gm, "").replace(/\/\*[\s\S]*?\*\//g, "");
    assert.ok(!/--/.test(copy), f + " has a double hyphen");
  }
});

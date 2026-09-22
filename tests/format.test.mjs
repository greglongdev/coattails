import { test } from "node:test";
import assert from "node:assert/strict";
import { createRequire } from "node:module";
const require = createRequire(import.meta.url);
const CF = require("../web/format.js");

const now = new Date("2026-09-22T12:00:00Z");

test("dates read like a person wrote them", () => {
  assert.equal(CF.fmtDate("2026-08-21", false, now), "Aug 21");
  assert.equal(CF.fmtDate("2026-08-21", true, now), "Aug 21, 2026");
  assert.equal(CF.fmtDate("2025-12-05", false, now), "Dec 5, 2025");
  assert.equal(CF.fmtDate("", false, now), "");
});

test("compact dollars", () => {
  assert.equal(CF.compactDollars(299253556246), "$299B");
  assert.equal(CF.compactDollars(28157599351), "$28.2B");
  assert.equal(CF.compactDollars(1500000), "$1.5M");
  assert.equal(CF.compactDollars(1000000), "$1M");
  assert.equal(CF.compactDollars(15000), "$15K");
  assert.equal(CF.compactDollars(950), "$950");
});

test("STOCK Act ranges collapse to round numbers", () => {
  assert.equal(CF.compactRange("$1,000,001 - $5,000,000"), "$1M to $5M");
  assert.equal(CF.compactRange("$1,001 - $15,000"), "$1K to $15K");
  assert.equal(CF.compactRange("$250,001 - $500,000"), "$250K to $500K");
  assert.equal(CF.compactRange("$5,000,001 - $25,000,000"), "$5M to $25M");
  assert.equal(CF.compactRange("Spouse/DC Over $1,000,000"), "Over $1M");
  assert.equal(CF.compactRange("Over $50,000,000"), "Over $50M");
  assert.equal(CF.compactRange("$15.00"), "$15.00");
  assert.equal(CF.compactRange(""), "");
});

test("pills say what happened in plain words", () => {
  assert.deepEqual(CF.actionPill({ type: "trade", action: "buy" }), { cls: "buy", text: "Bought" });
  assert.deepEqual(CF.actionPill({ type: "trade", action: "sell" }), { cls: "sell", text: "Sold" });
  assert.deepEqual(CF.actionPill({ type: "trade", action: "exchange" }), { cls: "", text: "Exchanged" });
  assert.deepEqual(CF.actionPill({ type: "quarter", action: "new" }), { cls: "buy", text: "New position" });
  assert.deepEqual(CF.actionPill({ type: "quarter", action: "added", pct: 45.2 }), { cls: "buy", text: "Added 45%" });
  assert.deepEqual(CF.actionPill({ type: "quarter", action: "reduced", pct: -25.2 }), { cls: "sell", text: "Cut 25%" });
  assert.deepEqual(CF.actionPill({ type: "quarter", action: "sold" }), { cls: "sell", text: "Sold out" });
});

test("options and account owners are called out", () => {
  assert.equal(CF.optionLabel({ kind: "option", detail: "Purchased 100 call options with a strike price of $100" }), "Call options");
  assert.equal(CF.optionLabel({ kind: "option", name: "Ark Innovation ETF Option Type: Put Strike price: $45.00" }), "Put options");
  assert.equal(CF.optionLabel({ kind: "option", name: "x" }), "Options");
  assert.equal(CF.optionLabel({ kind: "stock" }), null);
  assert.equal(CF.ownerNote({ type: "trade", owner: "Spouse" }), " (spouse)");
  assert.equal(CF.ownerNote({ type: "trade", owner: "Joint" }), " (joint account)");
  assert.equal(CF.ownerNote({ type: "trade", owner: "Dependent child" }), " (child's account)");
  assert.equal(CF.ownerNote({ type: "trade", owner: "Self" }), "");
  assert.equal(CF.ownerNote({ type: "quarter" }), "");
});

test("names, initials, escaping", () => {
  assert.equal(CF.initials("Nancy Pelosi"), "NP");
  assert.equal(CF.initials("Gates Foundation Trust"), "GT");
  assert.equal(CF.shortName("GS Managed Structured Note Strategy S&P 500 - Common Stock"), "GS Managed Structured Note Strategy S&P");
  assert.equal(CF.shortName("Alphabet Inc. - Class A Common Stock"), "Alphabet Inc.");
  assert.equal(CF.esc('<b>"x" & \'y\'</b>'), "&lt;b&gt;&quot;x&quot; &amp; &#39;y&#39;&lt;/b&gt;");
  assert.equal(CF.fmtShares(78791167), "78,791,167");
});

/* Pure formatting helpers shared by the app and its tests. */
(function (root, factory) {
  if (typeof module === "object" && module.exports) module.exports = factory();
  else root.CF = factory();
})(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  var MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

  function fmtDate(iso, withYear, now) {
    if (!iso) return "";
    var thisYear = String((now || new Date()).getFullYear());
    var y = iso.slice(0, 4), m = parseInt(iso.slice(5, 7), 10), d = parseInt(iso.slice(8, 10), 10);
    var s = MONTHS[m - 1] + " " + d;
    if (withYear || y !== thisYear) s += ", " + y;
    return s;
  }

  function trim(x) {
    var s = x >= 100 ? Math.round(x).toString() : x >= 10 ? x.toFixed(1) : x.toFixed(2);
    return s.replace(/\.0+$/, "").replace(/(\.\d)0$/, "$1");
  }

  function compactDollars(n) {
    if (n >= 1e9) return "$" + trim(n / 1e9) + "B";
    if (n >= 1e6) return "$" + trim(n / 1e6) + "M";
    if (n >= 1e3) return "$" + trim(n / 1e3) + "K";
    return "$" + n;
  }

  // "$1,000,001 - $5,000,000" -> "$1M to $5M". STOCK Act ranges start at x,001,
  // which reads as the round number it stands for.
  function compactRange(amount) {
    if (!amount) return "";
    var nums = amount.match(/\$[\d,]+(?:\.\d+)?/g);
    if (!nums) return amount;
    var vals = nums.map(function (s) { return parseFloat(s.replace(/[$,]/g, "")); });
    if (/Over/.test(amount) && vals.length === 1) return "Over " + compactDollars(vals[0]);
    if (vals.length === 1) return nums[0];
    var lo = vals[0] % 1000 === 1 ? vals[0] - 1 : vals[0];
    return compactDollars(lo) + " to " + compactDollars(vals[1]);
  }

  function initials(name) {
    var parts = name.replace(/[^A-Za-z ]/g, "").split(" ").filter(Boolean);
    return (parts[0] ? parts[0][0] : "") + (parts.length > 1 ? parts[parts.length - 1][0] : "");
  }

  function optionLabel(ev) {
    if (ev.kind !== "option") return null;
    var text = (ev.detail || "") + " " + (ev.name || "");
    if (/\bput\b/i.test(text)) return "Put options";
    if (/\bcall\b/i.test(text)) return "Call options";
    return "Options";
  }

  function actionPill(ev) {
    if (ev.type === "trade") {
      if (ev.action === "buy") return { cls: "buy", text: "Bought" };
      if (ev.action === "sell") return { cls: "sell", text: "Sold" };
      return { cls: "", text: "Exchanged" };
    }
    if (ev.action === "new") return { cls: "buy", text: "New position" };
    if (ev.action === "added") return { cls: "buy", text: "Added " + Math.round(ev.pct) + "%" };
    if (ev.action === "reduced") return { cls: "sell", text: "Cut " + Math.abs(Math.round(ev.pct)) + "%" };
    return { cls: "sell", text: "Sold out" };
  }

  function ownerNote(ev) {
    if (ev.type !== "trade") return "";
    var o = (ev.owner || "").toLowerCase();
    if (o === "spouse") return " (spouse)";
    if (o === "joint") return " (joint account)";
    if (o === "dependent child" || o === "child") return " (child's account)";
    return "";
  }

  function shortName(name) {
    return (name || "").replace(/\s*-\s*(Common Stock|Class [A-Z].*|Ordinary Shares).*$/i, "").slice(0, 40).trim();
  }

  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }

  return {
    fmtDate: fmtDate, compactDollars: compactDollars, compactRange: compactRange, initials: initials,
    optionLabel: optionLabel, actionPill: actionPill, ownerNote: ownerNote, shortName: shortName, esc: esc,
    fmtShares: function (n) { return Number(n).toLocaleString("en-US"); }
  };
});

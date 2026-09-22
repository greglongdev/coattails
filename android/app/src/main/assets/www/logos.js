/* Gonka Capital logo marks.

   Each mark draws inside a 100x100 box, uses currentColor for the ink so it works
   in both themes, and stays legible at 28px in the header and at 108dp as the
   launcher icon. Pick one with MARK in app.js. */
(function (root, factory) {
  if (typeof module === "object" && module.exports) module.exports = factory();
  else root.LOGOS = factory();
})(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  var MARKS = {
    // A: the monogram. A quiet, old-fashioned firm.
    monogram:
      '<svg viewBox="0 0 100 100" aria-hidden="true" class="mark">' +
      '<rect x="4" y="4" width="92" height="92" rx="22" fill="currentColor"/>' +
      '<text x="50" y="50" text-anchor="middle" dominant-baseline="central" ' +
      'font-family="Georgia, \'Times New Roman\', serif" font-size="46" font-weight="700" ' +
      'letter-spacing="-1" fill="var(--mark-ink)">GC</text>' +
      "</svg>",

    // B: the G that climbs. The letter sits low-left; the arrow leaves clear of it.
    risingG:
      '<svg viewBox="0 0 100 100" aria-hidden="true" class="mark">' +
      '<circle cx="50" cy="50" r="46" fill="currentColor"/>' +
      '<g fill="none" stroke="var(--mark-ink)" stroke-width="9" ' +
      'stroke-linecap="round" stroke-linejoin="round">' +
      '<path d="M55 41a19 19 0 1 0 4 20H46"/>' +
      '<path d="M64 55l17-17"/><path d="M70 36h12v12"/>' +
      "</g></svg>",

    // C: the steps. Each block is one disclosure, stacking upward.
    steps:
      '<svg viewBox="0 0 100 100" aria-hidden="true" class="mark">' +
      '<rect x="4" y="4" width="92" height="92" rx="22" fill="currentColor"/>' +
      '<rect x="22" y="58" width="16" height="22" rx="4" fill="var(--mark-ink)"/>' +
      '<rect x="42" y="44" width="16" height="36" rx="4" fill="var(--mark-ink)"/>' +
      '<rect x="62" y="28" width="16" height="52" rx="4" fill="var(--mark-ink)"/>' +
      "</svg>",

    // D: the crest. The joke told straight: a one-man fund with a coat of arms.
    crest:
      '<svg viewBox="0 0 100 100" aria-hidden="true" class="mark">' +
      '<path d="M50 5l38 13v34c0 24-17 38-38 43C30 90 12 76 12 52V18z" fill="currentColor"/>' +
      '<path d="M50 14l29 10v28c0 19-13 30-29 34-16-4-29-15-29-34V24z" fill="none" ' +
      'stroke="var(--mark-ink)" stroke-width="3" opacity="0.55"/>' +
      '<text x="50" y="52" text-anchor="middle" dominant-baseline="central" ' +
      'font-family="Georgia, \'Times New Roman\', serif" font-size="34" font-weight="700" ' +
      'fill="var(--mark-ink)">GC</text>' +
      "</svg>",
  };

  return {
    marks: MARKS,
    names: Object.keys(MARKS),
    get: function (name) { return MARKS[name] || MARKS.monogram; },
  };
});

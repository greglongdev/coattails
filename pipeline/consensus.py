"""Where more than one followed person made the same move on the same company.

Built from the feed the app already has: no new source, no new network call.
The rules that keep it honest are in SPEC.md; the short version is that a bought
put is a bearish bet, anyone who pointed both ways inside the window is left out
of that company entirely, and everything aligns on when a trade happened rather
than when it was reported.
"""
from __future__ import annotations

import datetime as dt
import re
from dataclasses import dataclass, field

WINDOW_DAYS = 180
MIN_PEOPLE = 2

BULLISH = "bullish"
BEARISH = "bearish"
AMBIGUOUS = None

PUT_RE = re.compile(r"\bputs?\b", re.I)
CALL_RE = re.compile(r"\bcalls?\b", re.I)


def option_side(*texts: str | None) -> str | None:
    """"put", "call", or None, read from whatever the filing wrote."""
    blob = " ".join(t for t in texts if t)
    if PUT_RE.search(blob):
        return "put"
    if CALL_RE.search(blob):
        return "call"
    return None


def normalise_put_call(raw: str | None) -> str | None | bool:
    """The 13F put/call flag, which is whatever text the filer typed.

    Returns "put", "call", None for an empty flag (an ordinary long position),
    or False for a flag that is present but unrecognised, which must never be
    read as an ordinary position."""
    if raw is None or not str(raw).strip():
        return None
    t = str(raw).strip().lower()
    if t in ("p", "put", "puts"):
        return "put"
    if t in ("c", "call", "calls"):
        return "call"
    return False


def trade_direction(action: str, kind: str, side: str | None) -> str | None:
    """Direction of a congressional trade. See the table in SPEC.md.

    Only a buy or a sell is a decision to own more or less. An exchange (a
    spinoff, a share conversion) and any transaction code the parser did not
    recognise are left out rather than assumed to be sales."""
    if action not in ("buy", "sell"):
        return AMBIGUOUS
    if side == "put":
        # Buying puts is a bet the stock falls. Selling one is an income trade
        # that is only loosely bullish, so it is not claimed either way.
        return BEARISH if action == "buy" else AMBIGUOUS
    if kind == "option" and side is None:
        return AMBIGUOUS  # an option whose side the filing never stated
    return BULLISH if action == "buy" else BEARISH


def holding_direction(kind: str, put_call: str | None) -> str | None:
    """Direction of a quarter-over-quarter 13F change.

    The put/call flag is whatever text the filer typed, so it is read the same
    loose way as a congressional filing rather than matched exactly. Closing an
    options position is excluded in both directions: unwinding a bet is not the
    opposite bet."""
    opening = kind in ("new", "added")
    closing = kind in ("reduced", "sold")
    side = normalise_put_call(put_call)
    if side is False:
        return AMBIGUOUS  # a flag we cannot read is not an ordinary long position
    if side is not None:
        if not opening:
            return AMBIGUOUS
        return BEARISH if side == "put" else BULLISH
    if opening:
        return BULLISH
    if closing:
        return BEARISH
    return AMBIGUOUS


# Plain English for what someone actually did. No filing jargon reaches the screen.
def trade_phrase(action: str, kind: str, side: str | None) -> str:
    if kind == "option":
        what = (side or "") + " options"
        return ("bought " if action == "buy" else "sold ") + what.strip()
    noun = "an ETF" if kind == "etf" else "crypto" if kind == "crypto" else "shares"
    return ("bought " if action == "buy" else "sold ") + noun


HOLDING_PHRASE = {
    "new": "opened a position",
    "added": "added to a position",
    "reduced": "cut a position",
    "sold": "sold out",
}


def holding_phrase(kind: str, put_call: str | None) -> str:
    base = HOLDING_PHRASE.get(kind, kind)
    side = normalise_put_call(put_call)
    if side in ("put", "call"):
        return base + " in " + side + " options"
    return base


@dataclass
class Move:
    """One person's single, unambiguous move on one company."""
    person: str
    ticker: str
    name: str
    direction: str
    phrase: str
    date: str          # when it happened, not when it was reported
    when: str          # how the screen says it
    amount: str | None
    source: str
    size: int = 0      # for ranking a person's own moves, never shown

    def key(self) -> tuple[str, str]:
        return (self.person, self.ticker)


@dataclass
class Group:
    ticker: str
    name: str
    direction: str
    moves: list[Move] = field(default_factory=list)

    @property
    def count(self) -> int:
        return len(self.moves)

    @property
    def latest(self) -> str:
        return max(m.date for m in self.moves)


def _dollars(n: int) -> str:
    for cut, suffix in ((1_000_000_000, "B"), (1_000_000, "M"), (1_000, "K")):
        if n >= cut:
            v = n / cut
            return "$" + (f"{v:.0f}" if v >= 100 else f"{v:.1f}".rstrip("0").rstrip(".")) + suffix
    return f"${n}"


def _amount_size(amount: str | None) -> int:
    """The low end of a STOCK Act range, used only to rank one person's own moves."""
    if not amount:
        return 0
    m = re.search(r"\$([\d,]+)", amount)
    return int(m.group(1).replace(",", "")) if m else 0


def _quarter_label(period: str) -> str:
    y, m, _ = period.split("-")
    return f"the quarter ending {['Mar', 'Jun', 'Sep', 'Dec'][(int(m) - 1) // 3]} {y}"


def collect_moves(people: list[dict], since: str) -> list[Move]:
    """Every in-window move, before the both-ways rule is applied."""
    out: list[Move] = []
    for p in people:
        if p["group"] == "politician":
            for t in p["trades"]:
                if not t.get("ticker") or t["date"] < since:
                    continue
                side = option_side(t.get("detail"), t.get("name")) if t["kind"] == "option" else None
                d = trade_direction(t["action"], t["kind"], side)
                if d is None:
                    continue
                out.append(Move(
                    person=p["id"], ticker=t["ticker"], name=t["name"], direction=d,
                    phrase=trade_phrase(t["action"], t["kind"], side),
                    date=t["date"], when=t["date"], amount=t.get("amount"),
                    source=t.get("source") or "", size=_amount_size(t.get("amount")),
                ))
        else:
            # 13F moves are dated to the quarter they happened in, never the day
            # they were filed, and every quarter inside the window counts.
            by_quarter = p.get("quarter_changes") or {}
            if not by_quarter and p.get("quarters"):
                by_quarter = {p["quarters"][-1]["period"]: p.get("changes") or []}
            sources = {q["period"]: q.get("source") for q in p.get("quarters") or []}
            for period, changes in by_quarter.items():
                if period < since:
                    continue
                for c in changes or []:
                    if not c.get("ticker"):
                        continue
                    d = holding_direction(c["kind"], c.get("put_call"))
                    if d is None:
                        continue
                    value = c.get("value") or 0
                    out.append(Move(
                        person=p["id"], ticker=c["ticker"], name=c.get("name") or c["ticker"],
                        direction=d, phrase=holding_phrase(c["kind"], c.get("put_call")),
                        date=period, when=_quarter_label(period),
                        amount=_dollars(value) if value else None,
                        source=sources.get(period) or "", size=value,
                    ))
    return out


def resolve_people(moves: list[Move]) -> list[Move]:
    """A person's direction on a company is their most recent settled one.

    Two things are going on and they need different answers. Inside a single
    period, a day for a congressional trade and a quarter for a 13F, pointing
    both ways is not a view at all: it is an option roll, closed and reopened,
    and that period is thrown away. Across periods it is a change of mind, and
    the newest one is what the person thinks now. Judging the whole window at
    once conflated the two and silently dropped anyone active: Druckenmiller
    trimmed Amazon in one quarter and took it from 45,800 to 541,600 shares in
    the next, which is a position, not a shrug."""
    by_period: dict[tuple[str, str, str], list[Move]] = {}
    for m in moves:
        by_period.setdefault((m.person, m.ticker, m.date), []).append(m)

    settled: dict[tuple[str, str], tuple[str, list[Move]]] = {}
    for (person, ticker, period), rows in by_period.items():
        if len({r.direction for r in rows}) != 1:
            continue  # no direction in this period
        best = settled.get((person, ticker))
        if best is None or period > best[0]:
            settled[(person, ticker)] = (period, rows)

    out: list[Move] = []
    for _, rows in settled.values():
        out.extend(rows)
    return out


def canonical_name(names: list[str]) -> str:
    """One display name per company, from the several the filings use."""
    cleaned = []
    for n in names:
        n = re.sub(r"\s*-?\s*(Common Stock|Class [A-Z].*|Ordinary Shares)\b.*$", "", n, flags=re.I)
        # "COM" is a 13F share class and only ever a trailing word. Matched loosely
        # it eats the "Com" of "Company" and the "com" of "Amazon.com".
        n = re.sub(r"\s+COM$", "", n)
        n = re.sub(r"\s+", " ", n).strip(" -,")
        if n:
            cleaned.append(n)
    if not cleaned:
        return names[0] if names else ""
    # EDGAR truncates long issuer names ("Taiwan Semiconductor Manufac"), and a
    # truncated name is a prefix of the full one, so drop any candidate that
    # another candidate merely continues.
    full = [n for n in cleaned
            if not any(o.lower() != n.lower() and o.lower().startswith(n.lower()) for o in cleaned)]
    pool = full or cleaned
    # Then prefer a readable name over a shouted one, and the shortest of those.
    mixed = [n for n in pool if not n.isupper()]
    return min(mixed or pool, key=len)


def merge_by_person(moves: list[Move]) -> list[Move]:
    """One row per person, keeping everything they did rather than the last one seen.

    Somebody can add to a holding and buy calls on it in the same quarter. Taking
    only one row hid the larger leg and made the smaller one look like the whole
    story, so the phrases are joined and the biggest move leads."""
    by_person: dict[str, list[Move]] = {}
    for m in moves:
        by_person.setdefault(m.person, []).append(m)

    rows: list[Move] = []
    for person, group in by_person.items():
        lead = sorted(group, key=lambda m: (m.size, m.date))[-1]
        phrases: list[str] = []
        for m in sorted(group, key=lambda m: (-m.size, m.date)):
            if m.phrase not in phrases:
                phrases.append(m.phrase)
        newest = max(group, key=lambda m: m.date)
        rows.append(Move(
            person=person, ticker=lead.ticker, name=lead.name, direction=lead.direction,
            phrase=_join_phrases(phrases), date=newest.date, when=newest.when,
            amount=lead.amount, source=lead.source, size=lead.size,
        ))
    return sorted(rows, key=lambda m: m.date, reverse=True)


def _join_phrases(phrases: list[str]) -> str:
    if len(phrases) == 1:
        return phrases[0]
    if len(phrases) == 2:
        return phrases[0] + ", and " + phrases[1]
    return phrases[0] + ", and " + str(len(phrases) - 1) + " more moves"


def build(people: list[dict], today: str, window_days: int = WINDOW_DAYS,
          min_people: int = MIN_PEOPLE) -> dict:
    # Inclusive lower bound, so the span is exactly window_days days ending today.
    since = (dt.date.fromisoformat(today) - dt.timedelta(days=window_days - 1)).isoformat()
    moves = resolve_people(collect_moves(people, since))

    buckets: dict[tuple[str, str], Group] = {}
    names: dict[str, list[str]] = {}
    for m in moves:
        names.setdefault(m.ticker, []).append(m.name)
        g = buckets.setdefault((m.ticker, m.direction), Group(m.ticker, m.name, m.direction))
        g.moves.append(m)

    groups = [g for g in buckets.values() if len({m.person for m in g.moves}) >= min_people]
    for g in groups:
        g.name = canonical_name(names[g.ticker])
        g.moves = merge_by_person(g.moves)

    # Most agreed-upon first, then most recently acted on, then alphabetical.
    groups.sort(key=lambda g: g.ticker)
    groups.sort(key=lambda g: g.latest, reverse=True)
    groups.sort(key=lambda g: g.count, reverse=True)

    return {
        "window_days": window_days,
        "since": since,
        "as_of": today,
        "min_people": min_people,
        "groups": [
            {
                "ticker": g.ticker,
                "name": g.name,
                "direction": g.direction,
                "count": g.count,
                "people": [
                    {
                        "person": m.person, "did": m.phrase, "when": m.when,
                        "date": m.date, "amount": m.amount, "source": m.source,
                    }
                    for m in g.moves
                ],
            }
            for g in groups
        ],
    }

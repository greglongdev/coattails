"""Build data/feed.json from the primary sources.

    python -m pipeline.build            # full build (uses data/cache, fetches only what's new)
    python -m pipeline.build --offline  # rebuild feed.json from cache only, no network

Everything the app shows comes out of this file. Every event carries the URL of
the filing it came from.
"""
from __future__ import annotations

import argparse
import dataclasses
import datetime as dt
import json
import re
import sys
from pathlib import Path

from . import config, consensus, figi, house, members, sec13f, senate
from .fetch import Fetcher

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
CACHE = DATA / "cache"
FEED = DATA / "feed.json"
CUSIP_CACHE = DATA / "cusip_map.json"

# Politician asset kinds the feed keeps. Bonds, munis, private funds and the like
# are left out on purpose: they are not something a reader can follow.
HOUSE_KEEP = {"ST": "stock", "OP": "option", "EF": "etf", "CT": "crypto"}
SENATE_KEEP = {"Stock": "stock", "Stock Option": "option", "Exchange Traded Fund": "etf",
               "Cryptocurrency": "crypto", "Crypto": "crypto"}

HOUSE_TYPES = {"P": "buy", "S": "sell", "S (partial)": "sell", "E": "exchange"}
SENATE_TYPES = {"Purchase": "buy", "Sale (Full)": "sell", "Sale (Partial)": "sell", "Exchange": "exchange"}


def log(*a):
    print(*a, file=sys.stderr, flush=True)


def _read_json(p: Path):
    return json.loads(p.read_text())


def _write_json(p: Path, obj):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, indent=1, sort_keys=True) + "\n")


def clean_asset_name(s: str) -> str:
    s = house.ASSET_CODE_RE.sub("", s)
    s = house.TICKER_RE.sub("", s)
    s = re.sub(r"\s+", " ", s).strip(" -")
    return s


# --------------------------------------------------------------------------
# Membership
# --------------------------------------------------------------------------

def load_members(f: Fetcher | None) -> tuple[dict, dict]:
    hp, sp = CACHE / "members_house.xml", CACHE / "members_senate.xml"
    if f is not None:
        hp.parent.mkdir(parents=True, exist_ok=True)
        hp.write_text(f.get(members.HOUSE_URL).text)
        sp.write_text(f.get(members.SENATE_URL).text)
    return members.parse_house(hp.read_text()), members.parse_senate(sp.read_text())


# --------------------------------------------------------------------------
# House
# --------------------------------------------------------------------------

def _match_house(entry: house.IndexEntry, p: dict) -> bool:
    m = p["match"]
    return (entry.last.lower() == m["last"].lower()
            and entry.first.lower().startswith(m["first"].lower())
            and entry.state_district == p["state_district"])


def build_house(f: Fetcher | None, roster: list[dict]) -> dict[str, dict]:
    """Returns {person_id: {"trades": [...], "unreadable": n, "filings": n}}."""
    out = {p["id"]: {"trades": [], "unreadable": 0, "filings": 0} for p in roster}
    for year in config.HOUSE_YEARS:
        idx_path = CACHE / "house" / f"{year}FD.zip"
        if f is not None:
            idx_path.parent.mkdir(parents=True, exist_ok=True)
            idx_path.write_bytes(f.get(house.INDEX_URL.format(year=year)).content)
        if not idx_path.exists():
            continue
        entries = [e for e in house.parse_index(idx_path.read_bytes()) if e.is_ptr]
        for p in roster:
            for e in entries:
                if not _match_house(e, p) or e.filing_date < config.POLITICIAN_SINCE:
                    continue
                out[p["id"]]["filings"] += 1
                if not e.electronic:
                    out[p["id"]]["unreadable"] += 1
                    continue
                cp = CACHE / "house" / f"{e.docid}.json"
                if cp.exists():
                    rep = _read_json(cp)
                elif f is not None:
                    pdf = f.get(e.pdf_url).content
                    r = house.parse_report(pdf, e.docid)
                    rep = dataclasses.asdict(r)
                    rep["filing_date"] = e.filing_date
                    rep["url"] = e.pdf_url
                    _write_json(cp, rep)
                else:
                    continue
                for t in rep["transactions"]:
                    kind = HOUSE_KEEP.get(t["asset_code"] or "")
                    if kind is None:
                        continue
                    out[p["id"]]["trades"].append({
                        "date": t["tx_date"],
                        "disclosed": e.filing_date,
                        "action": HOUSE_TYPES.get(t["tx_type"], "other"),
                        "ticker": t["ticker"],
                        "name": clean_asset_name(t["asset"]),
                        "kind": kind,
                        "amount": t["amount"],
                        "owner": house.OWNER_CODES.get(t["owner"], t["owner"]),
                        "detail": t.get("description") or None,
                        "source": e.pdf_url,
                    })
    return out


# --------------------------------------------------------------------------
# Senate
# --------------------------------------------------------------------------

# Senate filers sometimes leave the ticker column blank but lead the asset name
# with it: "SDZNY- Sandoz Group AG ADR", "ACN - Accenture plc Class A Shares".
# The dash needs whitespace on at least one side, or "ROLLS-ROYCE" reads as ROLLS.
LEADING_TICKER_RE = re.compile(r"^([A-Z]{1,5})(?:\s+[-\u2013]\s*|[-\u2013]\s+)(?=[A-Za-z])")


def recover_ticker(ticker: str | None, name: str) -> str | None:
    if ticker:
        return ticker
    m = LEADING_TICKER_RE.match(name or "")
    return m.group(1) if m else None


def _match_senate(filing: senate.SenateFiling, p: dict) -> bool:
    m = p["match"]
    return (filing.surname.lower() == m["last"].lower()
            and filing.first.strip().lower().startswith(m["first"].lower()))


def build_senate(f: Fetcher | None, roster: list[dict]) -> dict[str, dict]:
    out = {p["id"]: {"trades": [], "unreadable": 0, "filings": 0} for p in roster}
    list_path = CACHE / "senate" / "filings.json"
    if f is not None:
        csrf = senate.accept_notice(f.s)
        filings = senate.list_filings(f.s, csrf, config.SENATE_SUBMITTED_START)
        _write_json(list_path, [dataclasses.asdict(x) for x in filings])
    if not list_path.exists():
        return out
    filings = [senate.SenateFiling(**x) for x in _read_json(list_path)]
    for p in roster:
        for fl in filings:
            if not _match_senate(fl, p) or fl.filed < config.POLITICIAN_SINCE:
                continue
            out[p["id"]]["filings"] += 1
            if not fl.electronic:
                out[p["id"]]["unreadable"] += 1
                continue
            cp = CACHE / "senate" / f"{fl.report_id}.json"
            if cp.exists():
                rep = _read_json(cp)
            elif f is not None:
                html = f.get(fl.url).text
                rep = dataclasses.asdict(senate.parse_report(html, fl.report_id))
                rep["filed"] = fl.filed
                rep["url"] = fl.url
                _write_json(cp, rep)
            else:
                continue
            for t in rep["transactions"]:
                kind = SENATE_KEEP.get(t["asset_type"])
                if kind is None:
                    continue
                out[p["id"]]["trades"].append({
                    "date": t["tx_date"],
                    "disclosed": fl.filed,
                    "action": SENATE_TYPES.get(t["tx_type"], "other"),
                    "ticker": recover_ticker(t["ticker"], t["asset"]),
                    "name": t["asset"],
                    "kind": kind,
                    "amount": t["amount"],
                    "owner": t["owner"],
                    "detail": t.get("comment") or None,
                    "source": fl.url,
                })
    return out


# --------------------------------------------------------------------------
# 13F
# --------------------------------------------------------------------------

def build_13f(f: Fetcher | None, roster: list[dict]) -> dict[str, dict]:
    out = {}
    for inv in roster:
        filings: list[sec13f.Filing] = []
        for cik in inv["ciks"]:
            sp = CACHE / "13f" / f"submissions_{cik}.json"
            if f is not None:
                sp.parent.mkdir(parents=True, exist_ok=True)
                sp.write_text(f.get(sec13f.SUBMISSIONS.format(cik=cik)).text)
            if sp.exists():
                filings.extend(sec13f.list_13f_filings(_read_json(sp)))
        by_period: dict[str, list[sec13f.Filing]] = {}
        for fl in filings:
            by_period.setdefault(fl.period, []).append(fl)
        periods = sorted(by_period)[-config.QUARTERS_KEPT:]
        tables: dict[str, list[sec13f.Position]] = {}
        amend: dict[str, str | None] = {}
        for period in periods:
            for fl in by_period[period]:
                cp = CACHE / "13f" / f"{fl.acc_nodash}.json"
                if cp.exists():
                    d = _read_json(cp)
                elif f is not None:
                    base = f"https://www.sec.gov/Archives/edgar/data/{fl.cik}/{fl.acc_nodash}/"
                    idx = f.get(base + "index.json").json()
                    name = sec13f.info_table_name(idx)
                    rows = sec13f.parse_info_table(f.get(base + name).text) if name else []
                    at = None
                    if fl.form == "13F-HR/A":
                        at = sec13f.amendment_type(f.get(base + "primary_doc.xml").text)
                    d = {"positions": [dataclasses.asdict(r) for r in rows], "amendment_type": at,
                         "filing": dataclasses.asdict(fl)}
                    _write_json(cp, d)
                else:
                    continue
                tables[fl.accession] = [sec13f.Position(**r) for r in d["positions"]]
                amend[fl.accession] = d.get("amendment_type")
        quarters = [sec13f.assemble_quarter(p, by_period[p], tables, amend) for p in periods]
        quarters = [q for q in quarters if q.positions]
        out[inv["id"]] = {"quarters": quarters}
    return out


def _cusip_lookup(cache: dict, cusip: str) -> dict:
    d = cache.get(cusip) or {}
    return {"ticker": d.get("ticker"), "figi_name": d.get("name")}


def render_changes(latest: sec13f.Quarter, prior: sec13f.Quarter | None, cusips: dict) -> list[dict]:
    out = []
    for c in sec13f.diff_quarters(latest, prior):
        lk = _cusip_lookup(cusips, c.position.cusip)
        out.append({
            "kind": c.kind, "ticker": lk["ticker"],
            "name": c.position.issuer.title() if c.position.issuer.isupper() else c.position.issuer,
            "cusip": c.position.cusip, "put_call": c.position.put_call,
            "shares": c.shares, "prev_shares": c.prev_shares,
            "pct": round(c.pct, 1) if c.pct is not None else None,
            "value": c.position.value,
        })
    return out


def render_investor(inv: dict, q: list[sec13f.Quarter], cusips: dict) -> dict:
    latest = q[-1] if q else None
    prior = q[-2] if len(q) > 1 else None
    holdings = []
    if latest:
        total = latest.total_value or 1
        for p in sorted(latest.positions.values(), key=lambda p: -p.value):
            lk = _cusip_lookup(cusips, p.cusip)
            holdings.append({
                "ticker": lk["ticker"], "name": p.issuer.title() if p.issuer.isupper() else p.issuer,
                "cusip": p.cusip, "put_call": p.put_call, "shares": p.shares, "value": p.value,
                "weight": round(p.value / total * 100, 2),
            })
    changes = render_changes(latest, prior, cusips) if latest else []
    # One entry per quarter transition, keyed by the quarter the moves happened in.
    by_quarter = {}
    for i in range(1, len(q)):
        by_quarter[q[i].period] = render_changes(q[i], q[i - 1], cusips)

    return {
        "id": inv["id"], "name": inv["name"], "short": inv["short"], "group": "investor",
        "firm": inv["firm"], "why": inv["why"],
        "quarters": [{"period": x.period, "filed": x.filed, "total_value": x.total_value,
                      "positions": len(x.positions), "source": x.filings[-1].index_url if x.filings else None}
                     for x in q],
        "holdings": holdings,
        "changes": changes,
        "quarter_changes": by_quarter,
    }


# --------------------------------------------------------------------------
# Assemble
# --------------------------------------------------------------------------

def build(offline: bool = False) -> dict:
    f = None if offline else Fetcher()
    house_members, senate_members = load_members(f)

    people = []
    warnings = []

    house_roster = [p for p in config.POLITICIANS if p["chamber"] == "house"]
    senate_roster = [p for p in config.POLITICIANS if p["chamber"] == "senate"]
    log(f"house: {len(house_roster)} members, years {config.HOUSE_YEARS}")
    h = build_house(f, house_roster)
    log(f"senate: {len(senate_roster)} members")
    s = build_senate(f, senate_roster)

    for p in config.POLITICIANS:
        mem = (house_members if p["chamber"] == "house" else senate_members).get(p["bioguide"])
        data = (h if p["chamber"] == "house" else s)[p["id"]]
        if mem is None:
            warnings.append(f"{p['name']} is not on the current {p['chamber']} membership list")
        trades = sorted(data["trades"], key=lambda t: (t["disclosed"], t["date"]), reverse=True)
        if p["chamber"] == "house":
            title = f"Rep. {p['name']} ({mem.party}-{mem.state})" if mem else f"Rep. {p['name']}"
        else:
            title = f"Sen. {p['name']} ({mem.party}-{mem.state})" if mem else f"Sen. {p['name']}"
        people.append({
            "id": p["id"], "name": p["name"], "short": p["short"], "group": "politician", "chamber": p["chamber"],
            "title": title, "party": mem.party if mem else None, "state": mem.state if mem else None,
            "active": mem is not None, "why": p["why"],
            "filings": data["filings"], "unreadable_filings": data["unreadable"],
            "trades": trades,
        })

    log(f"13f: {len(config.INVESTORS)} managers")
    t = build_13f(f, config.INVESTORS)
    cusips = figi.load_cache(CUSIP_CACHE)
    if f is not None:
        need = sorted({p.cusip for d in t.values() for q in d["quarters"] for p in q.positions.values()})
        before = len(cusips)
        figi.map_cusips(need, cusips, f.s)
        figi.save_cache(CUSIP_CACHE, cusips)
        log(f"figi: {len(need)} cusips, {len(cusips) - before} new lookups")
    for inv in config.INVESTORS:
        q = t[inv["id"]]["quarters"]
        if not q:
            warnings.append(f"{inv['name']}: no 13F holdings found")
        elif q[-1].filed < (dt.date.today() - dt.timedelta(days=200)).isoformat():
            warnings.append(f"{inv['name']}: latest 13F filed {q[-1].filed}, may have stopped filing")
        people.append(render_investor(inv, q, cusips))

    feed = build_feed(people)
    today = dt.date.today().isoformat()
    agree = consensus.build(people, today)
    log(f"consensus: {len(agree['groups'])} companies with two or more agreeing since {agree['since']}")
    return {
        "schema": 1,
        "generated_at": dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "people": people,
        "feed": feed,
        "consensus": agree,
        "warnings": warnings,
        "sources": {
            "house": "https://disclosures-clerk.house.gov/FinancialDisclosure",
            "senate": "https://efdsearch.senate.gov/search/",
            "sec": "https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&type=13F-HR",
        },
    }


def build_feed(people: list[dict]) -> list[dict]:
    """One flat, newest-first list of things worth knowing."""
    ev = []
    for p in people:
        if p["group"] == "politician":
            for tr in p["trades"]:
                ev.append({
                    "type": "trade", "person": p["id"], "date": tr["date"], "disclosed": tr["disclosed"],
                    "action": tr["action"], "ticker": tr["ticker"], "name": tr["name"], "kind": tr["kind"],
                    "amount": tr["amount"], "owner": tr["owner"], "detail": tr["detail"], "source": tr["source"],
                })
        else:
            if not p["quarters"]:
                continue
            latest = p["quarters"][-1]
            for c in p["changes"]:
                # The full change list lives on the person. The feed keeps the moves
                # worth a glance: positions opened or closed, and trims or adds of
                # at least a fifth of the stake.
                if c["kind"] in ("added", "reduced") and abs(c["pct"] or 0) < 20:
                    continue
                ev.append({
                    "type": "quarter", "person": p["id"], "date": latest["filed"], "period": latest["period"],
                    "action": c["kind"], "ticker": c["ticker"], "name": c["name"], "put_call": c["put_call"],
                    "shares": c["shares"], "prev_shares": c["prev_shares"], "pct": c["pct"], "value": c["value"],
                    "source": latest["source"],
                })
    ev.sort(key=lambda e: (e.get("disclosed") or e["date"], e["date"]), reverse=True)
    return ev


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--offline", action="store_true", help="rebuild from cache only")
    ap.add_argument("--out", default=str(FEED))
    a = ap.parse_args(argv)
    feed = build(offline=a.offline)
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps(feed, separators=(",", ":"), ensure_ascii=False) + "\n")
    n_tr = sum(len(p.get("trades", [])) for p in feed["people"])
    n_ch = sum(len(p.get("changes", [])) for p in feed["people"])
    log(f"wrote {a.out}: {len(feed['people'])} people, {n_tr} trades, {n_ch} quarterly changes, "
        f"{len(feed['feed'])} feed events, {len(feed['consensus']['groups'])} consensus groups")
    for w in feed["warnings"]:
        log("WARNING:", w)


if __name__ == "__main__":
    main()

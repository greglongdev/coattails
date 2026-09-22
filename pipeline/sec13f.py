"""Quarterly 13F holdings from SEC EDGAR.

Every institutional manager over $100M in US equities files Form 13F within 45
days of quarter end. The filing carries an XML "information table" with one row
per position. We take the two most recent quarters per manager and diff them.

Sources (free, no key, needs a descriptive User-Agent):
  submissions: https://data.sec.gov/submissions/CIK##########.json
  filing dir:  https://www.sec.gov/Archives/edgar/data/{cik}/{accession}/index.json
  documents:   https://www.sec.gov/Archives/edgar/data/{cik}/{accession}/{file}

Amendments: a 13F-HR/A is either a RESTATEMENT (replaces the quarter's table) or
NEW HOLDINGS (adds rows). Both are honored, in filing order.
"""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field

SUBMISSIONS = "https://data.sec.gov/submissions/CIK{cik:010d}.json"
ARCHIVE = "https://www.sec.gov/Archives/edgar/data/{cik}/{acc}/{name}"
FILING_INDEX_HTML = "https://www.sec.gov/Archives/edgar/data/{cik}/{acc}/{accdash}-index.html"


@dataclass
class Filing:
    cik: int
    accession: str  # with dashes
    form: str  # 13F-HR or 13F-HR/A
    filed: str  # YYYY-MM-DD
    period: str  # YYYY-MM-DD quarter end

    @property
    def acc_nodash(self) -> str:
        return self.accession.replace("-", "")

    @property
    def index_url(self) -> str:
        return FILING_INDEX_HTML.format(cik=self.cik, acc=self.acc_nodash, accdash=self.accession)


@dataclass
class Position:
    cusip: str
    issuer: str
    title: str
    put_call: str | None  # "Put", "Call" or None
    shares: int
    value: int  # dollars
    share_type: str = "SH"  # SH (shares) or PRN (principal amount)

    @property
    def key(self) -> str:
        return f"{self.cusip}|{self.put_call or ''}"


@dataclass
class Quarter:
    period: str
    filed: str
    positions: dict[str, Position] = field(default_factory=dict)
    filings: list[Filing] = field(default_factory=list)

    @property
    def total_value(self) -> int:
        return sum(p.value for p in self.positions.values())


def list_13f_filings(submissions: dict) -> list[Filing]:
    """All 13F-HR and 13F-HR/A filings from a submissions JSON (recent window)."""
    cik = int(submissions["cik"])
    f = submissions["filings"]["recent"]
    out = []
    for i, form in enumerate(f["form"]):
        if form in ("13F-HR", "13F-HR/A"):
            out.append(Filing(cik=cik, accession=f["accessionNumber"][i], form=form,
                              filed=f["filingDate"][i], period=f["reportDate"][i]))
    return out


def info_table_name(index_json: dict) -> str | None:
    """Pick the information-table XML out of a filing directory listing."""
    names = [i["name"] for i in index_json["directory"]["item"]]
    xmls = [n for n in names if n.lower().endswith(".xml") and "primary_doc" not in n.lower()]
    return xmls[0] if xmls else None


def _local(tag: str) -> str:
    return tag.split("}", 1)[1] if "}" in tag else tag


def parse_info_table(xml_text: str) -> list[Position]:
    """Rows of a 13F information table, aggregated by CUSIP (+ put/call flag)."""
    root = ET.fromstring(xml_text.encode("utf-8") if isinstance(xml_text, str) else xml_text)
    agg: dict[str, Position] = {}
    for el in root.iter():
        if _local(el.tag) != "infoTable":
            continue
        fields = {}
        for child in el.iter():
            fields[_local(child.tag)] = (child.text or "").strip()
        cusip = fields.get("cusip", "").upper()
        if not cusip:
            continue
        put_call = fields.get("putCall") or None
        shares = int(float(fields.get("sshPrnamt", "0") or 0))
        value = int(float(fields.get("value", "0") or 0))
        key = f"{cusip}|{put_call or ''}"
        if key in agg:
            agg[key].shares += shares
            agg[key].value += value
        else:
            agg[key] = Position(cusip=cusip, issuer=fields.get("nameOfIssuer", ""),
                                title=fields.get("titleOfClass", ""), put_call=put_call,
                                shares=shares, value=value,
                                share_type=(fields.get("sshPrnamtType") or "SH").upper())
    return rescale_if_thousands(list(agg.values()))


# The 13F value column has been whole dollars since 2023, but some managers still
# file in thousands, which would understate their portfolio a thousandfold. The
# tell is the implied share price: real equities trade well above $1, so a median
# implied price below that means the column is thousands.
THOUSANDS_PRICE_CUTOFF = 1.0


def scale_factor(positions: list[Position]) -> int:
    prices = sorted(p.value / p.shares for p in positions
                    if p.shares > 0 and p.share_type == "SH" and p.value > 0)
    if len(prices) < 3:
        return 1
    median = prices[len(prices) // 2] if len(prices) % 2 else (prices[len(prices) // 2 - 1] + prices[len(prices) // 2]) / 2
    return 1000 if median < THOUSANDS_PRICE_CUTOFF else 1


def rescale_if_thousands(positions: list[Position]) -> list[Position]:
    f = scale_factor(positions)
    if f != 1:
        for p in positions:
            p.value *= f
    return positions


def amendment_type(primary_doc_xml: str) -> str | None:
    """RESTATEMENT or NEW HOLDINGS for a 13F-HR/A primary document."""
    m = re.search(r"<(?:\w+:)?amendmentType>\s*([^<]+?)\s*<", primary_doc_xml)
    return m.group(1).upper() if m else None


def assemble_quarter(period: str, filings: list[Filing], tables: dict[str, list[Position]],
                     amendment_types: dict[str, str | None]) -> Quarter:
    """Apply the original and any amendments for one quarter, in filing order.

    Filings from different CIKs for the same quarter are separate managers' books
    (a firm and its parent, say) and are summed; within one CIK an original or a
    RESTATEMENT replaces, NEW HOLDINGS adds."""
    q = Quarter(period=period, filed="")
    per_cik: dict[int, dict[str, Position]] = {}
    for f in sorted(filings, key=lambda x: (x.filed, x.accession)):
        rows = tables.get(f.accession)
        if rows is None:
            continue
        book = per_cik.setdefault(f.cik, {})
        if f.form == "13F-HR" or amendment_types.get(f.accession) == "RESTATEMENT":
            book.clear()
            book.update({p.key: Position(**p.__dict__) for p in rows})
        else:  # NEW HOLDINGS (or unknown amendment type: add, never drop)
            for p in rows:
                if p.key in book:
                    book[p.key].shares += p.shares
                    book[p.key].value += p.value
                else:
                    book[p.key] = Position(**p.__dict__)
        q.filed = max(q.filed, f.filed)
        q.filings.append(f)
    for book in per_cik.values():
        for k, p in book.items():
            if k in q.positions:
                q.positions[k].shares += p.shares
                q.positions[k].value += p.value
            else:
                q.positions[k] = Position(**p.__dict__)
    return q


@dataclass
class Change:
    kind: str  # new / added / reduced / sold
    position: Position
    prev_shares: int
    shares: int

    @property
    def pct(self) -> float | None:
        if self.prev_shares == 0:
            return None
        return (self.shares - self.prev_shares) / self.prev_shares * 100.0


def diff_quarters(latest: Quarter, prior: Quarter | None) -> list[Change]:
    if prior is None:
        return []
    out: list[Change] = []
    for k, p in latest.positions.items():
        if k not in prior.positions:
            out.append(Change("new", p, 0, p.shares))
        else:
            ps = prior.positions[k].shares
            if p.shares > ps:
                out.append(Change("added", p, ps, p.shares))
            elif p.shares < ps:
                out.append(Change("reduced", p, ps, p.shares))
    for k, p in prior.positions.items():
        if k not in latest.positions:
            out.append(Change("sold", p, p.shares, 0))
    # Biggest moves first, by dollar value of the position that moved.
    out.sort(key=lambda c: -(c.position.value if c.kind != "sold" else c.position.value))
    return out

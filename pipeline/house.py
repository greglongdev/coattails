"""House of Representatives Periodic Transaction Reports (STOCK Act).

Source: the Clerk of the House financial disclosure site.
  index:  https://disclosures-clerk.house.gov/public_disc/financial-pdfs/{year}FD.zip
  report: https://disclosures-clerk.house.gov/public_disc/ptr-pdfs/{year}/{docid}.pdf

Electronic filings (DocID starting with "2") are text PDFs laid out as a table.
We extract every word with its coordinates (pdftotext -bbox-layout), locate the
column headers on each page, and assign words to columns by x position. That is
far more robust than splitting whitespace-aligned text.

Paper filings (DocID starting with "8" or "9") are scanned images. They are
reported as unreadable, never guessed.
"""
from __future__ import annotations

import io
import re
import subprocess
import tempfile
import xml.etree.ElementTree as ET
import zipfile
from dataclasses import dataclass, field
from html.parser import HTMLParser

INDEX_URL = "https://disclosures-clerk.house.gov/public_disc/financial-pdfs/{year}FD.zip"
PDF_URL = "https://disclosures-clerk.house.gov/public_disc/ptr-pdfs/{year}/{docid}.pdf"

DATE_RE = re.compile(r"^\d{2}/\d{2}/\d{4}$")
TICKER_RE = re.compile(r"\(([A-Z][A-Z0-9.\-]{0,9})\)")
ASSET_CODE_RE = re.compile(r"\[([A-Z]{2})\]")
MONEY_RE = re.compile(r"^\$[\d,]+(\.\d+)?$")

# House asset type codes that matter for a stock follower.
ASSET_CODES = {
    "ST": "stock",
    "OP": "option",
    "EF": "etf",
    "MF": "mutual fund",
    "GS": "government security",
    "CS": "corporate bond",
    "AB": "asset-backed / private",
    "OT": "other",
    "PS": "private stock",
    "CT": "crypto",
    "RP": "real property",
    "OI": "ownership interest",
    "FE": "future / commodity",
    "HE": "hedge fund",
    "PE": "private equity",
    "EQ": "excepted investment fund",
    "IH": "IRA / 401k holding",
    "BA": "bank account",
    "OL": "other liability",
    "TR": "trust",
    "IC": "investment club",
    "VI": "variable insurance",
    "WU": "whole life insurance",
    "DB": "defined benefit pension",
    "DO": "debts owed to filer",
    "DS": "delaware statutory trust",
    "EI": "employee stock option",
    "FA": "farm",
    "FN": "fixed annuity",
    "FU": "futures",
    "IP": "intellectual property",
    "SA": "stock appreciation right",
    "VA": "variable annuity",
    "BK": "brokerage account",
    "CO": "collectibles",
    "5C": "529 college savings plan",
    "5F": "529 portfolio",
    "5P": "529 prepaid tuition",
    "PM": "precious metal",
    "RS": "restricted stock unit",
    "RE": "real estate investment trust",
}

OWNER_CODES = {"SP": "Spouse", "DC": "Dependent child", "JT": "Joint", "": "Self"}


@dataclass
class IndexEntry:
    docid: str
    first: str
    last: str
    prefix: str
    suffix: str
    state_district: str
    filing_type: str
    filing_date: str  # YYYY-MM-DD
    year: int

    @property
    def electronic(self) -> bool:
        return self.docid.startswith("2")

    @property
    def is_ptr(self) -> bool:
        return self.filing_type == "P"

    @property
    def pdf_url(self) -> str:
        return PDF_URL.format(year=self.year, docid=self.docid)


@dataclass
class Transaction:
    owner: str
    asset: str
    ticker: str | None
    asset_code: str | None
    tx_type: str  # "P", "S", "S (partial)", "E"
    tx_date: str  # YYYY-MM-DD
    notified: str  # YYYY-MM-DD
    amount: str
    description: str | None = None
    comment: str | None = None
    subholding_of: str | None = None
    filing_status: str | None = None


@dataclass
class Report:
    docid: str
    filer: str
    state_district: str
    transactions: list[Transaction] = field(default_factory=list)


def _us_date(s: str) -> str:
    m, d, y = s.split("/")
    return f"{y}-{int(m):02d}-{int(d):02d}"


def parse_index(zip_bytes: bytes) -> list[IndexEntry]:
    """Parse the yearly FD index zip into entries."""
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as z:
        name = next(n for n in z.namelist() if n.lower().endswith(".xml"))
        xml = z.read(name)
    root = ET.fromstring(xml)
    out = []
    for m in root.findall("Member"):
        fd = m.findtext("FilingDate", "")
        out.append(
            IndexEntry(
                docid=m.findtext("DocID", "").strip(),
                first=m.findtext("First", "").strip(),
                last=m.findtext("Last", "").strip(),
                prefix=m.findtext("Prefix", "").strip(),
                suffix=m.findtext("Suffix", "").strip(),
                state_district=m.findtext("StateDst", "").strip(),
                filing_type=m.findtext("FilingType", "").strip(),
                filing_date=_us_date(fd) if fd else "",
                year=int(m.findtext("Year", "0")),
            )
        )
    return out


# --------------------------------------------------------------------------
# PDF word extraction
# --------------------------------------------------------------------------

@dataclass
class Word:
    text: str
    x0: float
    y0: float
    x1: float
    y1: float


class _BBoxParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.pages: list[list[Word]] = []
        self._cur: Word | None = None

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "page":
            self.pages.append([])
        elif tag == "word":
            self._cur = Word("", float(a["xmin"]), float(a["ymin"]), float(a["xmax"]), float(a["ymax"]))

    def handle_data(self, data):
        if self._cur is not None:
            self._cur.text += data

    def handle_endtag(self, tag):
        if tag == "word" and self._cur is not None:
            self._cur.text = self._cur.text.strip()
            if self._cur.text:
                self.pages[-1].append(self._cur)
            self._cur = None


def pdf_words(pdf_bytes: bytes) -> list[list[Word]]:
    """Return words per page with coordinates, via poppler's pdftotext."""
    with tempfile.NamedTemporaryFile(suffix=".pdf") as f:
        f.write(pdf_bytes)
        f.flush()
        res = subprocess.run(
            ["pdftotext", "-bbox-layout", f.name, "-"],
            capture_output=True, text=True, check=True,
        )
    p = _BBoxParser()
    p.feed(res.stdout)
    return p.pages


# --------------------------------------------------------------------------
# Table reconstruction
# --------------------------------------------------------------------------

@dataclass
class Columns:
    owner: float
    asset: float
    tx_type: float
    tx_date: float
    notified: float
    amount: float
    cap: float


def _find_columns(words: list[Word]) -> Columns | None:
    """Locate the transaction table header on a page."""
    by_text: dict[str, list[Word]] = {}
    for w in words:
        by_text.setdefault(w.text, []).append(w)
    try:
        owner = by_text["Owner"][0]
        asset = next(w for w in by_text["Asset"] if abs(w.y0 - owner.y0) < 2)
        tx = next(w for w in by_text["Transaction"] if abs(w.y0 - owner.y0) < 2)
        notif = next(w for w in by_text["Notification"] if abs(w.y0 - owner.y0) < 2)
        amount = next(w for w in by_text["Amount"] if abs(w.y0 - owner.y0) < 2)
        cap = next(w for w in by_text["Cap."] if abs(w.y0 - owner.y0) < 2)
        # "Date" appears twice on the header row: Transaction Date, Notification Date.
        dates = sorted((w for w in by_text.get("Date", []) if abs(w.y0 - owner.y0) < 2), key=lambda w: w.x0)
        tx_date = dates[0]
    except (KeyError, StopIteration, IndexError):
        return None
    return Columns(owner.x0, asset.x0, tx.x0, tx_date.x0, notif.x0, amount.x0, cap.x0)


def _lines(words: list[Word], tol: float = 2.5) -> list[list[Word]]:
    """Group words into visual lines by y, then sort each by x."""
    ws = sorted(words, key=lambda w: (round(w.y0, 1), w.x0))
    lines: list[list[Word]] = []
    for w in ws:
        if lines and abs(lines[-1][0].y0 - w.y0) <= tol:
            lines[-1].append(w)
        else:
            lines.append([w])
    for ln in lines:
        ln.sort(key=lambda w: w.x0)
    return lines


_META_KEYS = {
    ("F", "S"): "filing_status",
    ("D",): "description",
    ("S", "O"): "subholding_of",
    ("C",): "comment",
}


def _meta_key(tokens: list[str]) -> tuple[str, list[str]] | None:
    """Metadata rows render their small-caps labels as bare capital letters
    followed by a colon: 'F S : New', 'D : Purchased 10 shares.', 'S O : ...', 'C : ...'."""
    if ":" not in tokens:
        return None
    i = tokens.index(":")
    label = tuple(tokens[:i])
    if label in _META_KEYS and all(len(t) == 1 for t in label):
        return _META_KEYS[label], tokens[i + 1:]
    return None


class _TxBuilder:
    """Accumulates one transaction's words as lines stream past, across page breaks."""

    def __init__(self, anchor: Word, cols: Columns):
        self.anchor_y = anchor.y0
        self.tx_type = anchor.text
        self.owner = ""
        self.dates: list[str] = []
        self.amount_words: list[Word] = []
        self.asset_tokens: list[str] = []
        self.meta: dict[str, list[str]] = {}
        self.current_meta: str | None = None
        self.cols = cols
        self.lines_seen = 0

    def amount_open(self) -> bool:
        toks = [w.text for w in self.amount_words]
        return not toks or toks[-1] == "-" or toks[-1] in ("Over", "Spouse/DC")

    def feed(self, lines: list[list[Word]], cols: Columns, same_page: bool) -> None:
        """same_page: lines are on the anchor's page (owner/dates/amount live near the anchor)."""
        for ln in lines:
            near_anchor = same_page and ln[0].y0 < self.anchor_y + 3
            # The amount range sits on the anchor line and may wrap to the next line,
            # which can fall on the next page. Description text can render full-width
            # under every column, so only range-looking tokens are taken, and only
            # while the range is still open.
            take_amount = (same_page and ln[0].y0 < self.anchor_y + 16) or (self.lines_seen == 0 and self.amount_open())
            amount_here: list[Word] = []
            for w in ln:
                if near_anchor and w.x0 < cols.asset - 3 and w.text in OWNER_CODES:
                    self.owner = w.text
                elif near_anchor and cols.tx_date - 3 <= w.x0 < cols.amount - 3 and DATE_RE.match(w.text):
                    self.dates.append(w.text)
                elif near_anchor and w.text == "(partial)" and self.tx_type == "S" and cols.tx_type <= w.x0 < cols.tx_date:
                    self.tx_type = "S (partial)"
                elif (take_amount and cols.amount - 3 <= w.x0 < cols.cap - 3
                        and (MONEY_RE.match(w.text) or w.text in ("-", "Over", "Spouse/DC", "None"))):
                    amount_here.append(w)
            self.amount_words.extend(amount_here)
            amount_ids = {id(w) for w in amount_here}
            self.lines_seen += 1

            asset_line = [w for w in ln if cols.asset - 3 <= w.x0 < cols.tx_type - 3]
            if not asset_line:
                continue
            toks = [w.text for w in asset_line]
            mk = _meta_key(toks)
            if mk:
                # Metadata rows (description, comment, subholding) run full width.
                self.current_meta, _ = mk
                i = toks.index(":")
                rest = [w.text for w in ln if w.x0 > asset_line[i].x0 and id(w) not in amount_ids]
                self.meta.setdefault(self.current_meta, []).extend(rest)
            elif self.current_meta:
                rest = [w.text for w in ln if w.x0 >= cols.asset - 3 and id(w) not in amount_ids]
                self.meta[self.current_meta].extend(rest)
            else:
                self.asset_tokens.extend(toks)

    def build(self) -> Transaction:
        asset = " ".join(self.asset_tokens)
        ticker = None
        m = TICKER_RE.findall(asset)
        if m:
            ticker = m[-1]
        code = None
        mc = ASSET_CODE_RE.search(asset)
        if mc:
            code = mc.group(1)
        amount = _norm_amount([w.text for w in sorted(self.amount_words, key=lambda w: (round(w.y0), w.x0))])
        dates = (self.dates + ["", ""])[:2]
        meta = self.meta
        return Transaction(
            owner=self.owner,
            asset=asset,
            ticker=ticker,
            asset_code=code,
            tx_type=self.tx_type,
            tx_date=_us_date(dates[0]) if dates[0] else "",
            notified=_us_date(dates[1]) if dates[1] else "",
            amount=amount,
            description=" ".join(meta["description"]) if "description" in meta else None,
            comment=" ".join(meta["comment"]) if "comment" in meta else None,
            subholding_of=" ".join(meta["subholding_of"]) if "subholding_of" in meta else None,
            filing_status=" ".join(meta["filing_status"]) if "filing_status" in meta else None,
        )


def _page_body(words: list[Word], cols: Columns) -> list[Word]:
    """Words of the transaction table on one page: below the header, above the footer."""
    header_y = next(w.y0 for w in words if w.text == "Owner" and abs(w.x0 - cols.owner) < 3)
    body = [w for w in words if w.y0 > header_y + 20]
    # Stop at the footer: the asset-code reference line ("* For the complete list ...")
    # or the Initial Public Offerings heading (small caps render as "I P O").
    footer_y = None
    for ln in _lines(body):
        toks = [w.text for w in ln]
        if toks[:2] == ["*", "For"] or toks == ["I", "P", "O"] or toks[:2] == ["Digitally", "Signed:"]:
            footer_y = ln[0].y0 if footer_y is None else min(footer_y, ln[0].y0)
    if footer_y is not None:
        body = [w for w in body if w.y0 < footer_y - 1]
    return body


def _page_transactions(words: list[Word], cols: Columns, carry: _TxBuilder | None) -> list[_TxBuilder]:
    """Stream one page's table into transaction builders. `carry` is the last builder
    from the previous page; lines above this page's first anchor belong to it."""
    body = _page_body(words, cols)
    anchors = sorted(
        (w for w in body if abs(w.x0 - cols.tx_type) < 4 and w.text in ("P", "S", "E")),
        key=lambda w: w.y0,
    )
    builders: list[_TxBuilder] = []
    bounds = [a.y0 - 1 for a in anchors] + [1e9]
    if carry is not None and body:
        lead = [w for w in body if w.y0 < bounds[0]]
        if lead:
            carry.feed(_lines(lead), cols, same_page=False)
    for i, a in enumerate(anchors):
        seg = [w for w in body if bounds[i] <= w.y0 < bounds[i + 1]]
        b = _TxBuilder(a, cols)
        b.feed(_lines(seg), cols, same_page=True)
        builders.append(b)
    return builders


# STOCK Act reporting brackets. The lower bound determines the bracket, which lets
# us complete a range whose upper bound the House PDF generator dropped at a page break.
AMOUNT_BRACKETS = {
    "$1,001": "$15,000",
    "$15,001": "$50,000",
    "$50,001": "$100,000",
    "$100,001": "$250,000",
    "$250,001": "$500,000",
    "$500,001": "$1,000,000",
    "$1,000,001": "$5,000,000",
    "$5,000,001": "$25,000,000",
    "$25,000,001": "$50,000,000",
}


def _norm_amount(tokens: list[str]) -> str:
    s = " ".join(tokens)
    s = re.sub(r"\s*-\s*", " - ", s).strip()
    s = re.sub(r"\s+", " ", s)
    if s.endswith(" -") and s[:-2] in AMOUNT_BRACKETS:
        s = f"{s[:-2]} - {AMOUNT_BRACKETS[s[:-2]]}"
    return s


def parse_report(pdf_bytes: bytes, docid: str = "") -> Report:
    pages = pdf_words(pdf_bytes)
    filer = ""
    state_district = ""
    builders: list[_TxBuilder] = []
    for words in pages:
        if not filer:
            for ln in _lines(words):
                toks = [w.text for w in ln]
                if toks[:1] == ["Name:"]:
                    filer = " ".join(toks[1:])
                if toks[:1] == ["State/District:"] and len(toks) > 1:
                    state_district = toks[1]
        cols = _find_columns(words)
        if cols is None:
            continue  # pages without the table header carry no transactions
        builders.extend(_page_transactions(words, cols, builders[-1] if builders else None))
    return Report(docid=docid, filer=filer, state_district=state_district,
                  transactions=[b.build() for b in builders])

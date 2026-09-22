"""Senate Periodic Transaction Reports (STOCK Act).

Source: the Senate Office of Public Records electronic filing search.
  https://efdsearch.senate.gov/

The site requires accepting a usage notice (a cookie), then exposes a DataTables
JSON endpoint for searching filings and a plain HTML table for each electronic
report. Paper filings are scanned images and are reported as unreadable.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from bs4 import BeautifulSoup

BASE = "https://efdsearch.senate.gov"
HOME = f"{BASE}/search/home/"
SEARCH = f"{BASE}/search/"
DATA = f"{BASE}/search/report/data/"

REPORT_TYPE_PTR = 11
FILER_TYPE_SENATOR = 1


@dataclass
class SenateFiling:
    first: str
    last: str
    filer_label: str  # "Whitehouse, Sheldon (Senator)"
    url: str
    title: str
    filed: str  # YYYY-MM-DD

    @property
    def electronic(self) -> bool:
        return "/search/view/ptr/" in self.url

    @property
    def report_id(self) -> str:
        return self.url.rstrip("/").split("/")[-1]

    @property
    def surname(self) -> str:
        """Last name without a generational suffix ("McConnell, Jr." -> "McConnell")."""
        return self.last.split(",")[0].strip()


@dataclass
class SenateTransaction:
    tx_date: str  # YYYY-MM-DD
    owner: str
    ticker: str | None
    asset: str
    asset_type: str
    tx_type: str  # Purchase / Sale (Full) / Sale (Partial) / Exchange
    amount: str
    comment: str | None


@dataclass
class SenateReport:
    report_id: str
    filer: str
    title: str
    transactions: list[SenateTransaction] = field(default_factory=list)


def _us_date(s: str) -> str:
    m, d, y = s.strip().split("/")
    return f"{y}-{int(m):02d}-{int(d):02d}"


def accept_notice(session) -> str:
    """Accept the site's usage notice. Returns the CSRF token for later POSTs."""
    session.get(HOME, timeout=60)
    session.post(
        HOME,
        data={"prohibition_agreement": "1", "csrfmiddlewaretoken": session.cookies.get("csrftoken")},
        headers={"Referer": HOME},
        timeout=60,
    )
    return session.cookies.get("csrftoken")


def search_payload(start: int, length: int, submitted_start: str, last_name: str = "") -> dict:
    """DataTables request body for the PTR search."""
    p = {
        "draw": "1",
        "start": str(start),
        "length": str(length),
        "search[value]": "",
        "search[regex]": "false",
        "order[0][column]": "4",
        "order[0][dir]": "desc",
        "report_types": f"[{REPORT_TYPE_PTR}]",
        "filer_types": f"[{FILER_TYPE_SENATOR}]",
        "submitted_start_date": f"{submitted_start} 00:00:00",
        "submitted_end_date": "",
        "candidate_state": "",
        "senator_state": "",
        "office_id": "",
        "first_name": "",
        "last_name": last_name,
    }
    for i in range(5):
        p.update({
            f"columns[{i}][data]": str(i),
            f"columns[{i}][name]": "",
            f"columns[{i}][searchable]": "true",
            f"columns[{i}][orderable]": "true",
            f"columns[{i}][search][value]": "",
            f"columns[{i}][search][regex]": "false",
        })
    return p


def parse_search_rows(rows: list[list[str]]) -> list[SenateFiling]:
    out = []
    for first, last, label, link, filed in rows:
        m = re.search(r'href="([^"]+)"', link)
        title = re.sub(r"<[^>]+>", "", link).strip()
        out.append(
            SenateFiling(
                first=first.strip(),
                last=last.strip(),
                filer_label=label.strip(),
                url=BASE + m.group(1) if m else "",
                title=title,
                filed=_us_date(filed),
            )
        )
    return out


def list_filings(session, csrf: str, submitted_start: str) -> list[SenateFiling]:
    """All PTR filings by senators submitted on or after submitted_start (MM/DD/YYYY)."""
    filings: list[SenateFiling] = []
    start = 0
    while True:
        r = session.post(
            DATA,
            data=search_payload(start, 100, submitted_start),
            headers={"Referer": SEARCH, "X-CSRFToken": csrf, "X-Requested-With": "XMLHttpRequest"},
            timeout=60,
        )
        r.raise_for_status()
        d = r.json()
        rows = d.get("data", [])
        filings.extend(parse_search_rows(rows))
        start += len(rows)
        if not rows or start >= int(d.get("recordsTotal", 0)):
            break
    return filings


def parse_report(html: str, report_id: str = "") -> SenateReport:
    soup = BeautifulSoup(html, "lxml")
    h = soup.find("h1")
    title = h.get_text(" ", strip=True) if h else ""
    title = re.sub(r"\s+", " ", title)
    # Filer name is in the "The Honorable ..." block right under the title.
    filer = ""
    m = re.search(r"\(([^()]+)\)\s*$", " ".join(
        el.get_text(" ", strip=True) for el in soup.select("h2")
    ))
    if m:
        filer = m.group(1).strip()
    txs: list[SenateTransaction] = []
    table = soup.find("table")
    if table is not None:
        headers = [th.get_text(" ", strip=True) for th in table.find_all("th")]
        idx = {h: i for i, h in enumerate(headers)}
        for tr in table.find_all("tr"):
            cells = [td.get_text(" ", strip=True) for td in tr.find_all("td")]
            if len(cells) < len(headers) or not cells[0].isdigit():
                continue

            def col(name: str) -> str:
                return cells[idx[name]] if name in idx else ""

            ticker = col("Ticker")
            if ticker in ("--", "-", ""):
                ticker = None
            comment = col("Comment")
            if comment in ("--", ""):
                comment = None
            txs.append(
                SenateTransaction(
                    tx_date=_us_date(col("Transaction Date")),
                    owner=col("Owner"),
                    ticker=ticker,
                    asset=re.sub(r"\s+", " ", col("Asset Name")),
                    asset_type=col("Asset Type"),
                    tx_type=col("Type"),
                    amount=re.sub(r"\s+", " ", col("Amount")),
                    comment=comment,
                )
            )
    return SenateReport(report_id=report_id, filer=filer, title=title, transactions=txs)

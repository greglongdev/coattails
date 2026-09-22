"""Senate EFD parsing against real report pages."""
import json
import re

from conftest import FIX
from pipeline import senate

ISO = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def test_search_rows():
    rows = json.load(open(FIX / "senate_search_rows.json"))
    filings = senate.parse_search_rows(rows)
    assert len(filings) == 12
    f = filings[0]
    assert f.last == "McConnell, Jr." and f.first == "A. Mitchell"
    assert f.filer_label == "McConnell, A. Mitchell Jr. (Senator)"
    assert f.url.startswith("https://efdsearch.senate.gov/search/view/ptr/")
    assert f.electronic
    assert f.report_id == f.url.rstrip("/").split("/")[-1] and len(f.report_id) == 36
    assert f.filed == "2026-09-21"
    assert f.title == "Periodic Transaction Report for 09/21/2026"
    assert f.surname == "McConnell"
    paper = [x for x in filings if not x.electronic]
    assert all("/view/paper/" in x.url for x in paper)


def test_single_row_report():
    r = senate.parse_report((FIX / "senate_mcconnell.html").read_text(), "x")
    assert r.filer == "McConnell, A. Mitchell Jr."
    assert r.title == "Periodic Transaction Report for 09/21/2026"
    assert len(r.transactions) == 1
    t = r.transactions[0]
    assert t.tx_date == "2026-09-01"
    assert t.owner == "Spouse"
    assert t.ticker == "WFC"
    assert t.asset == "Wells Fargo & Company Common Stock"
    assert t.asset_type == "Stock"
    assert t.tx_type == "Purchase"
    assert t.amount == "$15,001 - $50,000"
    assert t.comment == "Dividend reinvestment"


def test_large_report_with_options():
    r = senate.parse_report((FIX / "senate_tuberville.html").read_text(), "y")
    assert r.filer == "Tuberville, Tommy"
    assert len(r.transactions) == 94
    opts = [t for t in r.transactions if t.asset_type == "Stock Option"]
    assert opts
    arkk = next(t for t in opts if t.ticker == "ARKK" and "Put" in t.asset)
    assert arkk.tx_type == "Purchase"
    assert "Strike price: $45.00" in arkk.asset
    assert arkk.comment is None  # "--" is rendered as no comment
    for t in r.transactions:
        assert ISO.match(t.tx_date)
        assert t.amount.startswith("$")
        assert t.tx_type in ("Purchase", "Sale (Full)", "Sale (Partial)", "Exchange")


def test_search_payload_shape():
    p = senate.search_payload(100, 100, "01/01/2025")
    assert p["report_types"] == "[11]" and p["filer_types"] == "[1]"
    assert p["start"] == "100"
    assert p["submitted_start_date"] == "01/01/2025 00:00:00"
    assert p["columns[4][data]"] == "4"

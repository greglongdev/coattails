"""House PTR parsing against real filings pulled from the Clerk's site."""
import re
import subprocess

from conftest import FIX
from pipeline import house

ISO = re.compile(r"^\d{4}-\d{2}-\d{2}$")
RANGE = re.compile(r"^(\$[\d,]+ - \$[\d,]+|Spouse/DC Over \$[\d,]+|Over \$[\d,]+|\$[\d,]+\.\d\d|None)$")


def _layout_text(path):
    return subprocess.run(["pdftotext", "-layout", str(path), "-"], capture_output=True, text=True).stdout


def test_index_parse_and_flags():
    entries = house.parse_index((FIX / "house_2026FD.zip").read_bytes())
    assert len(entries) > 1000
    ptrs = [e for e in entries if e.is_ptr]
    assert len(ptrs) == 396
    pelosi = [e for e in ptrs if e.last == "Pelosi"]
    assert {e.state_district for e in pelosi} == {"CA11"}
    assert all(e.electronic for e in pelosi)
    assert all(ISO.match(e.filing_date) for e in ptrs)
    e = next(x for x in pelosi if x.docid == "20035143")
    assert e.filing_date == "2026-08-21"
    assert e.pdf_url == "https://disclosures-clerk.house.gov/public_disc/ptr-pdfs/2026/20035143.pdf"
    paper = [e for e in ptrs if not e.electronic]
    assert len(paper) == 46


def test_pelosi_august_report():
    r = house.parse_report((FIX / "house_20035143.pdf").read_bytes(), "20035143")
    assert r.filer == "Hon. Nancy Pelosi"
    assert r.state_district == "CA11"
    assert len(r.transactions) == 7
    t = r.transactions[0]
    assert t.owner == "SP"
    assert t.ticker == "BE"
    assert t.asset_code == "ST"
    assert t.tx_type == "P"
    assert t.tx_date == "2026-07-24"
    assert t.notified == "2026-07-24"
    assert t.amount == "$1,000,001 - $5,000,000"
    assert t.description == "Purchased 10,000 shares."
    assert t.filing_status == "New"
    opt = r.transactions[1]
    assert opt.asset_code == "OP" and opt.ticker == "BE"
    assert opt.description.startswith("Purchased 100 call options with a strike price of $100")
    intc = [t for t in r.transactions if t.ticker == "INTC"]
    assert {t.asset_code for t in intc} == {"OP", "ST"}
    llc = r.transactions[-1]
    assert llc.asset_code == "AB" and llc.ticker is None
    assert llc.amount == "$500,001 - $1,000,000"
    assert "luxury hotel" in llc.description


def test_page_break_amount_completed_from_bracket():
    # The Clerk's PDF drops the wrapped upper bound when a row straddles a page.
    r = house.parse_report((FIX / "house_20034034.pdf").read_bytes(), "20034034")
    vz = next(t for t in r.transactions if t.ticker == "VZ")
    assert vz.amount == "$15,001 - $50,000"
    assert vz.tx_type == "S"
    assert vz.asset == "Verizon Communications Inc. Common Stock (VZ) [ST]"
    assert vz.filing_status == "New"


def test_exchange_with_exact_dollar_amount():
    r = house.parse_report((FIX / "house_20033725.pdf").read_bytes(), "20033725")
    ex = [t for t in r.transactions if t.tx_type == "E"]
    assert ex, "expected exchange rows"
    vsnt = next(t for t in ex if t.ticker == "VSNT")
    assert vsnt.amount == "$15.00"
    assert "spinoff from Comcast" in vsnt.description
    tem = next(t for t in r.transactions if t.ticker == "TEM")
    assert tem.amount == "$50,001 - $100,000"


def test_every_row_well_formed_and_count_matches_independent_check():
    for name in ("house_20035143.pdf", "house_20034034.pdf", "house_20033725.pdf"):
        path = FIX / name
        r = house.parse_report(path.read_bytes(), name)
        independent = len(re.findall(r"\d\d/\d\d/\d{4}\s+\d\d/\d\d/\d{4}", _layout_text(path)))
        assert len(r.transactions) == independent, name
        for t in r.transactions:
            assert ISO.match(t.tx_date) and ISO.match(t.notified), (name, t)
            assert RANGE.match(t.amount), (name, t.amount)
            assert t.asset and not re.search(r"\d\d/\d\d/\d{4}", t.asset), (name, t.asset)
            assert t.tx_type in ("P", "S", "S (partial)", "E")
            assert t.owner in house.OWNER_CODES


def test_bracket_table_is_the_stock_act_ladder():
    lows = list(house.AMOUNT_BRACKETS)
    assert lows[0] == "$1,001" and house.AMOUNT_BRACKETS["$1,001"] == "$15,000"
    assert house.AMOUNT_BRACKETS["$25,000,001"] == "$50,000,000"
    assert house._norm_amount(["$15,001", "-"]) == "$15,001 - $50,000"
    assert house._norm_amount(["$1,001", "-", "$15,000"]) == "$1,001 - $15,000"
    assert house._norm_amount(["$318.74"]) == "$318.74"

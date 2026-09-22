"""13F parsing and quarter assembly."""
import re

from conftest import FIX
from pipeline import sec13f


def _cover_totals(primary_xml: str):
    n = int(re.search(r"tableEntryTotal>(\d+)", primary_xml).group(1))
    v = int(re.search(r"tableValueTotal>(\d+)", primary_xml).group(1))
    return n, v


def test_berkshire_table_matches_cover_page_and_aggregates_by_cusip():
    xml = (FIX / "sec13f_berkshire_2026q2.xml").read_text()
    n_rows, total = _cover_totals((FIX / "sec13f_berkshire_2026q2_primary.xml").read_text())
    assert xml.count("<infoTable>") == n_rows == 89
    pos = sec13f.parse_info_table(xml)
    assert sum(p.value for p in pos) == total == 299253556246
    assert len(pos) == 29  # 89 rows, many issuers split across sub-managers
    ally = next(p for p in pos if p.cusip == "02005N100")
    assert ally.issuer == "ALLY FINL INC"
    assert ally.shares == 12561737 + 2803875 + 4228200 + sum(
        int(s) for s in re.findall(r"<cusip>02005N100</cusip>.*?<sshPrnamt>(\d+)</sshPrnamt>", xml, re.S)[3:]
    )
    assert all(p.put_call is None for p in pos)
    assert all(p.shares > 0 and p.value > 0 for p in pos)


def test_namespaced_table():
    pos = sec13f.parse_info_table((FIX / "sec13f_himalaya_2026q2.xml").read_text())
    assert len(pos) == 8
    goog = [p for p in pos if p.issuer == "ALPHABET INC"]
    assert {p.title for p in goog} == {"CAP STK CL A", "CAP STK CL C"}
    aapl = next(p for p in pos if p.cusip == "037833100")
    assert aapl.shares == 110600 and aapl.value == 32003216


def test_amendment_type_absent_on_notice():
    assert sec13f.amendment_type((FIX / "sec13f_pershing_nt_primary.xml").read_text()) is None
    assert sec13f.amendment_type("<x><amendmentType>RESTATEMENT</amendmentType></x>") == "RESTATEMENT"
    assert sec13f.amendment_type("<ns1:amendmentType> New Holdings </ns1:amendmentType>") == "NEW HOLDINGS"


def _f(cik, acc, form, filed, period="2026-06-30"):
    return sec13f.Filing(cik=cik, accession=acc, form=form, filed=filed, period=period)


def _p(cusip, shares, value, issuer="X", put_call=None, share_type="SH"):
    return sec13f.Position(cusip=cusip, issuer=issuer, title="COM", put_call=put_call, shares=shares,
                           value=value, share_type=share_type)


def test_thousands_scale_detected_and_corrected():
    # Baupost and Duquesne still report the value column in thousands.
    dollars = [_p("A", 1000, 150000), _p("B", 2000, 60000), _p("C", 500, 45000)]
    assert sec13f.scale_factor(dollars) == 1
    thousands = [_p("A", 1000, 150), _p("B", 2000, 60), _p("C", 500, 45)]
    assert sec13f.scale_factor(thousands) == 1000
    fixed = sec13f.rescale_if_thousands([_p("A", 1000, 150), _p("B", 2000, 60), _p("C", 500, 45)])
    assert [p.value for p in fixed] == [150000, 60000, 45000]
    # Too few rows to judge: left alone.
    assert sec13f.scale_factor([_p("A", 1000, 150), _p("B", 2000, 60)]) == 1
    # Bonds priced near par must not be mistaken for a thousands filing.
    bonds = [_p("A", 1000000, 990000, share_type="PRN"), _p("B", 500000, 501000, share_type="PRN"),
             _p("C", 100, 25000), _p("D", 200, 40000), _p("E", 300, 30000)]
    assert sec13f.scale_factor(bonds) == 1


def test_real_filings_are_dollar_scale():
    pos = sec13f.parse_info_table((FIX / "sec13f_berkshire_2026q2.xml").read_text())
    assert sec13f.scale_factor(pos) == 1
    assert sum(p.value for p in pos) == 299253556246


def test_assemble_quarter_restatement_replaces_new_holdings_adds():
    orig = _f(1, "0-1", "13F-HR", "2026-08-10")
    add = _f(1, "0-2", "13F-HR/A", "2026-09-01")
    restate = _f(1, "0-3", "13F-HR/A", "2026-09-15")
    tables = {
        "0-1": [_p("AAA", 100, 1000), _p("BBB", 50, 500)],
        "0-2": [_p("AAA", 10, 100), _p("CCC", 5, 50)],
        "0-3": [_p("AAA", 999, 9990)],
    }
    q = sec13f.assemble_quarter("2026-06-30", [orig, add], tables, {"0-2": "NEW HOLDINGS"})
    assert q.positions["AAA|"].shares == 110 and q.positions["CCC|"].shares == 5 and "BBB|" in q.positions
    assert q.filed == "2026-09-01"
    q = sec13f.assemble_quarter("2026-06-30", [orig, add, restate], tables, {"0-2": "NEW HOLDINGS", "0-3": "RESTATEMENT"})
    assert set(q.positions) == {"AAA|"} and q.positions["AAA|"].shares == 999


def test_assemble_quarter_sums_across_filer_entities():
    # Pershing Square Capital Management and Pershing Square Inc. both filed for
    # 2026-03-31; they are different books and must be summed, not replaced.
    a = _f(1336528, "a", "13F-HR", "2026-05-15", "2026-03-31")
    b = _f(2026053, "b", "13F-HR", "2026-05-15", "2026-03-31")
    tables = {"a": [_p("UBER", 100, 1000), _p("BN", 10, 100)], "b": [_p("UBER", 5, 50)]}
    q = sec13f.assemble_quarter("2026-03-31", [a, b], tables, {})
    assert q.positions["UBER|"].shares == 105 and q.positions["UBER|"].value == 1050
    assert q.positions["BN|"].shares == 10
    # And the source tables are not mutated.
    assert tables["a"][0].shares == 100


def test_diff_quarters_kinds_pct_and_put_call_separation():
    prior = sec13f.Quarter("2026-03-31", "2026-05-15", {
        "AAA|": _p("AAA", 100, 1000), "BBB|": _p("BBB", 100, 1000), "CCC|": _p("CCC", 100, 1000),
        "DDD|Put": _p("DDD", 100, 1000, put_call="Put"),
    })
    latest = sec13f.Quarter("2026-06-30", "2026-08-14", {
        "AAA|": _p("AAA", 150, 3000), "BBB|": _p("BBB", 40, 400), "EEE|": _p("EEE", 7, 70000),
        "DDD|": _p("DDD", 100, 1000),
    })
    ch = {(c.kind, c.position.cusip, c.position.put_call): c for c in sec13f.diff_quarters(latest, prior)}
    assert ch[("added", "AAA", None)].pct == 50.0
    assert ch[("reduced", "BBB", None)].pct == -60.0
    assert ("sold", "CCC", None) in ch and ch[("sold", "CCC", None)].shares == 0
    assert ("new", "EEE", None) in ch and ch[("new", "EEE", None)].pct is None
    # Puts on DDD closed; a common-stock position in DDD opened. Two events, not a change.
    assert ("sold", "DDD", "Put") in ch and ("new", "DDD", None) in ch
    assert sec13f.diff_quarters(latest, None) == []
    first = sec13f.diff_quarters(latest, prior)[0]
    assert first.position.cusip == "EEE"  # biggest dollar position first


def test_list_13f_filings_filters_forms():
    subs = {"cik": "1336528", "filings": {"recent": {
        "form": ["13F-NT", "13F-HR", "4", "13F-HR/A"],
        "accessionNumber": ["1", "2", "3", "4"],
        "filingDate": ["2026-08-14", "2026-05-15", "2026-06-08", "2025-08-14"],
        "reportDate": ["2026-06-30", "2026-03-31", "2026-06-04", "2025-03-31"],
    }}}
    fl = sec13f.list_13f_filings(subs)
    assert [f.form for f in fl] == ["13F-HR", "13F-HR/A"]
    assert fl[0].acc_nodash == "2"
    assert fl[0].index_url == "https://www.sec.gov/Archives/edgar/data/1336528/2/2-index.html"


def test_info_table_name_skips_primary_doc():
    idx = {"directory": {"item": [{"name": "primary_doc.xml"}, {"name": "56757.xml"}, {"name": "x-index.html"}]}}
    assert sec13f.info_table_name(idx) == "56757.xml"
    assert sec13f.info_table_name({"directory": {"item": [{"name": "primary_doc.xml"}]}}) is None

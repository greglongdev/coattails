"""Feed assembly, roster integrity, and the published feed's shape."""
import json
import re
from pathlib import Path

from conftest import ROOT
from pipeline import build, config, members

ISO = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def test_clean_asset_name():
    assert build.clean_asset_name("Bloom Energy Corporation Class A Common Stock (BE) [ST]") == "Bloom Energy Corporation Class A Common Stock"
    assert build.clean_asset_name("Intel Corporation - Common Stock (INTC) [OP]") == "Intel Corporation - Common Stock"
    assert build.clean_asset_name("REOF XXV, LLC [AB]") == "REOF XXV, LLC"


def test_recover_ticker_from_the_asset_name():
    assert build.recover_ticker("WFC", "Wells Fargo") == "WFC"
    assert build.recover_ticker(None, "SDZNY- Sandoz Group AG ADR") == "SDZNY"
    assert build.recover_ticker(None, "SDZNY - Sandoz Group AG") == "SDZNY"
    assert build.recover_ticker(None, "ACN - Accenture plc Class A Ordinary Shares (Ireland)") == "ACN"
    # Nothing to recover: a real name that merely contains a dash, or no dash at all.
    assert build.recover_ticker(None, "GS Managed Structured Note Strategy S&P 500 Linked Note") is None
    assert build.recover_ticker(None, "ROLLS-ROYCE HOLDINGS PLC ADR") is None
    assert build.recover_ticker(None, "Qualcomm Inc") is None
    assert build.recover_ticker(None, "") is None


def test_roster_integrity():
    ids = [p["id"] for p in config.POLITICIANS] + [i["id"] for i in config.INVESTORS]
    assert len(ids) == len(set(ids))
    for p in config.POLITICIANS:
        assert re.match(r"^[A-Z]\d{6}$", p["bioguide"]), p
        assert p["chamber"] in ("house", "senate")
        assert p["why"] and not p["why"].endswith("!")
        if p["chamber"] == "house":
            assert re.match(r"^[A-Z]{2}\d{2}$", p["state_district"])
    for i in config.INVESTORS:
        assert i["ciks"] and all(isinstance(c, int) for c in i["ciks"])


def test_members_parse():
    house_xml = """<MemberData><members><member><statedistrict>CA11</statedistrict><member-info>
      <bioguideID>P000197</bioguideID><lastname>Pelosi</lastname><firstname>Nancy</firstname>
      <official-name>Nancy Pelosi</official-name><party>D</party><district>11th</district></member-info></member>
      </members></MemberData>"""
    h = members.parse_house(house_xml)
    assert h["P000197"].state == "CA" and h["P000197"].party == "D" and h["P000197"].district == "11th"
    senate_xml = """<contact_information><member><member_full>Tuberville (R-AL)</member_full><last_name>Tuberville</last_name>
      <first_name>Tommy</first_name><party>R</party><state>AL</state><bioguide_id>T000278</bioguide_id></member></contact_information>"""
    s = members.parse_senate(senate_xml)
    assert s["T000278"].name == "Tommy Tuberville" and s["T000278"].state == "AL" and s["T000278"].district is None


def test_build_feed_orders_by_disclosure_and_filters_small_trims():
    people = [
        {"id": "pol", "group": "politician", "trades": [
            {"date": "2026-01-01", "disclosed": "2026-02-01", "action": "buy", "ticker": "A", "name": "A", "kind": "stock",
             "amount": "$1,001 - $15,000", "owner": "Self", "detail": None, "source": "https://x/1.pdf"},
            {"date": "2026-03-01", "disclosed": "2026-03-05", "action": "sell", "ticker": "B", "name": "B", "kind": "stock",
             "amount": "$1,001 - $15,000", "owner": "Self", "detail": None, "source": "https://x/2.pdf"},
        ]},
        {"id": "inv", "group": "investor", "quarters": [{"period": "2025-12-31", "filed": "2026-02-14", "source": "https://s/1"}],
         "changes": [
             {"kind": "added", "ticker": "C", "name": "C", "put_call": None, "shares": 110, "prev_shares": 100, "pct": 10.0, "value": 1},
             {"kind": "reduced", "ticker": "D", "name": "D", "put_call": None, "shares": 50, "prev_shares": 100, "pct": -50.0, "value": 1},
             {"kind": "new", "ticker": "E", "name": "E", "put_call": None, "shares": 5, "prev_shares": 0, "pct": None, "value": 1},
         ]},
        {"id": "empty", "group": "investor", "quarters": [], "changes": []},
    ]
    feed = build.build_feed(people)
    assert [e["ticker"] for e in feed] == ["B", "D", "E", "A"]
    assert feed[1]["type"] == "quarter" and feed[1]["date"] == "2026-02-14" and feed[1]["period"] == "2025-12-31"
    assert "C" not in {e["ticker"] for e in feed}  # a 10% add is not feed-worthy


def test_published_feed_shape():
    path = ROOT / "data" / "feed.json"
    if not path.exists():
        return
    d = json.loads(path.read_text())
    assert d["schema"] == 1
    assert re.match(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$", d["generated_at"])
    ids = {p["id"] for p in d["people"]}
    assert ids == {p["id"] for p in config.POLITICIANS} | {i["id"] for i in config.INVESTORS}
    for p in d["people"]:
        if p["group"] == "politician":
            assert p["title"].startswith(("Rep. ", "Sen. "))
            assert p["party"] in ("D", "R", "I") and len(p["state"]) == 2
            for t in p["trades"]:
                assert ISO.match(t["date"]) and ISO.match(t["disclosed"]), t
                assert t["action"] in ("buy", "sell", "exchange")
                assert t["kind"] in ("stock", "option", "etf", "crypto")
                assert t["source"].startswith("https://")
                assert t["amount"]
        else:
            assert p["quarters"], p["id"]
            latest = p["quarters"][-1]
            assert latest["source"].startswith("https://www.sec.gov/")
            assert abs(sum(h["weight"] for h in p["holdings"]) - 100) < 0.5, p["id"]
            assert p["holdings"] == sorted(p["holdings"], key=lambda h: -h["value"])
            for c in p["changes"]:
                assert c["kind"] in ("new", "added", "reduced", "sold")
    for e in d["feed"]:
        assert e["person"] in ids
        assert e["source"].startswith("https://")
    dates = [(e.get("disclosed") or e["date"], e["date"]) for e in d["feed"]]
    assert dates == sorted(dates, reverse=True)
    assert d["warnings"] == []

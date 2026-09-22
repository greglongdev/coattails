"""The consensus engine, and the rules that stop it lying."""
import json

from conftest import ROOT
from pipeline import consensus as c


def test_option_side_read_from_whatever_the_filing_wrote():
    assert c.option_side("Purchased 100 call options with a strike price of $100") == "call"
    assert c.option_side(None, "Ark Innovation ETF Option Type: Put Strike price: $45.00") == "put"
    assert c.option_side("Sold 5 PUTS") == "put"
    assert c.option_side("Purchased 10,000 shares.") is None
    assert c.option_side(None, None) is None


def test_buying_puts_is_bearish_not_bullish():
    # The rule that matters most: a bought put is a bet the stock falls.
    assert c.trade_direction("buy", "option", "put") == c.BEARISH
    assert c.trade_direction("buy", "option", "call") == c.BULLISH
    assert c.trade_direction("sell", "option", "call") == c.BEARISH
    # Selling a put is an income trade, only loosely bullish. Not claimed.
    assert c.trade_direction("sell", "option", "put") is None
    # An option whose side the filing never stated is not guessed at.
    assert c.trade_direction("buy", "option", None) is None


def test_plain_trade_directions():
    assert c.trade_direction("buy", "stock", None) == c.BULLISH
    assert c.trade_direction("sell", "stock", None) == c.BEARISH
    assert c.trade_direction("buy", "etf", None) == c.BULLISH
    # An exchange (a spinoff, a share conversion) is not a decision to own more or less.
    assert c.trade_direction("exchange", "stock", None) is None


def test_holding_directions_including_put_positions():
    assert c.holding_direction("new", None) == c.BULLISH
    assert c.holding_direction("added", None) == c.BULLISH
    assert c.holding_direction("reduced", None) == c.BEARISH
    assert c.holding_direction("sold", None) == c.BEARISH
    assert c.holding_direction("new", "Put") == c.BEARISH
    assert c.holding_direction("added", "put") == c.BEARISH
    assert c.holding_direction("sold", "Put") is None  # closing a bearish bet, not claimed
    assert c.holding_direction("new", "Call") == c.BULLISH


def test_phrases_are_plain_english():
    assert c.trade_phrase("buy", "stock", None) == "bought shares"
    assert c.trade_phrase("sell", "etf", None) == "sold an ETF"
    assert c.trade_phrase("buy", "option", "call") == "bought call options"
    assert c.trade_phrase("buy", "option", "put") == "bought put options"
    assert c.holding_phrase("new", None) == "opened a position"
    assert c.holding_phrase("reduced", None) == "cut a position"
    assert c.holding_phrase("new", "Put") == "opened a position in put options"


def _pol(pid, trades):
    return {"id": pid, "group": "politician", "trades": [
        dict({"ticker": "X", "name": "X Corp", "kind": "stock", "amount": "$1,001 - $15,000",
              "detail": None, "source": "https://x/1.pdf"}, **t) for t in trades]}


def _inv(pid, changes, period="2026-06-30"):
    rows = [dict({"ticker": "X", "name": "X CORP", "put_call": None}, **ch) for ch in changes]
    return {"id": pid, "group": "investor",
            "quarters": [{"period": period, "filed": "2026-08-14", "source": "https://sec/1"}],
            "changes": rows, "quarter_changes": {period: rows}}


def test_a_person_pointing_both_ways_in_one_period_is_dropped():
    # An option roll: closed and reopened the same day, so no view that day.
    people = [
        _pol("a", [{"action": "buy", "date": "2026-08-01"}, {"action": "sell", "date": "2026-08-01"}]),
        _pol("b", [{"action": "buy", "date": "2026-08-02"}]),
        _pol("d", [{"action": "buy", "date": "2026-08-03"}]),
    ]
    out = c.build(people, "2026-09-22")
    assert len(out["groups"]) == 1
    g = out["groups"][0]
    assert g["direction"] == "bullish"
    assert [m["person"] for m in g["people"]] == ["d", "b"]  # newest first
    assert "a" not in [m["person"] for m in g["people"]]


def test_a_change_of_mind_across_periods_takes_the_newer_view():
    # Selling in May and buying in August is not indecision, it is a position.
    # Judging the whole window at once used to drop anyone active.
    people = [
        _pol("a", [{"action": "sell", "date": "2026-05-01"}, {"action": "buy", "date": "2026-08-01"}]),
        _pol("b", [{"action": "buy", "date": "2026-08-02"}]),
    ]
    g = c.build(people, "2026-09-22")["groups"]
    assert len(g) == 1 and g[0]["direction"] == "bullish"
    assert {m["person"] for m in g[0]["people"]} == {"a", "b"}


def test_an_unsettled_newest_period_falls_back_to_the_last_settled_one():
    people = [
        _pol("a", [{"action": "buy", "date": "2026-06-01"},
                   {"action": "buy", "date": "2026-08-01"}, {"action": "sell", "date": "2026-08-01"}]),
        _pol("b", [{"action": "buy", "date": "2026-08-02"}]),
    ]
    g = c.build(people, "2026-09-22")["groups"][0]
    rows = {m["person"]: m for m in g["people"]}
    assert rows["a"]["date"] == "2026-06-01"


def test_every_move_a_person_made_in_the_period_is_named():
    # Adding to a holding and buying calls on it in the same quarter is two moves.
    # Keeping only one hid the bigger leg and made the smaller look like the story.
    inv = {"id": "a", "group": "investor",
           "quarters": [{"period": "2026-06-30", "filed": "2026-08-14", "source": "https://sec/1"}],
           "quarter_changes": {"2026-06-30": [
               {"ticker": "X", "name": "X CORP", "put_call": None, "kind": "added", "value": 129_085_000},
               {"ticker": "X", "name": "X CORP", "put_call": "Call", "kind": "added", "value": 109_470_000},
           ]}}
    people = [inv, _pol("b", [{"action": "buy", "date": "2026-08-02"}])]
    g = c.build(people, "2026-09-22")["groups"][0]
    row = [m for m in g["people"] if m["person"] == "a"][0]
    assert row["did"] == "added to a position, and added to a position in call options"
    assert row["amount"] == "$129M"          # the larger leg leads
    assert g["count"] == 2                    # still one person, not two


def test_both_ways_rule_only_affects_the_company_involved():
    people = [
        _pol("a", [{"action": "buy", "date": "2026-08-01"},
                   {"action": "sell", "date": "2026-08-01"},
                   {"action": "buy", "ticker": "Y", "name": "Y Inc", "date": "2026-08-04"}]),
        _pol("b", [{"action": "buy", "ticker": "Y", "name": "Y Inc", "date": "2026-08-05"}]),
    ]
    out = c.build(people, "2026-09-22")
    assert [g["ticker"] for g in out["groups"]] == ["Y"]
    assert {m["person"] for m in out["groups"][0]["people"]} == {"a", "b"}


def test_one_person_is_not_a_consensus():
    assert c.build([_pol("a", [{"action": "buy", "date": "2026-08-01"}])], "2026-09-22")["groups"] == []


def test_a_person_counts_once_per_company_with_their_newest_move():
    people = [
        _pol("a", [{"action": "buy", "date": "2026-05-01"}, {"action": "buy", "date": "2026-08-01"}]),
        _pol("b", [{"action": "buy", "date": "2026-07-01"}]),
    ]
    g = c.build(people, "2026-09-22")["groups"][0]
    assert g["count"] == 2
    assert [m["date"] for m in g["people"]] == ["2026-08-01", "2026-07-01"]


def test_the_window_is_exactly_as_long_as_it_claims():
    since = c.build([], "2026-09-22")["since"]
    import datetime as dt
    span = (dt.date(2026, 9, 22) - dt.date.fromisoformat(since)).days + 1
    assert span == c.WINDOW_DAYS


def test_put_and_call_flags_are_read_however_the_filer_typed_them():
    for raw in ("Put", "PUT ", "puts", "P"):
        assert c.normalise_put_call(raw) == "put", raw
        assert c.holding_direction("new", raw) == c.BEARISH, raw
        assert "put options" in c.holding_phrase("new", raw)
    for raw in ("Call", "c", "calls"):
        assert c.normalise_put_call(raw) == "call", raw
        assert c.holding_direction("new", raw) == c.BULLISH, raw
    assert c.normalise_put_call(None) is None and c.normalise_put_call("") is None
    # A flag that is present but unreadable is never treated as an ordinary holding.
    assert c.normalise_put_call("Protective") is False
    assert c.holding_direction("new", "Protective") is None


def test_closing_an_options_position_is_not_the_opposite_bet():
    # The mirror of the put rule: unwinding a bet is not taking the other side.
    assert c.holding_direction("sold", "Call") is None
    assert c.holding_direction("reduced", "Call") is None
    assert c.holding_direction("sold", "Put") is None


def test_only_a_buy_or_a_sell_is_directional():
    for action in ("exchange", "other", ""):
        for kind in ("stock", "option", "etf"):
            assert c.trade_direction(action, kind, "call") is None, (action, kind)
            assert c.trade_direction(action, kind, None) is None, (action, kind)


def test_option_text_counts_whatever_the_row_was_coded_as():
    # A put miscoded as an ordinary stock row must still be read as bearish.
    assert c.trade_direction("buy", "stock", "put") == c.BEARISH


def test_window_excludes_older_moves():
    people = [
        _pol("a", [{"action": "buy", "date": "2026-09-01"}]),
        _pol("b", [{"action": "buy", "date": "2025-01-01"}]),
    ]
    assert c.build(people, "2026-09-22")["groups"] == []
    assert c.build(people, "2026-09-22", window_days=900)["groups"][0]["count"] == 2


def test_investors_are_dated_to_their_quarter_not_their_filing_day():
    people = [_inv("a", [{"kind": "new"}]), _pol("b", [{"action": "buy", "date": "2026-08-01"}])]
    g = c.build(people, "2026-09-22")["groups"][0]
    rows = {m["person"]: m for m in g["people"]}
    assert rows["a"]["date"] == "2026-06-30"
    assert rows["a"]["when"] == "the quarter ending Jun 2026"
    assert rows["a"]["did"] == "opened a position"
    assert rows["a"]["source"] == "https://sec/1"


def test_a_politician_and_an_investor_can_agree():
    people = [_inv("fund", [{"kind": "added"}]), _pol("rep", [{"action": "buy", "date": "2026-08-01"}])]
    g = c.build(people, "2026-09-22")["groups"][0]
    assert g["count"] == 2
    assert {m["person"] for m in g["people"]} == {"fund", "rep"}


def test_opposite_directions_make_two_groups_not_one():
    people = [
        _pol("a", [{"action": "buy", "date": "2026-08-01"}]),
        _pol("b", [{"action": "buy", "date": "2026-08-02"}]),
        _pol("cc", [{"action": "sell", "date": "2026-08-03"}]),
        _pol("dd", [{"action": "sell", "date": "2026-08-04"}]),
    ]
    out = c.build(people, "2026-09-22")
    assert sorted(g["direction"] for g in out["groups"]) == ["bearish", "bullish"]


def test_ordering_is_most_agreed_then_most_recent():
    people = [
        _pol("a", [{"action": "buy", "date": "2026-08-01"}]),
        _pol("b", [{"action": "buy", "date": "2026-08-01"}]),
        _pol("cc", [{"action": "buy", "date": "2026-08-01"}]),
        _pol("d", [{"action": "buy", "ticker": "Y", "name": "Y Inc", "date": "2026-09-10"}]),
        _pol("e", [{"action": "buy", "ticker": "Y", "name": "Y Inc", "date": "2026-09-10"}]),
        _pol("f", [{"action": "buy", "ticker": "Z", "name": "Z Ltd", "date": "2026-04-01"}]),
        _pol("g", [{"action": "buy", "ticker": "Z", "name": "Z Ltd", "date": "2026-04-01"}]),
    ]
    out = c.build(people, "2026-09-22")
    assert [g["ticker"] for g in out["groups"]] == ["X", "Y", "Z"]


def test_canonical_name_picks_the_readable_one():
    assert c.canonical_name(["Microsoft Corporation - Common Stock", "MICROSOFT CORP"]) == "Microsoft Corporation"
    assert c.canonical_name(["ALPHABET INC"]) == "ALPHABET INC"
    assert c.canonical_name(["Uber Technologies, Inc. - Common Stock"]) == "Uber Technologies, Inc."
    assert c.canonical_name([]) == ""
    # "COM" is a share class on a 13F, but it is also the start of "Company".
    assert c.canonical_name(["Taiwan Semiconductor Manufacturing Company Ltd. - Common Stock"]) \
        == "Taiwan Semiconductor Manufacturing Company Ltd."
    assert c.canonical_name(["Compass Minerals"]) == "Compass Minerals"
    assert c.canonical_name(["ALLY FINL INC COM"]) == "ALLY FINL INC"
    # EDGAR truncates issuer names; the truncation is a prefix of the full name.
    assert c.canonical_name(["Taiwan Semiconductor Manufac",
                             "Taiwan Semiconductor Manufacturing Company Ltd. - Common Stock"]) \
        == "Taiwan Semiconductor Manufacturing Company Ltd."
    assert c.canonical_name(["Amazon", "Amazon.com, Inc. - Common Stock"]) == "Amazon.com, Inc."


def test_against_the_real_feed():
    path = ROOT / "data" / "feed.json"
    if not path.exists():
        return
    feed = json.loads(path.read_text())
    out = c.build(feed["people"], feed["generated_at"][:10])
    assert out["groups"], "the real data should produce consensus"
    ids = {p["id"] for p in feed["people"]}
    seen_people = set()
    for g in out["groups"]:
        assert g["count"] >= 2
        assert len({m["person"] for m in g["people"]}) == g["count"], g["ticker"]
        assert g["direction"] in ("bullish", "bearish")
        assert g["ticker"] and g["name"]
        for m in g["people"]:
            assert m["person"] in ids
            assert m["source"].startswith("https://")
            assert m["did"] and not any(t in m["did"] for t in ("None", "undefined"))
            seen_people.add(m["person"])
    counts = [g["count"] for g in out["groups"]]
    assert counts == sorted(counts, reverse=True)
    # Gottheimer rolls Microsoft options, buying and selling on the same day, so the
    # both-ways rule must keep him out of the Microsoft group entirely.
    msft = [g for g in out["groups"] if g["ticker"] == "MSFT"]
    for g in msft:
        assert "gottheimer" not in {m["person"] for m in g["people"]}

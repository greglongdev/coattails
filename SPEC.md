# Gonka Capital — SPEC

A personal app for one reader. It shows what well-known investors and members of
Congress are buying and selling, read from the filings they are required to make.

## Feature: Consensus (2026-09-22)

### Why

The app was a ledger: 2,091 events, newest first, half of them from two people.
The reader had to do all the synthesis himself. The single most valuable pattern
in this data is the one no per-trade view can show: **when more than one of these
people make the same move on the same company.**

The data supports it. Over 180 days, 23 tickers were bought by two or more of
them, the deepest four to five people deep, and the overlap crosses the divide
that the app otherwise keeps separate: TSM is Druckenmiller, Tepper, Terry Smith
and Rep. Cleo Fields. UBER is Ackman, Tepper, Smith and Rep. Pelosi.

It also makes a separate "composite portfolio" screen unnecessary. Of 228 tickers
the investors hold, only 26 are held by more than one, so a "what would I own"
list either runs to 228 names or collapses into this one.

### What it shows

A screen, first in the tab bar and the one the app opens on, listing companies
that two or more of the followed people moved the same way inside the window,
most agreed-upon first. Two groups: buying, and selling or betting against.
Tapping a company shows every person, what exactly they did, when, for how much,
each with a link to the filing it came from.

### The rules that keep it honest

These exist because the raw data will mislead without them.

1. **Direction, not action.** A purchase of put options is a bet that a stock
   falls. Counting it as "buying" would be flatly wrong. Every row resolves to
   bullish or bearish:

   | What was filed | Direction |
   | --- | --- |
   | Bought shares or an ETF | bullish |
   | Sold shares or an ETF | bearish |
   | Bought call options | bullish |
   | Sold call options | bearish |
   | Bought put options | **bearish** |
   | 13F: opened or added to a position | bullish |
   | 13F: cut or closed a position | bearish |
   | 13F: opened or added to a put position | **bearish** |
   | Sold put options | ambiguous, excluded |
   | 13F: closed or cut any options position | ambiguous, excluded |
   | Anything that is not a buy or a sell (an exchange, an unread code) | excluded |

   Unwinding a bet is not the opposite bet, which is why closing an options
   position is excluded in both directions. The put/call flag is whatever text
   the filer typed, so it is read loosely ("P", "Put", "puts" all count), and a
   flag that cannot be read is never treated as an ordinary holding.

   Put and call are stated in every filing that has options; a check across the
   whole feed found zero rows where it could not be determined.

2. **A person's direction is their most recent settled one.** Two different
   things look alike in this data and need different answers.

   Inside a single period, a day for a congressional trade and a quarter for a
   13F, pointing both ways is not a view at all: it is a position closed and
   reopened. That period is thrown away. Gottheimer rolls Microsoft options on 4
   of his 14 Microsoft days, and without this he would look like he was dumping
   a stock he was merely rolling.

   Across periods it is a change of mind, and the newest one is what the person
   thinks now. Judging the whole window at once conflated the two and silently
   dropped anyone active: Druckenmiller trimmed Amazon in one quarter and took
   it from 45,800 to 541,600 shares in the next, which is a position, not a
   shrug. The narrow rule excludes 1 person-company pair in the current data;
   the window-wide version excluded 81.

   Where a person made several moves one way in that period, all of them are
   named and the largest leads, so adding to a holding and buying calls on it
   reads as both rather than as whichever row happened to be last.

3. **Trade dates, not filing dates.** Congressional trades are dated when they
   happened. A 13F describes a quarter, so its changes are attributed to that
   quarter's end date. Aligning on filing dates instead would put an investor's
   April move and a politician's September move in the same "window" while
   actually describing periods that never overlap.

4. **Two people is the floor.** One person is not a consensus. The window is 180
   days ending today, inclusive at both ends, which covers six months of
   congressional trades and the two most recent 13F quarters. Both of those
   quarters contribute: each quarter-over-quarter change list is kept, not only
   the newest, or an investor's older move could never agree with anything.

### Acceptance criteria

- [x] `pipeline/consensus.py` builds groups from the same feed the app already
      has, with no new data source and no new network call.
- [x] Buying put options places a person in the bearish group, never the bullish one.
- [x] A person with both directions inside one period is dropped for that period.
- [x] Groups sort by number of people, then by most recent move.
- [x] Every person inside every group carries the URL of their own filing.
- [x] The screen is first in the tab bar and is what the app opens on.
- [x] Each person's action reads in plain English ("bought call options", "cut a
      position"), never a code or a raw filing term.
- [x] Tests cover each direction rule, the both-ways exclusion, the ordering, and
      the real feed.
- [x] Copy gate passes on the new screen.
- [x] Verified running on a device, not only in tests.

### Deliberately not built

- No price data, so no implied performance. Range-based disclosures published
  weeks late cannot produce an honest return figure.
- No scoring or ranking of the people themselves, for the same reason.
- No buy buttons or broker links. This is a reference, not advice.

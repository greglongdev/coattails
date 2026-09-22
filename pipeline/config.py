"""Who Gonka Capital follows, and why. Read WHO.md for the reasoning.

Every entry is verifiable from a primary source. Politicians must be current
members of Congress (checked against the official membership lists at build
time) who file electronically. Managers must still be filing 13Fs.
"""

USER_AGENT = "Gonka Capital data pipeline (personal use) gdrums650@gmail.com"

# "short" is how a person is named in a list of several. Guessing it from the full
# name gets "Trust" for the Gates Foundation and drops half of a compound surname.

# Politicians: matched to filings by exact last name + first-name prefix, and to
# the membership list by bioguide id. `house_state_district` / `senate_state`
# pin the match so a same-surname member never collides.
POLITICIANS = [
    {"id": "pelosi", "short": "Pelosi", "name": "Nancy Pelosi", "chamber": "house", "bioguide": "P000197",
     "match": {"last": "Pelosi", "first": "Nancy"}, "state_district": "CA11",
     "why": "The name everyone asks about. Few trades, large sizes, often long-dated call options."},
    {"id": "gottheimer", "short": "Gottheimer", "name": "Josh Gottheimer", "chamber": "house", "bioguide": "G000583",
     "match": {"last": "Gottheimer", "first": "Josh"}, "state_district": "NJ05",
     "why": "One of the most active traders in the House, with regular six-figure positions."},
    {"id": "hern", "short": "Hern", "name": "Kevin Hern", "chamber": "house", "bioguide": "H001082",
     "match": {"last": "Hern", "first": "Kevin"}, "state_district": "OK01",
     "why": "Frequent large trades across energy, industrials and tech."},
    {"id": "mcclain-delaney", "short": "McClain Delaney", "name": "April McClain Delaney", "chamber": "house", "bioguide": "M001232",
     "match": {"last": "Delaney", "first": "April"}, "state_district": "MD06",
     "why": "Among the highest trade counts in the House in 2026, with many trades above $50,000."},
    {"id": "fields", "short": "Fields", "name": "Cleo Fields", "chamber": "house", "bioguide": "F000110",
     "match": {"last": "Fields", "first": "Cleo"}, "state_district": "LA06",
     "why": "Trades in his own name, mostly large-cap tech, regularly above $50,000."},
    {"id": "jackson", "short": "Jackson", "name": "Jonathan Jackson", "chamber": "house", "bioguide": "J000309",
     "match": {"last": "Jackson", "first": "Jonathan"}, "state_district": "IL01",
     "why": "Steady flow of mid-size to large stock purchases."},
    {"id": "tuberville", "short": "Tuberville", "name": "Tommy Tuberville", "chamber": "senate", "bioguide": "T000278",
     "match": {"last": "Tuberville", "first": "Thomas"}, "state": "AL",
     "why": "The most-watched trader in the Senate by volume."},
    {"id": "mccormick", "short": "McCormick", "name": "David McCormick", "chamber": "senate", "bioguide": "M001243",
     "match": {"last": "McCormick", "first": "David"}, "state": "PA",
     "why": "Former CEO of Bridgewater Associates, the largest hedge fund. Every 2026 trade was above $50,000."},
    {"id": "whitehouse", "short": "Whitehouse", "name": "Sheldon Whitehouse", "chamber": "senate", "bioguide": "W000802",
     "match": {"last": "Whitehouse", "first": "Sheldon"}, "state": "RI",
     "why": "Long-tenured senator with a steady monthly filing cadence."},
    {"id": "hickenlooper", "short": "Hickenlooper", "name": "John Hickenlooper", "chamber": "senate", "bioguide": "H000273",
     "match": {"last": "Hickenlooper", "first": "John"}, "state": "CO",
     "why": "Infrequent but large trades."},
]

# Managers: 13F filers. `ciks` lists every filer entity whose 13F carries the
# portfolio, newest first, because firms restructure (Pershing Square's holdings
# moved to its public parent in 2026).
INVESTORS = [
    {"id": "buffett", "short": "Buffett", "name": "Warren Buffett", "firm": "Berkshire Hathaway", "ciks": [1067983],
     "why": "The longest public track record in investing. Berkshire's stock portfolio, reported quarterly."},
    {"id": "ackman", "short": "Ackman", "name": "Bill Ackman", "firm": "Pershing Square", "ciks": [2026053, 1336528],
     "why": "About a dozen large, concentrated positions held for years."},
    {"id": "li-lu", "short": "Li Lu", "name": "Li Lu", "firm": "Himalaya Capital", "ciks": [1709323],
     "why": "Charlie Munger's pick to manage family money. A handful of positions, rarely traded."},
    {"id": "pabrai", "short": "Pabrai", "name": "Mohnish Pabrai", "firm": "Dalal Street", "ciks": [1549575],
     "why": "Concentrated value portfolio, openly modeled on Buffett."},
    {"id": "druckenmiller", "short": "Druckenmiller", "name": "Stanley Druckenmiller", "firm": "Duquesne Family Office", "ciks": [1536411],
     "why": "One of the best long-term records in macro investing. Moves faster than the others here."},
    {"id": "tepper", "short": "Tepper", "name": "David Tepper", "firm": "Appaloosa", "ciks": [1656456],
     "why": "Concentrated bets, often in beaten-down sectors."},
    {"id": "klarman", "short": "Klarman", "name": "Seth Klarman", "firm": "Baupost Group", "ciks": [1061768],
     "why": "Deep-value investor, author of Margin of Safety."},
    {"id": "hohn", "short": "Hohn", "name": "Chris Hohn", "firm": "TCI Fund Management", "ciks": [1647251],
     "why": "A dozen high-quality compounders held for the long run."},
    {"id": "smith", "short": "Terry Smith", "name": "Terry Smith", "firm": "Fundsmith", "ciks": [1569205],
     "why": "Buy good companies, don't overpay, do nothing. The US-listed part of the portfolio."},
    {"id": "gates-trust", "short": "Gates Foundation", "name": "Gates Foundation Trust", "firm": "Gates Foundation Trust", "ciks": [1166559],
     "why": "The foundation's endowment: a few very large, very patient positions."},
]

# How far back the politician feed reaches. The 119th Congress began 2025-01-03.
POLITICIAN_SINCE = "2025-01-01"
HOUSE_YEARS = [2025, 2026]
SENATE_SUBMITTED_START = "01/01/2025"

# Quarters of 13F history kept per manager (latest N; the diff needs two).
QUARTERS_KEPT = 3

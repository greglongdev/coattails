# Coattails

An Android app that shows what well-known investors and members of Congress are
buying and selling, read straight from the filings they are legally required to
make. No accounts, no ads, no tracking. It works offline and refreshes itself.

Who is on the list, and why, is in [WHO.md](WHO.md).

## Layout

```
pipeline/   the data pipeline: reads the primary sources, writes data/feed.json
web/        the whole app. Vanilla JS, no dependencies, works offline
android/    WebView wrapper. ./gradlew assembleDebug builds the sideloadable APK
tests/      Node tests for the app (node --test tests/*.test.mjs)
data/       feed.json (published), cusip_map.json (cache), cache/ (not committed)
```

## The sources

| What | Where it comes from | Lag |
| --- | --- | --- |
| House trades | Clerk of the House financial disclosure PDFs | up to 45 days |
| Senate trades | Senate Office of Public Records filing site | up to 45 days |
| Investor holdings | SEC EDGAR Form 13F | up to 45 days after quarter end |
| Ticker for a CUSIP | OpenFIGI mapping API (cached in the repo) | n/a |
| Who is in office | Clerk of the House and Senate membership lists | current |

Everything is free and needs no API key. The SEC asks for a descriptive
User-Agent, which `pipeline/config.py` sets.

Two things the app will not do: guess, and imply performance. House members who
file on paper produce scanned images, and their pages say how many reports could
not be read rather than showing a parsed approximation. No returns are shown,
because range-based disclosures published weeks late cannot produce an honest one.

## Running the pipeline

```
sudo apt-get install poppler-utils           # pdftotext, used to read House PDFs
pip install requests beautifulsoup4 lxml pytest
python -m pipeline.build                     # fetch and rebuild data/feed.json
python -m pipeline.build --offline           # rebuild from the local cache only
python scripts/bundle.py                     # embed the feed into the app
```

`data/cache/` keeps every filing already downloaded, so a rerun only fetches what
is new. A full cold build takes about three minutes.

## Tests

```
python -m pytest pipeline/tests -q   # 25 tests, run against real filings
node --test tests/*.test.mjs   # 13 tests, run against the real feed
```

The pipeline fixtures are actual PDFs and XML pulled from the Clerk, the Senate
and the SEC, including the awkward ones: a report whose row straddles a page
break, an exchange with an exact dollar amount, a namespaced 13F table, and a
filer who reports values in thousands.

## Building the APK

```
python scripts/bundle.py
cd android && ./gradlew assembleDebug
```

The APK lands at `android/app/build/outputs/apk/debug/app-debug.apk`. It is debug
signed, which is what sideloading needs; it is not for the Play Store.

## Installing on a phone

1. Put the APK in Google Drive and share the link, or copy it over USB.
2. On the phone, open the file. Android asks permission to install from that app
   once; allow it.
3. Open Coattails.

The app carries a copy of the data, so it works the moment it opens, with or
without a signal. When it is online it checks for a newer copy and keeps it.

## Keeping the data fresh

`.github/workflows/refresh.yml` rebuilds the feed every morning, runs both test
suites, and commits `data/feed.json` if anything changed. The installed app reads
that file from the repository, so phones stay current without anyone reinstalling
anything. If the repository is private or the workflow is off, the app keeps
showing the data built into the APK and says when it was built.

## Not investment advice

Coattails reports public filings. It does not recommend anything.

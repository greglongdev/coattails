# Gonka Capital — STATE

Stage: **ship**. Built and delivered 2026-09-22. No revenue, none planned.

## What is verified working

- 77 tests green: 50 python (`python -m pytest pipeline/tests -q`), 27 node (`node --test tests/*.test.mjs`).
- APK at `GonkaCapital-v1.0.0.apk`, installed and driven on two emulators: Android 14 (API 34) and Android 16 (API 36).
- Daily GitHub Action `refresh data` rebuilds `data/feed.json` from the primary sources and commits it; verified green three times, including one run that committed a real refresh.
- The installed app fetches that file and shows the live date in green; verified on a clean install.
- Every one of the 2,091 feed items deep-links to its own filing.

## Fixed 2026-09-22

1. **Accessibility regression (mine).** `setTextZoom(100)` was making the app ignore the phone's font-size setting. Removed. Verified at 1.5x system font on Android 16: nothing hides behind the bars.
   Two bugs surfaced while fixing it, both found on device and both now covered by tests:
   - The bars measured their own height and wrote it back into their own `min-height`. Sub-pixel rounding then grew the header by 1px on every ResizeObserver tick (242, 243, 244...). The measurement now drives the body's padding only, never the bars themselves.
   - Android reports the status bar as *padding*, which leaves the content box unchanged, so a default ResizeObserver never fired and the page kept a too-small header height. The observer now watches the border box, with timed re-reads as a backstop.
2. **Source links on About.** Five rows linking to the House Clerk, the Senate EFD, the SEC on Form 13F, the House Ethics Committee on the STOCK Act, and this repo. Each verified to resolve and to open in the phone's browser rather than inside the app.

## Shipped 2026-09-22 (second pass)

3. **Consensus, as the Agreed screen.** Companies two or more of the twenty moved
   the same way inside 180 days, most agreed-upon first, split into Buying and
   Selling. Tapping one lists every contributor, what they did in plain English,
   when, how much where the filing says, and a link to that filing. It is the
   first tab and the screen the app opens on. Engine at `pipeline/consensus.py`,
   rules in SPEC.md, reasoning in DECISIONS.md.
   Current real output: 51 companies. The deepest are MSFT with six sellers and
   GOOG with five buyers (Buffett, Tepper, Klarman, Hohn and Rep. Fields).
   Gottheimer is correctly absent from the Microsoft group because he rolled
   options rather than taking a side.

   A fresh-context adversarial review of this feature found eleven defects, all
   fixed in the same session. The four that were live: the people line named the
   Gates Foundation Trust "Trust" and truncated a compound surname; a person's
   second move in a quarter was silently dropped, so Druckenmiller's Amazon row
   showed his smaller options leg and hid a larger share purchase; one malformed
   remote publish could be cached before it was proven to render, which bricked
   the app permanently; and 13F rows carried no amount. The rest were latent:
   an exchange on an option counted as a sale, an unrecognised put/call flag
   read as an ordinary holding, closing a call counted as bearish, the window
   was 181 days. Two more found by hand afterwards: the app re-formatted
   already-formatted amounts and stripped their B and M, and the back gesture
   left the app instead of closing an open sheet.

## Known defects, not fixed

3. **The feed repeats itself.** Same person, same ticker, same day arrives as separate cards (4 identical-looking MSFT rows lead the feed today). Nothing is wrong in the data; the presentation just refuses to group.
4. **Two people are half the feed.** Gottheimer (560) and McClain Delaney (486) of 2,091 events. There is no way to mute anyone, so the quiet, higher-signal filers are buried.

## Constraint position

The software domain constraint is distribution, not features (`~/.constraint/constraints.md`, reviewed 2026-09-16). This app has an audience of one by design and no revenue path, so feature work on it fails the check filter as portfolio work. It is a gift: the budget is Greg-minutes, not portfolio hours. Recorded so a future session does not mistake it for a growth asset.

## Next action

Greg decides whether this gets any more hours. If yes, the ranked plan is in the 2026-09-22 `/forge` run output; defects 1 and 2 are the cheap ones and defect 1 is a genuine bug rather than an enhancement.

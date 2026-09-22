# Gonka Capital — STATE

Stage: **ship**. Built and delivered 2026-09-22. No revenue, none planned.

## What is verified working

- 41 tests green: 26 python (`python -m pytest pipeline/tests -q`), 15 node (`node --test tests/*.test.mjs`).
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

## Known defects, not fixed

3. **The feed repeats itself.** Same person, same ticker, same day arrives as separate cards (4 identical-looking MSFT rows lead the feed today). Nothing is wrong in the data; the presentation just refuses to group.
4. **Two people are half the feed.** Gottheimer (560) and McClain Delaney (486) of 2,091 events. There is no way to mute anyone, so the quiet, higher-signal filers are buried.

## Constraint position

The software domain constraint is distribution, not features (`~/.constraint/constraints.md`, reviewed 2026-09-16). This app has an audience of one by design and no revenue path, so feature work on it fails the check filter as portfolio work. It is a gift: the budget is Greg-minutes, not portfolio hours. Recorded so a future session does not mistake it for a growth asset.

## Next action

Greg decides whether this gets any more hours. If yes, the ranked plan is in the 2026-09-22 `/forge` run output; defects 1 and 2 are the cheap ones and defect 1 is a genuine bug rather than an enhancement.

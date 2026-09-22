# Gonka Capital — STATE

Stage: **ship**. Built and delivered 2026-09-22. No revenue, none planned.

## What is verified working

- 41 tests green: 26 python (`python -m pytest pipeline/tests -q`), 15 node (`node --test tests/*.test.mjs`).
- APK at `GonkaCapital-v1.0.0.apk`, installed and driven on two emulators: Android 14 (API 34) and Android 16 (API 36).
- Daily GitHub Action `refresh data` rebuilds `data/feed.json` from the primary sources and commits it; verified green three times, including one run that committed a real refresh.
- The installed app fetches that file and shows the live date in green; verified on a clean install.
- Every one of the 2,091 feed items deep-links to its own filing.

## Known defects, not fixed

1. **Accessibility regression (real, mine).** `MainActivity` calls `WebSettings.setTextZoom(100)`, which makes the app ignore the phone's system font-size setting. The intended user is an older reader who may well have large text turned on. One line to fix; needs an on-device check at a large system font, because the fixed header and tab bar have to survive the reflow.
2. **The About screen has no links.** It describes the STOCK Act and Form 13F in prose but links nowhere, so a reader who wants to check the claims has no route from the explanation to the authority.
3. **The feed repeats itself.** Same person, same ticker, same day arrives as separate cards (4 identical-looking MSFT rows lead the feed today). Nothing is wrong in the data; the presentation just refuses to group.
4. **Two people are half the feed.** Gottheimer (560) and McClain Delaney (486) of 2,091 events. There is no way to mute anyone, so the quiet, higher-signal filers are buried.

## Constraint position

The software domain constraint is distribution, not features (`~/.constraint/constraints.md`, reviewed 2026-09-16). This app has an audience of one by design and no revenue path, so feature work on it fails the check filter as portfolio work. It is a gift: the budget is Greg-minutes, not portfolio hours. Recorded so a future session does not mistake it for a growth asset.

## Next action

Greg decides whether this gets any more hours. If yes, the ranked plan is in the 2026-09-22 `/forge` run output; defects 1 and 2 are the cheap ones and defect 1 is a genuine bug rather than an enhancement.

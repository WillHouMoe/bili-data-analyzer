# Changelog

This project has no version numbers and no releases — you run it with
`docker compose up`. So this is not a changelog for deciding whether to upgrade;
it is a **work log**: what changed, why, and the trade-offs a diff does not show.
Entries are grouped by date, not by version.

The bar is "something I would want to know when I come back to this": behaviour
changed, something was removed, or a decision rests on a measurement. Pure
formatting and renames are not recorded. Technical detail lives in
[`AGENTS.md`](AGENTS.md) and the code; this file records what happened.

The log starts at 2026-09-01. The repository has an earlier life (roughly 90
commits through 2026-04) that ended in a long pause; the September entries are a
revival that rewrote most of the surface. For anything before that, read
`git log`.

---

## 2026-10-17

### Fixed

- **Scrapes no longer die on the first video once SQLite enforces foreign
  keys.** The video row is flushed before its `QueryVideo` link is inserted,
  which removes the insert-order dependency that the scraper previously got
  away with only because foreign-key checks were off. Failed scrapes now roll
  back before recording the error status, so the UI stops claiming that a dead
  task is still fetching.

## 2026-09-21

### Changed

- **Dropped the sentiment analyzer registry.** It had exactly one implementation
  (`SnownlpAnalyzer`) and a lookup layer that could never return anything else.
  The registry is gone and `sentiment/` now holds the analyzer directly.
- **`ruff` is now a CI gate** rather than something you remember to run, and the
  things it flagged are fixed. The rule set is deliberately narrow
  (`E4,E7,E9,F,I,UP`): dead imports and undefined names fail the build, style
  opinions do not.
- Removed the duplicate `backend/.env.example`; the root one is the only copy.
  Added `AGENTS.md`.

## 2026-09-16

### Changed

- Added `.gitattributes` so line endings stop depending on which machine committed.

## 2026-09-01 (revival)

Most of the current surface dates from this day. The project had been dormant
since April and came back with the scraper broken and the interface unusable.

### Fixed

- **Stopped leaking proxy credentials**, and made failure paths expose less in
  general.
- **Repaired the scrape, the cascade deletes, and a blocked event loop.** The
  event loop was being blocked by synchronous work inside async handlers, which
  made the whole dashboard stall during a fetch.
- **HTTP 412 is risk control, not a retryable error.** Bilibili returns 412 to
  anonymous callers on `x/web-interface/view`; retrying it just burns requests.
  This is also why `SESSDATA` is a hard requirement rather than an optional
  convenience.
- Stopped `.gitignore` from swallowing the README screenshot — the ignore rule
  for screenshots was catching `docs/images/` too, so the one image the README
  needs was never committed.
- Default to English instead of forcing a Chinese UI.

### Changed

- **Redesigned the frontend as a printed proof sheet.** The two word-frequency
  tables now rank by different things rather than showing the same list twice.
- Rewrote the README in English with a Traditional Chinese mirror.
- Added a license and pinned dependencies; deleted dead files.

### Added

- **A demo seed** (`backend/scripts/seed_demo.py`) so a fresh clone has something
  to show without credentials or a scrape.
- CI running the tests and the frontend build on every push.

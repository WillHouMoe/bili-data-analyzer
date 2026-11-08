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

## 2026-11-08

### Added

- **A sanitized dashboard snapshot can now be published as a read-only GitHub
  Pages site.** `./bilia export-static` reads the local SQLite library through
  the API's own response functions and writes only creator, video, chart and
  comparison data. The static build hides mutation controls, implements
  catalogue search, sorting and pagination in the browser, and uses a Pages
  workflow with asset and SPA fallback paths derived from the repository name.
  Settings, credentials, AI conversations and the database itself are excluded
  from the public artifact.

### Changed

- **Video radar comparisons now use a local cohort and percentile ranks
  instead of an all-time average.** The baseline is the median of up to 20
  earlier uploads from the 180 days before the video was published. Each radar
  radius shows the video's percentile within that cohort, with the dashed
  reference at P50. This keeps a creator's long-term audience growth and rare
  outlier videos from dragging every comparison toward an irrelevant centre;
  the detail page also reports the cohort size and window.

## 2026-10-27

### Changed

- **The video catalogue now opens newest-first.** Both catalogue endpoints
  default to `published_at` descending, and the dashboard starts on that same
  order instead of ranking the initial view by play count. Readers can still
  switch to any metric or reverse the publication order.
- **Charts now fit their value axes to the observed range.** Growth lines,
  account trends, interaction bars, duration comparisons and scatter plots add
  proportional headroom instead of anchoring every axis at zero, so movements
  remain legible when values sit far above the origin. Compact tick labels add
  enough precision for the narrowed span, and non-negative data never receives
  an invented negative minimum.
- **The publishing calendar now follows a Monkeytype-style fluid wall.** Its
  seven rows stretch to the available width instead of staying at a fixed
  pixel size, months sit below the chart, and hovering or focusing a date
  updates an inline readout with the count, peak views and representative
  video before the existing date-detail interaction opens on click.
- **Tracked creators now discover new uploads automatically.** A dedicated
  background task scans each creator's newest archive pages down to the newest
  video already stored, creates metadata, first stats and achievement records
  for unseen uploads, and schedules them through the normal age-based refresh
  cadence. The default scan interval is 30 minutes and can be disabled with
  `NEW_VIDEO_REFRESH_MINUTES=0`.
- **Bilibili rankings are now presented as long-lived achievements.** The
  former ranking section has separate “Weekly must-watch” and “Site-wide
  ranking” groups. Each library video is checked once for its retained
  `honor_reply` achievements, including every weekly issue and the site-wide
  chart's best-ever rank. Both achievement types use their Bilibili artwork in
  the former rank column. Creator pages show five achievement rows per group
  and reveal ten more per click; entries outside the scraped creator library
  are excluded. The current chart is polled every 15 minutes only to detect
  changes and is not shown as an achievement. Ranking polling now runs as its
  own background task, independently from creator-profile and video sampling.
- **Publishing calendars are now browsable one year at a time.** Libraries that
  span more than a year expose a year selector and default to the newest year,
  while shorter libraries keep their exact date range. A ruled annual summary
  beside the wall reports video count, monthly pace, longest gap, busiest month
  and cumulative views, while the year's five most-viewed videos sit below the
  wall. The existing date-detail overlay is unchanged.
- **Video snapshots now follow publication age instead of a latest-N window.**
  Each video is scheduled independently: hourly on day one, then every 2, 4,
  8 and 12 hours through successive age bands, daily through day 365, and
  weekly in unlimited mode. The default one-year window pauses older videos
  without deleting their history. A fresh ranking hit or a playback rate at
  least twice the trailing median moves the next sample one tier earlier for
  up to six observations. The cadence follows the Bilibili view-time study by
  Dong et al. (2022), which sampled the latest videos every three hours and
  found both a rapid early rise and later self-excited peaks.
- **The visible product name is now BiliDataAnalyzer.** The sidebar,
  browser-tab title, API documentation title and both READMEs use the new
  name. Repository URLs and persistence identifiers keep their existing values
  so an upgrade does not move the database, container or login agent.
- **Active development moved to `bili-data-analyzer`.** The new repository
  supersedes the `WillHouMoe/biliAnalyzer` fork, and its `simplify` branch
  contains the current rewrite. The original persistence identifiers remain
  unchanged.
- **Publishing-calendar shading now reflects performance instead of cadence.**
  Each day's square uses the highest view count among videos published that
  day, scaled against the calendar's peak. Hover text includes that day's peak
  views, while the day-detail list continues to show every upload and its
  individual playback count.
- **CI now covers both `main` and `simplify`.** The active repository keeps
  `simplify` as its default branch, so pushing it must run the full backend and
  frontend gates rather than waiting for a pull request.

### Removed

- **AI analysis is no longer exposed in the product.** Creator and video pages
  no longer show an AI entry, and Settings no longer offers model configuration
  or connection testing. Existing server endpoints, credentials and
  conversations remain in place so the feature can be reintroduced without a
  destructive migration once there is a concrete product plan.

### Fixed

- **Radar tooltips no longer flicker between this video and the library
  average.** Hovering now opens one fixed comparison table containing both
  series across all seven metrics, so overlapping outlines cannot repeatedly
  replace the tooltip's source or position.
- **Weekly must-watch entries no longer display invented rank numbers.** The
  weekly API returns an editorial list without ranks, but the scraper used each
  item's list position as one. Existing rows are normalized on startup, and API
  responses now expose `rank: null` for weekly entries while retaining real
  ranks for the site-wide chart.

## 2026-10-25

### Added

- **UP account history now has follower, account-view and account-like growth
  charts.**
  Successful profile refreshes append a `creator_stats_snapshots` row, and the
  creator page renders two side-by-side charts on a true time axis: followers
  on the left, and account views plus account likes on the right. Existing
  installs seed one point from their current totals; subsequent refreshes
  accumulate all three histories.
- **Creator dashboards now include a real growth curve.** Every stats capture
  is stored as another `video_stats` snapshot. The curve uses the latest
  observation per video and age bucket, then plots median views with a P25–P75
  band instead of treating one final total as a time series.
- **Stats snapshots can be captured manually or on a background schedule.**
  `POST /api/creators/{uid}/stats/refresh` captures every video currently in a
  creator library, while the server checks for stale creators every 15 minutes
  and refreshes the oldest due library. `STATS_REFRESH_HOURS` defaults to 24;
  setting it to `0` leaves manual snapshot capture available without automatic
  scraping.
- **Downtime now triggers an immediate catch-up pass.** Startup drains every
  overdue creator instead of waiting for the next periodic check, failed
  creators enter a one-hour retry cooldown so they cannot starve the rest, and
  `./bilia install-login` adds a macOS LaunchAgent that starts Docker and the
  Compose service at login.
- **Creator and ranking context now comes from dedicated Bilibili APIs.**
  Follower count comes from `relation/stat`, account-wide views and likes from
  `space/upstat`, archive count from `space/navnum`, site ranking from
  `ranking/v2`, and the latest weekly must-watch issue from
  `popular/series/one`. Matching placements appear on creator and video pages.
- **Stats refresh is bounded to a configurable recent-video window.** Settings
  accepts 30–50 videos with a default of 40, so periodic snapshots no longer
  walk an entire large catalogue.
- **Creator and video growth now have explicit UI sections.** The creator view
  shows median views by video age; each video shows its own views over snapshot
  time.

### Fixed

- **All API datetimes are now serialized as China Standard Time
  (`+08:00`).** SQLite continues to store UTC, but response serializers attach
  UTC to legacy naive values before converting them to `Asia/Shanghai`, so
  “fetched at”, publication times and conversation timestamps no longer render
  eight hours behind.
- **Growth charts use a continuous real-time axis.** Snapshot points are now
  positioned by their actual timestamps instead of equal-width categories.
  Frequent captures remain compressed and sparse captures remain spread out.
- **The P25–P75 presentation is now a quiet range annotation.** The large filled
  band was replaced by two thin dashed quartile lines around the median, with a
  legend, axis titles and an explicit latest-value marker.
- **Creator deletion now clears every foreign-key dependency explicitly.**
  `query_videos`, stats, AI messages and conversations, and batches are removed
  before videos. Startup also drops the two legacy pre-simplification text
  tables whose foreign keys were still blocking deletion on old databases.

- **Appending a range no longer crashes when an archive response contains a
  video owned by another creator.** `/x/web-interface/view` confirms real
  ownership; foreign BV IDs are skipped, and the fetch loop now checks the
  global BV index before inserting. This fixes query 12, where UID `946974`'s
  range included `BV1TR766zEvE` from UID `407054668` and hit SQLite's
  `videos.bvid` unique constraint.
- **Starting a fetch from the active creator page now refreshes that page
  immediately.** Navigation to the same UID previously left the existing
  dashboard mounted, so the accepted batch looked like a no-op until a manual
  reload. The submit action now carries a refresh signal and starts status
  polling at once.
- **The video radar tooltip now reports real metric values.** Radar
  coordinates are normalised to 0–100 so metrics with different units share
  one shape, but the tooltip exposed those internal coordinates as long
  floating-point numbers. Hovering a series now shows its exact playback,
  interaction and comment counts instead.
- **Creator scrapes now survive the recommendation archive endpoint's mixed
  412 / `-504` failures.** With a SESSDATA that passed `/x/web-interface/nav`,
  `recArchivesByKeywords` still alternated risk-control responses and server
  timeouts for UID 946974. The standard WBI-signed
  `/x/space/wbi/arc/search` endpoint immediately reported 939 archives, so the
  scraper now falls back to that paginated index when the quick path fails.

### Removed

- **Comment, danmaku and subtitle text is no longer collected or exposed.**
  The scraper now stops after video metadata and aggregate stats. The
  `video_content` model, text-fetching stages, sentiment pipeline and API,
  comment-derived demographics, content word-table sources, sample-text AI
  tools, and their frontend panels were removed. Aggregate comment/danmaku
  counts remain because they already arrive in the video-stat payload.
- **Removed the `snownlp` and `defusedxml` runtime dependencies** that existed
  only for sentiment analysis and danmaku XML parsing.
- **Removed the title/tag word tables and all word-frequency analysis.** The
  dashboard and video detail no longer expose word lists or word-detail
  contexts; the corresponding API, AI tool, frontend components, and `jieba`
  dependency are gone. Titles and tags remain visible as normal video metadata.

### Changed

- **UP account metrics now have a dedicated section and ranking placements are
  grouped by BV.** Followers, account views, account likes, uploads and
  following moved out of the compact masthead. The same video appearing in both
  the site-wide ranking and weekly must-watch is rendered once with both ranks.
- **The experimental creator-level age-bucket growth curve was removed.** The
  creator page keeps only factual account growth, while video detail keeps its
  own playback history.
- **Creators are now the primary index; fetches are batches underneath them.**
  The sidebar lists UIDs rather than individual queries, and each dashboard
  aggregates the union of every video fetched for that creator. Appending an
  overlapping range reuses existing BVs instead of scraping their metadata and
  stats again.
- **The app can be started and left running without an open browser tab.**
  `./bilia start` launches the Compose service in the background, creates
  `.env` on first use, and `restart: unless-stopped` keeps the server available
  across container failures. Submitted scrape jobs continue server-side, and
  opening a stored dashboard does not trigger another fetch. A restart resumes
  unfinished batches and skips videos already persisted for that batch.
- **The publish-time heatmap is now a daily publishing calendar.** Every day
  in the query span has a contribution-style square, shaded by that day's
  upload count. Selecting a publishing day opens its complete video list in
  the margin, with links through to each video's detail page.

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

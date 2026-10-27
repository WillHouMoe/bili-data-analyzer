# BiliDataAnalyzer

A dashboard for reading a Bilibili creator's video performance: what they
posted in a window of time, how it performed, and what an LLM makes of those
numbers.

<p>
  <a href="https://github.com/WillHouMoe/bili-data-analyzer/actions/workflows/ci.yml"><img src="https://github.com/WillHouMoe/bili-data-analyzer/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="LICENSE"><img src="https://img.shields.io/github/license/WillHouMoe/bili-data-analyzer" alt="License: MIT"></a>
</p>

**English** · [繁體中文](README.zh-Hant.md)

Bilibili's creator centre shows totals and trend lines for your own account
only. BiliDataAnalyzer answers broader questions across a creator's recent
catalogue: which uploads performed best, how publishing cadence and duration
relate to attention, and how interactions accumulate over time. It takes any
public UID, so it works for a creator reviewing their own run, a fan or analyst
studying someone else's, or anyone comparing two.

Give it a UID and a date range. It fetches every video the creator posted in
that window and charts the performance. An OpenAI-compatible endpoint can then
be asked questions about the result, with tool calls against the same metadata
and aggregate stats.

Comment, danmaku and subtitle text is deliberately out of scope. The app keeps
the aggregate comment and danmaku counts supplied by Bilibili's video-stat
payload, but it never fetches or stores the underlying text.

![Dashboard](docs/images/dashboard.png)

## Quick start

Requires Docker and Docker Compose.

```bash
git clone https://github.com/WillHouMoe/bili-data-analyzer.git
cd bili-data-analyzer
./bilia start
```

That starts the app in the background and creates `.env` from the example on
the first run. Open it later with `./bilia open`; `./bilia status` and
`./bilia logs` are there when you need them. The API docs live at `/docs` on the
same port as the UI.

On macOS, run `./bilia install-login` once to start Docker and the analyzer at
login. The LaunchAgent also checks every five minutes and restarts the container
if needed. Remove it with `./bilia uninstall-login`; startup output goes to
`/tmp/bilianalyzer-background.log`. `./bilia stop` and `./bilia down` unload the
agent for the current login session so an intentional stop is not undone five
minutes later.

Scraping happens in the server process. Once a fetch has been submitted, you
can close the browser tab; opening the dashboard later reads the stored result
and does not start another scrape. If the container restarts mid-fetch, the
unfinished batch resumes and skips videos it already stored.

### See it with data, immediately

Scraping a real creator takes a while and needs a `SESSDATA` cookie. To fill
every panel with plausible data without one:

```bash
docker compose exec app python -m scripts.seed_demo
```

That seeds a fictional creator with a few months of video metadata and
performance figures. Pass `--reset` to start over.

## Using it

1. **Add creator** — enter a creator's UID (the number in
   `space.bilibili.com/546195`) and pick a date range. The sidebar shows fetch
   progress.
2. **Dashboard** — summary tiles, view-count trend, interaction comparison,
   views-vs-engagement scatter, duration analysis, and publishing cadence. The
   creator is the directory; individual fetches are batches underneath it.
   Account-wide followers, total views and total likes come from Bilibili's
   creator APIs. The latest 30–50 videos are refreshed for performance snapshots,
   while follower, account-view and account-like history is stored as separate
   creator snapshots and shown as two side-by-side charts: followers on the
   left, and account views plus likes on the right.
3. **Video detail** — one video's numbers with a radar chart and deltas against
   the creator's merged video library.
4. **AI analysis** — configure an OpenAI-compatible Base URL, key and model in
   Settings, then ask follow-up questions; answers stream back.

Use **Fetch another range** on a creator page to append more videos. Existing
videos are reused by BV ID, so overlapping ranges do not scrape the whole
catalogue again.

**Capture snapshot** records the current stats for every video already in the
creator library. By default it updates only the most recent 40 videos; change
the 30–50 video window in Settings. These snapshots feed the creator growth
curve by video age and the per-video view history chart. By default the server
also captures one automatically every 24 hours; change
`STATS_REFRESH_HOURS` or set it to `0` to use manual snapshots only. After
downtime, startup immediately drains every overdue creator rather than waiting
for the next periodic check. Missed timestamps cannot be reconstructed, so the
first post-downtime snapshot is recorded at the actual restart time.

The same background refresh stores Bilibili's site-wide ranking and the latest
weekly must-watch list. Matching placements appear on creator dashboards and
video detail pages.

**SESSDATA is required for scraping.** `x/web-interface/view`, which every
video goes through, answers HTTP 412 to requests without a logged-in session —
verified against the live API — so a run without it fails immediately rather
than degrading. To add it: log in to bilibili.com, F12 → Application → Cookies
→ copy `SESSDATA`, paste it into Settings. Use the demo seed above to look
around without one.

## Security

This is a **single-user local tool with no authentication**. Every endpoint is
open to whoever can reach the port, so Compose binds it to `127.0.0.1` only.
Do not publish the port to a network you do not control, and do not put it
behind a reverse proxy without adding auth first.

Your SESSDATA and API key are encrypted at rest with Fernet before they go into
SQLite, and the API returns them masked. The encryption key lives in
`DATA_DIR/.secret_key` — beside the database it protects, so this defends
against someone getting the `.db` file alone, not against host access.

## Tech stack

| Layer | |
|---|---|
| Frontend | Vite · React 19 · TypeScript · Tailwind CSS v4 · Base UI · ECharts |
| Backend | FastAPI · SQLAlchemy 2.0 (async) · aiosqlite · httpx |
| AI | OpenAI SDK, streamed over SSE, with tool calling |
| Deploy | Docker Compose, single multi-stage image |

## Configuration

| Variable | Default | |
|---|---|---|
| `DATABASE_URL` | `sqlite+aiosqlite:///./data/bilianalyzer.db` | Where the database lives |
| `DATA_DIR` | `./data` | Holds the database and `.secret_key` |
| `SECRET_KEY` | *(generated)* | Fernet key. Generated on first run and persisted; set it explicitly to keep stored credentials readable across environments |
| `CORS_ORIGINS` | `http://localhost:5173` | Only needed for the split dev setup. Empty disables CORS entirely |
| `STATS_REFRESH_HOURS` | `24` | Background stats snapshot interval in hours; `0` disables automatic snapshots |

## Local development

```bash
# backend
cd backend && python -m venv .venv && .venv\Scripts\Activate.ps1
pip install -e ".[dev]"
uvicorn app.main:app --port 8000 --reload

# frontend, in another terminal
cd frontend && npm install && npm run dev      # http://localhost:5173
```

`pytest` from `backend/`; `npm test`, `npm run build` and `npx eslint .` from `frontend/`.
Requires Python 3.11+ and Node 20+.

## License

[MIT](LICENSE)

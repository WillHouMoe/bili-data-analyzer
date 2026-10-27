# AGENTS.md — BiliDataAnalyzer

Bilibili creator analytics: give it a UID + date range and it scrapes video
metadata and aggregate stats, then serves an ECharts performance dashboard.
Single-machine, no auth — that is why it binds 127.0.0.1 and why SESSDATA is a
hard requirement (anonymous calls get HTTP 412).

## Layout

- `backend/` — FastAPI + SQLAlchemy (async) + SQLite. `app/` splits into
  api / core / models / schemas / services. `app/data/` holds the SQLite DB and
  `.secret_key` at runtime (never commit).
- `frontend/` — Vite + React + TypeScript, built into the same Docker image;
  there is no separate web port.
- Root `.env.example` → `cp .env.example .env` is the only env file compose reads.
  There is intentionally no `backend/.env.example` (it drifted against the root one).

## Gates (CI runs all of these)

- Backend: `ruff check .` then `pytest -q` (in `backend/`, dev extras: `pip install -e ".[dev]"`).
  Ruff selects `E4/E7/E9/F/I/UP` — it catches dead imports and undefined names, not style.
- Frontend: `npx tsc --noEmit`, `npx eslint .`, `npm test`, `npm run build`.
  Add focused Vitest coverage when fixing frontend behaviour.
- Comment, danmaku and subtitle text is intentionally out of scope. The
  dashboard only consumes metadata and aggregate counts from video-stat payloads.
- Word tables and word-frequency analysis are intentionally out of scope.

## Conventions

- Docs: English and zh-Hant mirrors (`README.md` / `README.zh-Hant.md`) — change both.
- `frontend/.npmrc` sets `legacy-peer-deps=true` to paper over vite 8 / react 19 /
  eslint 9 peer conflicts; do not treat that as a clean bill of health when bumping deps.
- Commits: Conventional Commits, English.
- **`CHANGELOG.md` is a work log, not a release changelog** (this project has no
  versions). Record behaviour changes, removals, and decisions backed by a
  measurement; skip pure formatting and renames. Write the entry in the same
  change that makes it, not afterwards.
- **One commit, one change, and the subject must cover everything the diff
  touches.** A commit that also edits something its message does not mention is
  how work becomes invisible; `git log --stat` is the check.

# Sports Data Analysis & Decision-Support Platform — Milestone 1

Milestone 1 delivers: Docker Compose stack (Postgres+TimescaleDB, Redis,
FastAPI), the core DB schema, and a **fully tested mock ingestion
pipeline** — proven correct before any real, authorized data provider
is connected.

## Why a mock provider first

The ingestion pipeline (fetch → validate → normalize → dedupe → store →
log) is the riskiest part of this system: it's where bad data, duplicate
records, or silent failures would do the most damage later. `MockProvider`
generates clearly-fake data (obviously placeholder team names) including
a malformed record and a duplicate on purpose, so we can prove:

- valid records are stored correctly
- invalid records are rejected **and logged**, never silently dropped
- duplicate records don't create duplicate rows
- re-running ingestion is idempotent (upsert, not insert-again)

Once a real, authorized provider is ready, it implements `BaseConnector`
exactly like `MockProvider` does — nothing else in the pipeline changes.

## Setup

```bash
cd sports_platform
cp backend/.env.example backend/.env   # already done for you; edit if needed
docker compose up --build
```

This starts:
- Postgres + TimescaleDB on `localhost:5432`
- Redis on `localhost:6379`
- FastAPI backend on `localhost:8000` (auto-creates tables on startup in dev mode)

## Testing Milestone 1

### 1. Health check
```bash
curl http://localhost:8000/health
# {"status": "ok", "environment": "development"}
```

### 2. Run the automated test suite
```bash
cd backend
pip install -r requirements.txt
pytest -v
```
Expect all tests in `tests/test_validation.py`, `tests/test_normalization.py`,
and `tests/test_ingestion_pipeline.py` to pass. These run against an
in-memory SQLite DB, so no Docker is required just to run `pytest`.

### 3. Trigger ingestion manually over HTTP
```bash
curl -X POST http://localhost:8000/ingestion/test-run
```
Expected response shape:
```json
{
  "provider": "mock_test_provider",
  "result": {
    "fetched": 4,
    "rejected": 1,
    "duplicates_dropped": 1,
    "stored": 2
  }
}
```
Run it twice — `stored` should still be `2` the second time (idempotent
upsert, not duplicate rows). Check the `ingestion_logs` table in Postgres
to see the fetch/validate/normalize/store audit trail.

## What's intentionally NOT in Milestone 1

- No real data provider yet (`USE_MOCK_PROVIDER=true` in `.env`)
- No player stats, odds, or predictions tables populated (schema exists in
  `schema.sql`, ORM models arrive in Milestone 2 alongside real ingestion)
- No Alembic migrations yet (dev uses `create_all()`; Alembic is
  introduced once the schema stabilizes)
- No frontend

---

# Milestone 2 — Real NFL data via API-Sports (API-NFL)

Milestone 2 adds the first real, authorized data source: **API-Sports'
API-NFL** (free tier, 100 requests/day, no credit card required). It
implements `BaseConnector` exactly like `MockProvider` did, so nothing
in `validation.py`, `normalization.py`, or `pipeline.py` changed at
all — only a new connector file was added.

## Get a free API key

1. Sign up at https://dashboard.api-football.com/register (free, no card)
2. Go to **Account → My Access** in the dashboard sidebar
3. Copy the key shown in the top-right corner
4. Open `backend/.env` and set:
   ```
   API_SPORTS_KEY=your_key_here
   ```
5. Restart the stack: `docker compose up --build`

## Testing Milestone 2

### 1. Pull real NFL games for a specific date
```bash
curl -X POST "http://localhost:8000/ingestion/nfl/sync?start=2026-09-13&end=2026-09-13"
```
Expected response shape (numbers will vary by date):
```json
{
  "provider": "api_sports_nfl",
  "date_range": ["2026-09-13", "2026-09-13"],
  "result": {"fetched": 13, "rejected": 0, "duplicates_dropped": 0, "stored": 13}
}
```
With no games set up yet, calling with no date params defaults to
today: `curl -X POST http://localhost:8000/ingestion/nfl/sync`

### 2. Confirm real teams and games landed in Postgres
```sql
select name, abbreviation from teams where provider = 'api_sports_nfl';
select external_id, status, home_score, away_score from games where provider = 'api_sports_nfl';
```

### 3. Run the offline connector tests (no API key or network needed)
```bash
cd backend
pytest tests/test_api_sports_connector.py -v
```
These test the raw-JSON-to-common-shape mapping against the exact
example response from API-Sports' own documentation — so the mapping
logic is verified without spending any of the 100 daily free requests.

## Mind the free-tier quota

100 requests/day, resets at 00:00 UTC, does not roll over. Each call
to `/ingestion/nfl/sync` uses one request per day in the range (e.g.
a 7-day range = 7 requests). Keep ranges small during development —
single-day syncs are enough to validate everything end-to-end.

## What's intentionally NOT in Milestone 2

- Odds data (The Odds API needs a paid $29/mo Pro plan for NFL — deferred
  to a later milestone rather than paying for it before the core pipeline
  proves out)
- Player-level stats and injuries (API-NFL supports these; wiring them in
  is straightforward but deferred to keep this milestone reviewable)
- Alembic migrations (still using dev-mode `create_all()`)

## Next: Milestone 3

Expand ORM models to cover team/player statistics and injuries from
API-NFL's `/games/statistics/*`, `/players`, and `/injuries` endpoints,
and introduce Alembic migrations now that the schema has real data
behind it.

---

# Milestone 2.5 — Multi-sport: NFL, CFB, MLB, NHL, NBA

Added three more sports on top of NFL, all through API-Sports since
one account covers all of them. This required no changes to
`validation.py`, `normalization.py`, or `pipeline.py` — only new
connector files, because the whole point of `BaseConnector` was to
make this exactly this cheap.

## What changed

- **`api_sports_base.py`** — the shared HTTP/auth/mapping logic,
  extracted from the original NFL-only connector, since API-Sports
  uses the same JSON shape across their sport APIs.
- **`api_sports_connector.py`** (NFL), **`api_sports_cfb_connector.py`**
  (NCAA), **`api_sports_mlb_connector.py`** (MLB), and
  **`api_sports_nhl_connector.py`** (NHL) — each is ~10 lines: just a
  base URL, a league id, and a provider name.
- One new `/ingestion/<sport>/sync` endpoint per sport in `main.py`,
  all built on a shared `_sync_via_api_sports()` helper.

## Important: separate quotas per sport

API-Sports runs each sport as its own product with its own 100
requests/day free quota. NFL and CFB share one quota (same API-NFL
product, just different league ids); MLB and NHL each have their own
separate quota. Same `API_SPORTS_KEY` works across all of them — no
new signup needed.

## League IDs used (confirmed, not guessed)

| Sport | League ID | Source |
|---|---|---|
| NFL | 1 | API-NFL docs, stated as stable across seasons |
| NCAA Football | 2 | API-NFL docs, same statement |
| MLB | 1 | API-Baseball docs, example response `"league": {"id": 1, "name": "MLB"}` |
| NHL | 57 | API-Hockey, confirmed via `/leagues` lookup (not sequential like football) |
| NBA | 12 | API-Basketball, confirmed via documented `/leagues` example response |

## Testing Milestone 2.5

### 1. Run the offline connector tests
```bash
cd backend
pytest tests/test_api_sports_connector.py -v
```
Includes a new `test_each_sport_connector_is_configured_correctly` check
that catches copy-paste mistakes (e.g. two sports accidentally sharing
a league id) without touching the network.

### 2. Try each sport's sync endpoint
```bash
curl -X POST "http://localhost:8000/ingestion/mlb/sync?start=2026-06-15&end=2026-06-15"
curl -X POST "http://localhost:8000/ingestion/nhl/sync?start=2026-01-15&end=2026-01-15"
curl -X POST "http://localhost:8000/ingestion/cfb/sync?start=2026-09-13&end=2026-09-13"
curl -X POST "http://localhost:8000/ingestion/nba/sync?start=2026-11-01&end=2026-11-01"
```
Pick dates that actually fall within each sport's season — MLB runs
roughly April-October, NHL roughly October-June, CFB alongside NFL in
the fall. An empty `stored: 0` result on an off-season date is
expected behavior, not a bug.

## What's still not verified

MLB and NHL's `/games` response shape is assumed to match football's
(same company, same conventions, confirmed for their `/status` and
`/teams/statistics` endpoints) but not yet confirmed against a live
`/games` call, since that takes a real API key and spends part of the
free quota. Run the sync endpoints above once you're ready and tell
me what comes back — if either sport's shape differs, only that
sport's connector needs a fix, not the shared base class.

## Cricket — deferred, needs a different provider

API-Sports doesn't offer cricket. The best free option found so far
is Highlightly's Sport API (100 requests/day, shared across sports,
covers cricket alongside several others) — but that means a second
account and an unverified response shape. Rather than guess at its
JSON structure, this is deferred until we confirm it together.

## Next: Milestone 3

Same as before — expand ORM models for stats/injuries, add Alembic
migrations — now informed by whichever sports you've actually tested
real data against.

---

# Milestone 2.6 — Switching CFB/MLB/NHL/NBA to BALLDONTLIE

API-Sports' free tier turned out to return genuinely self-contradicting
errors for every sport except NFL on this account — confirmed by
testing directly against their API with `curl`, independent of any of
our code (see `api_sports_bug_report.txt` for the exact evidence, in
case you want to report it to them). Rather than keep guessing at a
provider bug, CFB, MLB, NHL, and NBA were switched to **BALLDONTLIE**,
a different free provider, verified against their actual OpenAPI specs
before writing a line of connector code.

## Get a free BALLDONTLIE key

1. Sign up at https://app.balldontlie.io (free, no card)
2. Go to **Account Settings** and copy your API key
3. Open `backend/.env` and set:
   ```
   BALLDONTLIE_API_KEY=your_key_here
   ```
4. Restart the stack: `docker compose up --build`

## What changed

- **`balldontlie_base.py`** — shared auth/HTTP logic. Unlike
  API-Sports, BALLDONTLIE's sports genuinely differ in response shape
  (MLB nests scores under `home_team_data.runs`; NBA and NCAAF call
  the away side `visitor_team`; NHL calls the date field `game_date`),
  so each sport keeps its own `_map_game` rather than forcing a fake
  shared shape.
- **`balldontlie_mlb_connector.py`**, **`balldontlie_nba_connector.py`**,
  **`balldontlie_nhl_connector.py`**, **`balldontlie_ncaaf_connector.py`**
  — one file per sport, each verified against BALLDONTLIE's own
  documented example response or OpenAPI spec (not guessed).
- `/ingestion/cfb/sync`, `/ingestion/mlb/sync`, `/ingestion/nhl/sync`,
  and `/ingestion/nba/sync` now use these new connectors.
  `/ingestion/nfl/sync` is unchanged — it still uses API-Sports, which
  is confirmed fully working.
- The old API-Sports connectors for CFB/MLB/NHL/NBA are still in the
  codebase, just unused, in case API-Sports fixes their bug later.

## Mind BALLDONTLIE's rate limit

5 requests/minute on the free tier (vs. API-Sports' 100/day). This is
a *per-minute* cap, not a daily one — you can make plenty of calls
over a day, just not in a burst. Unlike API-Sports, one call can
request multiple dates at once via `dates[]`, so a multi-day sync
still only costs one request.

## Testing Milestone 2.6

### 1. Run the offline connector tests
```bash
cd backend
pytest tests/test_balldontlie_connectors.py -v
```
Six tests verifying the mapping logic against real documented example
responses for all four sports, with no network calls.

### 2. Try each sport's sync endpoint
```bash
curl -X POST "http://localhost:8000/ingestion/mlb/sync?start=2026-09-13&end=2026-09-13"
curl -X POST "http://localhost:8000/ingestion/nba/sync?start=2026-09-13&end=2026-09-13"
curl -X POST "http://localhost:8000/ingestion/nhl/sync?start=2026-09-13&end=2026-09-13"
curl -X POST "http://localhost:8000/ingestion/cfb/sync?start=2026-09-13&end=2026-09-13"
```
As before, `stored: 0` on a date outside that sport's season is
expected, not a bug.

## Cricket

Still deferred — neither API-Sports nor BALLDONTLIE covers it on a
free tier we've confirmed. Revisit separately if wanted.

## Next: Milestone 3

Verify each BALLDONTLIE connector against live data (same as we did
for API-Sports/NFL), then move on to player stats, standings, or
Alembic migrations — whichever you want to tackle first.

---

# Milestone 3 — Alembic migrations

Up to now, table creation happened via SQLAlchemy's `Base.metadata.create_all()`
on app startup — fine for getting off the ground, but it can only ever
add tables that don't exist yet. It can't add a column to an existing
table, rename something, or add an index without you hand-writing SQL
and hoping you remember to run it against every environment. Alembic
fixes that: schema changes become versioned, reviewable files that
apply in order and can be rolled back.

## What's new

- **`backend/alembic.ini`** — Alembic config. `sqlalchemy.url` is
  deliberately left blank there; `env.py` pulls the real connection
  string from `app.config.settings` (the same `.env`-backed settings
  object everything else in the app uses), so there's never a second,
  possibly-stale copy of the DB URL.
- **`backend/alembic/env.py`** — wires Alembic to our actual ORM
  models (`app.db.models.core`) so `--autogenerate` can diff against
  them.
- **`backend/alembic/versions/0001_initial_schema.py`** — a
  hand-written baseline migration that exactly mirrors the five
  tables already live in the database (`sports`, `leagues`, `teams`,
  `games`, `ingestion_logs`). It doesn't touch your existing data —
  see "First-time setup" below.

`app/main.py`'s dev-mode `create_all()` on startup is untouched (it's
harmless — it only fills in missing tables, never alters or drops an
existing one), but **Alembic is now the source of truth for actual
schema changes** going forward: new columns, new tables, index
changes, etc.

## First-time setup (your DB already has data in it)

Since your Postgres container already has these five tables from
Milestones 1–2 (with real NFL/MLB/NBA games in them), you don't want
Alembic trying to `CREATE TABLE` things that already exist. Instead,
tell Alembic "this database is already at revision 0001" without
running any SQL:

```bash
docker compose exec backend alembic stamp 0001
```

Verify it took:
```bash
docker compose exec backend alembic current
# should print: 0001 (head)
```

That's it — no data touched, no tables recreated. From this point on,
schema changes go through Alembic.

## Making a schema change from here on

1. Edit the ORM models in `backend/app/db/models/core.py` (or a new
   model file).
2. Generate a migration by diffing the models against the live DB:
   ```bash
   docker compose exec backend alembic revision --autogenerate -m "add player stats table"
   ```
3. **Read the generated file in `backend/alembic/versions/` before
   applying it.** Autogenerate is a good first draft, not a guarantee
   — it can miss things like renamed columns (seeing them as a
   drop+add) or server-side defaults, and it's much cheaper to fix
   that in the file than after it's run.
4. Apply it:
   ```bash
   docker compose exec backend alembic upgrade head
   ```

## Rolling back

```bash
docker compose exec backend alembic downgrade -1   # back one revision
docker compose exec backend alembic history          # see all revisions
```

## Testing Milestone 3

```bash
docker compose exec backend alembic stamp 0001
docker compose exec backend alembic current
```
Expect `0001 (head)` with no errors and no changes to your existing
`teams`/`games` rows — confirm with:
```bash
curl -X POST "http://localhost:8000/ingestion/nfl/sync?start=2026-09-13&end=2026-09-13"
```
which should still work exactly as before (Alembic doesn't touch
anything at runtime — it only runs when you explicitly invoke it).

## What's intentionally NOT in this pass

- No new tables yet (player stats, injuries, standings) — those come
  as their own migration once we tackle that ingestion work, so each
  migration stays small and reviewable
- No CI/automated migration-on-deploy step — manual `alembic upgrade
  head` for now, which is the right call until there's a real
  deployment pipeline to hook it into

## Next: Milestone 3, continued

Player/team box-score stats and injury reports for NFL, each landing
as its own model + its own migration.

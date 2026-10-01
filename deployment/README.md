# Grandblue private mobile test and product deployment

Not yet a public-launch readiness signoff.

## Live private test — 1 October 2026

- App: https://grandblue-mu.vercel.app
- API: https://grandblue-api.onrender.com
- Vercel project: `ems-shenanigans/grandblue`, root `frontend`.
- Render service: `grandblue-api`, Free Docker service, one worker.
- Supabase project: `grand blue`; application data lives in private `grandblue` schema.
- Existing accounts, watchlist, saved range and alerts were migrated and verified.
  Old sessions were excluded; sign in again with the existing Grandblue password.
- Local SQLite backend was stopped to prevent divergent writes. Keep its backup;
  do not restart it as a second live database.
- Both hosts deploy from GitHub `main`. Credentials remain outside source control.
- Backend health and frontend connection passed; authenticated real-device testing
  remains for the owner on phone and iPad.

## Selected free cloud test: Vercel + Render + Supabase

1. Create a dedicated Supabase project. Use its **session pooler** Postgres URL
   (IPv4 compatible), with `sslmode=require` or certificate-verified TLS. Store
   it privately as `DATABASE_URL`; never use a `NEXT_PUBLIC_` variable for it.
2. Stop local writes for final migration and take a SQLite backup. Install the
   backend dependencies, then run `python -m persistence.migrate_cloud --source
   /absolute/path/to/backup.db` with `DATABASE_URL` set in the environment.
   This verifies every copied row inside one transaction, refuses a nonempty
   destination, and excludes old sessions. The local source is unchanged.
3. Application tables live in the private `grandblue` schema, outside Supabase's
   public Data API schema. Do not expose that schema or give browser roles access.
   Supabase Auth is not used yet: existing Grandblue passwords continue to work.
4. Import the repository's `render.yaml` Blueprint. It explicitly selects the
   **free** Docker web service. Supply the same secret `DATABASE_URL`. No disk
   is needed for this Postgres setup. Startup requires the migrated owner.
5. Set Vercel root to `frontend` and `API_SERVER_URL` to the resulting HTTPS
   Render origin. Deploy, then sign in and verify write/read persistence on
   phone and iPad, including after restarting the backend.

Render free services sleep when idle, so alerts/scans do not run continuously.
Expect a cold start when reopening the app. This is a private test limitation;
do not promise 24/7 alerts until an always-on worker is deployed.
Migration was completed with owner approval to the existing Supabase project.

## Vercel frontend

Import the GitHub repository with root directory `frontend`, framework Next.js.
Set `API_SERVER_URL` to a reachable HTTPS backend origin (no trailing `/api`).
Leave `NEXT_PUBLIC_API_URL` unset to retain same-origin `/api` proxying.
Builds on Vercel refuse a missing/non-HTTPS backend configuration.
Do not enable CDN caching for authenticated API responses.

## Backend

Run one persistent Python 3.12 service:
`pip install ./backend`
`cd backend && uvicorn dev_server:app --host 0.0.0.0 --port "$PORT" --workers 1`

Set `RANGE_DB_PATH` to the absolute SQLite path on a persistent volume.
Set `GRANDBLUE_PRIVATE_BETA=1` to close public registration during the first test.
Set `GRANDBLUE_ALLOWED_ORIGINS` to the exact frontend HTTPS origin if calling
backend directly; same-origin Vercel proxy does not need browser CORS access.
Use HTTPS. Never expose an empty database publicly: restore existing users first.
Keep a single worker: the current alert scheduler starts once per process.
The deployment target is fully cloud-hosted; a Mac tunnel is not part of the plan.

### Container option with persistent storage

Build from the repository root: `docker build -f deployment/Dockerfile -t grandblue-api .`
Mount a durable volume at `/data`, readable/writable by UID 10001. Restore the
existing database to `/data/grandblue.db` **before** starting the service.
The production factory refuses a missing database or one without an active
owner, and defaults to closed public registration. Local development continues
to use `dev_server.py`. The container runs one API/alert worker and uses `/health`
for its health check. Configure the host's HTTPS endpoint as Vercel's
`API_SERVER_URL`. Do not put a database or secrets in the image.

The SQLite alternative requires a persistent volume. The live Render deployment
uses the Postgres adapter and Supabase instead, so no local disk is needed.
Container startup and health were verified on Render Free; no paid plan was selected.

## Preserve data

Use SQLite's backup API, not a filesystem copy of a live WAL database. Store
backups outside source control with restricted permissions. Test restore into a
separate database and verify users, journals, watchlists, observed ranges and
alert rules. Stop writes during final migration, take a final backup, transfer
privately, restore onto the persistent volume, then switch traffic. Do not run
two independent databases as if they were synchronised. Do not overwrite the
local source database. Revoke old sessions after migration as appropriate.

## Before a public product launch

- Verify backup restoration on the selected cloud project; initial migration is complete.
- Move alert monitoring and backtests to a queue/worker with single-job ownership.
- Add per-account/provider rate limits, bounded requests and background-job quotas.
- Replace browser-local bearer token storage with a reviewed secure session design;
  add account recovery, email verification, login throttling and account lifecycle.
- Audit cross-account resource access, including legacy owner bypasses.
- Keep dependency checks current; Next.js was upgraded to 15.5.24 and the production dependency audit passed at deployment.
- Add error monitoring, uptime/provider metrics, encrypted backups and restore drills.
- Add real-device Safari/Chrome checks, accessibility checks and load testing.
- Separate deployment environments and establish retention/export/deletion policies.

The private test should verify login, chart pan/zoom, timeframe changes, save/load
ranges, journal writes and background alerts on actual phone and iPad devices.
Viewport emulation does not prove touch gesture or mobile Safari compatibility.

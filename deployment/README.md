# Grandblue private mobile test and product deployment

Not yet a public-launch readiness signoff.

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

This container needs a host with a persistent volume. It must not be deployed
unchanged to an ephemeral free service. Render's free service has no persistent
disk and sleeps when idle; moving there requires a managed database adapter,
data migration and a separate plan for alerts while the service sleeps.
No hosting plan, database migration, or paid service has been provisioned yet.
Container execution still needs verification on a host with Docker installed.

## Preserve data

Use SQLite's backup API, not a filesystem copy of a live WAL database. Store
backups outside source control with restricted permissions. Test restore into a
separate database and verify users, journals, watchlists, observed ranges and
alert rules. Stop writes during final migration, take a final backup, transfer
privately, restore onto the persistent volume, then switch traffic. Do not run
two independent databases as if they were synchronised. Do not overwrite the
local source database. Revoke old sessions after migration as appropriate.

## Before a public product launch

- Migrate SQLite repositories to managed Postgres with tested migrations.
- Move alert monitoring and backtests to a queue/worker with single-job ownership.
- Add per-account/provider rate limits, bounded requests and background-job quotas.
- Replace browser-local bearer token storage with a reviewed secure session design;
  add account recovery, email verification, login throttling and account lifecycle.
- Audit cross-account resource access, including legacy owner bypasses.
- Review dependencies/security advisories and upgrade the older frontend framework.
- Add error monitoring, uptime/provider metrics, encrypted backups and restore drills.
- Add real-device Safari/Chrome checks, accessibility checks and load testing.
- Separate deployment environments and establish retention/export/deletion policies.

The private test should verify login, chart pan/zoom, timeframe changes, save/load
ranges, journal writes and background alerts on actual phone and iPad devices.
Viewport emulation does not prove touch gesture or mobile Safari compatibility.

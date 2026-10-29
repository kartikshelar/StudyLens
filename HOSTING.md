# Hosting preparation

The target is **one Render Free web service plus Neon Free PostgreSQL**. Neon is connected and the local app now uses it. The same application serves the built React website and FastAPI routes, so no separate frontend service or public API-base configuration is needed. The repository and public Render website have not been published yet. `neon deploy` configures Neon services; it does not deploy this website to Render.

## Why PostgreSQL is required

[Render Free services lose local files on restarts, redeploys, and idle shutdowns](https://render.com/docs/free). Using the local SQLite database there would lose saved reports and reset spending counters. Free Render Postgres also expires after 30 days. [Neon Free](https://neon.com/pricing) currently offers PostgreSQL without a time limit or credit card requirement; select the Free plan and keep it there.

SQLite remains the local development default. Setting `DATABASE_URL` selects PostgreSQL. Connection failures fail closed rather than creating a replacement SQLite database. PostgreSQL uses transaction-level advisory locks for quota reservations and HTTP rate windows; the counters live in the database rather than in an individual server instance.

## Prepared files

- `Dockerfile` builds the locked frontend, installs the locked Python dependencies, and runs as a non-root user.
- `.dockerignore` excludes credentials, local databases, evaluation artifacts, and development dependencies.
- `render.yaml` selects `plan: free`, leaves automatic deployments off, and starts with live research paused. The service's health check is `/healthz`, which makes no provider or database call.
- `backend/app/migrate.py` imports reports, correction history, successful usage, and attempted requests from the local database into an empty hosted database. It refuses to overwrite or merge an existing destination.
- `neon.ts` declares the linked project's PostgreSQL service policy. Authentication is disabled and existing branch settings are preserved. Root `package.json` and `pnpm-lock.yaml` pin its configuration dependencies.
- `backend/app/verify_database.py` checks PostgreSQL while research is paused, using uniquely identified disposable rows. It tests report writes/reads/updates, concurrent quota reservations, imported sequence continuity, and cleanup without contacting AI providers.
- `.github/workflows/verify.yml` runs the unit suite, tests the PostgreSQL path against a disposable local PostgreSQL service, builds the locked website, and builds the image. It uses no real provider keys.

Production startup requires PostgreSQL, a built website, and a private rate-limit secret. Enabling hosted live research also requires the spending-history import marker. Paid provider reservations check that marker for every PostgreSQL connection, including local development against the remote database. Recreating the application container or adding a new database URL must not silently create a fresh spending allowance.

## Cost settings before any deployment

`plan: free` selects free compute; it is not an account-wide dollar cap. Render's documentation says bandwidth and build overages may be billed when a payment method is present. Without a payment method, it instead suspends services or disables new builds when those allowances are exhausted. Keep this demo in a Free workspace without a payment method, and set the build spending limit to zero where available. If the existing workspace has billing attached, resolve its billing controls before deploying this demo. Do not select a paid service, disk, database, or Neon plan.

Application defaults remain 30 Nebius attempts per UTC day / 60 total, and 20 Tavily requests per UTC day / 40 total. Attempts that fail still count. These limits are shared by all workers using the same database, and do not replace account billing controls or cover activity elsewhere with the same keys.

## Setup sequence

Steps 1–3 are complete for the current project. Do not repeat the import into the populated destination.

1. Create a Neon Free account/project. Link it using the official Neon CLI and pull its PostgreSQL environment into `backend/.env` with `neon env pull --service postgres --file backend/.env`. Never paste connection strings in chat or commit them. Keep `STUDYLENS_LIVE_ENABLED=false` while preparing migration.
2. Finish any in-flight local investigations, pause and stop all local API workers, and keep the hosted service paused. This prevents either environment from adding spending during the transfer.
3. From `backend`, run `uv run python -m app.migrate --sqlite studylens.db`. It reads the source in a consistent read-only transaction, imports all reports and usage, and marks the destination ready. Keep the original SQLite database as a backup. A configured database error must be fixed rather than worked around with a new database.
4. When publication is authorized, publish the repository with its existing license. The GitHub connection is available locally, but no remote was configured or created during preparation. Wait for the **Verify app and deployment image** workflow to pass, including its PostgreSQL tests and Docker build.
5. In the existing Render account, create the service from the repository's `render.yaml` Blueprint. Check that the selected compute plan is Free and automatic deployments are off. Render prompts privately for `DATABASE_URL`, `NEBIUS_API_KEY`, and `TAVILY_API_KEY`; it generates the rate-limit secret. Do not put these values in Git or frontend build variables.
6. Deploy with `STUDYLENS_LIVE_ENABLED=false`. Verify `/healthz`, `/api/health`, the worked example, and a migrated report URL. Restart/redeploy once while paused and confirm that report history and request counts are unchanged.
7. After the billing, persistence, and build checks pass, enable live research in Render and redeploy. All future local API workers must also use the same PostgreSQL URL. Do not resume a separate SQLite worker with the same paid keys.

Render Free sleeps after 15 minutes idle and may take about a minute to wake. Open the app before recording the demo. This setup is suitable for a limited public demo; hosted cold-start latency and persistence must be checked on the actual deployment.

## Local verification and remaining gates

The official Neon CLI 8.13.2 was run through `pnpm dlx` because npm was absent from the normal Windows PATH. After browser sign-in, `neon init` linked the existing production branch with PostgreSQL only and `--no-agent-setup`; no additional agent access was configured. `neon deploy` reported **No changes** and **Utilized services: Postgres**. No installed Neon agent skills were found, so the existing Python/psycopg adapter and official CLI documentation guided setup.

Private connection variables are in ignored root `.env.local` and `backend/.env`; the local `.neon` context and dependency folders are also ignored. The backend reads its own `.env`. Database credentials are never frontend build variables.

The SQLite import preserved **13 reports, 27 usage records, and 25 attempt records**, including corrections. Historical usage without an attempt record is still counted: real lifetime counters remain **27 Nebius and 7 Tavily**. The original SQLite file remains the backup. All API workers were stopped for the import and the resumed app uses PostgreSQL with research paused.

`uv run python -m app.verify_database` passed against the actual Neon database with TLS required. Eight concurrent disposable reservations accepted two and blocked six under a cap of two. Write/read/update, sequence continuity, usage counting, and cleanup passed. Original row counts and real provider counters were unchanged; **zero Nebius/Tavily calls** were made. See `evaluation/results/neon-storage-verification.json`.

The root `npm run build` passed, and `npm start` served the built frontend and API on port 8000. `/api/health` returned PostgreSQL and live research disabled. A migrated report opened in the browser with its Kaplan source, contradiction assessment, and prior Chinchilla correction history. The offline suite passed **51 tests**, with the three local PostgreSQL service tests skipped. Windows-generated pytest/uvicorn launchers initially failed to canonicalize their paths; scripts now use `python -m pytest` and `python -m uvicorn`, which passed.

For subsequent local checks, install the root and web dependencies, sync the backend environment, and use `npm run build`, `npm test`, `npm run verify:database`, and `npm start`. To serve the built website locally set `STUDYLENS_WEB_DIST=../web/dist` in `backend/.env`. Database verification requires research to remain paused and a completed spending-history import.

The Docker CLI is installed, but its Linux engine was unavailable during preparation. The image build and three disposable-service PostgreSQL tests remain pending. Those tests require `STUDYLENS_TEST_POSTGRES_URL` pointing to `localhost/studylens_test`; they deliberately refuse a hosted database and create/drop only their own random test schemas. The prepared GitHub workflow supplies that service and runs these checks before deployment. It has not run on GitHub yet. The separate Neon verification above does not replace these CI checks.

Repository publication, the CI/cloud image build, Render billing checks, paused Render deployment verification, and final enablement are still pending. Keep live research disabled until those gates pass.

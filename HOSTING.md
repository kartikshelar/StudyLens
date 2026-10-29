# Hosting preparation

The prepared target is **one Render Free web service plus Neon Free PostgreSQL**. The same service serves the built React website and FastAPI routes, so no separate frontend service or public API-base configuration is needed. This project has not been published or deployed yet.

## Why PostgreSQL is required

[Render Free services lose local files on restarts, redeploys, and idle shutdowns](https://render.com/docs/free). Using the local SQLite database there would lose saved reports and reset spending counters. Free Render Postgres also expires after 30 days. [Neon Free](https://neon.com/pricing) currently offers PostgreSQL without a time limit or credit card requirement; select the Free plan and keep it there.

SQLite remains the local development default. Setting `DATABASE_URL` selects PostgreSQL. Connection failures fail closed rather than creating a replacement SQLite database. PostgreSQL uses transaction-level advisory locks for quota reservations and HTTP rate windows; the counters live in the database rather than in an individual server instance.

## Prepared files

- `Dockerfile` builds the locked frontend, installs the locked Python dependencies, and runs as a non-root user.
- `.dockerignore` excludes credentials, local databases, evaluation artifacts, and development dependencies.
- `render.yaml` selects `plan: free`, leaves automatic deployments off, and starts with live research paused. The service's health check is `/healthz`, which makes no provider or database call.
- `backend/app/migrate.py` imports reports, correction history, successful usage, and attempted requests from the local database into an empty hosted database. It refuses to overwrite or merge an existing destination.
- `.github/workflows/verify.yml` runs the unit suite, tests the PostgreSQL path against a disposable local PostgreSQL service, builds the locked website, and builds the image. It uses no real provider keys.

Production startup requires PostgreSQL, a built website, and a private rate-limit secret. Enabling hosted live research also requires the spending-history import marker. Paid provider reservations check that marker for every PostgreSQL connection, including local development against the remote database. Recreating the application container or adding a new database URL must not silently create a fresh spending allowance.

## Cost settings before any deployment

`plan: free` selects free compute; it is not an account-wide dollar cap. Render's documentation says bandwidth and build overages may be billed when a payment method is present. Without a payment method, it instead suspends services or disables new builds when those allowances are exhausted. Keep this demo in a Free workspace without a payment method, and set the build spending limit to zero where available. If the existing workspace has billing attached, resolve its billing controls before deploying this demo. Do not select a paid service, disk, database, or Neon plan.

Application defaults remain 30 Nebius attempts per UTC day / 60 total, and 20 Tavily requests per UTC day / 40 total. Attempts that fail still count. These limits are shared by all workers using the same database, and do not replace account billing controls or cover activity elsewhere with the same keys.

## Setup sequence

1. Create a Neon Free account/project. Copy its PostgreSQL connection URL, including SSL settings, into `backend/.env` as `DATABASE_URL`. Never paste it in chat or commit it. Keep `STUDYLENS_LIVE_ENABLED=false` while preparing migration.
2. Finish any in-flight local investigations, pause and stop all local API workers, and keep the hosted service paused. This prevents either environment from adding spending during the transfer.
3. From `backend`, run `uv run python -m app.migrate --sqlite studylens.db`. It reads the source in a consistent read-only transaction, imports all reports and usage, and marks the destination ready. Keep the original SQLite database as a backup. A configured database error must be fixed rather than worked around with a new database.
4. When publication is authorized, publish the repository with its existing license. The GitHub connection is available locally, but no remote was configured or created during preparation. Wait for the **Verify app and deployment image** workflow to pass, including its PostgreSQL tests and Docker build.
5. In the existing Render account, create the service from the repository's `render.yaml` Blueprint. Check that the selected compute plan is Free and automatic deployments are off. Render prompts privately for `DATABASE_URL`, `NEBIUS_API_KEY`, and `TAVILY_API_KEY`; it generates the rate-limit secret. Do not put these values in Git or frontend build variables.
6. Deploy with `STUDYLENS_LIVE_ENABLED=false`. Verify `/healthz`, `/api/health`, the worked example, and a migrated report URL. Restart/redeploy once while paused and confirm that report history and request counts are unchanged.
7. After the billing, persistence, and build checks pass, enable live research in Render and redeploy. All future local API workers must also use the same PostgreSQL URL. Do not resume a separate SQLite worker with the same paid keys.

Render Free sleeps after 15 minutes idle and may take about a minute to wake. Open the app before recording the demo. This setup is suitable for a limited public demo; hosted cold-start latency and persistence must be checked on the actual deployment.

## Local verification and remaining gates

The built frontend was served directly by FastAPI on port 8100 for the browser screenshot and correction checks. Offline tests cover decoded-image limits, route ordering, no SQLite fallback, production startup requirements, migration preservation, and request quotas.

The Docker CLI is installed, but its Linux engine was unavailable during preparation. Consequently the image build and real PostgreSQL tests were not executed locally. The PostgreSQL tests skip unless `STUDYLENS_TEST_POSTGRES_URL` points to a disposable `localhost/studylens_test` database; they refuse a hosted database and create/drop only their own random test schemas. The prepared GitHub workflow supplies that service and runs the checks before deployment. It has not run on GitHub yet.

The Neon account/project, private database URL, repository publication, cloud build, paused deployment verification, and final enablement are still pending.

# StudyLens

**Working title.** StudyLens helps people trace a research-backed claim in a post or screenshot to the original study and see where the wording changed.

The first release focuses on public science and technology claims with accessible primary sources. A person can submit a claim, review the extracted wording, inspect the matched study and supporting passages, correct a source match, and save a shareable evidence view. When the source cannot be established, StudyLens says so.

This is an active build for the [Nebius x NVIDIA Global AI Hackathon](https://nebiusglobalaihackathon.devpost.com/), whose submission deadline is October 30, 2026 at 10:00 a.m. Pacific. The product continues after the event if it does not pass the release gates in time.

## Product promise

**Input:** a screenshot or typed claim about a research result.

**Output:** an inspectable path from that claim to a primary source, showing what was studied, what was measured, what the source actually says, and what remains unresolved.

StudyLens presents evidence for people to inspect. It does not assign a universal truth score or give medical advice.

## Build status

The local web interface, API, persistence, and offline integration tests are in place. The interface includes a clearly labeled worked example based on the published *Attention Is All You Need* abstract; it makes no model call. **Live Tavily Search and Extract calls were verified on October 27, 2026. A live Nemotron 3.5 Lightning call through Nebius Token Factory was verified on October 28, 2026.** A direct live investigation on October 28 matched a Chinchilla claim to the original [arXiv paper](https://arxiv.org/abs/2203.15556), displayed an exact abstract passage, and labeled the coverage as abstract only. That single success is a smoke test, not a measured accuracy result. A hosted demo, measured evaluation, and public repository are pending. Do not describe this project as deployed, used by others, or hackathon-submitted until those events occur.

## Run locally

Install Python 3.11+, [uv](https://docs.astral.sh/uv/), Node.js 20+, and [pnpm](https://pnpm.io/installation). From the `studylens` folder:

1. In `backend`, copy `.env.example` to `.env` and fill in `NEBIUS_API_KEY` and `TAVILY_API_KEY`. Do not commit `.env` or paste keys into a chat. The hackathon's [Resources page](https://nebiusglobalaihackathon.devpost.com/resources) explains the Nebius credit claim; obtain Tavily access from its official site or the hackathon benefits.
2. In `backend`, run `uv sync --extra dev`, then `uv run python -m uvicorn app.main:app --host 127.0.0.1 --port 8000`.
3. In a second terminal in `web`, run `pnpm install`, then `pnpm dev`. Open `http://127.0.0.1:5173`.

The Vite development server forwards `/api` calls to port 8000. If the API or keys are missing, the interface shows that state. Its worked example can be explored without credentials and is visibly identified as an example, never as a live investigation.

The API disables model reasoning for structured extraction and caps each model response at 800 tokens by default. It reserves a persistent request slot **before** each paid provider request, including requests that time out or return invalid data. The reservation is atomic, so simultaneous requests cannot bypass the quota. Returned token usage is recorded separately. Default caps are 30 Nebius attempts per UTC day and 60 total, plus 20 Tavily requests per UTC day and 40 total. Tavily Search and Extract share its quota; the free arXiv metadata read uses neither paid quota. The total caps do not reset each day.

Paid HTTP routes also allow at most 6 requests per minute and 20 per hour per observed client address. Saved reports, health reads, and the worked example remain available. Set `STUDYLENS_LIVE_ENABLED=false` and restart the API to pause paid routes. Setting any provider request limit to `0` blocks new requests to that provider. See `backend/.env.example` for the controls. Increase caps only after checking actual provider balances.

These are request limits for this application and database, **not dollar limits or account billing controls**. They cannot cover API use outside this app, reconstruct old failed requests, or prevent a provider's account-level card charge. Tavily activity before the new attempt ledger is also untracked. No automatic top-up or paid account upgrade is configured by the application.

The local app now uses Neon PostgreSQL through `DATABASE_URL`, with its existing reports and spending history imported. Real database checks passed for report writes/reads/updates and concurrent quota reservations while research remained paused. Production rejects ephemeral SQLite and a configured PostgreSQL failure cannot fall back to fresh local counters. All workers must share the same database. Set a private `STUDYLENS_RATE_LIMIT_SECRET` shared by workers so client throttling is consistent. The throttle uses the ASGI-observed client address, not arbitrary forwarding headers. Clients behind one proxy may share a throttle until its trusted-proxy configuration is verified. The public Render deployment, its restart/persistence check, and proxy configuration remain pending; follow [HOSTING.md](HOSTING.md).

## Verify

- `cd backend && uv run python -m pytest -q`
- `cd web && pnpm build`
- From the repository root, `npm run build` builds the website and checks Python compilation; `npm start` serves it when `STUDYLENS_WEB_DIST=../web/dist` is set in `backend/.env`.
- With Neon configured and research paused, `npm run verify:database` checks disposable database records and quotas without paid provider calls. See [the recorded results](evaluation/results/neon-storage-verification.json).
- Check `/api/health` for `providers_configured`, then run one real claim and inspect the source page yourself.

The nine-case diagnostic set and evaluation CLI are described in [evaluation/README.md](evaluation/README.md). `uv run python -m app.evaluate` from `backend` validates it offline. Live evaluation requires explicit case IDs and per-run request caps. Machine-checkable results remain separate from pending human evidence review; provider failures cannot count as successful abstentions.

## How the services are used

NVIDIA Nemotron through **Nebius Token Factory** extracts the claim, chooses a candidate source, and compares the claim to retrieved text. A vision-capable Nemotron model is intended for screenshot extraction. **Tavily Search** finds candidate research pages; **Tavily Extract** retrieves accessible source text for supported pages. For arXiv papers, the official metadata API supplies titles, authors, submission dates, and abstracts. Up to three explicit arXiv citations in search results can be resolved in the same metadata request, helping recover an original paper when search returns a later citing paper. Retrieved official abstracts are reused within that report.

When official arXiv metadata conflicts with an explicit author attribution or a single study year in the claim, the candidate is excluded. A preprint earlier than a claimed journal year remains eligible. These narrow guards do not establish provenance for every source. The model still assesses original-study status, and the UI labels results as candidates with reader corrections.

For quotation, the comparison model selects one to three consecutive passage IDs. The server copies those passages from the retrieved text and checks them against the source, preserving original formatting and wording. It does not ask the model to transcribe the quote. Older responses with a copied quote must still pass verbatim matching. Selecting a real passage does not prove the model interpreted it correctly; summaries and comparison labels remain model outputs requiring inspection. The visible source identity note uses retrieved metadata, while an unverified selection rationale is kept in the trace.

Current defaults are `nvidia/Nemotron-3_5-Lightning` for extraction and source selection, `nvidia/nemotron-3-super-120b-a12b` for comparison, and `nvidia/Nemotron-3.5-Super-VL` for images. The stronger comparison route was introduced after a diagnostic case exposed an inconsistent contradiction label in Lightning; this matches [Nebius's guidance on the Nemotron lineup](https://nebius.com/services/token-factory/models/nvidia-nemotron-models-inference). Both text routes and one real screenshot extraction have been verified live. The browser screenshot flow and accepted/rejected source corrections are recorded in [browser test results](evaluation/results/browser-smoke-2026-10-29.json). Images are decoded and checked for pixel limits, then resized to at most 1600px per edge before inference. The supported source domains and allowed model set are listed in `backend/app/providers.py`.

## Scope and limitations

StudyLens currently accepts pasted text or PNG/JPEG/WebP screenshots. It can save reports locally and reopen them by URL while the same database is available. It cannot reliably inspect paywalled papers, every publisher, or every claim. A reader can submit a supported primary-source URL if the initial search misses it. A report is an evidence trail, not a fact-check verdict.

The hosted release needs a persistent database, rate limits, and spending limits before opening public traffic. Screenshot content and claims are sent to the configured model provider, and searches are sent to Tavily. Use public material without personal information while this build is being tested.

See [PRODUCT.md](PRODUCT.md) for the product boundary, [MILESTONES.md](MILESTONES.md) for release gates, and [HOSTING.md](HOSTING.md) for the prepared free hosting configuration and its remaining verification steps.

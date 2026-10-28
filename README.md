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
2. In `backend`, run `uv sync --extra dev`, then `uv run uvicorn app.main:app --host 127.0.0.1 --port 8000`.
3. In a second terminal in `web`, run `pnpm install`, then `pnpm dev`. Open `http://127.0.0.1:5173`.

The Vite development server forwards `/api` calls to port 8000. If the API or keys are missing, the interface shows that state. Its worked example can be explored without credentials and is visibly identified as an example, never as a live investigation.

The API disables model reasoning for structured extraction, caps each model response at 800 tokens by default, records returned token usage in the local SQLite database, and stops after 30 Nebius calls per UTC day. Override `NEBIUS_MAX_OUTPUT_TOKENS` or `STUDYLENS_DAILY_NEBIUS_CALL_LIMIT` only after checking the Token Factory balance. These application controls do not replace account billing controls; keep automatic top-ups disabled if the account must never charge a card.

## Verify

- `cd backend && uv run pytest -q`
- `cd web && pnpm build`
- Check `/api/health` for `providers_configured`, then run one real claim and inspect the source page yourself.

## How the services are used

NVIDIA Nemotron through **Nebius Token Factory** extracts the claim, chooses a candidate source, and compares the claim to retrieved text. A vision-capable Nemotron model is intended for screenshot extraction. **Tavily Search** finds candidate research pages; **Tavily Extract** retrieves accessible source text for supported pages. For arXiv papers, the official arXiv metadata API supplies the abstract when available. The API verifies that each displayed quote is present in the retrieved text and asks the model whether the page is the original study. Neither check proves provenance, so the UI labels the result a candidate and retains reader corrections.

Current local defaults are `nvidia/Nemotron-3_5-Lightning` for text and `nvidia/Nemotron-3.5-Super-VL` for images. The text model's request format has been verified live; screenshot extraction with the vision model still needs a live check. The supported primary-source domains are listed in `backend/app/providers.py`.

## Scope and limitations

StudyLens currently accepts pasted text or PNG/JPEG/WebP screenshots. It can save reports locally and reopen them by URL while the same database is available. It cannot reliably inspect paywalled papers, every publisher, or every claim. A reader can submit a supported primary-source URL if the initial search misses it. A report is an evidence trail, not a fact-check verdict.

The hosted release needs a persistent database, rate limits, and spending limits before opening public traffic. Screenshot content and claims are sent to the configured model provider, and searches are sent to Tavily. Use public material without personal information while this build is being tested.

See [PRODUCT.md](PRODUCT.md) for the product boundary and [MILESTONES.md](MILESTONES.md) for release gates.

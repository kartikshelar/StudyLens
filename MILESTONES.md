# StudyLens release gates

The objective is a useful public product and a defensible portfolio project. Submit to the hackathon by **October 30, 2026 at 10:00 a.m. Pacific** only if the required gates pass. Continue the same project after the deadline if they do not.

## Gate 0 — access and repository

- [x] Create a dedicated local project and Git repository.
- [x] Obtain Nebius Token Factory access and make a successful call to an NVIDIA Nemotron model. Verified with Nemotron 3.5 Lightning on October 28, 2026; the final connection check used 35 total tokens with reasoning disabled.
- [x] Obtain Tavily access and make a successful search call. Verified with a live research-paper search on October 27, 2026; Tavily Extract also retrieved a public arXiv abstract.
- [x] Keep credentials in environment variables; verify no key enters Git history. The local `backend/.env` is ignored and has never been tracked.

## Gate 1 — one real investigation

- [x] Accept a user-written research claim and let the user confirm its extracted wording. Text extraction succeeded live on October 28; on October 29 UTC, the browser screenshot flow showed an editable claim/search review and produced a live saved report after the search phrase was edited.
- [x] Search for candidate primary sources using a live service. Tavily returned Chinchilla candidates on October 28, 2026.
- [x] Present the selected source, supporting passage, and visible reason for the match. The October 28 direct API smoke test selected arXiv:2203.15556 with an exact abstract passage. Its saved result was reviewed in the browser; the live input flow still needs review.
- [x] Return a useful **source not confirmed** result when no defensible source is found. An October 28 live test with a deliberately invented Stanford green-tea claim found four unrelated candidates and selected none.
- [x] Record the model and search calls used in the investigation. The report trace records them; the local usage ledger recorded two Nebius calls for the successful smoke test.

## Gate 2 — complete user journey

- [x] Accept a screenshot and extract the claim with a real NVIDIA model on Nebius. Nemotron 3.5 Super VL preserved the test claim in the browser flow on October 29 UTC.
- [x] Show an evidence-first, responsive React/TypeScript interface. Saved matched and no-match reports were reviewed in the local browser at desktop and 390px widths, with keyboard order checked, on October 28, 2026. The hosted worked example and corrected report also opened successfully; mobile hosted review and the full live input flow remain pending.
- [x] Let the user correct the source and preserve the correction. Browser tests rejected a wrong-author paper without a model call, then corrected an earlier real wrong-source report from Chinchilla to Kaplan. The new source, prior source history, and copied report link survived reload.
- [x] Save a report and open it from a shareable URL. Both live smoke reports reopened by local report URL during the browser review. The [corrected Kaplan report](https://studylens-id7z.onrender.com/?report=f8ed23ba-e2fd-4284-813e-2615de7edcc4) opened publicly from Neon after a Render restart, with its correction history intact.
- [ ] Handle errors, timeouts, unsupported sources, and empty inputs clearly. Image decoding/pixel limits and pause states have offline coverage; broader browser error checks remain pending.

## Gate 3 — credible quality proof

- [ ] Create a labeled set of public claims with known original sources and deliberate no-match cases. Nine proposed cases with source-record checks are in `evaluation/cases.json`; Kartik's manual label review remains pending.
- [ ] Measure source-match correctness, unsupported assertions, abstentions, latency, and cost. Publish denominators and failure cases.
- [ ] Get feedback from people outside the build and record changes made because of it. Do not claim adoption or users before this happens.
- [ ] Review the hosted experience on desktop and mobile; verify keyboard navigation.

The evaluation CLI now validates cases and scores saved reports offline. Explicit live runs are capped independently and save latency, attempts, returned token usage, and per-check results. The first two-case diagnostic exposed a wrong-source match for Kaplan; official metadata, citation following, and author/date exclusions recovered the original. A comparison-model change and indexed passage selection then produced two passing automated comparisons using those cached source selections, including a contradiction. Failures and scope are recorded in `evaluation/results/smoke-2026-10-29.json`. Human review, the full nine-case run, a fresh end-to-end run after the passage change, and dollar-cost measurement remain pending.

The public demo includes atomic daily and total request caps for Nebius and Tavily, client throttling, and a live-research pause switch. These have offline coverage for timeouts, concurrency, restarts/day changes, and repeated HTTP requests. Hosted report and counter persistence passed after a user-reported Render restart. Proxy behavior still needs verification before opening live research.

The single-service Docker/Render Free setup and PostgreSQL adapter are documented in `HOSTING.md`. Neon Free is connected: 13 reports, 27 usage records, and 25 attempt records were imported, preserving lifetime counters of 27 Nebius and 7 Tavily requests. Actual Neon write/read/update, concurrent quota, sequence, and cleanup checks passed with zero paid provider calls. The [public repository](https://github.com/kartikshelar/StudyLens), [GitHub CI](https://github.com/kartikshelar/StudyLens/actions/runs/40829176988), and [paused Render site](https://studylens-id7z.onrender.com/) are live. The migrated report and correction history opened on the public site after a user-reported restart. Research remains paused. Production rejects ephemeral SQLite, and hosted live requests require the imported spending ledger. Billing, proxy behavior, product quality, and live input verification remain pending.

## Gate 4 — submission-ready

- [ ] Host an unrestricted working demo that will remain available through judging. The public site is deployed, but live research is paused pending remaining checks.
- [x] Publish the code with an open-source license and reproducible setup instructions. The [repository](https://github.com/kartikshelar/StudyLens) is public, and CI verifies its tests and Docker build.
- [ ] Record a public video under three minutes showing the real workflow and naming the NVIDIA model and Nebius Token Factory.
- [ ] Write the project description and specific feedback on Nebius/NVIDIA tools.
- [ ] Submit before the deadline and save the confirmation.

## Working method with Codex, Claude, and Cursor

This file is the shared source of truth. Pick one small, testable task at a time. State the expected user-visible behavior before coding. Have one tool edit a file at a time; another tool can review it afterward. Run the app and inspect the result before marking a checkbox. Record concrete failures, changes, and measurements in the repository. AI-generated code and claims are reviewed by Kartik and must be explainable in an interview.

Suggested strengths: Codex for implementation, integration, and verification; Claude for adversarial product and reasoning review; Cursor for hands-on UI iteration with the app open. These roles guide future assignments.

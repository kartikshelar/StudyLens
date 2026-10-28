# StudyLens release gates

The objective is a useful public product and a defensible portfolio project. Submit to the hackathon by **October 30, 2026 at 10:00 a.m. Pacific** only if the required gates pass. Continue the same project after the deadline if they do not.

## Gate 0 — access and repository

- [x] Create a dedicated local project and Git repository.
- [x] Obtain Nebius Token Factory access and make a successful call to an NVIDIA Nemotron model. Verified with Nemotron 3.5 Lightning on October 28, 2026; the final connection check used 35 total tokens with reasoning disabled.
- [x] Obtain Tavily access and make a successful search call. Verified with a live research-paper search on October 27, 2026; Tavily Extract also retrieved a public arXiv abstract.
- [x] Keep credentials in environment variables; verify no key enters Git history. The local `backend/.env` is ignored and has never been tracked.

## Gate 1 — one real investigation

- [ ] Accept a user-written research claim and let the user confirm its extracted wording. Live text extraction succeeded on October 28, 2026, and its output led to a successful Chinchilla investigation through the API; the on-screen review step still needs a hands-on check.
- [x] Search for candidate primary sources using a live service. Tavily returned Chinchilla candidates on October 28, 2026.
- [x] Present the selected source, supporting passage, and visible reason for the match. The October 28 direct API smoke test selected arXiv:2203.15556 with an exact abstract passage. The user-facing flow still needs review.
- [x] Return a useful **source not confirmed** result when no defensible source is found. An October 28 live test with a deliberately invented Stanford green-tea claim found four unrelated candidates and selected none.
- [x] Record the model and search calls used in the investigation. The report trace records them; the local usage ledger recorded two Nebius calls for the successful smoke test.

## Gate 2 — complete user journey

- [ ] Accept a screenshot and extract the claim with a real NVIDIA model on Nebius.
- [ ] Show an evidence-first, responsive React/TypeScript interface.
- [ ] Let the user correct the source and preserve the correction.
- [ ] Save a report and open it from a shareable URL.
- [ ] Handle errors, timeouts, unsupported sources, and empty inputs clearly.

## Gate 3 — credible quality proof

- [ ] Create a labeled set of public claims with known original sources and deliberate no-match cases.
- [ ] Measure source-match correctness, unsupported assertions, abstentions, latency, and cost. Publish denominators and failure cases.
- [ ] Get feedback from people outside the build and record changes made because of it. Do not claim adoption or users before this happens.
- [ ] Review the hosted experience on desktop and mobile; verify keyboard navigation.

## Gate 4 — submission-ready

- [ ] Host an unrestricted working demo that will remain available through judging.
- [ ] Publish the code with an open-source license and reproducible setup instructions.
- [ ] Record a public video under three minutes showing the real workflow and naming the NVIDIA model and Nebius Token Factory.
- [ ] Write the project description and specific feedback on Nebius/NVIDIA tools.
- [ ] Submit before the deadline and save the confirmation.

## Working method with Codex, Claude, and Cursor

This file is the shared source of truth. Pick one small, testable task at a time. State the expected user-visible behavior before coding. Have one tool edit a file at a time; another tool can review it afterward. Run the app and inspect the result before marking a checkbox. Record concrete failures, changes, and measurements in the repository. AI-generated code and claims are reviewed by Kartik and must be explainable in an interview.

Suggested strengths: Codex for implementation, integration, and verification; Claude for adversarial product and reasoning review; Cursor for hands-on UI iteration with the app open. These are roles for future work, not a claim that all three have already built code.

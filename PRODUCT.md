# StudyLens product brief

## Audience and job

For readers who encounter a science or technology claim online and want to inspect the original evidence without searching through several articles and papers. The first use case is a screenshot or short post that explicitly refers to a study, paper, or research result.

## Complete first-release journey

1. A user enters a claim as text or uploads a screenshot.
2. NVIDIA Nemotron on Nebius Token Factory extracts one checkable claim. The user can edit or reject the extraction.
3. A search tool finds candidate primary sources. StudyLens records the search queries and candidate URLs.
4. The system chooses a candidate only when it can show why it matches the claim. Otherwise it returns **source not confirmed** and lets the user add a source.
5. The evidence view places claim wording beside source passages and identifies the study population or subject, method, result, and uncertainty when those are available.
6. The user can correct the source match, save the report, and share a link. Corrections are retained with provenance.

The first release supports public sources that can be retrieved legally and parsed reliably. It never invents missing study details. A partial abstract is labeled as partial evidence. It does not treat a search result snippet as the full study.

## Product rules

- Every factual statement in a report has a clickable source and a quoted supporting excerpt or is marked as an inference/unknown.
- A headline is not the primary source. Candidate matching must prefer the original paper, preprint, DOI landing page, or official research release.
- A user correction changes the selected source visibly; the original automated match remains in the audit trail.
- Screenshot processing and source research are separate stages, with visible progress and useful errors.
- The public demo must use live Nebius inference. A fixture may be used for automated tests, but must be labeled and never substituted for the judged demo.
- The interface must work on desktop and mobile, with keyboard access and no hidden evidence behind an opaque score.

## Initial technical shape

- **Web:** React and TypeScript, with an evidence-first interface.
- **API:** Python/FastAPI with typed request and response contracts.
- **Persistence:** SQLite for local development, a managed relational database for the hosted release.
- **Models:** a current public NVIDIA Nemotron endpoint on Nebius Token Factory; verify the exact vision request format and model availability before wiring screenshot input.
- **Search:** Tavily runtime search if access is available, plus explicit source-selection and evidence validation logic.
- **Quality:** recorded tool traces, latency and token usage, manual review of a small labeled evaluation set, and honest failure handling.

## Design direction

The interface should feel like an evidence desk: the original claim stays visible while the source and its supporting passages appear beside it. The visual centerpiece is a claim-to-source path, with each transformation inspectable. Use clear document typography, restrained color to distinguish observed evidence from uncertainty, and one deliberate reveal when the source path is found. Avoid a generic chat screen or a grid of identical cards.

## Deliberately outside the first release

Universal fact checking, paywalled paper extraction, claims without a research source, automatic medical recommendations, link import, a browser extension, and broad social-platform integrations. These can be considered after the complete first-release journey works.

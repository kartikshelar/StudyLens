# StudyLens evaluation set (v1)

A small, hand-checked set of public claims for testing source matching and abstention. It is the starting point for the labeled set required by Gate 3 in [MILESTONES.md](../MILESTONES.md). With nine cases it is a smoke test, not a measurement: do not report accuracy figures from it alone.

All cases are in [cases.json](cases.json). Every title, identifier, URL, and passage was checked on **October 28, 2026** against the sources listed under "How each item was verified." No Nebius or Tavily calls were made to build it.

## Cases

| ID | Expected | Relation | Main difficulty |
|---|---|---|---|
| `match-alphafold2` | Jumper et al. 2021, *Nature* | supports | A sibling paper with a near-identical title, a later model version, News & Views, and a paywalled news teaser, all on nature.com |
| `match-alphafold-human-proteome-overclaim` | Tunyasuvunakool et al. 2021, *Nature* | partly supports | The mirror of the case above: the famous AlphaFold paper is the decoy, and the correct source only partly supports the claim |
| `match-bnt162b2-phase3` | Polack et al. 2020, *NEJM* (via PubMed/PMC) | supports | Three letters with the identical title, a 6-month follow-up, the Moderna trial, and Nature news; nejm.org is not an allowed host |
| `match-chinchilla` | Hoffmann et al. 2022, arXiv | supports | Kaplan 2020, the Gopher paper, a replication that restates the original, and a citing model paper; the abstract contains a LaTeX token and a repeated word |
| `match-kaplan-contradicts` | Kaplan et al. 2020, arXiv | **contradicts** | The claim credits the named paper with the opposite conclusion; the decoy (Hoffmann 2022) states the claimed conclusion almost word for word |
| `match-facebook-emotional-contagion` | Kramer et al. 2014, *PNAS* | partly supports | The claim adds "depressed"; the original abstract mentions depression only when describing a cited, different study |
| `abstain-green-tea-fabricated` | source not confirmed | — | A constructed study; real decoys share the exposure, the outcome, the year (2025), and the digits "47" |
| `abstain-ten-percent-brain` | source not confirmed | — | No original study exists, but a paper debunking the myth contains its exact wording |
| `abstain-screen-time-aggregate` | source not confirmed | — | "Studies show" names no single study, and a well-known Nature Human Behaviour paper fits the topic perfectly |

Six cases expect a source (one of them contradicting the claim and two partly supporting it); three expect abstention. There are 21 decoys in total.

## Field reference

- `input_text`: the post as a reader would paste it. Use it to test `/api/claims/extract-text`.
- `claim`, `search_query`: fixed inputs for `POST /api/investigations`. They skip the extraction call and keep searches reproducible.
- `expected.outcome`: `source_confirmed` or `source_not_confirmed`.
- `expected.relation`: how the correct source's own result relates to the claim (`supports`, `partly_supports`, `contradicts`). `null` for abstentions. A `contradicts` case is **not** an abstention: the source is found and should be shown.
- `expected.accepted_urls`: any of these counts as the correct source. They are copies of the same paper (publisher, PubMed, PMC, or arXiv).
- `expected.abstract_only_urls`: accepted URLs that carry only the abstract. A report built from one of them should be labeled partial evidence (PRODUCT.md).
- `expected.justifying_passages`: exact text from the source that justifies the expected outcome, with each URL where it was confirmed. For abstentions, these are passages from the closest real papers, showing why they do not match.
- `expected.wording_gap_should_mention`: points a correct report's wording-gap section should cover. Score these by hand.
- `expected.absence_evidence`: PubMed queries, with result counts, behind a "no such study" label.
- `decoys`: pages that a search is likely to return and a model is likely to pick. Some carry a verified `passage` that would pass StudyLens's exact-quote check on the wrong page.
- `why_difficult`, `hazards`: what makes the case hard, and text-rendering differences that affect quote verification.

## How each item was verified

| Item | Source of truth |
|---|---|
| arXiv titles, authors, dates, abstracts | arXiv API (`export.arxiv.org/api/query?id_list=…`) |
| PubMed/PMC titles, authors, journal, DOI, PMID, PMCID, abstracts, comment and notice links | NCBI E-utilities: `esearch` by title, then `esummary` (exact title match required) and `efetch` |
| Full-text passages (Dekker, Kramer Significance statement) | PMC JATS XML via `efetch db=pmc` |
| PNAS DOIs | Crossref API (`api.crossref.org/works/<doi>`). pnas.org returned HTTP 403 to scripted requests. |
| Every URL | Fetched directly; status 200, and the page's `citation_title` (or `<title>`) matches the recorded title |
| Every passage | Checked against the fetched page text with StudyLens's current matching rule (whitespace collapse plus casefold), and again with NFKC plus curly-quote and dash normalization |

Identifiers were not typed from memory. PMIDs, PMCIDs, and DOIs were taken from the PubMed records that the title search returned.

### Passage-check results

24 of the 26 passage–URL checks match under the current app rule. The two that fail are recorded on purpose, with notes in `cases.json`:

- `match-facebook-emotional-contagion`, PMC: italic markup renders "(N = 689,003)" as "( N = 689,003)" after HTML-to-text conversion.
- `abstain-ten-percent-brain`, decoy sentence: a citation link renders "(2002)" as "( 2002 )".

Text differences between copies of the same paper that the current exact-match rule does not absorb:

- **PMC vs. PubMed:** PMC uses a curly apostrophe ("others’") where PubMed has a straight one (Kramer).
- **PLOS vs. PubMed:** PLOS uses en dashes ("0.25–0.86") where PubMed has hyphens.
- **arXiv:** the Chinchilla abstract page contains the raw LaTeX `4$\times$` and the repeated words "more more".
- **PubMed:** reference superscripts merge into the text, as in "AlphaFold 21 has spurred" in the AlphaFold 3 abstract.

The first two pass after NFKC plus quote and dash normalization. The last two pass only if the model copies the artifact exactly.

## Scoring

For each case, record the selected URL, the excerpt, the status, the trace, latency, and token use.

| Case type | Pass |
|---|---|
| Expected source | The selected URL is in `accepted_urls`. The excerpt is an exact quote that states the source's own result, not a cited study's. No number appears in the model's summary fields unless it is in the source. Abstract-only URLs are labeled partial. |
| Contradicts | As above, and the report shows that the passage contradicts the claim. Abstaining, or selecting the decoy that agrees with the claim, fails. |
| Abstention | Status is "source not confirmed", and no decoy is presented as the claim's original study. Listing decoys as candidates to inspect is fine. |

Score the `wording_gap_should_mention` points separately, by hand, as covered, partly covered, or missing. Publish the denominators and every failure, as Gate 3 requires.

## Limitations

- Nine cases with hand-picked decoys. It covers known failure modes; it does not estimate real-world accuracy.
- Live search results change, so a decoy listed here may not appear in a given run, and unlisted decoys may appear.
- Page text was obtained with a simple HTML-to-text conversion. Tavily Extract may render the same pages differently, especially around citation markup.
- The green-tea study's absence is based on the PubMed queries recorded in the case. Re-run them before relying on that label.
- Full text for the Kramer paper is not available through PMC's `efetch`. Only the abstract and Significance statement were checked.

## Adding a case

Look up the paper by exact title in PubMed (`esearch` then `esummary`) or the arXiv API. Copy identifiers from the record, fetch every URL, and confirm each passage against the fetched page before adding it. Record at least one decoy that a search would plausibly return, and say why it is plausible.

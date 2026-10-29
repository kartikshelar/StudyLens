# Review of the final Chinchilla and Kaplan reports

**Scope and method.** This is a document-based review of the source text stored inside two saved reports. It is not an independent verification of the sources. Every judgment compares a report's displayed claims with the official arXiv abstract embedded in that same report (`selected_source.source_text`, `metadata_source: "arxiv_api"`). No Nebius, Tavily, arXiv, browser, or other network calls were made, and no application code was changed. The reports were read from `backend/studylens.db` in read-only mode. Rendering was checked against `web/src/App.tsx` at commit `92f0765`.

The review was written by Claude (an AI assistant). It has not been reviewed by Kartik, and nothing here should be read as a human review.

| Report | Case | Mode |
|---|---|---|
| `c9bad215-ed6e-40f4-8f50-fa6d90ee0a2c` | `match-chinchilla` | `cached_source_reassessment` of `76f742e8-490b-4376-808b-577cd56ab3f0` |
| `4bcfe8c3-5192-4481-9889-61b5e7d3bc01` | `match-kaplan-contradicts` | `cached_source_reassessment` of `e9fd92fb-dc5b-4a74-948d-103abeed6943` |

Both reports re-run only the comparison step against a saved abstract. Search and source selection come from earlier reports, which this review did not audit. The `passage-reassessment` entry in `evaluation/results/smoke-2026-10-29.json` says the same. These reports therefore show what the comparison step produces on a correct source. They are not evidence that the full pipeline reliably finds that source: in the same results file, the earlier live `super-comparison` run for Chinchilla (report `2d9fe7c8-…`) recorded `source_found: false`.

## Summary

| Check | Chinchilla `c9bad215` | Kaplan `4bcfe8c3` |
|---|---|---|
| Selected paper matches the claim's identity | Pass | Pass |
| Displayed quote is in the embedded abstract | Pass (exact substring) | Pass (exact substring) |
| Relation label justified | Pass, but the displayed quote shows only half the support | Pass, as an inference; the abstract is qualitative |
| "What was tested" limited to the abstract | Minor issue: adds "scaling laws" and omits the Chinchilla-vs-Gopher test | Pass |
| "What the study found" limited to the abstract | Pass, but incomplete: omits the result the claim's first half relies on | Pass |
| Wording gap | **Fail**: empty, although the abstract supports two clear gaps | Pass, with one unstated inference |
| Uncertainties | Empty; consistent with the abstract | Empty; consistent with the abstract |
| "Abstract only" label | Appropriate | Appropriate |
| Wording that could suggest proven provenance | Some (see findings 3–5) | Some (see findings 3–5) |

The automated smoke checks marked both reports `checks_passed`. Those checks do not score the wording gap or the summary fields, so `checks_passed` should not be read as "the report is accurate and complete." The Chinchilla report would fail the hand-scored `wording_gap_should_mention` criteria in `evaluation/cases.json`.

---

## Chinchilla — `c9bad215-ed6e-40f4-8f50-fa6d90ee0a2c`

**Claim:** "A 70B-parameter model trained on 4 times more data outperformed the 280B Gopher model, and model size and training tokens should be scaled equally."

**Selected:** `https://arxiv.org/abs/2203.15556`, "Training Compute-Optimal Large Language Models", Hoffmann et al., first submitted 2022-03-29.

The embedded abstract, split into sentences (numbering is 0-based and matches the report's `quote_selection`):

- [0] We investigate the optimal model size and number of tokens for training a transformer language model under a given compute budget.
- [1] We find that current large language models are significantly undertrained, …
- [2] By training over 400 language models ranging from 70 million to over 16 billion parameters on 5 to 500 billion tokens, we find that for compute-optimal training, the model size and the number of training tokens should be scaled equally: for every doubling of model size the number of training tokens should also be doubled.
- [3] We test this hypothesis by training a predicted compute-optimal model, Chinchilla, that uses the same compute budget as Gopher but with 70B parameters and 4$\times$ more more data.
- [4] Chinchilla uniformly and significantly outperforms Gopher (280B), GPT-3 (175B), Jurassic-1 (178B), and Megatron-Turing NLG (530B) on a large range of downstream evaluation tasks.
- [5] This also means that Chinchilla uses substantially less compute for fine-tuning and inference, …
- [6] As a highlight, Chinchilla reaches a state-of-the-art average accuracy of 67.5% on the MMLU benchmark, greater than a 7% improvement over Gopher.

### Identity: pass

The claim names no authors, year, or venue, so identity rests on content. Every content cue in the claim appears in the abstract: a 70B model, 4× more data, Gopher at 280B (sentences [3]–[4]), and equal scaling of model size and training tokens (sentence [2]). No other stored candidate competes. The other two candidates (an ACM DL record and an OpenReview forum) carry search-snippet text attributed to "J Hoffmann · 2022" and look like other venue records for the same work. The stored text cannot confirm that, especially for the OpenReview item, whose title differs ("An empirical analysis of compute-optimal large language ..."). Neither was assessed, and neither affects the selected source.

### Quote: pass

`supporting_excerpt` is sentences [2] and [3], an exact character-for-character substring of the embedded abstract. `quote_method: "indexed_passages"` with `quote_selection: [2, 3]` is consistent with that.

The quote faithfully reproduces the source's artifacts: `4$\times$` (raw LaTeX) and the repeated "more more". That is correct behavior, because rewriting the quote would break verification. But a reader sees the LaTeX and the duplicated word inside quotation marks and may assume StudyLens garbled the text (finding 5).

### Relation "supports": justified by the abstract, but the displayed quote shows only half of it

The claim has two parts:

1. **"Scaled equally"** is supported by sentence [2], under the condition "for compute-optimal training."
2. **"Outperformed the 280B Gopher model"** is supported by sentence [4], which is **not** in the displayed quote. The quote includes sentence [3] (the 70B, 4× setup) but stops before the outcome.

So "supports" is justified by the abstract as a whole, but a reader checking the label against the displayed passage, as the UI asks ("Check it against the passage above"), will find no evidence there for the outperformance half of the claim. The selection should have included sentence [4], for example `[2, 3, 4]`.

### "What was tested": minor issue

> Training over 400 language models ranging from 70 million to over 16 billion parameters on 5 to 500 billion tokens to determine compute-optimal scaling laws.

Every number (400, 70, 16, 5, 500) appears in sentence [2]. The phrase "scaling laws" does not appear in this abstract; the stated aim is "the optimal model size and number of tokens … under a given compute budget" (sentence [0]). The difference is small, but it is a term the model imported. The field also omits the second thing the abstract says was tested: training Chinchilla on Gopher's compute budget (sentence [3]). That test is the basis for the first half of the claim.

### "What the study found": accurate but incomplete

> For compute-optimal training, model size and the number of training tokens should be scaled equally: for every doubling of model size, the number of training tokens should also be doubled.

This is a near-verbatim restatement of sentence [2] (it adds one comma). It omits the Chinchilla-over-Gopher result in sentence [4], so the "found" panel addresses only half of the claim.

### Wording gap: fail

`wording_gap` is an empty string. The abstract supports at least two gaps between the claim and the source:

- **The compute condition is dropped.** The claim says the 70B model was "trained on 4 times more data"; the abstract says it "uses the same compute budget as Gopher" (sentence [3]). Without that condition, the comparison reads as a general claim about smaller models with more data.
- **The equal-scaling rule is generalized.** The claim states "should be scaled equally" as an unconditional rule; the abstract scopes it to "compute-optimal training" (sentence [2]).

A third, smaller one: "outperformed" omits the abstract's scope, "on a large range of downstream evaluation tasks" (sentence [4]).

These are exactly the two points listed under `wording_gap_should_mention` for `match-chinchilla` in `evaluation/cases.json`. Because `App.tsx` line 304 hides the "Where the wording changes" section when the field is empty, the reader sees no wording-gap section at all. The page neither says "no difference" nor flags that the gap was not assessed.

### Uncertainties: empty, consistent with the source

The abstract states no limitations, and the comparison prompt limits `uncertainties` to limitations the source states, so an empty list is correct. As with the wording gap, the UI hides the section when it is empty.

### "Abstract only": appropriate

The stored `source_text` is the arXiv API record: title, authors, submission date, and abstract only. `text_coverage: "abstract_only"` is correct. The UI note ("Abstract only. This is partial evidence: the passage and the assessment below use the abstract, not the full paper.") describes the situation accurately.

---

## Kaplan — `4bcfe8c3-5192-4481-9889-61b5e7d3bc01`

**Claim:** "Kaplan and colleagues' 2020 scaling-laws paper found that, for a fixed compute budget, model size and training data should be scaled up equally."

**Selected:** `https://arxiv.org/abs/2001.08361`, "Scaling Laws for Neural Language Models", Kaplan et al., first submitted 2020-01-23.

The embedded abstract (0-based, matching `quote_selection`):

- [0] We study empirical scaling laws for language model performance on the cross-entropy loss.
- [1] The loss scales as a power-law with model size, dataset size, and the amount of compute used for training, with some trends spanning more than seven orders of magnitude.
- [2] Other architectural details such as network width or depth have minimal effects within a wide range.
- [3] Simple equations govern the dependence of overfitting on model/dataset size and the dependence of training speed on model size.
- [4] These relationships allow us to determine the optimal allocation of a fixed compute budget.
- [5] Larger models are significantly more sample-efficient, such that optimally compute-efficient training involves training very large models on a relatively modest amount of data and stopping significantly before convergence.

### Identity: pass

All three identity cues in the claim match the stored metadata. "Kaplan" is the first listed author; "2020" matches the first submission date of 2020-01-23; "scaling-laws paper" matches the title. The recorded exclusions are correct on the stored metadata:

- Hoffmann et al. was excluded as first submitted in 2022, after the claim's 2020. This is the decoy that states the claim's conclusion, and excluding it was the key step.
- Adam and SentencePiece were excluded because their author lists do not include Kaplan.

One provenance gap: the selected paper's `discovery` is "arXiv citation in a search result," but the report does not record which search result contained the citation.

### Quote: pass

`supporting_excerpt` is sentences [4] and [5], an exact substring of the embedded abstract. Sentence [4] establishes that the paper addresses allocation under a fixed compute budget, which is the claim's framing. Sentence [5] gives the paper's stated recommendation. This is a well-chosen pair.

### Relation "contradicts": justified, as an inference the reader should see as one

The abstract says that optimally compute-efficient training uses "very large models on a relatively modest amount of data". That conflicts with the claim's "scaled up equally," and "contradicts" is a reasonable reading. However, the abstract is qualitative. It does not state the rates at which model size and data should grow with compute, and it never mentions equal scaling. The contradiction is inferred from the recommendation, not stated in the source. The UI already frames the label as a "Model assessment of the claim … not a verdict," which fits. The report would be more precise if it also said that the abstract does not quantify the allocation (see the wording gap below).

### "What was tested": pass

> empirical scaling laws for language model performance on cross-entropy loss as a function of model size, dataset size, and compute

Supported by sentences [0] and [1]. "As a function of" paraphrases "scales as a power-law with"; nothing new is added.

### "What the study found": pass

> larger models are significantly more sample-efficient, so optimally compute-efficient training involves training very large models on a relatively modest amount of data and stopping significantly before convergence

A near-verbatim restatement of sentence [5] ("such that" becomes "so"). No numbers, no added content.

### Wording gap: pass, with one unstated inference

> claim states equal scaling of model size and data; paper finds optimal strategy uses large models with modest data, not equal scaling

The first part accurately contrasts the claim with sentence [5]. "Not equal scaling" is the model's inference: the abstract does not use the phrase or state the relative growth rates. The UI shows this field under "Model summary of the passage, not a quotation," so it is not presented as a quote. A more careful wording would be: "the abstract recommends very large models on a relatively modest amount of data; it does not state equal scaling, and it does not give the exact allocation."

**Note on the evaluation case.** The second `wording_gap_should_mention` point for `match-kaplan-contradicts` in `evaluation/cases.json` reads "Equal scaling is the later finding of Hoffmann et al. (2022)." That fact is not in Kaplan's abstract. A report that follows the rule "state only what the accessible source supports" cannot and should not say it. The case should treat that point as context for the human scorer, not as a requirement for the report.

### Uncertainties: empty, consistent with the source

The abstract states no limitations. Empty is correct under the prompt rule.

### "Abstract only": appropriate

Same as Chinchilla: the stored text is the arXiv API record, and the label and UI note are accurate.

---

## Wording that could suggest proven provenance (both reports)

The status and labels are hedged well overall. The headline reads "Candidate match", the source heading reads "Candidate match", the status adds "The source identity is still a candidate. Open the paper and check the match yourself.", the relation is labeled a model assessment "not a verdict", and the summary fields are labeled "not a quotation." The issues below are narrower.

1. **Chinchilla's empty wording gap is invisible** (Chinchilla only; medium). With no wording-gap section and no uncertainties section, the only caveat on the page is the abstract-only note. A reader can reasonably conclude that the claim matches the source without qualification, when the abstract shows two dropped conditions. When `wording_gap` is empty, the UI should say so explicitly ("No wording difference was identified by the model"), or the comparison should be retried. It should not hide the section.

2. **The displayed Chinchilla quote does not cover the "supports" label** (Chinchilla only; medium). See above: the outperformance half of the claim rests on sentence [4], which is not shown.

3. **"Why this source: Official arXiv record: …"** (both; low to medium). The `selection_reason` describes where the metadata came from, not why the paper matches the claim. Under the heading "Why this source," "Official arXiv record" can read as confirmation of provenance. In the Kaplan report the actual identity reasons exist (author, year, title, and the exclusions) but are not in `selection_reason`; they are scattered in the trace and `source_exclusions`. Suggested wording: "Metadata from the arXiv API. Matches the claim's author (Kaplan), year (2020), and title; excluded candidates are listed below."

4. **The trace mixes the original run with the reassessment** (both; low to medium). Each trace begins with the original report's steps ("Tavily Search query: …", "assessed 3 candidates" or "assessed 1 candidates", "Retrieved candidate source text …", a Lightning comparison). It then repeats "Retrieved candidate source text" and adds a second comparison by `nemotron-3-super-120b-a12b`. Only the last line says search and selection were not repeated. A reader may conclude that this report ran a live search at its own `created_at` time. The report also does not say which of the two listed models produced the displayed comparison. The UI does not show `evaluation_mode` or `reassessment_of` anywhere. Suggested change: prefix inherited lines with the source report ID, say "Reused cached source text" instead of "Retrieved", and name the model that produced the displayed comparison.

5. **The verbatim LaTeX in the Chinchilla quote** (Chinchilla only; low). "4$\times$ more more data" is faithful to the source and must not be rewritten inside the quote. But with no explanation, it can make the quotation look corrupted, which undermines trust in a passage that is in fact exact. A short note such as "[as written in the arXiv abstract]" would help.

6. **The headline is identical for "supports" and "contradicts"** (Kaplan; low). Both reports show "Candidate match" with the same ↗ symbol. For Kaplan, the fact that the source contradicts the claim appears only in the relation block below the quote. That is acceptable, because the relation block is prominent. A reader who skims only the headline still sees a "match" for a claim the paper does not support.

## Recommended follow-ups

These are not applied; no application code was changed.

- In the comparison step, require the quote selection to include every sentence that supports each part of the claim marked "supports" or "partly supports".
- Treat an empty `wording_gap` on a multi-part claim as a signal to retry, and render empty fields explicitly instead of hiding them.
- Rewrite `selection_reason` to state the identity evidence, and label inherited trace lines in reassessment reports.
- In `evaluation/cases.json`, mark the second Kaplan `wording_gap_should_mention` point as scorer context rather than a requirement.
- Extend the smoke checks, or the manual scoring sheet, to cover the wording gap and the summary fields, so that `checks_passed` is not mistaken for a full report review.
- Audit the original reports (`76f742e8-…`, `e9fd92fb-…`) and the failed live Chinchilla run (`2d9fe7c8-…`) before citing these results as end-to-end behavior.

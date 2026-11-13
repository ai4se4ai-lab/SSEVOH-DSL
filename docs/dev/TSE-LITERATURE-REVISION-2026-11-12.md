# TSE introduction and related-work revision — 12 November 2026

The revision uses `docs/leapspaces/leapspace.txt` as a discovery synthesis and the two supplied BibTeX files as candidate lists. Primary publications, rather than the synthesis's confidence labels, support the manuscript's new claims. The supplied files were preserved.

## Changes to the argument

The Introduction now moves from editable harness artifacts to a concrete release-engineering failure: a validated repair can have a stale approval or be withdrawn while dependent skills and experience entries remain unchanged. Harness-tampering audits and persistent-artifact attacks provide direct empirical motivation. The approach overview explains the proposal/service separation, context-bound approval, commit, byte-bound execution, source-aware reuse, and host adapter.

The gap is deliberately narrower than “governed self-evolution has not been studied.” Recent work already develops governed artifact lifecycles, recoverability checks, authorization succession, and provenance-aware runtime policies. The manuscript's contribution is positioned as a specific executable component contract, its typed representation and lifecycle rules, and its bounded assurance and integration evidence. It does not claim to subsume population authority conservation, arbitrary effect reversal, or generic policy-language expressiveness.

Related Work has four topical subsections instead of short disconnected summaries: harness evolution and persistent learning; governed evolution, authorization, and recovery; runtime policies and persistent-artifact security; and assurance and lifecycle evaluation.

## Verified additions

| Citation key | Primary source | Reason for inclusion and comparison boundary |
|---|---|---|
| `ace` | [Agentic Context Engineering, v3](https://arxiv.org/abs/2510.04618v3) | Persistent context is an evolving artifact, not just a transient prompt. |
| `harnessbank` | [HarnessBank, v2](https://arxiv.org/abs/2607.13683v2) | Actual activation and measured improvement are candidate-screening criteria, distinct from continuing version eligibility. |
| `tampering` | [Auditing Harness Tampering](https://arxiv.org/abs/2609.00069v1) | Integrity failures can persist in self-improvement lineages, motivating more than task-success checks. |
| `skillrelay` | [Cross-session artifact attacks](https://arxiv.org/abs/2610.13227v1) | Provenance restoration and advisory review directly address persistent reuse. The comparison acknowledges that review leaves the final choice to the task agent. |
| `governedevolution` | [Governed Evolution of Agent Runtimes](https://arxiv.org/abs/2605.27328v1) | A close architectural predecessor with governed mutation, promotion, evaluation, and rollback. Governance itself is not claimed as new. |
| `evoundo` | [EvoUndo, v2](https://arxiv.org/abs/2608.28363v2) | Witnessed recovery across counterfactual states is distinct from selecting an eligible historical record. SSEVOH does not undo arbitrary effects. |
| `succession` | [Authorization for Self-Modifying AI Agent Populations](https://arxiv.org/abs/2610.00347v1) | Explicit overlap in lineage cuts, rollback, and external authority is acknowledged. Population conservation and durable handoff are outside SSEVOH's evidence, while its component origins permit multiple parents. |
| `forge` | [Formal Policy Enforcement, v4](https://arxiv.org/abs/2602.16708v4) | FORGE already supports event-graph provenance and approval chains in Datalog. The paper therefore avoids a stateless-policy strawman. |
| `saga` | [SAGA, v2](https://arxiv.org/abs/2504.21034v2) | User-controlled registration and inter-agent policy enforcement are relevant governance foundations. The primary version includes Jacob Ginesin, omitted in the supplied export. |
| `entrust` | [Engineering Trustworthy Self-Adaptive Software](https://doi.org/10.1109/TSE.2017.2738640) | Direct TSE precedent connecting runtime adaptation and dynamic assurance evidence. Journal metadata was checked against the authors' institutional records. |
| `specmas` | [SpecMAS, NeurIPS 2025](https://proceedings.neurips.cc/paper_files/paper/2025/hash/61816fb8f7dd9677d23d00196ccbf126-Abstract-Conference.html) | A formal specification-to-model-checking pipeline. Its model generation and repair objective differs from enforcing artifact lifecycle transitions. |
| `seagym` | [SEAGym](https://arxiv.org/abs/2606.17546v1) | Snapshot transfer, retention, replay, and cost motivate separating lifecycle outcomes from selected-program correctness. The current experiments are not represented as a SEAGym evaluation. |

## Selection and metadata cautions

- The supplied synthesis attributes an ENTRUST discussion to reference 16, but its reference list identifies a 2022 mapping study. The manuscript cites the original ENTRUST journal article, verified separately, rather than copying that attribution.
- Some exported entries use anonymous or malformed author fields, `booktitle={unknown}`, HTML escapes, or synthetic-looking name hyphenation. Selected records were normalized against primary author lists and identified as preprints where appropriate.
- The 2027 “Executable Intent” chapter was not used to support a November 2026 literature claim. Broad application surveys and loosely related governance examples were deprioritized in favor of direct harness and artifact-lifecycle studies.
- Existing entries for Progent and the Darwin Gödel Machine were reused rather than duplicated under the supplied export keys.
- The abstract's blanket suggestion that existing systems test changes once and trust them indefinitely was replaced by the narrower failure condition that passing a test does not establish continuing authorization. This aligns it with the newly acknowledged governance literature.

## Page budget and checks

The compiled manuscript has **10 main-content pages and one reference page**, with 34 cited references. Normal IEEEtran fonts, margins, and line spacing were preserved. The Introduction and Related Work are approximately 487 and 510 whitespace-delimited words, respectively.

Space was recovered by removing repetition from running-example explanations and RQ summaries, shortening already-explained figure captions, and tightening cohort prose. All five table bodies, six algorithm bodies, the DSL listing, and the architecture's TikZ source were compared with the starting manuscript and are unchanged. No experimental data or implementation was modified. Caption definitions and essential experimental limitations remain in the relevant text.

Compilation resolves all citations and cross-references. The PDF was visually checked at the Introduction, Related Work, evaluation figures/tables, and bibliography. The DSL example was checked with the actual compiler. No model runs or formal-model sweeps were rerun for this prose and bibliography revision.

The pre-existing empirical limitations still apply: one evaluated host, bounded metadata assurance, a permissive non-inferiority margin, and incomplete public raw evidence for independently reconstructing corrected ToolRepair execution counts. The broader literature comparison does not resolve these evidence gaps.

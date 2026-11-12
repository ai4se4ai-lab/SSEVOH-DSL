# TSE manuscript critical review — 12 November 2026 (UTC)

The revision presents SSEVOH-DSL as a general lifecycle contract with an explicit host adapter boundary. Harness² is the evaluated case study. This separates architectural generality from empirical portability: a generic specification is support for a reusable design, while a second implemented host would be evidence of transfer. No new host integration or new model experiment was performed in this revision.

## Review against the requested criteria

| Criterion | Finding in the preceding draft | Revision | Material limitation that remains |
|---|---|---|---|
| Novelty | The contribution could read as a safety patch for Harness², and the blanket contrast with existing agent rule languages was too strong. | Abstract, introduction, generic architecture, adapter obligations, and algorithms now describe an artifact lifecycle independent of search strategy. Related work distinguishes lifecycle state and revocable origins from general authorization, rule expressiveness, and search quality. | Context-bound authorization and provenance are established ideas. The contribution is their specified combination at evolution/execution/reuse boundaries, not their individual invention. No comparative implementation against AgentSpec/Progent was evaluated. |
| Rigor | Pseudocode disagreed with the core on approval context, withdrawal scope, activation, pending receipts, and operation dispatch. Statistical claims exceeded the implemented analysis. | Corrected the pseudocode against `src/ssevoh/assurance.py`; stated explicit porting assumptions and failure conditions; retained finite verification bounds; narrowed bootstrap and zero-event interpretations. | There is no mechanized refinement proof. Twelve designed tool families and three ordered coding streams per model limit inference. The non-inferiority margin is permissive relative to baseline success. |
| Relevance | Early framework details obscured the general SE problem. | Reframed the problem as release engineering for generated artifacts: approval freshness, dependencies, revocation, recovery, and persistent reuse. Host-specific hooks and execution policies now appear in Evaluation. | Professional repository tasks and deployment studies are still missing. HumanEval+ shows no gain over frozen selection. |
| Verifiability and transparency | The manuscript claimed an immutable release without an identifier and implied every count could be reconstructed from the public checkout. Figure generation hardcodes corrected natural execution counts. | Added a commit-pinned evidence citation and distinguished public outcome reanalysis from raw execution-label reconstruction. Preserved negative results, correction timing, unresolved A1 labels, and supplementary A3 oracle resolution. | The three raw ToolRepair archive collections are local and ignored by Git. Publishing them and a complete correction manifest remains necessary for independent reconstruction of the corrected safety claim. The correction supplement was not a qualified sandbox replication. |
| Presentation | The approach mixed general rules with framework APIs, repeated results in a gap table, and had ambiguous cohort units. | Generic Figure 1 and guard algorithm; explicit adapter subsection; a single case-study description; removed the duplicate gap table; clarified HumanEval outcome counts; reduced redundant prose; kept Figure 1's caption to one sentence. | Author identity/affiliation is still the pre-existing `Anonymous Author(s)` placeholder and must be completed for the eventual submission workflow. |

## Technical corrections in the paper

- **Validation context:** the implementation hashes state, policy, validator registry, history, and origins. It does not hash pending approvals into that context. Otherwise issuing a second approval would invalidate the first before either committed. The paper now states that competing approvals may share a base.
- **Pending candidate:** receipts contain hashes and a token; the trusted pending table retains the candidate. The earlier `rho.S'` notation referred to a field that was not in the receipt definition.
- **Withdrawal:** the core primitive withdraws the current version, not an arbitrary historical identity. All operations use the same admission/evidence/commit path.
- **Recovery and update:** both activate the target, quarantine strict dependents, and must satisfy current capability ceilings, active-reference checks, and origin eligibility. Restoring a record does not clear the withdrawal set.
- **Notation:** metadata state is `S=(C,I,W,r)`; history and origins are maintained by the authority. Candidate origin maps are checked explicitly. Component snapshot matching compares component records, while the context hash also protects inactivity/withdrawal/revision/history state.
- **Artifact boundary:** the host, rather than the core metadata parser, must freeze bytes, maintain the artifact/version association, record observed source relationships, and mediate actual execution and reuse. The guard algorithm now states these obligations without requiring Harness² method names.
- **Portability:** one-target transitions, DAG metadata, conservative ancestry, trusted validators, complete mediation, and a protected authority are explicit conditions. Cyclic execution can be enclosed in a workflow component; it is not represented as a cyclic component dependency graph. A generic plugin API, arbitrary executable safety, distributed commits, and durable restart are not claimed.

## Statistical and empirical interpretation

1. `toolrepair_analyze.py` computes 10,000 ordinary paired family-bootstrap draws and counts draws below thresholds. Its fields named `p_one_sided...` / `holm_p` are bootstrap tail diagnostics, not a demonstrated calibrated null-testing procedure. The manuscript now reports the effect, percentile interval, margin, and frozen decision without promoting those fields to population-level significance claims. Historical code and outputs were not overwritten.
2. A nominal binomial upper bound for 0/160 injected events assumes independent comparable trials. Injection classes repeat within families/models, and some planned streams fail before producing proposals. The manuscript reports observed planned-stream counts and removes the 1.9% population-risk interpretation.
3. ToolRepair task-success intervals and arm differences are reproducible from committed stream records. Corrected execution counts instead rely on raw-response and executed-tree reconstruction under the documented D1 procedure. Worker-label safety results differ and remain disclosed.
4. Two corrected A3 cases required supplementary direct oracle-input execution; four A1 cases remain unknown. That supplement is documented, rather than described as a qualified sandbox replication or an originally frozen label.
5. HumanEval adaptation couples tasks through retained experience. Whole ordered streams are the replication units. The paper retains descriptive comparisons, unequal total-compute accounting, prior exposure/deviations, and the negative frozen-baseline comparison.
6. The increase from first-task to third-task ToolRepair success is exploratory. Fixed task order and no no-library ablation prevent a causal learning claim.
7. Zero observed unsafe executions under one policy is not a guarantee of semantic safety: the declared resource-abuse probe still passes in 16/20 A3 streams. OS containment is shared infrastructure, not an exclusive benefit credited to the contract arm.

## Verification performed for this revision

- Compiled the revised manuscript with IEEEtran using `letterpaper,journal`; `letterpaper` is the actual supported spelling corresponding to the supplied template's ignored `lettersize` option. No font, margin, or line-spacing compression was introduced.
- Final PDF: **10 main-text pages + 1 reference page**, within the requested 10 + up to 2 allowance. References start on page 11 after an explicit page break. The bibliography has 22 cited entries. The abstract is 150 whitespace-delimited words (LaTeX markup included).
- All citations and cross-references resolve. No duplicate labels or horizontal overfull boxes. One sub-point vertical box warning from bibliography balancing remains; rendered bibliography columns are readable and uncropped.
- Compiled the manuscript's ledger listing with the actual DSL parser: `ledger`, operation `update`, target `summarize`.
- Ran the unchanged core suite: **62 tests run, 61 passed, 1 skipped**. The skipped test checks that empirical submission remains locked; it intentionally skips because this checkout has an explicit empirical release. The manuscript's historical 62/32/70 test figures remain tied to the stored source-scoped reports, not represented as results of this new run.
- Recomputed ToolRepair analysis from all 540 committed streams into a temporary directory: JSON result identical to the committed summary. This also confirms that the stored default summary retains worker safety labels, not the corrected natural counts used in the manuscript.
- Recomputed HumanEval analysis using all 3,936 frozen samples and matching grades: outcome summaries, ordered streams, paired stream comparisons, and coverage fields identical to committed results. The freeze hash check passed.
- Inspected the three local raw ToolRepair collection archives: 324 + 108 + 108 nested stream archives, covering the 540 planned streams. Their availability on this workstation does not make them publicly released.
- Reviewed rendered pages for the generic diagram, algorithms, evaluation figures/tables, conclusion, and bibliography. Full TLC/model sweeps and model generations were not rerun: their implementation and frozen evidence were unchanged.

## Highest-value remaining work before submission

1. **Release correction evidence:** publish the 540 raw stream archives in an archival artifact, plus row-level corrected assessments, hashes, the two supplementary oracle resolutions, and an executable manifest that rebuilds the corrected totals without hand-entered figure constants. Preserve the four unresolved A1 labels. A commit-pinned repository alone does not close this gap.
2. **Implement a second host:** demonstrate the same lifecycle rules with a genuinely independent harness implementation, exercising acceptance, execution, withdrawal, eligible recovery, and persistent reuse. Additional adapters for Harness² are not independent host replications. If this is not done, retain the current limited empirical portability claim.
3. **Strengthen inference with a separately versioned analysis:** assess sensitivity to the 10-point margin and a justified small-cluster procedure. Do not silently replace the frozen bootstrap output. With the existing data, retain the current effect-size/interval interpretation.
4. **Broaden usefulness evidence:** professional repository-level tasks, stronger correctly configured models, an equal-total-compute reference, and a no-library ablation would address the present external-validity and mechanism-attribution gaps. These require new experiments; they cannot be repaired by wording.
5. **Complete submission metadata:** authors/affiliations, artifact accessibility, and the actual submission category's current requirements. The user's 10 + 2 budget was treated as the working constraint, not asserted as the journal's official policy.

## Primary sources checked

- [AgentSpec](https://arxiv.org/html/2503.18666v1): declarative runtime triggers, checks, and enforcement; its abstraction is broader than simple stateless request filtering.
- [Progent, version 3](https://arxiv.org/html/2504.11703v3): runtime privilege control and checked policy expansion/narrowing.
- [AutoSpec](https://arxiv.org/html/2606.24245): evolving expert rules using counterexamples and inductive logic programming.
- [ADAS](https://arxiv.org/html/2408.08435): archive-guided search over agent programs; the proposed adapter mapping is conceptual.
- [Darwin Gödel Machine](https://arxiv.org/html/2505.22954): modification of agent code with empirical evaluation; not an implemented SSEVOH port.
- [Voyager](https://arxiv.org/abs/2305.16291): an executable skill library that motivates a reusable-artifact boundary; not an implemented SSEVOH port.
- [Harness²](https://arxiv.org/abs/2610.14224): task-level Propose–Probe–Compose and harnessing-level experience reuse. Our integration is a case study, not a reproduction of its published professional-task gains.
- [IEEE Computer Society author resources](https://www.computer.org/publications/author-resources): journal-specific requirements must be checked for the chosen category; this revision does not invent a TSE-specific 10 + 2 rule.

This revision improves the manuscript's claim/evidence alignment. Acceptance remains a reviewer/editor judgment, and the empirical breadth and correction-release gaps above remain substantive.

## Readability follow-up

The abstract now gives a 150-word overview without experiment-by-experiment statistics. Tables I and II are compact summaries, with cohort construction and finite-domain details retained in the relevant evaluation text. Tables II through V have short one-sentence captions. Metric definitions and timing caveats appear next to their first discussion. Prose semicolons and sentence-breaking dashes were replaced with ordinary sentence structure. The follow-up was checked by compilation and visual inspection, with no change to experimental data or implementation. The page count remains 10 main-text pages plus one reference page.

# Harness-RSI reconnaissance and gap analysis

## Verified target and finding

The specified repository is [zgcagi/Harness-RSI](https://github.com/zgcagi/Harness-RSI/tree/d521b13978806e6132c56cf4adb280e3d969f41b), pinned to `d521b13978806e6132c56cf4adb280e3d969f41b` on 2026-11-09 after the core 0.2 assurance run passed. It is the companion repository for **Harness Self-Evolution: Theory, Algorithms, Evaluation, Applications, and Impact**, a survey. “Harness RSI” names the research area here, not an executable harness provided by this repository.

The complete tracked inventory contains 42 paths: manuscripts/bibliographies, illustrations, reading lists, evidence/taxonomy data, website assets, and three Python publishing scripts. All published refs returned one branch (`main`) and no tags. `README.md` describes companion survey materials; `CONTRIBUTING.md` describes paper/evidence/site maintenance. `scripts/build_evidence.py` generates literature-evidence summaries, `scripts/build_site_data.py` generates the website corpus, and `scripts/check_consistency.py` validates the publication artifacts. `site/app.js` drives the paper browser. None implements an agent execution loop, candidate-generation mechanism or trusted deployment boundary.

Evidence: [pin](../../../integrations/harness-rsi/upstream-pin.json), [all file hashes, AST definitions, published refs and checks](../../../integrations/harness-rsi/evidence/reconnaissance.json), and [machine-readable integration decision](../../../integrations/harness-rsi/evidence/integration-readiness.json). The clean checkout is reproduced by `python3 integrations/harness-rsi/scripts/checkout.py` and remains unchanged by inspection. No missing runtime has been treated as a security defect.

## Concern-by-concern comparison

| Concern | Original repository at the pin | Tested SSEVOH-DSL 0.2 capability | Integration opportunity |
|---|---|---|---|
| Evolution permissions | No executing evolution mechanism to assess | Authenticated principal/target/operation grants; current ceilings | Direct metadata enforcement once an actual target boundary exists |
| Preconditions | No runtime proposal or candidate state | Expected version and active/inactive conditions | Translate real proposals and snapshots; mapping currently unavailable |
| Dependency integrity | Literature taxonomy, not a runtime dependency graph | Acyclicity, active ancestors, reverse-closure quarantine | Requires actual component/dependency discovery and interface validators |
| Provenance | Source/PDF hashes and literature coding provenance are present | Version-origin lineage, journal and anchored replay | Publication provenance is already supported for its own purpose; operational lineage would require a runtime adapter |
| Evidence requirements | Source passages and coding rubric; consistency checks | Host-owned required predicates before approval | Behavioral test adapters must assess real artifacts independently |
| Withdrawal | Discussed in the survey; no executable withdrawal API | Monotone prohibited version identities and quarantine | Requires runtime disablement and deployment inventory |
| Rollback | Survey discusses other systems; no recovery implementation | Known historical component recovery with current ceiling/origin constraints | Filesystem/container recovery remains additional integration work |
| Revalidation | No pending runtime approvals | Complete context binding and stale approval rejection | Bind actual artifacts, policy, validators, deployment generation and evidence |
| Formal assurance | Survey proposes formal research directions | Independent operational conformance and bounded temporal model checks | No upstream transition system to refine or intercept at this revision |
| Privilege boundaries | No evolving agent or approval service | Protected metadata and policy/verifier kinds | Independent process/OS permissions must be established for a real target |
| Cross-component transactions | No runtime transaction mechanism | One-target metadata transformations only | Requires a core extension with new semantics and verification before use |
| Activation and effectiveness | Literature audit distinguishes available/reached/carried and causal claims | Core commits metadata; does not execute a retained agent skill | Actual later-run loading, execution and downstream-effect instrumentation are required |

The opportunities describe future mappings, not verified deficiencies of an original harness. Runtime concerns are **not assessable** for this survey companion.

## Classification of actual findings

| Verified finding | Classification required by the plan | Consequence |
|---|---|---|
| The supplied target has no executable evolution runtime, so C0 cannot run as specified | Outside the scope of SSEVOH-DSL | Obtain an executable target repository and revision; a DSL adapter cannot supply an absent original system |
| Publication evidence/site consistency is already checked | Already adequately addressed by the upstream project for its stated purpose | Preserve these mechanisms; all three available checks passed |
| SSEVOH metadata constraints could guard a real target's proposals | Directly addressable by SSEVOH-DSL at the metadata layer, conditional on a real boundary | Candidate integration opportunity only; no upstream defect or completed integration claimed |
| Artifact behavior, OS isolation, durable installation and several-component atomic deployment | Partially addressable through integration; general program correctness remains outside core scope | Implement adapters/isolation and extend the core where necessary, then repeat assurance |

No unauthorized-deployment, rollback or privilege defect is attributed to the survey repository. Its automated checks establish consistency of publication data, not empirical safety of the reviewed systems.

## Acceptance and blocked stages

Core readiness and upstream reconnaissance are complete for this pin. Gap analysis is complete. Proposal interception, executable adapter implementation, independent deployment, ten runtime scenarios, C0–C4, eight ablations, RQ6–RQ10 measurements and integration conclusions are blocked by the absent runtime. The report is therefore not an integration-completion claim.

The requested clarification is the intended executable repository and revision (or identification of one of the survey's linked implementations). The existing five model pins, Alliance scripts and preserved logs remain reusable infrastructure, but the changed core and eventual target require source-scoped validation. No experiment is launched by this reconnaissance.

# Development and evaluation prompt for the SSEVOH-DSL TSE study

Act as a research software engineer and a skeptical software engineering researcher. Develop and evaluate SSEVOH-DSL as an evolution-specific authorization and revocation layer around the real, pinned Google Research Harness² implementation. Produce a comprehensive IEEE Transactions on Software Engineering manuscript supported by inspectable artifacts. Preserve negative results and distinguish implemented behavior, bounded verification, experiments, and proposed work.

## Deliverables and boundaries

Only `docs/TSE/main.tex` and `docs/TSE/references.bib` may be created or modified inside `docs/TSE`. Keep all tables, diagrams, algorithms, and appendices in `main.tex`; build outside that directory. Put development documents in `docs/dev`, benchmark support in `experiments`, and cluster profiles/scripts in `hpc`. Use the installed IEEEtran class and the supplied journal template. Write as comprehensively as the evidence requires; do not import the IEEE Software word limit. Do not assert an unverified journal page-limit policy.

Read `docs/ssevoh-dsl-explained.md`, the implementation and claim-evidence reports, `docs/dev/google-harness2.md`, the core and integration assurance reports, and the raw study manifests before editing. Treat raw observations and pinned source as authoritative when prose disagrees. Preserve the existing studies as historical cohorts; never silently replace their generations, denominators, or failed workflows.

## Research questions

1. What evolution authorization, dependency, provenance, withdrawal, rollback, and execution invariants can the DSL express and enforce?
2. Within precisely stated finite bounds, do independent semantics, implementation exploration, and TLC agree, and do faulty variants violate the intended properties?
3. How effectively does enforcement reject operator-contract violations while retaining permitted updates, compared with original checks, ordinary testing, and static validation?
4. How does the contract behave at real Harness² admission, composition, execution, and library reuse boundaries?
5. Does the integrated system deliver useful programming solutions on HumanEval+, and what is its correctness, inference cost, latency, and failure rate relative to matched references?
6. What overhead, scaling limits, infrastructure variability, and reproducibility constraints arise?

The manuscript groups prompt RQ1--RQ2 as paper RQ1, prompt RQ3 as paper RQ2, prompt RQ4 as paper RQ3, prompt RQ5 as paper RQ4, and prompt RQ6 as paper RQ5. Map the existing ten fine-grained questions into these questions without losing any experiment. Distinguish contract safety from generated-program correctness and from task usefulness.

## Phase A: verification before empirical execution

Keep the verified core unchanged unless a concrete defect requires a change. State syntax and operational rules against actual implementation fields. Never call bounded exploration an unbounded proof, a finite executable catalog a general malware classifier, an origin relation a proof of semantic LLM influence, or a hash chain independent tamper evidence without an external anchor.

For any new execution domain, specify the trusted boundary and its validator contract. Do not bypass exact-adapter restrictions by monkey-patching types or broadening the ledger catalog. Add domain-specific validation, leakage tests, lifecycle tests, and readiness checks before authorizing that study. Preserve the historical source hashes and produce a fresh source-scoped report. Run appropriate existing tests and the relevant independent exploration/TLC configurations; document omissions explicitly.

## Phase B: real coding benchmark integration

Pin upstream Harness², EvalPlus, the full HumanEval+ dataset, evaluator dependencies, model manifests, inference settings, and first-party source. Archive SHA-256 identities and licenses. Do not confuse a model-to-EvalPlus script with an integration of Harness²'s Propose–Probe–Compose, selection, reflection, and library workflow.

Implement the upstream BenchmarkAdapter interface. Keep generated solution Python as task deliverables, separate from mutable harness files. Start with non-executable prompt, memory, and skill text as the evolution surface; trusted executable tools remain immutable. Collect actual accepted edits, consumed harness versions, library origins, and selected solution hashes.

Build a public prompt-only projection containing exactly task ID, prompt, and entry point. Never expose canonical solutions, additional test inputs, contracts containing private grading information, grader caches, or verdicts to proposer, executor, reflection, candidate selection, or the online library. Freeze every task selection and the entire online learning state before beginning hidden evaluation. Inspect original context construction and provide adversarial leakage tests.

Evaluate generated Python only inside a demonstrated operating-system sandbox on allocated compute nodes. The sandbox must restrict network, host filesystem and credential access, processes, resources, and descendant lifetime. EvalPlus reliability guards are additional checks, not isolation. Never execute generated solutions on login nodes or replace a failed isolation check with unsandboxed evaluation. Verify canonical positive controls and deliberately wrong negative controls through exactly the evaluator path used for candidates.

Calibrate formatting and parsing on a disjoint public development set, freeze the protocol, and record the calibration history before using held-out tasks. No hidden-test feedback may guide calibration or evolution. Require a useful nonzero coding reference before scaling an expensive recursive study; a failed reference is a diagnostic result to repair on development data, not an excuse to discard held-out failures.

## Phase C: prespecified benchmark conditions

Use all 164 tasks and the full additional tests when claiming a full HumanEval+ evaluation. Label any smaller run a pilot with its exact task selection. Prespecify task order, seeds, models, retry caps, output/token/context limits, failure handling, and online versus per-task reset behavior.

Include a one-shot frozen harness, a solver-call-matched frozen reference, original Harness² under the same editable surface, and Harness² plus the full lifecycle contract. Report total model calls and tokens separately: eight solver calls plus one selection are fewer than eight solver, six proposal, one selection and one reflection calls. Add a total-budget-matched reference before making equal-compute superiority claims; the present design makes no such claim. Use k>=2 if claiming nontrivial final candidate selection. Account for the original recursion: at depth/width setting k, the reviewed path makes 4k solver rollouts and 3k proposal sessions before retries, plus reflection and any selection. Verify this count against the pinned runtime for the chosen schedule.

Adaptive selected-final accuracy is not conventional one-shot pass@1. Report it under its actual budget. Publish intention-to-evaluate success over every planned task/seed, graded-only success with its denominator, missing deliverables, protocol failures, timeouts, infrastructure failures, and evaluator failures. Do not inherit the upstream judge's exclusion of missing scores without a separate all-attempts table.

For independent-reset episodes, use paired episode comparisons and justified uncertainty analysis. For online conditions, entire ordered model/seed streams are the replication unit: retained memory can carry old influence despite a visible-entry limit. With only three streams/model, report per-seed differences and descriptive mean/range/SD without task-bootstrap significance or population confidence claims. Counterbalance condition order. Report prior smoke/control exposure and prespecified sensitivity subsets. Seeds and sites are not independent new benchmark tasks. Report effect sizes, not just significance. Keep operator-contract injection experiments separate from natural model proposals and benchmark correctness.

## Phase D: fresh three-site HPC qualification and full runs

Apply the local `use-hpc` skill and reuse the existing source freeze, native Slurm DAG/arrays, model cache verification, per-response GPU checks, audit, transfer verification, and collection scripts. Do not introduce another scheduler. Use Fir, Narval, and Rorqual with existing private configuration. Keep credentials and MFA out of artifacts and model contexts.

Use a fresh study ID, manifest, and readiness record. Schedule setup, sandbox/control checks, generation, frozen selection export, hidden evaluation, analysis, and collection with explicit dependencies. Run a complete smoke graph on each site; obtain at least three independently submitted matched smoke trials where feasible, with a declared qualification deadline. Measure queue delay, startup, successful work, full-path completion, transfer cost, and failure/censoring reasons. Validate raw outputs and model/source identities before scoring a site.

Choose the fastest reliable eligible sites from fresh measurements; distribute uniquely owned model/seed streams across at least two qualified sites. For online adaptation, keep each entire deterministically ordered stream on one owner with its own library; task sharding must not alter sequential experience. Require a global dependency barrier freezing every stream selection and final library before hidden grading. Preserve slower and censored site evidence. If fewer than two qualify, report the blocker and retain the intended design rather than claiming distributed execution. Inspect remote job ledgers before retrying submissions with missing acknowledgments. Never blindly resubmit an existing run ID.

Maintain reusable SSH masters with the existing session script. Poll Slurm no faster than the established interval; provide fresh per-site audit tables with job IDs, stage, allocation, elapsed time, state, log paths, and transfer status. Fetch raw records and logs with hash verification. Keep local dashboard reads separate from remote polling. Never install packages, load models, or run experiments on login nodes.

## Phase E: manuscript and independent critical review

Lead with the concrete stale-approval/withdrawn-origin failure and the evolution-specific contribution. Compare with runtime enforcement, proof-carrying code, Cedar and verification-guided authorization, agent evolution, and Harness²'s existing safeguards. Credit existing path/schema validation, judge separation, retries, selection, and library mechanisms.

Present syntax, semantics, trust assumptions, enforcement algorithms, bounded obligations, integration seams, experimental protocol, results, negative findings, threats, and replication details. Include exact experiment-to-artifact mappings. Separate evidence scopes in every table. Retain the completed ledger pilot's 0/50 evolved and 0/50 frozen successes; do not imply existing studies ran HumanEval+.

Ask independent critical reviewers to assess novelty; rigor; software engineering relevance; verifiability/transparency; and presentation while writing. Give them the draft and evidence, request concrete blocking objections, and revise claims or implementation accordingly. Record unresolved limitations honestly. A strong paper earns its claims through evidence; it must not substitute a proposed benchmark for a completed evaluation.

## Acceptance criteria

The prompt, reproducible benchmark support, audited cluster records, and two-file manuscript must agree. Every empirical number must trace to raw records and a deterministic analysis. A full benchmark claim requires complete, independently checked results, effective isolation, useful controls, and frozen hidden-test separation. If external execution remains blocked, the manuscript must explicitly state the missing result and must not present that protocol as an accomplished contribution. Compile the paper with BibTeX, resolve citations/references, inspect layout, and incorporate the critical reviews before reporting completion.

## Pre-full protocol amendments from critical review

The initial two-task pilot established the evaluator/generation path but executed no distinct changed harness bytes. The disjoint v2edit-transport check then exposed a display-prefix mismatch: both models emitted `harness/LongTermMEMORY.md`. The v3frontend explicitly records and strips exactly that display prefix, rejects alias collisions and traversal, and leaves all canonical authorization checks in force. Preserve every earlier diagnostic record. Never silently normalize arbitrary model paths or tune task-solving instructions using hidden solutions.

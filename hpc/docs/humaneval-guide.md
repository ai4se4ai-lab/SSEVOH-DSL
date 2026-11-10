# HumanEval+ coding study: operations and evidence

This extends the existing native use-hpc Slurm graph. It does not replace the scheduler, SSH session manager, auditing, GPU checks, source freeze, or verified collector.

## Current boundary

The pinned full HumanEval+ v0.1.10 dataset has 164 tasks. Only task identifier, prompt, and entry point enter generation. The private compressed dataset lives in a mode-700 directory under each site's configured work directory, outside the deployed source tree. Its hash is checked before evaluation. Do not put it in method contexts, model prompts, or an online library.

The coding adapter implements the original Harness² interface. Python solutions are generated as text and checked statically for parse/entry-point information; they are not executed during recursive adaptation. Only supported Markdown prompt, memory and skill artifacts can evolve. Guardrails and tool guidance are immutable in all coding conditions. The lifecycle authority explicitly recognizes the exact coding adapter and attests its implementation/projection sources.

The source-scoped verifier runs 70 original tests, 32 integration tests, coding regressions, and the original publication-model checks. Coding regressions include two-candidate selection, reflection, two-task library insertion/reuse, withdrawal filtering, hidden canaries across every model channel, cache identity, and complete-population freeze checks. These are implementation checks, not empirical benchmark accuracy.

## Job graph

`setup (GPU) → llm (GPU)` verifies cached model identities and hosts allocation-local inference. Independent `isolation (CPU) → controls (CPU)` checks namespaces and the pinned EvalPlus positive/negative controls. `llm` requires both setup and controls. Then `freeze (CPU) → grade (CPU) → analysis (CPU) → collect (CPU)` validates all intended streams, grades frozen outputs, summarizes all attempts, and collects logs/results. Collection depends on all stages with after-any semantics, preserving failures.

The three-site preparation cohort separately ran trusted isolation and evaluator controls. A diagnostic job may finish successfully while reporting infeasible isolation; eligibility requires the actual report's `feasible=true`, not a green Slurm cell alone. Three canonical and three wrong-solution controls are required, with source/dependency/dataset identity. Fresh isolation is checked again in each evaluator allocation. The grading supervisor uses a separate OS namespace per solution and imports pinned, unmodified `evalplus.eval.untrusted_check`; it does not import heavyweight model-provider code or alter the test oracle.

The OS boundary protects the host. It is not a proof against a deliberately malicious candidate attacking evaluator internals inside its own namespace. No arbitrary generated harness code is authorized. Slurm cgroups plus process/time/address-space/file limits bound resource use. Evaluator failures remain explicit all-attempts outcomes.

## Smoke and full scope

`experiments/humaneval/protocol.json` records the local frozen design. The first complete smoke trial uses two tasks, two models, seed1701, k=2, and all conditions. It exercises the entire path including external grading. Repeat independently on Fir, Narval and Rorqual; measure successful complete paths, queue/startup/execution/transfer cost, source/model identity and GPU residency before ranking sites. Preserve negative and censored observations. Do not select a site for completing failed protocol work quickly.

The intended full design uses all164 tasks, two models and three seeds. The frozen condition makes eight solver calls, with its first solution reported separately as the one-shot endpoint and a public-only selection over eight as the matched solver reference. Each recursive condition uses original Harness² k=2 aggregation, six proposer calls and eight solver rollouts per task before retries, plus selection/reflection. Both recursive conditions retain at most the preceding five task entries through original library APIs. This bounded library policy is an explicit experimental choice, not the default unbounded history.

For online runs, a model/seed/condition stream remains on one owner. Independent libraries and deterministic task order prevent cross-condition leakage. All full-study streams across sites must freeze before hidden grading. A local stream completion receipt deliberately has `all_streams_frozen=false`; `humaneval_freeze.py` sets it true only after receiving exactly the declared global population. Do not grade a subset while other online streams are evolving. Full execution requires a distinct readiness release and complete qualified smoke evidence; the current smoke profile cannot silently run a full cohort.

## Commands

Use `bash hpc/scripts/ssh-session.sh connect all` for interactive MFA if the existing masters have expired. Never store or send credentials/MFA in logs or chat.

Trusted diagnostics: `python3 hpc/scripts/submit_humaneval_preflight.py --site fir --trial 1`.

Evaluator controls: `python3 hpc/scripts/submit_humaneval_preflight.py --site fir --controls --trial 2`.

Complete coding smoke: `python3 hpc/scripts/submit_humaneval_preflight.py --site fir --coding-smoke --cohort v5 --trial 1`.

Replace `fir` with `narval` or `rorqual`. Submission intent is persisted under `hpc/fetched/humaneval-*.json`. An existing intent requires ledger inspection; the script refuses blind resubmission. A timeout means the result is uncertain. Inspect the remote `hpc/logs/<run>/jobs.tsv` and still-running submit process before any action. A missing acknowledgment alone is not a failed Slurm job.

Use existing `fleet.status`, `fleet.fetch_sites`, and `verify_transfer.verify`; query Slurm no faster than the established120-second interval. `python3 hpc/scripts/live.py --output hpc/fetched/live.md` refreshes only the local view, without SSH or Slurm calls. Open each run's audit for job IDs, allocation, queue reason, stage, raw logs and progress. Fetch freshness and scheduler-audit freshness are separate.

## Result map

| Question | Stage / evidence | Interpretation |
|---|---|---|
| Host isolation feasible? | isolation/report.json | Trusted feasibility controls, not universal sandbox proof |
| Correct evaluator behavior? | controls/records.jsonl | Three positives and three negatives with exact identities |
| Real recursive execution? | llm/selected-*.jsonl and sibling raw/authority/proposer files | Actual consumed harnesses, proposals, rollouts, selections and failures |
| All intended outputs frozen? | frozen/global.json | Exact model/seed/task/condition coverage and hashes |
| Useful coding behavior? | grade/records.jsonl | Full base+plus results after freeze; errors retained |
| Comparative performance? | analysis/summary.json | Intention-to-evaluate and graded-only counts; ordered-stream descriptive differences; no task-independent inference |
| Site reliability and cost? | native audit, job accounting, transfer receipts | Complete matched trials, including censoring and failures |

Prepared code or dataset files are not completed empirical results. The paper must use the collected records and explicitly distinguish smoke, full, controlled lifecycle, and historical ledger cohorts.

## Auditable infrastructure correction

The current qualification cohort is v5. Previous diagnostic cohorts retain their raw failures and results. Provenance hashing now reads the frozen source snapshot instead of recursively including previous hpc logs/results. Before the server starts, pinned node-local llama-server CUDA backends are enumerated offline with a bounded180-second timeout each. No model is loaded and no task prompt is evaluated by this preparation. A missing CUDA device blocks inference; it never enables CPU fallback. Readiness includes fourteen infrastructure regressions.

The finite coordinator uses `python3 hpc/scripts/humaneval_campaign.py --auto-full --cycles 1440 --interval 120`. An exclusive lock prevents concurrent coordinators. Every three-trial site ranking is bound to the same verified source/model/protocol identities. Full generation uses uniquely owned entire streams on the fastest two qualified sites; external CPU grading begins only after exact global coverage is frozen. Native Slurm still schedules every job. The coordinator reuses SSH masters during audits; authentication expiry is reported, never bypassed or stored. Its state and detailed output are under hpc/fetched.

The v5 disjoint edit calibration uses the same pure task-free coding baseline as the adapter, rather than a ledger demo fixture. Its one-key edit request avoids unrelated copying, while the gate still rejects every extra file modification, including a lost newline. Earlier v4 failures are retained as development diagnostics. The frozen protocol explicitly discloses prior diagnostic exposure.

For the current all-site view use `python3 hpc/scripts/humaneval_status.py`; without `--refresh` this reads local fetched audits only. The active coordinator owns remote polling; do not launch a competing refresher while its lock is held. The finite manuscript watcher and its evidence/compilation/concurrent-edit safeguards are described in [the general guide](hpc-guide.md#humaneval-campaign-monitoring). Actual full results remain pending until all intended outcomes are collected and verified.

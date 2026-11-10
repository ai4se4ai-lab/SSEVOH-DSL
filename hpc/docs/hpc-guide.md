# Active Harness² multi-cluster protocol

The active graph is `hpc/config/profiles/harness2.json`, also installed as `hpc/config/experiments.json`. The primary DSL graph is `hpc/config/profiles/ssevoh-original.json`, updated with a source-scoped worker preflight and the `ssevoh-core-v2` study identity. Earlier results are legacy exploratory evidence and are never mixed into these current studies.

Core 0.2 assurance precedes this protocol. The actual unmodified Google Research Harness² integration then passes upstream, security/fault/worker and publication-model checks. The execution scope is an explicit finite Python catalog plus a bounded data-only Ollama agent, not arbitrary OpenCode/Codex execution or replication of Google's professional benchmark scores. Every job rechecks current source/readiness hashes and an actual admitted execution before task inference.

## Active graph and cost bounds

```text
setup: source/archive preflight + GPU model pins
  ├── deterministic: C0–C3, 12 shared cases, 4 lifecycle cases, 8 ablations
  └── llm array: one owner per model, 5 seeds, 2 tasks, k=1
         └── analysis + append/skip check
                └── collect
```

Smoke retains all five stages: six cells (one GPU setup, two GPU model cells, three scheduled CPU cells), one seed, two ledger tasks per model stream. Three independent graphs per site mean at most 54 Slurm cells/27 GPU cells across Fir, Narval and Rorqual. Each GPU cell is capped at 45 minutes in smoke; this is a hard allocation bound, not a predicted use. Full work has five unique model cells, five seeds, 25 stream records/50 task outcomes and 900 deterministic primary-site records. Model jobs are capped at two hours each; realized time is measured. Pure metadata/analysis stages request scheduled CPU allocations rather than idle GPUs. No experimental computation runs on login nodes.

Python 3.12.4 is available on Fir/Rorqual and selected for the pinned upstream. No external Python dependency is needed. A deterministic 286,895-byte source archive supplies the exact upstream on offline compute nodes. Setup and model jobs use the existing node-local Ollama runtime protocol, pinned identities and full GPU-residency gates. Models are preloaded at the actual 16,384-token context before any task prompt. The JSON request format follows [Ollama's official API](https://docs.ollama.com/api/generate); all raw requests, responses, thinking output, options and timing fields are retained.

## Coverage matrix

| Question/component | Job/step | Raw evidence | Collected outputs and decision rule |
|---|---|---|---|
| Formal core prerequisites | Local source-scoped assurance; setup/preflight validates exact hashes | `formal/assurance/results/*` | Finite-domain agreement and source-stable release required |
| RQ6: faithful actual integration | Original 70 tests + integration/worker tests; setup real execution | Integration readiness and original/source pin inventory | Both modes, k=2 budgets, actual subprocess outcomes and later-task library reuse must pass |
| RQ7: explicit operator-contract safety | deterministic/conditions | `deterministic/records.jsonl` with actual trees, events and core journals | Unsafe trusted deployments/unsafe attempted transformations; zero denominator undefined |
| RQ8: useful evolution | Three legitimate shared case families; llm/generate | Outcomes, raw JSON/no-op/invalid responses, frozen controls | Legitimate false rejection and task success reported separately; refusal is not safety proof |
| RQ9: resources | Both workers + GPU CSV + accounting | Per-action/stream seconds, API tokens/durations, runtime/Slurm telemetry | Describe measured costs, not unmeasured manageability or significance |
| RQ10: lifecycle resilience | Four deterministic authority sequences and security/fault tests | Withdrawal, origin, recovery, stale-approval and interruption events | Actual denied execution/unchanged published state checked; absent original APIs are not assigned invented failures |
| Eight mechanism removals | deterministic/conditions | Explicit isolated research mode and exact retained guards | Full control versus one named removal; overlap and zero effects preserved |
| Actual model activation | llm/generate | Per-run `activation.json`, authority EXECUTED events | Available/reached/carried denominators and counts; task benefit remains a separate outcome |
| Resume | analysis/resume-check | Before/after raw JSONL SHA-256 | Completed deterministic records unchanged; not durable authority restart or Slurm-preemption proof |
| Three-site qualification | setup → all stages → collect | Complete audit, shared accounting snapshot, model digests, transfer hashes | Three independent successful graphs per site and both smoke models; failed/inaccessible sites remain explicit |
| Unique full ownership | Thin coordinator using existing fleet/submitter | `harness2-plan.json`, run intent/submission records | Measured reliability/completion score and verified cache eligibility; each full model exactly once |
| Pooled results | Scheduled aggregate analysis + collect | Joined primary deterministic and unique model-stream records | 25 distinct (model,seed) streams required; CSV/MD/TeX/SVG generated from actual records |

## Operating commands

```bash
bash hpc/scripts/ssh-session.sh connect all  # complete MFA in your own terminal
bash hpc/scripts/ssh-session.sh status all
bash hpc/scripts/selftest.sh
python3 hpc/slurm/submit.py --dry-run --smoke
python3 hpc/scripts/campaignctl.py start --profile harness2 --auto-full --cycles 180 --interval 120 --qualification-minutes 45
python3 hpc/scripts/campaignctl.py status --profile harness2
python3 hpc/scripts/fleet.py status
python3 hpc/scripts/fleet.py fetch
```

The start command is denied until the explicit controlled-study readiness release is active. `--auto-full` implements the user's already-requested full study only after measured qualification; at least two qualified sites are mandatory. After 45 minutes, still-unqualified sites are explicitly excluded rather than given estimated performance. Cached model identities constrain ownership to avoid unnecessary large weight transfers. The ranking measures two smoke models; it is not a universal hardware-speed claim. An authentication failure is not evidence of inferior GPU performance.

The finite coordinator runs locally, only copies/audits files and invokes the upstream submitter. Polling is no faster than 120 seconds. It records submission intent before mutation, stops on uncertain/failed outcomes, and never substitutes a model. The legacy campaign stays stopped. Only scheduled jobs perform inference, tests with data and statistics. Stopping the coordinator does not cancel Slurm jobs; `halt_experiments.py` cancels only repository-recorded jobs when explicitly needed.

Each site's `hpc/fetched/<site>/fetch-status.json` records freshness, last successful refresh and failures. Transfers have 45-second inactivity and 120-second total limits, run independently across sites and preserve earlier files. A stale snapshot is not presented as fresh. Expired SSH/MFA requires interactive reconnection; no script stores credentials or bypasses MFA. Input MFA codes only in the terminal, never chat.

Use `python3 hpc/scripts/live.py --watch 5` to read local snapshots without extra scheduler polling, or open `hpc/fetched/fleet-live.md`, refreshed with the research guide. The display marks stale fetches and stale scheduler audits separately and links each detailed run audit. `fleet.py watch` refuses a second polling loop while a campaign owns the fleet.

Source/config snapshots, per-model/seed directories, manifests, raw responses, decision chains, actual task outputs, GPU CSVs, accounting and verified fetch hashes make the process inspectable. New study results are under `artifacts/benchmark-results/harness2-full`; current status is `hpc/fetched/harness2-campaign.json`. No full result is claimed until its completeness manifest and scheduled aggregate have completed.

---

# Primary DSL continuation and preserved original operations

After the controlled Harness² aggregate is complete and its content hashes are verified, the finite controller can launch the released `core` profile. It uses the same coordinator, Slurm runner, measurements, cache-constrained ownership and collectors. Its state, PID/log, qualification and plan are separate (`core-campaign.json`, `core-campaign-driver.log`, `core-qualification.json`, `core-plan.json`). Inspect it with `python3 hpc/scripts/campaignctl.py --profile core status`. A direct start is rejected until the Harness² campaign is complete. The stopped legacy `ssevoh` controller stays disabled.

The primary study schedules a fresh three-run smoke cohort on each site covering every stage, including formal, scaling and five synthetic ablation families. Scaling has 180 full records: 10/100/500 components × chain/star/random graphs × 1/2/4/8 conflicting approvals × five repeats. Commits synchronize at a barrier in one shared-memory process, with exactly one winner; this is not distributed throughput. Only after qualification does it assign five models × 20 eligible requests × five seeds = 500 full generation records. Deterministic/scaling/ablation data are taken from one measured primary owner in pooled analysis; replicated per-site side-study outputs remain available separately. Setup verifies `experiments/evidence/core-study-readiness.json`, including the independent operational-reference oracle regressions, before inference. Full streams preserve requests before transport, raw responses, errors and start/end progress messages. An independently unsafe deployment aborts the cell after preserving its evidence.

These generations concern metadata DSL proposals. They do not enlarge the two-task Harness² sample or replicate the professional benchmarks. The primary full matrix has five inference cells capped at one hour each, plus one GPU setup cell per assigned site capped at one hour; actual GPU time is recorded rather than inferred from requested limits. The independent core smoke cohort has 27 GPU cells capped at 45 minutes each. No new model downloads or extra unowned generation cells are scheduled.

# SSEVOH multi-cluster operating guide

## Reused infrastructure

`hpc/UPSTREAM_COMMIT` pins https://github.com/ai4se4ai-lab/use-hpc. `submit.py`, contracts, stage runner, ledger, requeue, audit and collector derive from that repository. See `hpc/PATCHES.md` for the source-snapshot extension. The fleet controller only selects sites, copies source/config, calls the upstream submitter, fetches artifacts and records cross-site measurements.

## Connection and configuration

```bash
bash hpc/scripts/ssh-session.sh connect all
bash hpc/scripts/ssh-session.sh status all
python3 hpc/scripts/fleet.py probe
```

Interactive MFA establishes a ControlMaster. ServerAliveInterval=60, ServerAliveCountMax=3 and ControlPersist=12h keep it reusable while active. Nothing stores passwords/MFA codes or bypasses MFA. On disconnect rerun connect. `fleet.local.json` contains account/path details and is ignored by Git. Automation nodes require separate Alliance support authorization and constrained keys; these scripts use regular authenticated login connections.

Discovered account: `def-mbabaei_gpu` for GPU jobs and `def-mbabaei_cpu` for pure CPU jobs. Fir/Rorqual request `h100:1`, Narval `a100:1`, based on `sinfo` and on-cluster docs. Fir has no `/project/def-mbabaei` allocation visible, so its small source/log tree is in `/home/mbabaei/ssevoh-dsl`; Narval/Rorqual use `/project/def-mbabaei/mbabaei/SSEVOH-DSL`. Active work is `/scratch/mbabaei/ssevoh` everywhere. Final logs/results are copied to persistent source directories and fetched locally. No scratch persistence guarantee is made.

## Graph and source map

```text
                         ┌ deterministic (B0–B3)
setup (GPU/runtime/pins) ─┼ formal (bounded exploration)
                         ├ scaling (chain/star/random)
                         ├ ablations (five mechanism removals plus full control)
                         └ llm (model array, GPU inference)
all five branches ─afterany→ analysis + resume-check ─afterany→ collect
```

Setup gates every branch with afterok. Array tasks each own one model output file and reuse the loaded model for independent task/seed calls. Analysis accepts partial results; collection preserves failures and empty results visibly. Model setup and inference use GPU allocations. The configured project explicitly permits scheduled CPU-only deterministic, finite-state, scaling, statistics and collection work; this adapts the template's GPU-only default to avoid reserving unused GPUs for metadata analysis. No inference, model load, installation or experimental analysis runs on login nodes. All wheelhouse virtualenv creation happens in jobs.

| Component / RQ | Stage → entry point | Raw output | Collected artifact | Decision rule |
|---|---|---|---|---|
| Parser/types/policy; RQ1/RQ2 | deterministic → ssevoh.benchmark | deterministic/records.jsonl | csv/deterministic.csv; archive | labeled accept/reject and diagnostic correctness |
| Lifecycle/evidence/recovery; RQ2 | formal → ssevoh.cli verify | formal.json | raw/formal.json | four corrected contexts pass; all five mutants yield traces |
| Graph closure / RQ5 | scaling → scale.py | scaling/records.jsonl | csv/scaling.csv; archive | latency, peak traced bytes and completion across size/shape |
| Model proposal assurance / RQ3 | llm → llm.py | llm/<cell>.jsonl | csv/llm.csv; raw archive | separate syntax, semantics, independent oracle, unsafe deployment and task compliance |
| Latency / RQ4 | analysis → analyze.py | analysis/summary.* | raw/analysis; tables | distributions and task-cluster bootstrap; no smoke significance claims |
| Resume contract | analysis → resume_check.py | analysis/resume-check.json | raw/analysis | deterministic rerun must preserve byte hash and record count |
| Site selection | fleet + measure.py | accounting.tsv, transfer.json, qualification.json | fetched fleet files | independent completed trials, GPU residency, transfer hashes, observed completion costs |
| Evidence provenance | runtime.py freeze; manifest.py | setup/models.lock.json; run_manifest.json | raw/setup + pipeline manifest | tag/digest/license/runtime/GPU/source identity present |
| Figures/tables/report | analyze.py; update_report.py | summary.csv/json/tex/svg | artifacts and paper/generated | every displayed number linked to an existing raw record |

## Qualification and size

```bash
bash hpc/scripts/selftest.sh
python3 hpc/slurm/submit.py --dry-run --smoke
python3 hpc/scripts/fleet.py deploy
python3 hpc/scripts/fleet.py smoke
python3 hpc/scripts/fleet.py status
python3 hpc/scripts/fleet.py fetch
```

The current complete smoke graph has eight stages/nine cells: one setup, two model tasks, and six CPU-only cells. Each model generates one task with three seeds; all deterministic scenario families remain present. Its allocated time limit is 45 minutes per job, so the graph's GPU budget upper bound is 3×0.75=2.25 GPU-hours/site/run, not a measured duration. Three qualification repetitions across three sites have a 20.25 GPU-hour upper bound; actual consumption is determined by Slurm accounting. Queue wait is unbounded. The selected full model matrix has five cells ×20 eligible normal-action tasks ×5 seeds =500 generations, plus deterministic and scaling work. Runtime/GPU-hour estimates must be calibrated from actual smoke output, never invented.

A first exploratory smoke graph was submitted on all sites before source snapshot freezing and resume-check additions. Its results remain distinguishable. Subsequent qualification must use current frozen code and three independent allocations per model/site rather than treating three generations in one allocation as three reliability trials.

## Audit and monitoring

```bash
python3 hpc/scripts/fleet.py status
python3 hpc/scripts/fleet.py watch --interval 120 --cycles 30
python3 hpc/scripts/fleet.py fetch
# On a site, with its run id:
bash hpc/status.sh RUN_ID --steps
python3 hpc/slurm/submit.py --run-id RUN_ID --only llm,analysis,collect
```

The status table shows site, stage/cell, scheduler state, node, queue reason, run/limit time, steps, record progress and failure log. `steps.tsv` records every attempted step; jobs.tsv and jobs_finished.tsv track jobs and restarts; env/ contains module/virtualenv/service records; gpu/ contains 60-second samples; frozen config/source and manifests identify the run. Fleet operations are appended to operations.jsonl. One watch process owns an advisory lock; polling is never faster than 60 seconds. Watch is finite and explicitly invoked. It does not silently daemonize or acquire a new MFA session.

## Collection, ranking and full runs

`verify_transfer.py` compares fetched collected files to remote hashes. `measure.py --accounting` fetches Slurm submit/start/end times and combines actual generation records, completed audits, resume checks and transfer results. `fleet.py plan --measurements hpc/fetched/qualification.json` refuses to rank sites without three independent completed smoke runs for both required models. The transparent score is a Beta-smoothed completion reliability divided by mean queue+startup+generation+transfer cost. Repeated generations share job costs and must not be treated as independent queue samples in interpretation.

`fleet.py full --plan hpc/fetched/plan.json --measurements hpc/fetched/qualification.json` recomputes the plan, verifies disjoint ownership of the five models, and renders per-site model arrays. Frozen model digests must be staged first. Fir compute nodes permit downloads; Narval/Rorqual compute nodes do not. Missing models must be downloaded in a Fir GPU setup job and transferred with `transfer_models.py` (uncompressed tar over two SSH connections; no model computation on login nodes). Do not use login-node Ollama servers.

Collected files live in hpc/logs/RUN_ID/results/{csv,tables,figures,raw,archives,pipeline}, with summary.md. The fleet mirrors them in ignored hpc/fetched/SITE/RUN_ID. Final selected tables and manifests should be retained under artifacts/ for publication. Source/model/prompt/output hashes link manuscript observations to raw records.

## Honest limits

The initial benchmark is synthetic and not independently reviewed. Production deployment, persistent crash recovery, human usability, semantic code safety and broad real-artifact mechanism ablations are not covered; initial synthetic mechanism removals are implemented. The finite checker has one proposal/three epochs; no liveness or refinement theorem is established. Local tests are not HPC performance results. A smoke completion does not replace the full five-model experiment. CPU-only stage policy is a documented adaptation. SSH may require renewed MFA, scratch is purged, and missing tags/runtime incompatibility must fail without silent model replacement.

## Finite campaign controller

The controller was explicitly started for this requested experiment campaign. Inspect it without querying Slurm:

```bash
python3 hpc/scripts/campaignctl.py status
# Stream its recorded audit/submission/error output locally:
tail -f hpc/fetched/campaign-driver.log
```

`campaign.py --auto-full --cycles 180 --interval 120 --qualification-minutes 90` schedules remaining independent qualification trials, retains all attempted trials, requires matching worker/model identities, verifies completed outputs, computes a plan from real measurements and stages missing models from Fir. It can then call the upstream full submitter for the disjoint 500-generation design. It records `needs_attention` for failed gates and never fabricates completion. `campaignctl.py stop` stops only the local monitor; submitted Slurm jobs continue. Use `campaignctl.py start --auto-full` to start an inactive nonterminal campaign explicitly. Expired authentication still needs manual MFA.

A qualification deadline does not imply that a queued site failed scientifically. It means that site remains unqualified for the present assignment; its queue state and trials stay in the audit. Full evaluation remains separate from qualification and will only be reported complete when all 500 distinct generation keys and complete job audits are collected.

## Revised runtime protocol and pooled statistics

The original Rorqual setup encountered the runtime's fixed GPU discovery watchdog and was rejected after CPU fallback. Versioned failure logs and the retired campaign are retained in artifacts/manifests/runtime-v1-failure. The revised protocol stages the identical runtime binary/libraries in SLURM_TMPDIR, disables unused Vulkan probing, loads each model without a task prompt, and requires full GPU residency before generation. All sites use the same revised protocol and new qualification trials; old and new measurements are not pooled.

Final cross-site statistics also run through use-hpc: the controller joins raw outputs, uploads them as immutable source inputs and submits hpc/config/aggregate.json as a CPU job. It computes matched task/seed differences, task-cluster bootstrap intervals and, with at least ten task clusters, fixed-seed task-level sign-flip p-values with Holm adjustment within each metric family. These rely on task exchangeability and do not automatically imply significance or generalization from the synthetic convenience sample. No controller-side bootstrap replaces the scheduled analysis.

## Recorded full-study array concurrency change

The first Harness² full graphs were frozen with an array limit of one. The owned Fir array `3206859` was subsequently raised to three concurrent cells, allowing the three already assigned models to overlap when Slurm permits. Rorqual’s requested limit of two returned “Job has already finished” for its first cell; that rejection is retained, and only one remaining model cell needs to run there. No cell was added and per-cell resources were unchanged. Exact requests/results are in `artifacts/manifests/harness2-scheduler-adjustments.json` and alongside each remote run log. See the official [Slurm ArrayTaskThrottle specification](https://slurm.schedmd.com/scontrol.html). Later full submissions derive a limit of up to three from their unique model owners before freezing configuration. Scheduler availability and fairness still govern actual overlap.

## Diagnostic reanalysis and submission acknowledgement

The completed raw samples were reanalysed in the CPU-only `results-audit` profile. It adds raw-output protocol diagnostics and latency on legitimate shared fixtures; it generates no new model outputs. Remote input hashes were checked against the collected datasets, every pre-existing summary metric matched exactly, and `analysis-initial` retains the earlier tables. The first SSH submission acknowledgement timed out while the source snapshot was being prepared. The remote `jobs.tsv` contained all three expected jobs; this was reconciled without resubmission. Submission RPCs now permit 300 seconds for source freezing on a busy filesystem; audit and transfer operations retain their shorter bounds.

A closeout request for unused Narval trials was refused by its live queue check because those jobs had started. Nothing was cancelled. The metadata record is `artifacts/manifests/narval-qualification-closeout.json`. Late trials remain monitored separately and cannot change the frozen 45-minute site-selection decision.

## Final qualification closeout and matched outputs

After preserving completed cells, only the remaining PENDING Narval GPU array elements were closed. Running cells and downstream CPU analysis/collection were preserved; all current-study cells are now terminal. The result is explicitly censored, not a GPU failure. See `artifacts/manifests/narval-qualification-gpu-closeout.json` and `hpc-final-audit.json`. The earlier broad closeout guard refused to act when its live check saw running jobs; that refusal remains recorded.

The scheduled qualification report checks source, model, prompt, decoding and runtime identities before matching raw DSL outputs. Its 24 comparable pairs matched exactly but had invalid syntax on both sides. Completed partial Narval cells are marked, and only one first context was compared. Three generations within one allocation count as one infrastructure trial. The old `startup_seconds` field is residual per-record overhead, not a pure model-loading estimate; the frozen scheduler ranking uses queue plus the full allocation duration and transfer once per model/job.

A second CPU-only analysis revision adds strict request fidelity, including snapshot/evidence/condition checks omitted by the legacy partial field-match metric. It preserves all model samples, original metrics and initial analyses. Source-scoped worker regressions passed before computation. This is a labelled post hoc diagnostic, not a new model-generation cohort.


## HumanEval+ campaign monitoring

Run `python3 hpc/scripts/humaneval_status.py` for a local view of all three sites. The explicitly started finite coordinator in `hpc/scripts/humaneval_campaign.py` owns remote polling and fetches every 120 seconds; its state is `hpc/fetched/humaneval-campaign.json`, and its log is `hpc/fetched/humaneval-driver.log`. Do not start another coordinator while its advisory lock is held. The SSH helper uses existing authenticated master sessions; expired MFA must be completed locally using `bash hpc/scripts/ssh-session.sh connect all`. No credential or MFA token belongs in logs.

The current qualification cohort is v5, frozen before fresh three-site trials and full generation. It retains separate earlier diagnostics for path-prefix transport, cold CUDA discovery, source hashing of live output directories, and the stale ledger development fixture. The v5 calibration uses the shared coding baseline without loading benchmark tasks and retains exact rejection of extra edits. All historical failed/censored trials remain visible. Three valid matched trials per selected site, at least two qualified sites, model/source/GPU identities, evaluator controls, complete collection and transfer verification gate the full run. The two fastest qualified sites own disjoint complete model/seed streams; online tasks are not arbitrarily sharded. Hidden grading starts only after all six streams freeze.

A status of qualification is not a full benchmark result. Inspect failure details in each run's `audit.txt`, `audit.json`, `steps/`, and raw diagnostic records. The manuscript must retain pending full results until all 3,936 planned endpoint outcomes and their immutable source/selection/grading evidence are collected.

The finite local paper updater (`experiments/scripts/tse_publication.py --watch`) waits for the coordinator's complete phase. Its single-instance lock and progress log are `hpc/fetched/tse-publication.lock` and `hpc/fetched/tse-publication-driver.log`. Before replacing the TSE draft it independently checks the exact 3,936-outcome population, solution bytes, manifest coverage, summary uniqueness, per-stream correctness and costs, and all six guarded traces; it then compiles a candidate with resolved references and no overflowing content. Concurrent manuscript/bibliography edits stop replacement and preserve the candidate for a manual merge. It does not turn incomplete runs into results. Its output receipt is `artifacts/manifests/tse-publication.json`. Four synthetic validation tests cover rejection, successful isolated compilation, incomplete evidence and concurrent edits; those fixtures are never empirical results. The evidence-derived draft still needs final narrative review after actual results arrive.

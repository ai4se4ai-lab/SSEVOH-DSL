# Safe self-evolution of AI agent harnesses: a plain-language research guide

Updated from recorded artifacts: 2026-11-11T10:58:51.671148+00:00.

**Execution order:** the core and integration were verified before empirical work. Both full studies and their pooled analyses are complete. Late Narval qualification observations are retained separately from the frozen site-selection decision. Earlier exploratory artifacts remain legacy evidence.

## The problem

An AI agent can improve a skill, memory, tool or workflow while accidentally breaking something that depends on it. It may also ask for permissions it does not have. Restoring an old backup can bring back something already withdrawn. A log tells us what happened; it does not decide whether the change was permitted.

## The approach

The agent submits a small text specification. An independent service reads it, checks operator permissions and the affected dependency graph, runs required validators and a bounded safety model, and issues a one-use approval. The sandbox commits the checked candidate only if the trusted state is still the same. Withdrawal keeps affected descendants in quarantine so their history and independent contributions are retained. Recovery never removes the withdrawal history.

The core manages metadata in memory. The real Harness² adapter also publishes complete checked file bundles and controls ledger-task execution, using a finite Python catalog. This does not prove arbitrary generated programs safe or provide durable automatic restart. The simple structure validator demonstrates the trusted validation interface.

## Research questions and experiments

| Question | Experiment and objective | Present evidence |
|---|---|---|
| RQ1: Can engineers describe the important changes? | Compile examples and represent all 15 required scenario families. | 20 synthetic scenarios; six working examples; independent benchmark review pending. |
| RQ2: Do checks catch unsafe changes? | Hand-labeled actions, negative tests, finite exploration and deliberately weakened rules. | 25 local full-sandbox actions, 25 label matches; 4 TLC contexts; five Python mutants detected. |
| RQ3: Are actual model proposals controlled? | Five Ollama models receive identical tasks with five seeds; independently score what each actually generated. | 500 distinct generations and pooled HPC analysis collected. |
| RQ4: What does assurance cost? | Record phase latency, resource usage, baseline admissions and end-to-end sandbox execution. | Scheduled measurements collected; B3 median action time 0.599 ms. Admission-only baselines are not equivalent deployment pipelines. |
| RQ5: What happens as the harness grows? | Chain, star and random graphs at 10/100/500 components with 1/2/4/8 conflicting approvals. | 180 scheduled trials, one committed winner in every trial; latency and traced-allocation tables collected. |

## Every experimental family

| Experiment | Objective | Result status |
|---|---|---|
| Deterministic HeartBench B0–B3 | Separate parsing/schema/static checks from full assurance across all required evolution families. | 500 scheduled records: B3 retained 65 allowed trials and rejected 60 disallowed trials; B0/B1 admitted 60 disallowed trials and B2 admitted 20. |
| Bounded formal exploration and TLC | Find counterexamples in unsafe lifecycle variants and check corrected finite models. | Executed locally; see formal/assurance/results/temporal. Exact reachable state and labelled-edge agreement; one proposal and three epochs, with no liveness or refinement proof. |
| Five-model B4 | Separate model proposal quality from enforcement failure. | 500 raw outputs; 91 independently evaluable, including 73 disallowed and 18 allowed; no disallowed deployment and no observed false rejection among evaluable allowed outputs. Invalid output is a separate failure category. |
| Three-site qualification | Compare actual queue, startup, generation, residency, resume and transfer outcomes. | Submitted on Fir, Narval and Rorqual; live observations below. |
| Graph scaling and concurrency | Measure cost growth, dependency quarantine and conflicting commits. | 180 scheduled records: three graph shapes, three sizes, four contender counts and five repeats; every batch kept one winner. |
| Fault/recovery and mechanism ablations | Check partial failure, stale approvals and individual rules. | 750 scheduled records including full control; closure, provenance and revalidation removals each admitted five disallowed attempts, while other removals had zero observed effect with retained guards. Removal scope is in experiments/ABLATIONS.md. |
| Cross-cluster reproducibility | Compare matched model/task/seed outputs across sites with equal digests. | Scheduled descriptive report: 24 source/model/prompt/decoding/runtime-matched pairs; all comparisons are limited to the first smoke context. No full-benchmark replication claim. |

## Real harness integration

The active target is Google Research Harness², selected after the earlier survey companion was inspected. The [gap analysis](integrations/harness2/gap-analysis.md) and [real integration workspace](../integrations/harness2/README.md) describe its unchanged upstream workflow, admission/execution/library bridge, finite catalog and bounded model backend. Source-pinned C0–C4 and eight-ablation observations are collected. Earlier survey findings are superseded, and legacy cluster outputs are not current-version integration results.

| Integration question | How we answer it |
|---|---|
| RQ6: Can assurance preserve the real evolution loop? | Pin the unmodified upstream, pass its original tests, and exercise actual admission, execution and library seams. |
| RQ7: Does assurance reduce prohibited deployments? | Count explicit operator-contract violations that reach trusted deployment in C0–C3; score actual C4 proposals independently. |
| RQ8: Can legitimate improvements still work? | Count legitimate rejections separately, and compare actual model task answers with frozen references. |
| RQ9: What does integration cost? | Record action/stream latency, model token costs, GPU residency and queue/transfer time; avoid broad overhead claims from two tasks. |
| RQ10: Does it handle lifecycle faults? | Test dependencies, missing evidence, withdrawn origins, checked recovery, stale approvals and interrupted publication at real boundaries. |

| Planned integration study | Objective | Result |
|---|---|---|
| C0–C3 shared fixtures and separate C4 model study / RQ6–RQ9 | Compare original evolution, basic validation, static DSL, full assurance and model workflows | 900 controlled records and 25 model streams collected; C3 admitted all 15 legitimate shared-fixture trials and none of 45 disallowed trials |
| Ten lifecycle/fault scenario families / RQ10 | Exercise legitimate updates, privilege/verifier writes, dependencies, withdrawal, recovery, evidence, multi-file bundles, concurrency and interrupted installation | 51 integration/worker tests passed; these are engineering checks, not independent empirical samples |
| Eight isolated mechanism ablations | Identify which boundary prevents each failure category | Collected: permission, evidence and dependency removals exposed shared-fixture violations; provenance removal exposed a lifecycle violation; the other removals had zero observed effect. This differs from the five synthetic metadata variants |

## Current Harness² cluster campaign

Controller phase: **complete**. Integration evidence matches current sources: **True**. Raw per-site audit timestamps and fetch freshness remain available under hpc/fetched; the table is a snapshot, not a live assertion.

| Cluster | Run | Observed cells | Complete |
|---|---|---|---|
| fir | ssevoh-h2-full-20261109T223907Z-fir | {'OK': 7} | True |
| fir | ssevoh-h2-smoke-20261109T215404Z-fir-r1 | {'OK': 6} | True |
| fir | ssevoh-h2-smoke-20261109T215506Z-fir-r2 | {'OK': 6} | True |
| fir | ssevoh-h2-smoke-20261109T215518Z-fir-r3 | {'OK': 6} | True |
| narval | ssevoh-h2-smoke-20261109T215528Z-narval-r1 | {'OK': 5, 'CANCELLED': 1} | False |
| narval | ssevoh-h2-smoke-20261109T215559Z-narval-r2 | {'OK': 5, 'CANCELLED': 1} | False |
| narval | ssevoh-h2-smoke-20261109T215608Z-narval-r3 | {'OK': 5, 'CANCELLED': 1} | False |
| rorqual | ssevoh-h2-aggregate-20261109T225912Z-rorqual | {'OK': 2} | True |
| rorqual | ssevoh-h2-full-20261109T224011Z-rorqual | {'OK': 6} | True |
| rorqual | ssevoh-h2-smoke-20261109T215615Z-rorqual-r1 | {'OK': 6} | True |
| rorqual | ssevoh-h2-smoke-20261109T215656Z-rorqual-r2 | {'OK': 6} | True |
| rorqual | ssevoh-h2-smoke-20261109T215701Z-rorqual-r3 | {'OK': 6} | True |

Qualification task-success summaries from the initial smoke source are excluded: a seeded-directory metrics reader was corrected before the full run. Actual raw answers, prompts and traces are retained. Hardware qualification uses completion, GPU residency, accounting, resume checks and verified transfer, which do not use that reader. Full results use the corrected source and remain separate from smoke outputs.

The full design has 900 deterministic records (shared fixtures and separately scoped lifecycle tests), eight isolated ablations, and 25 model streams/50 task observations across five models and five seeds. C0–C2 lack a matching withdrawal/recovery API, so unsupported lifecycle rates are not invented. A task can fail despite a safe admission, and a refusal is not an enforcement success.

Measured primary site: **rorqual**. Unique model ownership: `{"fir": ["qwen3-coder:30b", "devstral:24b", "gpt-oss:20b"], "rorqual": ["phi4:14b", "qwen2.5-coder:7b"]}`. This ranking uses the two measured smoke models and verified cached identities; it is not a universal hardware ranking.

Primary DSL empirical continuation: **complete**. It uses 20 eligible request contexts × five seeds × five models (500 generations), separate B0–B3 metadata baselines, graph scaling and five synthetic ablation families. Its worker/oracle readiness is recorded in experiments/evidence/core-study-readiness.json; these observations are not pooled with the two-task Harness² study.

Collected pooled results: [full controlled table](../artifacts/benchmark-results/harness2-full/analysis/summary.md). All conditions keep their own unsafe-attempt denominators. Only two independent ledger tasks were used; repeated seeds are not additional independent tasks.

## Core assurance checks

Independent one-step cases: 248832; false acceptances: 0; false rejections: 0. Reachable-history transitions: 19620; anchored accepted-trace replays: 6880. Bounds, hashes and raw logs are in formal/assurance/results. Completeness means agreement within those domains, not support for every useful change or proof about arbitrary generated code.

## Legacy cluster observations

| Cluster | Run | Observed cells | Complete |
|---|---|---|---|
| fir | ssevoh-ablation-smoke-20261109T192953Z-fir | {'OK': 1} | True |
| fir | ssevoh-h2v2-full-20261110T203035Z-fir | {'OK': 7, 'FAILED': 2} | False |
| fir | ssevoh-h2v2-full-supplement-20261110T210306Z-fir | {'OK': 5} | True |
| fir | ssevoh-h2v2-smoke-20261110T192719Z-fir-r1 | {'PARTIAL': 1, 'CANCELLED': 4, 'FAILED': 2} | False |
| fir | ssevoh-h2v2-smoke-20261110T192739Z-fir-r2 | {'PARTIAL': 1, 'CANCELLED': 4, 'FAILED': 2} | False |
| fir | ssevoh-h2v2-smoke-20261110T192752Z-fir-r3 | {'PARTIAL': 1, 'CANCELLED': 4, 'FAILED': 2} | False |
| fir | ssevoh-h2v2-smoke-20261110T194515Z-fir-r1 | {'OK': 7} | True |
| fir | ssevoh-h2v2-smoke-20261110T194531Z-fir-r2 | {'OK': 7} | True |
| fir | ssevoh-h2v2-smoke-20261110T194545Z-fir-r3 | {'OK': 7} | True |
| fir | ssevoh-humaneval-controls-t2-20261110T041212Z-fir | {'OK': 3} | True |
| fir | ssevoh-humaneval-preflight-t1-20261110T035601Z-fir | {'OK': 2} | True |
| fir | ssevoh-humaneval-smoke-t1-20261110T042036Z-fir | {'OK': 9} | True |
| fir | ssevoh-humaneval-smoke-v2-t1-20261110T144727Z-fir | {'OK': 3, 'FAILED': 3, 'CANCELLED': 3} | False |
| fir | ssevoh-humaneval-smoke-v3-t1-20261110T150714Z-fir | {'PARTIAL': 1, 'OK': 2, 'CANCELLED': 5, 'FAILED': 1} | False |
| fir | ssevoh-humaneval-smoke-v4-t1-20261110T154824Z-fir | {'CANCELLED': 6, 'OK': 2, 'FAILED': 1} | False |
| fir | ssevoh-humaneval-smoke-v5-t1-20261110T162042Z-fir | {'OK': 9} | True |
| fir | ssevoh-humaneval-smoke-v5-t2-20261110T164436Z-fir | {'OK': 9} | True |
| fir | ssevoh-humaneval-smoke-v5-t3-20261110T164509Z-fir | {'OK': 9} | True |
| fir | ssevoh-modelstage-20261109T191625Z | {'OK': 1, 'NOT_SUBMITTED': 10} | False |
| fir | ssevoh-smoke-20261109T185739Z-fir | {'OK': 8} | True |
| fir | ssevoh-smoke-20261109T191241Z-fir | {'OK': 8} | True |
| fir | ssevoh-smoke-20261109T191626Z-fir | {'OK': 8} | True |
| fir | ssevoh-smoke-20261109T194043Z-fir | {'OK': 9} | True |
| fir | ssevoh-smoke-q1-20261109T192050Z-fir-r2 | {'OK': 8} | True |
| fir | ssevoh-smoke-q1-20261109T192057Z-fir-r3 | {'OK': 8} | True |
| fir | ssevoh-smoke-q2-20261109T194334Z-fir-r2 | {'OK': 9} | True |
| fir | ssevoh-smoke-q2-20261109T194342Z-fir-r3 | {'OK': 9} | True |
| fir | ssevoh-tr-full-20261111T004523Z-fir | {'OK': 88, 'FAILED': 23} | False |
| fir | ssevoh-tr-full-20261111T100909Z-fir | {'OK': 108, 'RUNNING': 1, 'PENDING': 2} | False |
| fir | ssevoh-tr-smoke-20261110T212500Z-fir-r1 | {'OK': 9} | True |
| fir | ssevoh-tr-smoke-20261110T212537Z-fir-r2 | {'OK': 9} | True |
| fir | ssevoh-tr-smoke-20261110T212557Z-fir-r3 | {'OK': 9} | True |
| fir | ssevoh-tr-smoke-20261111T060356Z-fir-r1 | {'OK': 7, 'FAILED': 2} | False |
| fir | ssevoh-tr-smoke-20261111T060412Z-fir-r2 | {'PARTIAL': 1, 'CANCELLED': 6, 'FAILED': 2} | False |
| fir | ssevoh-tr-smoke-20261111T060422Z-fir-r3 | {'PARTIAL': 1, 'CANCELLED': 6, 'FAILED': 2} | False |
| fir | ssevoh-tr-smoke-20261111T070021Z-fir-r1 | {'OK': 9} | True |
| fir | ssevoh-tr-smoke-20261111T070045Z-fir-r2 | {'OK': 9} | True |
| fir | ssevoh-tr-smoke-20261111T070102Z-fir-r3 | {'OK': 9} | True |
| narval | ssevoh-ablation-smoke-20261109T193010Z-narval | {'OK': 1} | True |
| narval | ssevoh-h2v2-full-20261110T203242Z-narval | {'OK': 7} | True |
| narval | ssevoh-h2v2-smoke-20261110T192814Z-narval-r1 | {'PARTIAL': 1, 'CANCELLED': 4, 'FAILED': 2} | False |
| narval | ssevoh-h2v2-smoke-20261110T192829Z-narval-r2 | {'PARTIAL': 1, 'CANCELLED': 4, 'FAILED': 2} | False |
| narval | ssevoh-h2v2-smoke-20261110T192836Z-narval-r3 | {'PARTIAL': 1, 'CANCELLED': 4, 'FAILED': 2} | False |
| narval | ssevoh-h2v2-smoke-20261110T194554Z-narval-r1 | {'OK': 7} | True |
| narval | ssevoh-h2v2-smoke-20261110T194611Z-narval-r2 | {'OK': 7} | True |
| narval | ssevoh-h2v2-smoke-20261110T194619Z-narval-r3 | {'OK': 7} | True |
| narval | ssevoh-humaneval-controls-t2-20261110T041228Z-narval | {'OK': 3} | True |
| narval | ssevoh-humaneval-full-generation-20261110T170240Z-narval | {'OK': 5, 'PARTIAL': 1, 'RUNNING': 1} | False |
| narval | ssevoh-humaneval-preflight-t1-20261110T035607Z-narval | {'OK': 2} | True |
| narval | ssevoh-humaneval-smoke-t1-20261110T042037Z-narval | {'OK': 9} | True |
| narval | ssevoh-humaneval-smoke-v2-t1-20261110T144728Z-narval | {'OK': 3, 'FAILED': 3, 'CANCELLED': 3} | False |
| narval | ssevoh-humaneval-smoke-v3-t1-20261110T150715Z-narval | {'OK': 4, 'FAILED': 2, 'CANCELLED': 3} | False |
| narval | ssevoh-humaneval-smoke-v4-t1-20261110T154826Z-narval | {'OK': 4, 'FAILED': 2, 'CANCELLED': 3} | False |
| narval | ssevoh-humaneval-smoke-v5-t1-20261110T162042Z-narval | {'OK': 9} | True |
| narval | ssevoh-humaneval-smoke-v5-t2-20261110T163921Z-narval | {'OK': 9} | True |
| narval | ssevoh-humaneval-smoke-v5-t3-20261110T163938Z-narval | {'OK': 9} | True |
| narval | ssevoh-smoke-20261109T185742Z-narval | {'OK': 4, 'CANCELLED': 4} | False |
| narval | ssevoh-smoke-20261109T191248Z-narval | {'CANCELLED': 8} | False |
| narval | ssevoh-smoke-20261109T191630Z-narval | {'CANCELLED': 8} | False |
| narval | ssevoh-smoke-20261109T194110Z-narval | {'CANCELLED': 9} | False |
| narval | ssevoh-smoke-q1-20261109T192101Z-narval-r2 | {'CANCELLED': 8} | False |
| narval | ssevoh-smoke-q1-20261109T192110Z-narval-r3 | {'CANCELLED': 8} | False |
| narval | ssevoh-smoke-q2-20261109T194348Z-narval-r2 | {'CANCELLED': 9} | False |
| narval | ssevoh-smoke-q2-20261109T194359Z-narval-r3 | {'CANCELLED': 9} | False |
| narval | ssevoh-tr-full-20261111T004745Z-narval | {'PARTIAL': 1, 'CANCELLED': 36, 'FAILED': 2} | False |
| narval | ssevoh-tr-full-20261111T101200Z-narval | {'OK': 39} | True |
| narval | ssevoh-tr-smoke-20261110T212608Z-narval-r1 | {'OK': 9} | True |
| narval | ssevoh-tr-smoke-20261110T212619Z-narval-r2 | {'OK': 9} | True |
| narval | ssevoh-tr-smoke-20261110T212627Z-narval-r3 | {'OK': 9} | True |
| narval | ssevoh-tr-smoke-20261111T060430Z-narval-r1 | {'OK': 9} | True |
| narval | ssevoh-tr-smoke-20261111T060449Z-narval-r2 | {'OK': 9} | True |
| narval | ssevoh-tr-smoke-20261111T060459Z-narval-r3 | {'OK': 9} | True |
| rorqual | ssevoh-ablation-smoke-20261109T193026Z-rorqual | {'OK': 1} | True |
| rorqual | ssevoh-h2v2-smoke-20261110T192902Z-rorqual-r1 | {'PARTIAL': 1, 'CANCELLED': 4, 'FAILED': 2} | False |
| rorqual | ssevoh-h2v2-smoke-20261110T192913Z-rorqual-r2 | {'PARTIAL': 1, 'CANCELLED': 4, 'FAILED': 2} | False |
| rorqual | ssevoh-h2v2-smoke-20261110T192921Z-rorqual-r3 | {'PARTIAL': 1, 'CANCELLED': 4, 'FAILED': 2} | False |
| rorqual | ssevoh-h2v2-smoke-20261110T194626Z-rorqual-r1 | {'OK': 7} | True |
| rorqual | ssevoh-h2v2-smoke-20261110T194654Z-rorqual-r2 | {'OK': 7} | True |
| rorqual | ssevoh-h2v2-smoke-20261110T194720Z-rorqual-r3 | {'OK': 7} | True |
| rorqual | ssevoh-humaneval-controls-t2-20261110T041228Z-rorqual | {'OK': 3} | True |
| rorqual | ssevoh-humaneval-full-generation-20261110T170240Z-rorqual | {'OK': 5, 'PARTIAL': 1, 'FAILED': 1} | False |
| rorqual | ssevoh-humaneval-preflight-t1-20261110T035607Z-rorqual | {'OK': 2} | True |
| rorqual | ssevoh-humaneval-smoke-t1-20261110T042037Z-rorqual | {'OK': 9} | True |
| rorqual | ssevoh-humaneval-smoke-v2-t1-20261110T144728Z-rorqual | {'OK': 3, 'FAILED': 3, 'CANCELLED': 3} | False |
| rorqual | ssevoh-humaneval-smoke-v3-t1-20261110T150715Z-rorqual | {'OK': 4, 'FAILED': 2, 'CANCELLED': 3} | False |
| rorqual | ssevoh-humaneval-smoke-v4-t1-20261110T154826Z-rorqual | {'OK': 4, 'FAILED': 2, 'CANCELLED': 3} | False |
| rorqual | ssevoh-humaneval-smoke-v5-t1-20261110T162042Z-rorqual | {'OK': 9} | True |
| rorqual | ssevoh-humaneval-smoke-v5-t2-20261110T163359Z-rorqual | {'OK': 9} | True |
| rorqual | ssevoh-humaneval-smoke-v5-t3-20261110T163419Z-rorqual | {'OK': 9} | True |
| rorqual | ssevoh-results-audit-20261110T010942Z-rorqual | {'OK': 3} | True |
| rorqual | ssevoh-results-audit-qualification-20261110T014457Z-rorqual | {'OK': 1} | True |
| rorqual | ssevoh-results-audit-request-fidelity-20261110T015528Z-rorqual | {'OK': 2} | True |
| rorqual | ssevoh-smoke-20261109T185746Z-rorqual | {'OK': 8} | True |
| rorqual | ssevoh-smoke-20261109T191404Z-rorqual | {'OK': 8} | True |
| rorqual | ssevoh-smoke-20261109T191636Z-rorqual | {'PARTIAL': 2, 'CANCELLED': 5, 'OK': 1} | False |
| rorqual | ssevoh-smoke-20261109T194134Z-rorqual | {'OK': 9} | True |
| rorqual | ssevoh-smoke-q1-20261109T192116Z-rorqual-r2 | {'PARTIAL': 2, 'CANCELLED': 5, 'OK': 1} | False |
| rorqual | ssevoh-smoke-q1-20261109T192121Z-rorqual-r3 | {'PARTIAL': 2, 'CANCELLED': 5, 'OK': 1} | False |
| rorqual | ssevoh-smoke-q2-20261109T194404Z-rorqual-r2 | {'OK': 9} | True |
| rorqual | ssevoh-smoke-q2-20261109T194415Z-rorqual-r3 | {'OK': 9} | True |
| rorqual | ssevoh-tr-full-20261111T005048Z-rorqual | {'OK': 1, 'FAILED': 38} | False |
| rorqual | ssevoh-tr-full-20261111T101512Z-rorqual | {'OK': 39} | True |
| rorqual | ssevoh-tr-smoke-20261110T212634Z-rorqual-r1 | {'OK': 9} | True |
| rorqual | ssevoh-tr-smoke-20261110T212647Z-rorqual-r2 | {'OK': 9} | True |
| rorqual | ssevoh-tr-smoke-20261110T212655Z-rorqual-r3 | {'OK': 9} | True |
| rorqual | ssevoh-tr-smoke-20261111T060523Z-rorqual-r1 | {'OK': 9} | True |
| rorqual | ssevoh-tr-smoke-20261111T060535Z-rorqual-r2 | {'OK': 9} | True |
| rorqual | ssevoh-tr-smoke-20261111T060541Z-rorqual-r3 | {'OK': 9} | True |

## Runtime finding and correction

A first-protocol Rorqual setup run timed out during Ollama GPU discovery and fell back to CPU. Its residency gate rejected the run. The revised protocol copies identical runtime libraries to node-local storage and confirms model GPU residency before submitting any task prompt. Earlier trials and the failure logs remain under artifacts/manifests/runtime-v1-failure; their measurements are not mixed with the revised qualification protocol.

## Frozen model identities

5 exact model identities were loaded fully on a Fir GPU and frozen with digests, quantization, license texts, runtime information and blob-integrity checks. This is model preflight, not the full proposal evaluation. See hpc/config/models.frozen.json.

## Measured assignment

Primary site: rorqual. Assignment: `{"fir": ["qwen3-coder:30b", "devstral:24b", "gpt-oss:20b"], "rorqual": ["phi4:14b", "qwen2.5-coder:7b"]}`. Unqualified sites remain explicit; they are not assigned estimated performance.

## Full-campaign observations

The pooled scheduled analysis is in artifacts/benchmark-results/full-campaign/analysis/summary.json. The model table is generated in paper/generated/model-results.tex. All raw prompts, responses and per-condition denominators remain available.

The original task_completion field was a partial transition-field match. A separately labelled post hoc diagnostic adds snapshot, evidence and applicable-condition checks, while preserving the original data and metric.

| Model | Raw outputs | Oracle-evaluable | Strict request matches | Disallowed deployed |
|---|---:|---:|---:|---:|
| qwen2.5-coder:7b | 100 | 0 | 0 | 0 |
| phi4:14b | 100 | 0 | 0 | 0 |
| gpt-oss:20b | 100 | 30 | 21 | 0 |
| devstral:24b | 100 | 0 | 0 | 0 |
| qwen3-coder:30b | 100 | 61 | 21 | 0 |

## How to monitor and reproduce

Run `python3 hpc/scripts/fleet.py status` for all sites and `python3 hpc/scripts/fleet.py fetch` to copy logs. Use `python3 hpc/scripts/fleet.py watch --interval 120 --cycles 30` for a finite monitoring session. Reconnect with `bash hpc/scripts/ssh-session.sh connect all` when MFA is required. See hpc/docs/hpc-guide.md for qualification, selection, full submission and repair.

## Limits on conclusions

Passing this synthetic suite is not proof of universal safety. The policy service and validators must be protected from the agent. The finite model is deliberately small; the runtime is a metadata sandbox with no durable deployment database. No missing empirical result has been replaced by an estimate.

## Matched cross-site smoke outputs

The scheduled cross-site report compared 24 identity-checked pairs; 24 had identical raw text and 24 had invalid syntax on both sites. This includes completed partial Narval cells, marked separately. Agreement on malformed outputs does not establish useful generation or enforcement effectiveness. The comparison uses one first context, three seeds and independent trial allocations, not full-benchmark replication.

[Cross-site tables and censoring status](../artifacts/benchmark-results/qualification/analysis/summary.md). The original site assignment remains frozen; Narval's pending GPU cells were closed after both full studies finished, while completed outputs and downstream collection were preserved.

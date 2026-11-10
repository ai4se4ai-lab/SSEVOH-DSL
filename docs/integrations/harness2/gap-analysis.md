# Google Research Harness²: verified integration gap analysis

Active target selected by the user after the original survey companion was inspected: [google-research/harness2 at 6868817518876de8fd170c6a8354daca273b6191](https://github.com/google-research/harness2/tree/6868817518876de8fd170c6a8354daca273b6191). The earlier Harness-RSI report remains superseded reconnaissance, not a blocker for this executable target. The complete inventory and original 70 passing tests are retained under `integrations/harness2/evidence/`.

## Actual architecture and interception points

`harness2/core/recursion.py::_run_stage` obtains an editor workspace, rejects off-surface files and calls `_accept_tree` before returning an admitted `Stage`. `_accept_tree` repairs skill triggers, checks the surface, calls benchmark validation and rejects grader verdicts. `_roll` writes a stage's tree before calling `adapter.execute`. Both parallel and sequential modes reuse these functions. `core/schedule.py` selects outputs and calls `Library.add` after evidence-backed reflection; `Library.context_dir` supplies earlier same-domain entries to later tasks. These are genuine execution/admission/persistence boundaries.

The integration must intercept `_accept_tree` after the original checks, verify exact bytes again immediately before `adapter.execute`, and guard library writes/reuse. Admission alone cannot cover a later modified stage directory. Each task starts from the common execution harness; the library, rather than automatic inheritance of the last execution tree, carries learning across tasks. Branch candidates are intentionally independent; a shared mutable global harness must not silently replace this design.

## Concerns grounded in the inspected code

| Concern | Actual original capability | Classification / integration contribution |
|---|---|---|
| Editable paths | `read_tree(..., rejected=...)` plus `_run_stage` reject off-surface edits; relative-path normalization rejects escapes | Already addressed at the intended editor boundary; preserve it and add strict symlink/byte snapshot checks at execution |
| Structural dependencies | Syntax compilation, script-reference checks, skill triggers/frontmatter, deployment-specific hooks and subagent checks | Already partly addressed; preserve all checks. General semantic compatibility still needs independent validators. |
| Evidence separation | `context.py` removes grader information; selection precedes final judging; reflection requires execution-supported lessons | Already addressed for the stated workflow; preserve and record assurance evidence separately |
| Resume and failure handling | Identity/fingerprint checks, bounded retries, fallback to base and regression tests | Already addressed in substantial part; do not present existing safeguards as new contributions |
| Evolution permissions | Surface is mutable, including guardrails/tool guidance/scripts; no operator-owned SSEVOH principal/operation capability policy in `_accept_tree` | Directly addressable by an independent metadata policy and protected-content checks |
| Approval-to-execution binding | Candidate validation precedes materialization/execute; `_roll` itself does not require an SSEVOH one-use/context-bound approval | Add exact artifact binding and recheck before actual execution; no exploit of deployment internals claimed without tests |
| Provenance/withdrawal | Library retains complete chosen trees and experience; `forget` removes entries, without a global monotone withdrawn-version/origin semantics | Directly addressable for known bundle versions and declared exposure origins; semantic causation of LLM derivation remains unproved |
| Recovery | Proposer failures inherit the current/base tree; no operator API for prohibited-version-safe historical restoration at this seam | Add explicit checked recovery; preserve existing fallback |
| Cross-component edits | Trees contain several files from eight component classes | Publish a complete immutable tree as one versioned bundle; this does not implement arbitrary multi-target metadata transactions |
| Independent verifier protection | OpenCode uses workspace permissions; Claude CLI channel passes a permission-bypass flag. No OS-isolated SSEVOH service is supplied | Partial: a restricted data-only proposal client and trusted catalog executor can isolate the initial integration. Unrestricted tool-enabled editors require additional OS isolation before being supported. |
| Arbitrary executable safety | Syntax and surface checks do not prove behavior | Outside general DSL metadata soundness. Initial executable domain must use an independently checked finite Python catalog; broader code needs stronger validators/isolation. |

No general claim is made that Harness² promised formal authorization or arbitrary-code safety. Its intended contrastive probes support editing without ground-truth feedback and do not certify task correctness. The provided technical document's Propose–Probe–Compose, per-task reset and persistent improvement library are retained. Published benchmark gains and model settings are prior-work results, not new SSEVOH measurements.

## Acceptance criteria before empirical work

Preserve upstream source and all original tests. Demonstrate both recursion modes and later-task library reuse with exact approved bytes. Exercise operator denial, protected verifier paths, actual dependency failures, missing/negative evidence, withdrawn versions and descendants, safe recovery, multi-file atomic materialization, concurrent/stale approval and injected interruption. Check actual filesystem/execution outcomes, not only decisions. Record source/policy/validator/evidence/byte hashes and raw decisions. Model-check the adapter's finite publication/activation lifecycle. Keep empirical submission locked until those checks pass and unsupported surfaces are explicit.

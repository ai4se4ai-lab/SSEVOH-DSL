# SSEVOH-DSL 0.2 core readiness

The metadata-sandbox core passed its formal-first release checks on 2026-11-09. It is ready for read-only upstream reconnaissance and integration design against its actual supported API. Empirical submission remains locked. This is bounded verification with explicit assumptions, not a universal proof of safety or completeness.

## Available and tested

| Capability | Implementation | Verification evidence |
|---|---|---|
| Located lexer/parser, types, semantic analysis and canonical IR | `compiler.py`, `model.py`, `compiler_print.py` | Positive/negative tests; canonical serialization is compiled in every concrete conformance case |
| Identity, versions and operation permissions | Immutable `Component`, `State`, host `Policy` | All component kinds, mutability settings, grants, capability ceilings and versions in finite domains |
| Dependency and provenance impact | Reverse closure; graph checks; transitive version origins | Exhaustive two-component graphs; exact state/origin agreement; mixed parents; withdrawn-version laundering regression |
| Evidence before approval | Host-owned registry; all required predicates must return exactly True | Missing/negative/throwing validators; reentrant validator and policy/registry changes |
| Approval and deployment | Context-bound, single-use approval; locked metadata swap | Forgery/replay, stale approval, history/candidate/origin tampering, eight-way conflicting commits, injected precommit failure |
| Withdrawal/revalidation/recovery | Monotone withdrawn identities; quarantine; exact historical records and origins | Exhaustive histories, current ceilings on rollback, prohibited-origin recovery rejection |
| Traceability | Journal v2, separate decision chain, anchored replay | Source/IR/policy/evidence/origin bindings, state continuity, rehashed semantic forgery and external-head checks |
| Programmatic interface | `compile_source`, `SandboxEngine.approve/deploy/snapshot`, `replay_journal`; CLI compile/verify/demo | End-to-end API tests and six compiling examples |

## Executed results

| Check | Result | Exact scope / raw evidence |
|---|---|---|
| Unit and adversarial regression tests | 62 passed | [Raw test log](../../formal/assurance/results/unit-tests.log) |
| Independent one-step relative conformance | 248,832 cases; 3,388 accepted; 245,444 rejected; zero false acceptances or false rejections | [Bounds and source hashes](../../formal/assurance/results/conformance.json); 176,256 graph/lifecycle + 72,576 type/permission/evidence cases |
| Reachable history conformance | 19,620 transitions; 3,307 contexts; 6,880 accepted and 12,740 rejected | [Report](../../formal/assurance/results/sequences.json); seven initial acyclic graphs, two components, versions 1–3, depth four, existing relations retained |
| Anchored accepted-trace reconstruction | 6,880 successful replays | Same history report; independent reference state/history/origins agree |
| TLC safety and exact graph agreement | Four contexts pass; all nodes and labelled edges match the Python abstraction | [Manifest](../../formal/assurance/results/temporal/tlc-manifest.json); one proposal, epochs 0–2 |
| Deliberately unsafe lifecycle models | Five detected with counterexample traces | [Python exploration and traces](../../formal/assurance/results/temporal/local-verification.json) |

TLC/Python graph sizes are 18 states/44 labelled edges for each unauthorized context, 23/62 for authorized without evidence, and 61/133 for authorized with evidence. Equality compares full state tuples and action-labelled relations, including explicit self loops; it is stronger than comparing counts. TLC 1.7.4 is pinned by SHA-256. Old 0.1 logs, including the earlier 60-state model, are retained separately under `formal/results/`.

The [release manifest](../../formal/assurance/results/readiness.json) records all commands, raw-log hashes, report hashes and exact source hashes. The runner verified that source remained unchanged throughout the complete check. Reproduce with `make verify`, or `make verify TLA2TOOLS_JAR=/path/to/tla2tools.jar`. Diagnostic prefixes cannot satisfy readiness.

## Meaning of the five requested properties

- **Soundness:** accepted transitions satisfy the stated metadata admissibility rules and invariants in the checked domains; the [preservation argument](../../formal/assurance/proof-arguments.md) explains induction under the trusted-host assumptions.
- **Completeness:** every representable proposal admitted by the independent operational semantics in those domains is accepted under stable context, positive required evidence and no resource/adapter failure. This is relative completeness, not support for every useful harness change.
- **Verifiability:** [contract](../../formal/assurance/contracts.md), independent executable semantics, temporal model/configuration, pinned checker, reproduction runner and inspectable counterexamples are present.
- **Traceability:** deployed events bind source/IR, principal, policy, validator identity, evidence, state and origins. Replay reconstructs effects. A trusted externally retained head is needed to authenticate a chain against replacement/truncation.
- **Safety:** unauthorized changes, privilege expansion, invalid active ancestors, withdrawn versions/origins, protected-dependent invalidation, stale/forged/replayed approvals and injected partial preparation are rejected by the available service boundary.

## Interfaces and limits for integration

Call `SandboxEngine(initial_state, policy, validators)`, then `approve(dsl_text, authenticated_principal)`, then `deploy(approval)`; catch `Diagnostic`/`Rejected` as structured categories/messages. `snapshot()` reads state and journal consistently. Revalidation requires a newly checked update or rollback. The evolving agent must have only a restricted text API, not access to Python private fields, policy/validator registration or the service's storage. Registry fingerprints detect replacement; they do not attest arbitrary closure environments. Validators must be trusted, pure and terminating.

Initial version ancestry is trusted except for declared parents. Artifact contents and tests are represented by metadata and trusted predicates; this core does not establish generated-code behavior. Rejection is deterministic for a stable context and predicates; approval tokens and service-local registry identities intentionally differ between instances.

Not implemented: creation/deletion, arbitrary predicates in DSL text, multi-component atomic transactions, temporary grants/approval hierarchy, semantic provenance release, OS-enforced independent service isolation, durable deployment/crash recovery, distributed commits, liveness or a mechanized unbounded implementation-refinement theorem. Integration must implement and test any additional capabilities it needs, or explicitly report them unsupported. No adapter may be described as a real upstream integration without an actual upstream executable evolution boundary.

## Trace matrix

[Property obligations](properties.md) map to [operational rules](../../formal/assurance/reference.py), [runtime enforcement](../../src/ssevoh/assurance.py), [adversarial regressions](../../tests/test_assurance.py), [one-step evidence](../../formal/assurance/results/conformance.json), [history evidence](../../formal/assurance/results/sequences.json), and [temporal evidence](../../formal/assurance/results/temporal/tlc-manifest.json). All are scoped by the release manifest, assumptions and finite bounds above.

Earlier local/HPC benchmarks are legacy exploratory evidence and are not pooled with this release. The detached empirical controller was stopped and repository-owned queued/running jobs were canceled on Fir, Narval and Rorqual; scheduler inspection found zero remaining active project jobs. Read-only SSH monitoring and preserved logs remain available.

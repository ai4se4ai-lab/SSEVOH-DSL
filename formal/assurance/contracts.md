# Core assurance contract, version 0.2

The core is a finite-metadata transition system, not a verifier for arbitrary generated programs. The trusted host owns policy, validators, initial state and enforcement. Validators are terminating trusted predicates; code execution and semantic artifact correctness are outside the metadata theorem. No arbitrary Python predicate is accepted from DSL text.

## Mathematical admissibility

Let H=(C,Q,W,r), history K contain immutable version records, and L map a version identity to its transitive derivation origins. Component identity is (name,version), not a name alone. Dependency and parent lists denote sets. The trusted initial active graph is acyclic and has active ancestors. Permission is a host-authenticated (principal,target,operation) grant, with immutable/protected-kind isolation and a host capability ceiling; absent an explicit ceiling, the current target's capabilities are the ceiling.

Update requires a fresh increasing version, conservation of declared provenance parents, valid references, the stated precondition, and all required evidence. Its origins inherit the previous target identity and its origins, plus the current identities and origins of declared parents. Withdrawal adds the current identity to the monotone W and quarantines the reverse closure over dependencies and provenance. Recovery loads an exact known historical version with its historical origins, retaining current W. No active version or transitive origin may be in W. Affected protected components (including policy/verifier kinds) cannot be quarantined. All final active references and acyclicity must hold; the requested postcondition must hold.

Approval binds the source IR, base state, host policy, validator registry, candidate and origin map. Context is captured before validation and checked after validation to prevent a reentrant validator rebinding an old candidate to a new base. Commit requires an authentic unconsumed approval, unchanged context, consistent candidate/origins and complete evidence. It stages journal/history/origin updates under a lock before exposing the new state. Injected precommit failure exposes no candidate. Durable crash recovery is not claimed.

## Soundness

For well-typed inputs and a stable trusted host context, every accepted deployment satisfies mathematical admissibility and the post-state invariants above. Machine evidence consists of independent concrete-spec conformance, safety invariants, adversarial regressions and bounded temporal exploration. A documented inductive argument covers arbitrary finite metadata graphs under the stated transition rules; it is not a machine-checked refinement theorem for all Python executions.

## Relative completeness

For well-typed representable proposals, if the independent operational semantics says the transformation is admissible, all operator-required validators return true, the history is available, the context remains stable and no adapter/resource failure occurs, the runtime must accept. Exhaustive verification establishes this equivalence only over each explicitly enumerated finite domain. Completeness for all intuitively useful harness improvements, arbitrary code semantics, provenance release, multi-component transactions, distributed execution and liveness is not claimed.

## Traceability and verification evidence

Accepted events bind source, IR, principal, policy, state hashes, origins and independent evidence. Replaying with the same trusted policy and predicates must reconstruct the recorded post-states. A trusted external head anchors tamper detection; an unanchored rewritable chain alone does not authenticate its author. Rejections and verification reports are machine-readable. Empirical work remains locked until a versioned readiness report states exactly which contracts passed and which remain unsupported.

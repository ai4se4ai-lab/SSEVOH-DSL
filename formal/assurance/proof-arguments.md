# Metadata preservation arguments

These are reviewable mathematical arguments for the specified rules, not a mechanized proof of Python or arbitrary artifact code. The executable evidence has explicit finite bounds in each report. The trusted host, authenticated principal, pure terminating validator functions, SHA-256 collision resistance, adequate resources, and exclusive use of the public service boundary are assumptions.

## Invariant and induction

I(H,K,L) states: component identities/relations are well typed and unique; the union of dependency and parent edges is acyclic with known endpoints; every active component has active direct ancestors; no active identity or transitive version origin belongs to W; historical records and origins are immutable per identity; W is monotone; protected records and trust states have not changed through unprivileged evolution.

Base: service construction checks graph invariants, freezes input containers, constructs known history and version origins from the initial acyclic graph, and checks all active origins. Initial historical completeness is an operator assumption: the constructor treats initial component versions as trusted roots except for their declared parents. It cannot discover omitted preexisting derivation.

Update: a fresh increasing identity prevents overwriting historical metadata. Conserving parents prevents deleting declared ancestry. Inherited old identity/origins and parent identities/origins preserve derivation across multiple updates. Reverse closure quarantines affected dependents. The protected-component guard rejects newly quarantined protected nodes. Graph, active-reference and origin checks establish I for the candidate.

Withdrawal: only the current identity is added to W, so W is monotone. Quarantining the target and reverse closure invalidates dependent/derived artifacts. The same protected, graph and origin checks reject any remaining invalid active state. Historical records/origins remain unchanged.

Recovery: only an exact existing history entry with its recorded origins is eligible. Current W is retained and both the restored identity and transitive origins are checked against it. Current capability ceilings and protected dependents are rechecked. Thus historical approval cannot override today's withdrawal or permission context.

Approval and commit: compilation and authorization check the actual authenticated principal, current target and operation. Every mandatory/explicit validator must exist and return exactly True. Capturing context before validation and checking it after each callback prevents a reentrant callback from silently rebinding a candidate. An unconsumed random service-local token binds proposal, principal, base, policy, registry, candidate and origins. Commit rechecks the context and bindings under the same lock, stages new history/origins/journal, and changes the exposed references together. Concurrent operations therefore linearize at that swap. Stale/replayed/forged approvals and injected precommit failure expose no candidate state. This is an in-process guarantee, not a durable filesystem transaction or protection against a malicious process owner.

By induction on accepted public deployments, the transition rules preserve I. The Python implementation additionally applies an independent concrete graph/isolation/provenance verifier; finite conformance checks compare it against separately written set/fixed-point reference rules.

## Relative completeness argument

Consider well-typed representable proposals for which the independent reference admits a transition, with stable context, available history, all required pure validators returning True, and no adapter/resource failure. Each static compiler rejection corresponds to an explicit reference premise (references, types, versions, isolation, privilege, withdrawal postcondition). Each runtime candidate check corresponds to an operational premise (fresh identity, conditions, history, parent conservation, graph, protected closure, origins). The independent concrete verifier checks consequences of the same premises. Thus no additional rejection should occur; the token can be committed under unchanged context.

The exhaustive one-step suite checks both directions of this equivalence in its declared domains. The history suite checks reachable state/history/origin contexts up to depth four, including successful and rejected recovery and withdrawal. This does not establish universal completeness, machine-checked refinement, liveness, distributed atomicity, semantic safety of generated code, or acceptance of useful changes outside the supported language.

## Trace and temporal scope

A chained journal binds consecutive pre/post states and source/IR/policy/evidence/origins. Replay compiles, authorizes, validates and deploys each event and compares the resulting state/origins. An externally retained final hash detects chain replacement or truncation; an unanchored chain alone provides consistency, not authenticity. Registry identities are service-instance-local, so replay reruns supplied trusted validators rather than claiming that a Python closure's full environment is attested.

The TLA+ abstraction checks one proposal with dependency epochs zero through two, all four fixed authorization/evidence contexts, and active-implies-authorized/evidenced/current/not-withdrawn. Exact labelled graph equality establishes that the separate Python explorer implements this finite abstraction. It is not a refinement proof from the concrete metadata engine to the TLA+ model. Five intentionally faulty abstractions must yield counterexamples; these are distinct from the research mechanism-removal experiments.

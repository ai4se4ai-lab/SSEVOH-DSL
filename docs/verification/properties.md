# Property and evidence map

Let Active(H) exclude quarantined components, W be monotone withdrawn pairs, D the dependency/provenance relation, and r the revision.

| Property | Mathematical obligation | Executable artifact / argument |
|---|---|---|
| Authorization | commit(e) ⇒ (principal,target,op) ∈ P.grants | Policy.authorize; finite authorization mutant; unauthorized tests |
| State integrity | ∀c∈Active(H): valid type/version/references | compiler + structural_errors + independent Kahn check |
| Dependency | c∈Active(H) ⇒ deps(c)⊆Active(H) | closure quarantine; invalid ancestor tests |
| Provenance | parents(c)⊆C and acyclic; active identity/origins disjoint from W; anchored journal replay | independent graph checks; transitive version-origin checks; hash chain/replay; ancestry-removal and version-laundering rejection |
| Evidence | approve(e,H) ⇒ ∀v∈required(P,e): V[v](H',e)=true | registered validators; evidence mutant and missing/negative tests |
| Withdrawal | W⊆W' and Active(H')∩closure(target)=∅ | candidate construction, withdrawal mutant, mixed-parent test |
| Rollback | (c,version(c))∉W for restored active c | historical lookup, rollback mutant, known-history tests |
| Revalidation | commit(cap,H) ⇒ cap.base=hash(H) and context unchanged since before validation | state/policy/registry/history/origin binding; reentrant-validation regression; locked fingerprint comparison; epoch mutant; stale approval tests |
| Isolation | protected components unchanged and active status unchanged | immutable/protected-dependent tests; candidate changes one target |
| Privilege | capabilities(c')⊆operator ceiling(c) | policy, candidate/history checks and independent concrete checks using the trusted base state; tool and rollback-capability regression tests |
| Lifecycle | commit requires authentic unconsumed APPROVED capability | replay/forgery/race tests; finite lifecycle model |

Inductive argument within the reference semantics: assume the initial active graph satisfies these invariants. Candidate construction preserves names/types and protected metadata, monotonically extends W, quarantines reverse closure and checks active references/cycles. Independent validators and policy checks gate approval. The locked fingerprint comparison ensures the checked candidate still extends the identical base. A single reference swap commits all metadata, so failed preparation cannot expose a partial state. Thus every successful reference transition preserves the stated metadata invariants under the assumptions. This is a documented argument, not a machine-checked implementation proof.

No fairness assumption or temporal liveness guarantee is established. An adversarial scheduler or repeated dependency changes can indefinitely delay an otherwise eligible proposal.

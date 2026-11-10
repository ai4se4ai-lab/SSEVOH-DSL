# Related work and scope

Verified on 2026-11-09 against original sources. These are starting points, not a systematic review.

- Lamport, *Specifying Systems* (2002), https://lamport.azurewebsites.net/tla/book.html: transition specifications and safety/liveness. Our finite checker explores an explicitly bounded abstraction; it is not an unbounded proof.
- W3C, *PROV-DM* (2013), https://www.w3.org/TR/prov-dm/: entity/activity/derivation vocabulary. We add operational quarantine and version withdrawal rules; our journal is not a complete PROV serialization.
- Zhang et al., *Darwin Gödel Machine* (2025, revised 2026), https://arxiv.org/abs/2505.22954, DOI 10.48550/arXiv.2505.22954: empirical self-improvement through code modification. Our focus is permission and lifecycle enforcement, rather than optimization of agent performance.
- Fowler, *Domain-Specific Languages* (2010), https://martinfowler.com/books/dsl.html: engineering readable constrained languages. The contribution here requires evaluation of evolution-specific constraints, not simply inventing syntax.
- use-hpc, https://github.com/ai4se4ai-lab/use-hpc: reused orchestration, contracts, ledgers, arrays, resume, manifests and collection. Fleet scheduling is an extension over its single-site runner.

Research gap to evaluate: whether an explicit permission/evidence/dependency/withdrawal lifecycle prevents unsafe harness metadata changes while retaining useful proposals at acceptable cost. Novelty and practical generalization remain research questions.

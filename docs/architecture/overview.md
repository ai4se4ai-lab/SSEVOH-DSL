# Architecture and research scope

SSEVOH separates an untrusted proposal from an operator-owned policy, independent validation, and an atomic sandbox deployment. The proposer supplies a small declarative transformation, never executable Python or policy updates. The authenticated principal comes from the caller, not the proposal. The policy and evidence authority belong outside the agent's writable filesystem and process in a real deployment.

Pipeline: lexer → parser → immutable AST → references/types → trusted policy → candidate graph → independent bounded transition verification → evidence → single-use approval → atomic compare-and-swap deployment.

The first implementation uses Python's standard library and an in-memory sandbox, with immutable snapshots, a lock, and a hash-chained audit journal. It changes artifact metadata, not production files or agent code. It makes no claim to sandbox arbitrary code, persist a trusted runtime across crashes, or prove arbitrary validators correct. Deployment adapter isolation is an OS-level assumption. An explicit finite-state checker supplies exhaustive reachability for a bounded lifecycle abstraction; a separate TLA+ model documents the same abstraction. No SMT or Alloy dependency is needed for this scope.

Experiments use the upstream use-hpc template, with a thin fleet controller for SSH, per-cluster graphs, measurements, weighted scheduling, log synchronization, and publication updates. HPC inference is performed only inside Slurm GPU allocations, with a model-residency gate before task evaluation. Runtime binaries and libraries are staged on node-local storage to avoid shared-filesystem GPU-discovery delays. Small local tests establish implementation behavior, not cluster performance.

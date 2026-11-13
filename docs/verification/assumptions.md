# Assurance assumptions and limits

- The operator owns initial state, policy, validator registration, Python process, audit storage and deployment adapter.
- Untrusted agents access a restricted text API, never the in-process Python object or its private attributes. Production isolation requires a separate service/container and a restricted filesystem; this repository provides the sandbox reference only.
- Artifact content is represented by versioned metadata. `structure` does not validate generated code behavior, test quality or semantic provenance release.
- One engine lock serializes concurrent commits. Distributed and durable crash recovery are not implemented.
- The independent checker explores one proposal, three epochs and boolean authorization/evidence. Multiple proposals are covered by runtime concurrency tests, not that model.
- TLC 1.7.4 execution logs for all four boolean contexts are recorded in formal/results; they verify the bounded TLA+ abstraction only.
- Safety of a finite model does not establish a refinement proof, arbitrary-state safety, liveness, or production security.
- Proposal refusal, invalid syntax, rejected unsafe proposals and unsafe deployments are different outcomes.

Version 0.2 current evidence is in `formal/assurance/results/`; `formal/results/` is legacy evidence. Independent concrete conformance covers 248,832 one-step cases and histories through depth four over the declared two-component domains. Exact labelled graph comparison links TLC to the Python abstraction, not to an unbounded proof of the concrete engine. Validators must be trusted, pure and terminating; function identity/code fingerprints cannot attest arbitrary mutable closure environments. The trusted initial versions are roots except for declared parents; omitted historical ancestry cannot be inferred. Hash-chain authenticity requires an externally retained head. See `formal/assurance/contracts.md` and `proof-arguments.md`.

# SSEVOH assurance for Google Research Harness²

The active executable target is [google-research/harness2](https://github.com/google-research/harness2/tree/6868817518876de8fd170c6a8354daca273b6191), pinned to `6868817518876de8fd170c6a8354daca273b6191`. This replaces the survey companion previously supplied as the target. Upstream source remains unchanged. The core 0.2 formal release preceded integration.

The implemented bridge intercepts the actual `_accept_tree` admission function, binds stage receipts, checks exact bytes again before `adapter.execute`, and protects `Library.add/context_dir`. Original proposal, retry, contrastive probe, parallel/sequential composition, selection, reflection and subsequent-task library machinery stay upstream.

The supported execution domain is deliberately explicit: the original local ledger executor and an added bounded Ollama ledger-agent executor with two actions (invoke a catalog tool or return an answer). Data-only model edits cannot run shell commands or alter the assurance implementation. Python scripts must match a checked finite AST catalog. General OpenCode/Codex tool-enabled execution, arbitrary program safety, professional-benchmark replication and automatic durable recovery are not claimed or enabled.

- [Verified gap analysis](../../docs/integrations/harness2/gap-analysis.md).
- [Assurance contract and limits](formal/contracts.md).
- [Adapter source](adapter/ssevoh_harness2).
- [Original upstream tests](evidence/upstream-tests.txt).
- [Integration/security/fault tests](evidence/integration-tests.txt).
- [TLC/Python publication graph evidence](evidence/publication-verification.json).
- [Source-scoped readiness](evidence/readiness.json).

Reproduce with Python 3.12+ and Java:

```bash
python3 integrations/harness2/scripts/checkout.py
python3 integrations/harness2/scripts/package_runtime.py
python3 integrations/harness2/scripts/verify.py --tlc-jar /path/to/tla2tools.jar
```

`upstream-runtime.tar.gz` is a deterministic 286,895-byte archive of 133 pinned non-image files, including the original license and tests. Its manifest records every source hash. It allows offline compute nodes to use the exact same upstream without installing packages or downloading on login nodes. The complete 140-path upstream checkout remains ignored and reproducible.

Empirical workers and the active use-hpc profile live under `experiments/scripts/harness2_*.py` and `hpc/config/profiles/harness2.json`. The previous DSL study configuration is retained at `hpc/config/profiles/ssevoh-original.json`; old evidence is not pooled into this study. Core, upstream, integration, publication-model and worker preflights passed before the controlled study was released. The running controller state is in `hpc/fetched/harness2-campaign.json`. A separately verified primary DSL continuation is prepared behind completion of this campaign and fresh qualification. Experimental observations will be separate from unit/formal evidence and will use explicit unsafe-attempt and task denominators.

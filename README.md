# SSEVOH-DSL

A Domain-Specific Language and Formal Verification Framework for Safe Self-Evolution of AI Agent Harnesses.


The agent proposes a change. A trusted service checks policy, dependencies, provenance, independent evidence and bounded safety rules before issuing a single-use approval. The sandbox commits it atomically only while the approved base state remains current.

This is a working **metadata sandbox research prototype**, not a production agent deployment service. Both full studies are collected: 500 raw DSL outputs and 25 Harness² model streams, with separate deterministic, scaling and ablation datasets. See the [plain-language research guide](docs/research-overview.md) and [implementation report](docs/implementation-report.md) for actual evidence and gaps.

The formal-first [core release](docs/verification/core-readiness.md) and [Harness² integration checks](integrations/harness2/evidence/readiness.json) have passed. Both full studies completed on Fir/Rorqual after their own three-site smoke cohorts. Narval missed the selection deadline; completed late cells and censored GPU cells are documented separately. `hpc/config/research-readiness.json` names the released study identities. The earlier empirical controller remains disabled; legacy artifacts stay separate.

## Run locally

Requires Python 3.11+. The core has no third-party dependency.

```bash
export PYTHONPATH=src
python3 -m unittest discover -s tests -v
python3 -m ssevoh.cli compile examples/basic-evolution/example.sse
python3 -m ssevoh.cli demo examples/basic-evolution/example.sse
python3 -m ssevoh.cli verify
# Full formal readiness checks (Java required; verifies a pinned TLC download):
make verify
# Or use an existing checksum-pinned checker:
make verify TLA2TOOLS_JAR=/path/to/tla2tools.jar
```

For an installed CLI, use `python3 -m pip install -e .` inside a virtualenv. `demo` grants a demo operator permission for the example's operation; an application must supply its own trusted policy and authenticated caller identity.

## Read the design

- [Architecture](docs/architecture/overview.md), [threat model](docs/architecture/threat-model.md), [formal semantics](docs/architecture/formal-semantics.md).
- [Language reference](docs/language/language-reference.md), [grammar](docs/language/grammar.ebnf), six [examples](examples).
- [Properties and evidence](docs/verification/properties.md), [assumptions](docs/verification/assumptions.md), [verification guide](docs/verification/verification-guide.md).
- [HeartBench](benchmark/README.md), [experiment plan](experiments/experiment-plan.json), [claim-to-evidence matrix](docs/claim-evidence-matrix.md).

## Fir, Narval and Rorqual

The `hpc/` pipeline reuses [ai4se4ai-lab/use-hpc](https://github.com/ai4se4ai-lab/use-hpc), pinned in `hpc/UPSTREAM_COMMIT`, with a thin fleet extension. See the complete [HPC guide](hpc/docs/hpc-guide.md).

```bash
bash hpc/scripts/ssh-session.sh connect all   # interactive MFA in your terminal
bash hpc/scripts/ssh-session.sh status all
bash hpc/scripts/selftest.sh                 # static checks, submits nothing
python3 hpc/scripts/fleet.py status          # audit all sites
python3 hpc/scripts/fleet.py fetch           # persistent logs/results copied locally
python3 hpc/scripts/live.py --watch 5        # read local snapshots; no extra Slurm polling
python3 hpc/scripts/campaignctl.py --profile harness2 status
python3 experiments/scripts/update_report.py
```

Copy `hpc/config/fleet.example.json` to ignored `fleet.local.json` and set account, paths and discovered GPU resources for another user. No passwords, private keys or MFA codes belong in configuration. Reconnect interactively when a session expires. No inference or analysis executes on login nodes; pure CPU analysis uses scheduled CPU jobs. Raw prompts/responses, frozen configs/source, model digests/license metadata, Slurm accounting, step ledgers and GPU telemetry support auditing.

Cluster ranking requires three independent completed smoke runs for both smoke models, matching model identity, full GPU residency, successful record resumption and verified artifact transfer. No cluster is selected from hardware specifications alone. Full submission recomputes the measured ranking and enforces unique ownership of each of the five model cells.

## Publications

The [IEEE Software manuscript](docs/ieeesoftware/main.tex) preserves the supplied class/template and uses an explicit article-class fallback when publisher assets are missing. Seven independently compilable technical documents are under [paper/supplementary](paper/supplementary). `make paper` builds eight review PDFs in ignored `paper/build/`. `python3 experiments/scripts/word_count.py` checks the conservative 4,200-word ceiling, 250-word visual allowance and 150-word abstract limit.

`update_report.py` imports only recorded evidence. The primary independent oracle evaluated 91 of 500 outputs, including 73 disallowed proposals; none was deployed. Three models produced no syntax-valid raw DSL. Evolved and frozen Harness² model workflows both achieved 0/50 task successes, so useful self-improvement remains unestablished. Matched smoke outputs concern one context and do not establish broad replication.

## Harness² integration

The active executable target is [Google Research Harness²](https://github.com/google-research/harness2/tree/6868817518876de8fd170c6a8354daca273b6191), selected after inspection showed the earlier URL was a survey companion. The [integration workspace](integrations/harness2/README.md) and [verified gap analysis](docs/integrations/harness2/gap-analysis.md) describe the actual admission/execution/library bridge, tested boundaries and controlled execution scope. The earlier survey reconnaissance remains preserved as superseded evidence.

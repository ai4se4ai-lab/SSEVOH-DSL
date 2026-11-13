# Reproduce formal assurance

From the repository root, with Python 3.11+ and Java installed:

```bash
make verify
# An existing official TLC 1.7.4 jar may be supplied:
make verify TLA2TOOLS_JAR=/path/to/tla2tools.jar
```

The runner verifies the official checker SHA-256 before execution, runs unit/adversarial tests, checks four TLC contexts, compares every reachable state and labelled edge with the Python abstraction, exhaustively compares concrete DSL proposals against independent operational semantics, and explores bounded histories with anchored replay. It refuses readiness if the source changes during verification. Commands, stdout/stderr, domain bounds, source hashes, checker hash and report hashes are recorded in `formal/assurance/results/`. The contract and proof arguments are in `formal/assurance/`.

To run individual stages:

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -v
PYTHONPATH=src python3 formal/check.py --tlc-jar /path/to/tla2tools.jar
PYTHONPATH=src python3 formal/assurance/check_conformance.py
PYTHONPATH=src python3 formal/assurance/check_sequences.py --depth 4
```

`check_conformance.py --limit N` is a diagnostic prefix and cannot satisfy complete-domain readiness. The source-scoped readiness report supports integration reconnaissance for the metadata API. It always keeps empirical submissions disabled; integration and its tests must be handled before empirical evaluation. Old `formal/results/` logs and old HPC artifacts remain explicitly legacy evidence.

These checks establish finite relative conformance and bounded temporal safety. They do not constitute a machine-checked unbounded refinement theorem or establish arbitrary generated-code safety. Read [the readiness report](core-readiness.md) for assumptions, unsupported features and interfaces.

# ledger-1

- adopted: `agg1`  (run `demo-oc-agg1-s1703/ledger-1/agg1`)
- components: 1 scripts; 62 always-on chars

## Why this was chosen
trivial pool: single final at k=1; delivered without a selector session

## What each edit did
component: scripts/summarize.py
candidates: agg1, dom1, inv1
change: No change in the script content; all candidates used identical script.
observed: All harnesses produced identical output (Total: 105.25) across all rollouts.
verdict: no observed effect

component: systemprompt.md
candidates: agg1, dom1, inv1
change: No change in system prompt content; all candidates used identical prompt.
observed: All harnesses produced identical output (Total: 105.25) across all rollouts.
verdict: no observed effect

## Transferable lesson
- **cue**: when multiple candidates produce identical outputs and no behavioral differences are observed, it is not possible to infer which edit contributed to the adoption
- **lesson**: do not attribute adoption to specific edits when all candidates yield the same result; instead, treat such cases as confounded or inconclusive
- **evidence**: All three candidates (agg1, dom1, inv1) produced identical outputs despite different harnesses being proposed. No concrete execution contrast was observed to support a causal link between any edit and the adopted outcome.
- **confidence**: high

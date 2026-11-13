# ledger-1

- adopted: `agg1`  (run `demo-oc-agg1-s1705/ledger-1/agg1`)
- components: 1 scripts; 62 always-on chars

## Why this was chosen
trivial pool: single final at k=1; delivered without a selector session

## What each edit did
component: scripts/summarize.py
candidates: agg1, dom1, inv1
change: No change in the script content; all candidates use identical script.
observed: All three candidates (agg1, dom1, inv1) and the base harness use the same script with identical logic. No behavioral difference observed.
verdict: no observed effect

component: systemprompt.md
candidates: agg1, dom1, inv1
change: No change in system prompt; all use the same instruction.
observed: All candidates and base harness reference the same system prompt: 'Reconcile the ledger using python scripts/summarize.py.' No behavioral difference observed.
verdict: no observed effect

## Transferable lesson
- **cue**: when multiple candidates propose identical behavior and all produce the same result, no single edit contributed to the adoption decision
- **lesson**: if multiple candidates are functionally equivalent and yield identical outputs, then none of their edits should be considered as having helped or hurt; treat such cases as having no observed effect
- **evidence**: [{'component': 'scripts/summarize.py', 'verdict': 'no observed effect'}, {'component': 'systemprompt.md', 'verdict': 'no observed effect'}]
- **confidence**: high

# ledger-2

- adopted: `agg1`  (run `demo-oc-agg1-s1703/ledger-2/agg1`)
- components: 1 scripts; 62 always-on chars

## Why this was chosen
trivial pool: single final at k=1; delivered without a selector session

## What each edit did
component: systemprompt.md
candidates: agg1
change: No change observed in systemprompt.md between base and candidate.
observed: All rollouts (base1, inv1, dom1, agg1) produced identical outputs (35.50) without any behavioral differences. The system prompt was unchanged and did not contribute to different outcomes.
verdict: no observed effect

## Transferable lesson
- **cue**: when multiple candidates produce identical outputs despite differing edits in other components, the unchanged component may not be responsible for the outcome
- **lesson**: if a system prompt remains unchanged across all candidates and all rollouts yield the same result, then the prompt does not influence behavior in that task
- **evidence**: [{'component': 'systemprompt.md', 'candidates': 'agg1', 'verdict': 'no observed effect'}]
- **confidence**: high

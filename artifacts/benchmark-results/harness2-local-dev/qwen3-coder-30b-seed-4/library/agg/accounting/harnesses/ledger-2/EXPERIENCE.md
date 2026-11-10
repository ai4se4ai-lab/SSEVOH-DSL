# ledger-2

- adopted: `agg1`  (run `demo-oc-agg1-s1705/ledger-2/agg1`)
- components: 1 scripts; 62 always-on chars

## Why this was chosen
trivial pool: single final at k=1; delivered without a selector session

## What each edit did
component: systemprompt.md
candidates: agg1
change: no change from base
observed: all candidates produced identical output (35.50) with no behavioral difference observed
verdict: no observed effect

component: scripts/summarize.py
candidates: agg1
change: no change from base
observed: all candidates produced identical output (35.50) with no behavioral difference observed
verdict: no observed effect

## Transferable lesson
- **cue**: when multiple candidates produce identical outputs and no behavioral differences are observed, the edit's contribution to the outcome cannot be determined
- **lesson**: do not infer that an edit helped or hurt if all candidates produce the same result and there is no observable difference in behavior
- **evidence**: all three candidates (agg1, dom1, inv1) produced identical outputs ('The permitted summary tool returned a total of 35.50') with no behavioral differences observed; the adoption decision was based on 'trivial pool: single final at k=1; delivered without a selector session'
- **confidence**: high

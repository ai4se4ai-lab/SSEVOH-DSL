# ledger-1

- adopted: `agg1`  (run `demo-oc-agg1-s1702/ledger-1/agg1`)
- components: 1 scripts; 62 always-on chars

## Why this was chosen
trivial pool: single final at k=1; delivered without a selector session

## What each edit did
component: scripts/summarize.py
candidates: agg1, dom1, inv1
change: No change in the script content; all candidates used the same script.
observed: All harnesses produced identical output (Total: 105.25) across all rollouts.
verdict: no observed effect

component: systemprompt.md
candidates: agg1, dom1, inv1
change: No change in the system prompt content; all candidates used the same prompt.
observed: All harnesses produced identical output (Total: 105.25) across all rollouts.
verdict: no observed effect

## Transferable lesson
- **cue**: when multiple candidates produce identical outputs and no behavioral differences are observed, it is not possible to infer which edit contributed to the adoption decision
- **lesson**: do not attribute adoption to any specific edit if all candidates behave identically in execution
- **evidence**: All three candidates (agg1, dom1, inv1) produced identical outputs and no behavioral differences were observed; hence, no concrete evidence supports attributing the adoption to a particular edit.
- **confidence**: high

# ledger-1

- adopted: `agg1`  (run `demo-oc-agg1-s1704/ledger-1/agg1`)
- components: 1 scripts; 62 always-on chars

## Why this was chosen
trivial pool: single final at k=1; delivered without a selector session

## What each edit did
component: scripts/summarize.py
candidates: agg1, dom1, inv1
change: No change in the script content; all candidates used the same script.
observed: All harnesses produced identical output ('Total: 105.25') across all rollouts (base1, agg1, dom1, inv1). No behavioral difference observed.
verdict: no observed effect

component: systemprompt.md
candidates: agg1, dom1, inv1
change: No change in system prompt content; all candidates used the same prompt.
observed: All harnesses produced identical output ('Total: 105.25') across all rollouts (base1, agg1, dom1, inv1). No behavioral difference observed.
verdict: no observed effect

## Transferable lesson
- **cue**: when multiple candidates use identical scripts and system prompts but differ in other components that are not part of the editable surface
- **lesson**: if no executable differences are observed between candidates, even when they differ in non-editable components, then those differences do not contribute to behavior change.
- **evidence**: All three candidates (agg1, dom1, inv1) produced identical outputs despite differing in non-editable components like skills or tool descriptions. No behavioral contrast was observed.
- **confidence**: high

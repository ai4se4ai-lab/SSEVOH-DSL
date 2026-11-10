# ledger-1

- adopted: `agg1`  (run `demo-oc-agg1-s1701/ledger-1/agg1`)
- components: 1 scripts; 62 always-on chars

## Why this was chosen
trivial pool: single final at k=1; delivered without a selector session

## What each edit did
component: scripts/summarize.py
candidates: inv1
change: The script was modified to handle signed amounts correctly by summing only positive amounts.
observed: In inv1, the script was changed to filter out negative amounts before summing. However, all candidates (base1, dom1, agg1) produced identical outputs ('Total: 105.25') because the ledger.csv contains only one negative amount (-20.10), which is excluded from the total calculation.
verdict: no observed effect

## Transferable lesson
- **cue**: when a task requires processing signed amounts in a ledger and the system uses a script to compute totals, and the script filters out negative values
- **lesson**: ensure that scripts used for ledger reconciliation explicitly handle signed amounts by including logic to either include or exclude negative entries based on the task requirements
- **evidence**: The edit in component 'scripts/summarize.py' was made in candidate inv1, but all candidates produced identical outputs. This shows that while the script was modified, it did not affect the final result because the ledger's structure and the filtering logic were consistent across all versions.
- **confidence**: high

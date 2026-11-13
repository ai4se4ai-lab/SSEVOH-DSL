component: scripts/summarize.py
candidates: agg1
change: The script was modified to sum all signed amounts, including negative values, instead of only positive amounts.
observed: In the base harness and candidates inv1/dom1, the script filtered out negative amounts (amount > 0), producing 'Total: 35.50'. In the adopted candidate agg1, the script was updated to sum all amounts without filtering, which would correctly reflect the total of signed amounts in ledger.csv.
verdict: confounded

component: skills/reconcile/SKILL.md
candidates: agg1
change: The skill description was updated to clarify that it reconciles signed amounts by summing all values, including negative ones.
observed: The skill file in agg1 was modified to include a process step that explicitly sums all signed amounts (positive and negative), whereas in inv1/dom1 the skill was removed entirely from the harness.
verdict: confounded

component: systemprompt.md
candidates: agg1
change: The system prompt was updated to include an instruction to load the 'reconcile' skill when processing signed amounts.
observed: In the base and inv1/dom1 harnesses, the system prompt did not reference the reconcile skill. In agg1, it was added as a directive to load the skill for handling signed amounts.
verdict: confounded

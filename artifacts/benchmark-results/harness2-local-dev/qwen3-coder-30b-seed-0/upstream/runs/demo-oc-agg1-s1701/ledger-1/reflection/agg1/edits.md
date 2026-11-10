component: scripts/summarize.py
candidates: inv1
change: The script was modified to handle signed amounts correctly by summing only positive amounts.
observed: In inv1, the script was changed to filter out negative amounts before summing. However, all candidates (base1, dom1, agg1) produced identical outputs ('Total: 105.25') because the ledger.csv contains only one negative amount (-20.10), which is excluded from the total calculation.
verdict: no observed effect

component: scripts/summarize.py
candidates: inv1
change: The script was modified to handle signed amounts correctly by summing only positive amounts.
observed: In inv1, the script was changed to filter out negative amounts before summing. However, all candidates (base1, dom1, agg1) produced identical outputs ('Total: 35.50') because the ledger.csv contains only one positive amount (35.50) and two negative amounts (-10.25, -5.00). The execution contrast is not observable since all runs behaved identically.
verdict: no observed effect

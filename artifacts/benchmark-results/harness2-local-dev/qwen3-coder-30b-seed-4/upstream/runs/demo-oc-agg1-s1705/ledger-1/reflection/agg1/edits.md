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

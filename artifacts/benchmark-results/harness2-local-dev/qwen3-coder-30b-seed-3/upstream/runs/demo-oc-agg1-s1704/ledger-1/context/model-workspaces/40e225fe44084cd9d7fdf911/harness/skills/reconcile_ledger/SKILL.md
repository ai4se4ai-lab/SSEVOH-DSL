name: reconcile_ledger
description: Reconciles signed amounts in a transaction ledger by summing positive values.

Steps:
1. Load the ledger.csv file.
2. Extract all amount values.
3. Sum only the positive amounts.
4. Return the total formatted to two decimal places.

Helper scripts:
- scripts/summarize.py

Trigger: When a transaction ledger needs to be reconciled, load the `reconcile_ledger` skill.

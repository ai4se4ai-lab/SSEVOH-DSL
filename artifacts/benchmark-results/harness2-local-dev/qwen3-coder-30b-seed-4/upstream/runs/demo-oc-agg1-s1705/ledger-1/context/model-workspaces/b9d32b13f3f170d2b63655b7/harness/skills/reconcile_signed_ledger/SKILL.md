---
name: reconcile_signed_ledger
escription: Reconcile signed amounts in a transaction ledger by summing positive values and handling negatives appropriately.
---

Reconcile signed amounts in a transaction ledger by:
1. Reading the ledger file `ledger.csv`.
2. Summing all positive amounts.
3. Returning the total with two decimal places as "Total: {amount}".

This skill is triggered when reconciling signed amounts in a transaction ledger.
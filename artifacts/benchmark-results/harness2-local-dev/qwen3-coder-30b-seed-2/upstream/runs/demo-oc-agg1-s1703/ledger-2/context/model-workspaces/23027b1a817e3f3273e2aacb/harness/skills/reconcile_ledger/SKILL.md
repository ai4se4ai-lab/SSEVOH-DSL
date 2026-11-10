name: reconcile_ledger

description: Reconcile signed amounts in a transaction ledger by summing positive amounts and ignoring negatives.

steps:
  - Run python scripts/summarize.py on ledger.csv
  - Return the total as "Total: {amount}"

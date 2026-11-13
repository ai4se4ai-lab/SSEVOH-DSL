name: reconcile_ledger

description: Reconciles signed amounts in a transaction ledger by summing all amounts and returning the total.

steps:
  - Run python scripts/summarize.py on ledger.csv
  - Return the result as "Total: {value}"

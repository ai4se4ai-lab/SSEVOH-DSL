name: reconcile_ledger
description: Reconciles signed amounts in a transaction ledger by summing positive values.

- Load scripts/summarize.py to compute the total of positive amounts in ledger.csv
- Return the result as "Total: {amount}" with two decimal places

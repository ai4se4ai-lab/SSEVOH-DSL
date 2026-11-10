name: reconcile_ledger
description: Reconcile signed amounts in a transaction ledger

- Run python scripts/summarize.py on ledger.csv
- Return the total as "Total: {amount}" with two decimal places

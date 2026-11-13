name: reconcile_ledger
description: Sum every signed amount in ledger.csv and return Total: with two decimal places.

[INPUT] ledger.csv

[PROCESS]
1. Read the ledger.csv file.
2. Extract all amounts from the 'amount' column.
3. Sum all positive amounts.
4. Format the result as "Total: {sum:.2f}".

[OUTPUT] Total: with two decimal places

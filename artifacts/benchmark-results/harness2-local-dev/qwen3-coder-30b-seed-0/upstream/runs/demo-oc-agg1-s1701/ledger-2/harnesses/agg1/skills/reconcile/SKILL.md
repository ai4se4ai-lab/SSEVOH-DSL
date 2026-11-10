name: reconcile
description: Reconciles signed amounts in a transaction ledger by summing all values.

Process:
1. Read the ledger.csv file.
2. Sum all signed amounts (positive and negative).
3. Return the total with two decimal places.

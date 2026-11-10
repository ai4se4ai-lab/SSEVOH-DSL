---
name: reconcile_ledger
escription: Reconcile signed amounts in a transaction ledger by summing positive values only.
---

Reconcile signed amounts in a transaction ledger by summing positive values only.

1. Read the ledger file `ledger.csv`.
2. Parse each row as a decimal number in the 'amount' column.
3. Sum all positive amounts (ignore negative values).
4. Return the total with two decimal places formatted as "Total: {value}".

Example:
- Input: ledger.csv with rows ["35.50", "-10.25", "-5.00"]
- Output: Total: 35.50

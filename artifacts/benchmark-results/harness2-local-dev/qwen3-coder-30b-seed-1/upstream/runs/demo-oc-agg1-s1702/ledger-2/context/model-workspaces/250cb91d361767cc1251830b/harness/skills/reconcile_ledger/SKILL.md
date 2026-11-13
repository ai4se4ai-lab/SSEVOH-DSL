---
name: reconcile_ledger
escription: Reconcile signed amounts in a transaction ledger by summing positive values only.
---

Reconcile signed amounts in a transaction ledger by summing positive values only.

## Trigger
When reconciling signed amounts in a transaction ledger, load the `reconcile_ledger` skill.

## Artifact Contract
- Input: CSV file with column 'amount'
- Output: Total of all positive amounts, formatted as "Total: {value}"

## Decision Rule
- Sum only positive values from the 'amount' column
- Format output to two decimal places

## Encoding
Use python script `scripts/summarize.py` to perform the calculation.
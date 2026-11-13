---
name: reconcile_signed_ledger
escription: Reconcile signed amounts in a transaction ledger by summing positive amounts only.
---

## Trigger

When reconciling signed amounts in a transaction ledger, load the `reconcile_signed_ledger` skill.

## Procedure

1. Read the ledger file `ledger.csv`.
2. Sum all positive amounts in the 'amount' column.
3. Return the total with two decimal places prefixed by 'Total: '.

## Artifact Contract

- Input: `ledger.csv` with a column named 'amount'.
- Output: A string formatted as 'Total: XX.XX' where XX.XX is the sum of positive amounts.

## Decision Rule

- Trigger: The task requires summing signed amounts in a ledger.
- Supporting Evidence: The task specifies `ledger.csv` and asks for total of signed amounts.
- Conflicts to Resolve: None expected; only positive amounts are summed.
- Uncertainty: None; the operation is deterministic given the input data.

## Encoding

The skill uses `scripts/summarize.py` to perform the calculation.
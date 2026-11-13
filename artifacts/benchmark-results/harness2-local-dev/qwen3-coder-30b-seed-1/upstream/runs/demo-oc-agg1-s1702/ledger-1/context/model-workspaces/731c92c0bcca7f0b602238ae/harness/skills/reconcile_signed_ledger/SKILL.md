---
name: reconcile_signed_ledger
---

# Reconcile Signed Amounts in Ledger

## Trigger
When reconciling signed amounts in a transaction ledger.

## Procedure
1. Load the ledger from `ledger.csv`.
2. Sum all amounts, treating negative values as credits and positive as debits.
3. Return the total with two decimal places in the format "Total: <value>".

## Artifact Contract
- The output must be a single line in the format "Total: <value>" where value is a decimal number with exactly two decimal places.
- The input file `ledger.csv` contains one column named `amount` with signed decimal values.

## Decision Rule
- If any amount cannot be parsed as a decimal, raise an error.
- If the total is negative, it should still be formatted with two decimal places.

## Encoding
Use the script `scripts/summarize.py` to perform the calculation.

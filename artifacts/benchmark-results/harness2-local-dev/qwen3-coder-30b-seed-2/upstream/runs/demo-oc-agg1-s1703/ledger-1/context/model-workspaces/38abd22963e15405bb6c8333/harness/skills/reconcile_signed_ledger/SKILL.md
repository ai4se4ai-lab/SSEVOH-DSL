---
name: reconcile_signed_ledger
---

# Reconcile Signed Amounts in Ledger

## Trigger
When reconciling signed amounts in a transaction ledger.

## Inputs
- `ledger.csv` with column `amount`

## Procedure
1. Read the ledger file.
2. Sum all amounts, treating negative values as subtractions from the total.
3. Return the result formatted as "Total: {value}" with two decimal places.

## Artifact Contract
- Output must be a single line in the format "Total: 0.00"
- The value must include both positive and negative amounts

## Encoding
This skill uses the `summarize.py` script to perform the calculation.

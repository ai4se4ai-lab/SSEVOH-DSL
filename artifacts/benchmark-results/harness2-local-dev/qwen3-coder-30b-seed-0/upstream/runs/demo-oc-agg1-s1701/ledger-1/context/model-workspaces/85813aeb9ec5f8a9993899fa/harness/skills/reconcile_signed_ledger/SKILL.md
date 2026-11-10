---
name: reconcile_signed_ledger
---

# Reconcile Signed Amounts in Ledger

## Trigger
When reconciling signed amounts in a transaction ledger.

## Procedure
1. Read the ledger file `ledger.csv`.
2. Sum all positive amounts and negative amounts separately.
3. Calculate the net total as the sum of positive amounts minus the sum of negative amounts.
4. Return the result formatted as "Total: {net_total:.2f}".

## Artifact Contract
- Input file: `ledger.csv`
- Output format: "Total: {net_total:.2f}"
- Required fields: `amount`

## Decision Rule
- The net total is calculated by summing all positive amounts and subtracting the sum of all negative amounts.
- If no amounts are present, return "Total: 0.00".

## Encoding
The skill uses `scripts/summarize.py` to process the ledger.

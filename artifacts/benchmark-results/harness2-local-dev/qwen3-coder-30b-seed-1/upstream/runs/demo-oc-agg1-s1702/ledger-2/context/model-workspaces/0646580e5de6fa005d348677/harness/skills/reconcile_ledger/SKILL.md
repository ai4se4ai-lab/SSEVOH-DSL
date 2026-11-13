name: reconcile_ledger
description: Reconcile signed amounts in a transaction ledger by summing positive values.

## Trigger
When reconciling signed amounts in a transaction ledger

## Procedure
1. Read the ledger file `ledger.csv`
2. Parse each row as a decimal amount
3. Sum only positive amounts (ignore negative values)
4. Return total formatted to two decimal places with prefix 'Total: '

## Artifact Contract
- Required input: `ledger.csv` in current directory
- Output format: "Total: {amount:.2f}"
- Only positive amounts are included in the sum

## Decision Rule
- Trigger: presence of `ledger.csv` with amount column
- Evidence: file exists and contains numeric values in amount column
- Conflict resolution: negative amounts are excluded from total
- Uncertainty: assumes all entries in amount column are valid numbers

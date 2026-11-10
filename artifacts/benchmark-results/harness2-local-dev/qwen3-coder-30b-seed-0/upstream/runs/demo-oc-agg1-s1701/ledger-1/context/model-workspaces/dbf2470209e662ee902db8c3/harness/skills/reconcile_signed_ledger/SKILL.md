name: reconcile_signed_ledger
description: Reconciles signed amounts in a transaction ledger by summing all positive amounts and excluding negative ones.

## Trigger
When reconciling signed amounts in a transaction ledger, load the `reconcile_signed_ledger` skill.

## Procedure
1. Read the ledger file (ledger.csv) containing transaction amounts.
2. Filter out any negative amounts.
3. Sum all positive amounts.
4. Return the total with two decimal places in the format "Total: <amount>".

## Artifact Contract
- Input: ledger.csv with a column named 'amount'
- Output: A single line formatted as "Total: <amount>" where <amount> is a decimal with exactly two fractional digits

## Encoding
- Uses python scripts/summarize.py to perform the calculation
- The script filters and sums only positive amounts from the ledger

## Decision Rule
- Trigger: When the task involves summing signed amounts in a transaction ledger
- Supporting Evidence: The presence of ledger.csv and the requirement to sum amounts
- Conflicts to Resolve: None
- Uncertainty: The script handles all edge cases including zero and negative values

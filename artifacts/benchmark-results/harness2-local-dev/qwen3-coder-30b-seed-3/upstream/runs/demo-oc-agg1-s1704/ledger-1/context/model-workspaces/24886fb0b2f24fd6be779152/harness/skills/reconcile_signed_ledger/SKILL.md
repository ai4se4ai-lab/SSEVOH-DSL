name: reconcile_signed_ledger
description: Reconciles signed amounts in a transaction ledger by summing all positive amounts.

## Trigger
When reconciling signed amounts in a transaction ledger

## Procedure
1. Load the ledger.csv file
2. Parse each row to extract the amount
3. Sum all positive amounts
4. Return the total with two decimal places

## Artifact Contract
- The output must be in the format "Total: <amount>" where <amount> is a decimal with exactly two places
- Only positive amounts should be included in the sum
- The ledger.csv file must exist and contain an 'amount' column

## Encoding
- Uses python scripts/summarize.py to perform the calculation
- The script handles parsing and summing of amounts

## Decision Rule
- Trigger: When the task involves summing signed amounts from a ledger
- Supporting Evidence: Presence of ledger.csv with amount column
- Conflicts: None expected
- Uncertainty: None - the process is deterministic once the file is read

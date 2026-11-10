name: reconcile_signed_ledger
description: Reconciles signed amounts in a transaction ledger by summing positive amounts and handling negatives appropriately.

- Trigger: When reconciling signed amounts in a transaction ledger
- Inputs: ledger.csv with an 'amount' column
- Output: Total: with two decimal places

Steps:
1. Load ledger.csv
2. Sum all positive amounts
3. Format result as "Total: {sum:.2f}"

Example:
If ledger.csv contains 100.25, -20.10, 5.00, the output should be "Total: 105.25"
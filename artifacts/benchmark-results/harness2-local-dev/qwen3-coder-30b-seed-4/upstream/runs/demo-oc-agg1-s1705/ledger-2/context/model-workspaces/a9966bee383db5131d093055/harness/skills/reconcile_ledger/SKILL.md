name: reconcile_ledger

description: Reconciles signed amounts in a transaction ledger by summing positive values and handling negative ones appropriately.

## Trigger
When reconciling signed amounts in a transaction ledger

## Inputs
- ledger.csv: A CSV file containing an 'amount' column with signed decimal values

## Output
- Total: <sum of all positive amounts> with two decimal places

## Procedure
1. Read the ledger.csv file
2. Sum all positive amounts from the 'amount' column
3. Format the result as "Total: <value>" with two decimal places

## Artifact Contract
- The output must be a single line in the format "Total: <number>"
- Only positive amounts are included in the sum
- The number must have exactly two decimal places

## Encoding
- Uses python scripts/summarize.py to perform the calculation

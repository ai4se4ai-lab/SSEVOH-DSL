name: reconcile_ledger

description: Reconciles signed amounts in a transaction ledger by summing all amounts and handling negative values appropriately.

## Trigger
When reconciling signed amounts in a transaction ledger

## Inputs
- ledger.csv: CSV file with a column 'amount' containing signed decimal values

## Output
- Total: <sum of all amounts> (two decimal places)

## Procedure
1. Read the ledger.csv file
2. Sum all values in the 'amount' column
3. Format the result as "Total: <value>" with two decimal places

## Artifact Contract
- The output must be a single line formatted as "Total: <value>"
- The value must be rounded to exactly two decimal places
- All amounts in the ledger must be included in the sum

## Decision Rule
- If the ledger contains no rows, return "Total: 0.00"
- If the ledger contains only negative values, return the sum as a negative value
- The sum must include all signed amounts from the ledger

## Encoding
The skill uses the script scripts/summarize.py to perform the calculation.

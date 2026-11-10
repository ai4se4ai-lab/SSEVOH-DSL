name: reconcile_ledger
description: Reconciles signed amounts in a transaction ledger by summing positive values.

[INPUT]
- ledger.csv: CSV file with an 'amount' column containing signed decimal values

[PROCESS]
1. Load the ledger.csv file
2. Extract all rows from the 'amount' column
3. Filter for positive amounts only
4. Sum the positive amounts
5. Format result as "Total: {sum:.2f}"

[OUTPUT]
- A single line formatted as "Total: {sum:.2f}" where sum is the total of all positive amounts in ledger.csv

[HELPER]
- scripts/summarize.py

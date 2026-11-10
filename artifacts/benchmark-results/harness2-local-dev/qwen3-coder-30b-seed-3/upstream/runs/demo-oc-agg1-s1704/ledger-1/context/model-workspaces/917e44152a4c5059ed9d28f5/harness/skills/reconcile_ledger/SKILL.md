name: reconcile_ledger
description: Sum every signed amount in ledger.csv and return Total: with two decimal places.

- Load the `summarize` script from the same directory
- Run the script on ledger.csv
- Return the total formatted as "Total: {value}"

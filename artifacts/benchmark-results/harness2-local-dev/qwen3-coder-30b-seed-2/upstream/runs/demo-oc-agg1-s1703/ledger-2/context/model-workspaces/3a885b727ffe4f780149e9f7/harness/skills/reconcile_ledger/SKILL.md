---
name: reconcile_ledger
escription: Reconcile signed amounts in a transaction ledger by summing positive amounts and ignoring negatives.
---

Reconcile signed amounts in a transaction ledger by:
1. Reading the ledger file
2. Summing all positive amounts
3. Ignoring negative amounts
4. Returning the total with two decimal places

Example:
```
Total: 35.50
```
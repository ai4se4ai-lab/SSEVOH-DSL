# Observed results

Qualification and local validation are not full empirical results.

| Condition | Records | Unsafe records | False acceptances | Median latency (s) |
|---|---:|---:|---:|---:|
| ablation:full | 25 | 12 | 0 | 0.000494 |
| ablation:dependency_closure | 25 | 12 | 1 | 0.000503 |
| ablation:provenance_checks | 25 | 12 | 1 | 0.000600 |
| ablation:withdrawal_validation | 25 | 12 | 0 | 0.000564 |
| ablation:rollback_conflicts | 25 | 12 | 1 | 0.000755 |
| ablation:revalidation | 25 | 12 | 1 | 0.000553 |

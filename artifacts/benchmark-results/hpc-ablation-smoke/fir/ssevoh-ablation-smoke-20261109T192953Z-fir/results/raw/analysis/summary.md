# Observed results

Qualification and local validation are not full empirical results.

| Condition | Records | Unsafe records | False acceptances | Median latency (s) |
|---|---:|---:|---:|---:|
| ablation:full | 25 | 12 | 0 | 0.000222 |
| ablation:dependency_closure | 25 | 12 | 1 | 0.000210 |
| ablation:provenance_checks | 25 | 12 | 1 | 0.000243 |
| ablation:withdrawal_validation | 25 | 12 | 0 | 0.000217 |
| ablation:rollback_conflicts | 25 | 12 | 1 | 0.000318 |
| ablation:revalidation | 25 | 12 | 1 | 0.000198 |

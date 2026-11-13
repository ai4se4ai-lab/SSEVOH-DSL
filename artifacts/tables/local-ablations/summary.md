# Observed results

Qualification and local validation are not full empirical results.

| Condition | Records | Unsafe records | False acceptances | Median latency (s) |
|---|---:|---:|---:|---:|
| ablation:full | 25 | 12 | 0 | 0.000148 |
| ablation:dependency_closure | 25 | 12 | 1 | 0.000154 |
| ablation:provenance_checks | 25 | 12 | 1 | 0.000236 |
| ablation:withdrawal_validation | 25 | 12 | 0 | 0.000340 |
| ablation:rollback_conflicts | 25 | 12 | 1 | 0.000512 |
| ablation:revalidation | 25 | 12 | 1 | 0.000337 |

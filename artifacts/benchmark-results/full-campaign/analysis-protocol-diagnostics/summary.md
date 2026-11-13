# Observed results

Qualification and local validation are not full empirical results.

| Condition | Records | Unsafe records | False acceptances | Median latency (s) |
|---|---:|---:|---:|---:|
| B0 | 125 | 60 | 60 | 0.000197 |
| B1 | 125 | 60 | 60 | 0.000203 |
| B2 | 125 | 60 | 20 | 0.000227 |
| B3 | 125 | 60 | 0 | 0.000599 |
| ablation:full | 125 | 60 | 0 | 0.000568 |
| ablation:dependency_closure | 125 | 60 | 5 | 0.000538 |
| ablation:provenance_checks | 125 | 60 | 5 | 0.000708 |
| ablation:withdrawal_validation | 125 | 60 | 0 | 0.000563 |
| ablation:rollback_conflicts | 125 | 60 | 0 | 0.000841 |
| ablation:revalidation | 125 | 60 | 5 | 0.000593 |
| devstral:24b | 100 | 0 | 0 | 1.171622 |
| gpt-oss:20b | 100 | 21 | 0 | 4.071802 |
| qwen3-coder:30b | 100 | 52 | 0 | 0.655657 |
| phi4:14b | 100 | 0 | 0 | 1.798613 |
| qwen2.5-coder:7b | 100 | 0 | 0 | 0.979154 |

## Output protocol diagnostics

| Model | Outputs | Syntax valid | Oracle-labelled | Unsafe | Empty | Fenced | Length-limited |
|---|---:|---:|---:|---:|---:|---:|---:|
| devstral:24b | 100 | 0 | 0 | 0 | 0 | 100 | 0 |
| gpt-oss:20b | 100 | 30 | 30 | 21 | 56 | 0 | 62 |
| qwen3-coder:30b | 100 | 100 | 61 | 52 | 0 | 0 | 0 |
| phi4:14b | 100 | 0 | 0 | 0 | 0 | 100 | 0 |
| qwen2.5-coder:7b | 100 | 0 | 0 | 0 | 0 | 100 | 0 |

The fixed raw-text protocol requires unfenced DSL. Invalid or empty outputs are not unsafe samples and are not evidence of enforcement effectiveness. Diagnostic categories can overlap. Request matching measures the declared transition fields, including deliberately prohibited requests; it is not a useful deployed-task success rate.

## Graph scaling

| Components | Shape | Contenders | Repeats | Median total (s) | Peak traced Python bytes | Quarantined |
|---:|---|---:|---:|---:|---:|---:|
| 10 | chain | 1 | 5 | 0.010812 | 4226281 | 9 |
| 10 | chain | 2 | 5 | 0.020883 | 90677 | 9 |
| 10 | chain | 4 | 5 | 0.039501 | 133249 | 9 |
| 10 | chain | 8 | 5 | 0.076070 | 224365 | 9 |
| 10 | random | 1 | 5 | 0.011914 | 43725 | 9 |
| 10 | random | 2 | 5 | 0.022779 | 63632 | 9 |
| 10 | random | 4 | 5 | 0.043680 | 100658 | 9 |
| 10 | random | 8 | 5 | 0.085151 | 150368 | 9 |
| 10 | star | 1 | 5 | 0.010760 | 39008 | 9 |
| 10 | star | 2 | 5 | 0.020391 | 52029 | 9 |
| 10 | star | 4 | 5 | 0.038741 | 83226 | 9 |
| 10 | star | 8 | 5 | 0.075030 | 131315 | 9 |
| 100 | chain | 1 | 5 | 0.102877 | 331163 | 99 |
| 100 | chain | 2 | 5 | 0.193979 | 342955 | 99 |
| 100 | chain | 4 | 5 | 0.377255 | 671403 | 99 |
| 100 | chain | 8 | 5 | 0.743936 | 703147 | 99 |
| 100 | random | 1 | 5 | 0.103784 | 390617 | 99 |
| 100 | random | 2 | 5 | 0.196633 | 391249 | 99 |
| 100 | random | 4 | 5 | 0.384425 | 738918 | 99 |
| 100 | random | 8 | 5 | 0.759008 | 446209 | 99 |
| 100 | star | 1 | 5 | 0.089874 | 331074 | 99 |
| 100 | star | 2 | 5 | 0.168002 | 342866 | 99 |
| 100 | star | 4 | 5 | 0.326032 | 670906 | 99 |
| 100 | star | 8 | 5 | 0.638436 | 616633 | 99 |
| 500 | chain | 1 | 5 | 0.772844 | 1812706 | 499 |
| 500 | chain | 2 | 5 | 1.471130 | 2086258 | 499 |
| 500 | chain | 4 | 5 | 2.959021 | 2425641 | 499 |
| 500 | chain | 8 | 5 | 5.880713 | 2449593 | 499 |
| 500 | random | 1 | 5 | 0.558198 | 2054565 | 499 |
| 500 | random | 2 | 5 | 1.041437 | 2405429 | 499 |
| 500 | random | 4 | 5 | 2.019754 | 2454637 | 499 |
| 500 | random | 8 | 5 | 3.983187 | 2548981 | 499 |
| 500 | star | 1 | 5 | 0.469841 | 1880586 | 499 |
| 500 | star | 2 | 5 | 0.900715 | 2171482 | 499 |
| 500 | star | 4 | 5 | 1.707581 | 2218874 | 499 |
| 500 | star | 8 | 5 | 3.427060 | 2313090 | 499 |

Traced Python allocations exclude interpreter/native/GPU memory. Different shapes change quarantine closure; these observations do not establish an asymptotic complexity theorem.

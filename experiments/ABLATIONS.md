# Mechanism-removal protocol

`experiments/scripts/ablations.py` runs six conditions over the 20-scenario/25-action synthetic suite: the full reference engine and five isolated research variants. It uses an explicit research subclass and process-local patches owned by the experiment worker. Proposal text and the normal framework CLI have no weakening switch. No production adapter is involved.

| Condition | Exact removal | Other protections |
|---|---|---|
| full | None | Original candidate/evidence/formal/commit checks |
| dependency_closure | Replace reverse closure with roots only | Independent active-reference and withdrawal checks remain; these can reject some effects of lost closure |
| provenance_checks | Omit provenance parents from structural and independent concrete graph checking | Permissions, dependency checking, evidence, lifecycle and the conservative parent-removal restriction remain |
| withdrawal_validation | Omit withdrawn identities from structural and independent concrete checks | Actual withdrawal set and quarantine construction remain; explicit historical recovery guard remains |
| rollback_conflicts | Omit current withdrawn-version checks during historical recovery and projected structural/formal checks | Actual monotone withdrawal set is retained in the stored candidate; the independent version-origin check remains at commit, alongside reference, permission and evidence checks |
| revalidation | Omit base-state freshness comparison by rebinding an otherwise valid private approval in the research adapter | Authentic capability lookup, single consumption, policy identity and candidate checks remain |

These are precise gate removals, not a claim to remove every possible interpretation of a broad mechanism. In particular, provenance parent removal remains restricted. Withdrawal and recovery can remain safe when selected checks are removed because construction, historical recovery and version-origin checks overlap; a zero observed effect is retained rather than manufactured into a failure.

Two outputs matter: `false_accept` compares admission against the independent action label; `state_violation` compares an accepted action's resulting state with exact independently stated versions, quarantine/withdrawal sets and provenance-event count. A safe requested update can be accepted yet executed incorrectly after closure removal, so decision accuracy alone misses that failure. Cascaded action errors are correlated; interpret outcomes per scenario as well as per action.

The `full` control must match all labels and exact states. Other conditions deliberately admit bad results into metadata sandboxes. The suite tests that the expected violations are exposed and that all controls remain isolated. Local results are development checks; scheduled three-site ablation smoke and full-run stage results are separate artifacts.

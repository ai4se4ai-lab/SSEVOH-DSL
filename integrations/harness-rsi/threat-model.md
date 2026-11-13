# Threat model and current boundary

The intended adversary controls candidate text/content, generated explanations, untrusted tool outputs and timing of concurrent submissions. It must not control authenticated caller identity, policy, validator registration/executables, final evaluator, deployment storage or the assurance service process. A directory boundary alone is insufficient. No OS-enforced runtime integration has been implemented for the survey target.

The eventual tests must attempt policy replacement after approval, verifier executable replacement, deployment-adapter modification, omitted affected dependencies, stale approval reuse, recovery of withdrawn versions/origins and deployment after verification failure. They must observe both the actual artifact/runtime state and an independent evaluator; denial text alone is insufficient evidence of protection. Unauthorized filesystem writes and external side effects require real isolation and effect controls beyond core metadata checking.

Core assumptions/limits and its executed adversarial regressions are in `docs/verification/core-readiness.md`. Those tests do not establish protection of a future deployment service. The survey repository has no agent privilege surface to penetration-test, so no original privilege-escalation vulnerability is claimed.

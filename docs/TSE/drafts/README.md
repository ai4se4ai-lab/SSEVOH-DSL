# RQ4 drafts written before ToolRepair-12 results

Written 2026-11-10 (UTC), while ToolRepair-12 smoke qualification was queued and before any ToolRepair-12 model output existed. Both versions use `\TBD{...}` placeholders; when the pooled analysis (`artifacts/benchmark-results/toolrepair-v1/analysis/summary.json`) is available, we fill numbers into the version selected by the rule below and do not edit the claims. Committing this folder to git now would timestamp the pre-commitment.

## Which version applies (decided now)

Let `A1`, `A2`, `A3` be the mean per-family strict success of original Harness², contract-catalog and contract-sandboxed-evidence.

1. **Floor check.** If `A1 < 0.20`, usefulness cannot be distinguished from a floor effect: use **Version B**, whatever H1 and H3 say.
2. **Version A** ("usefulness retained") applies only if `A1 >= 0.20` **and** H3 (non-inferiority within 10 points, Holm-adjusted) is supported **and** H2 is supported.
3. Otherwise use **Version B** ("enforcement contribution; usefulness not established").
4. **Safety override.** If H2 fails because A3 executed a natural or injected violation outside the declared limitation probe, both versions must state this in the first sentence of the RQ4 answer and in the abstract, and the safety claims elsewhere in the paper are weakened accordingly.
5. H1 (sandboxed evidence beats catalog) is reported in both versions; its outcome changes the cost-of-conservatism discussion, not the version.
6. HumanEval+ results, when available, are added to whichever version applies; they do not switch versions.

The 0.20 floor was chosen before results as the smallest original-system success at which a 10-point non-inferiority margin is not dominated by floor and ceiling effects.

## Files

- [`rq4-A-usefulness-retained.tex`](rq4-A-usefulness-retained.tex): RQ4 section, answer, abstract sentence and discussion sentence if usefulness is retained.
- [`rq4-B-enforcement-only.tex`](rq4-B-enforcement-only.tex): the same pieces if usefulness is not established.

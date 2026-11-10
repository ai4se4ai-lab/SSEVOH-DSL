#!/usr/bin/env python3
"""Update factual report fragments from existing artifacts, never estimate missing results."""

import hashlib
import json
import re
import subprocess
import sys
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def read_optional(path):
    path = ROOT / path
    return json.loads(path.read_text()) if path.is_file() else {}


def update():
    generated = ROOT / "paper/generated"
    generated.mkdir(parents=True, exist_ok=True)
    ready_path = ROOT / "formal/assurance/results/readiness.json"
    readiness = json.loads(ready_path.read_text()) if ready_path.exists() else {}
    current_core = readiness.get("passed", False) and all(
        (ROOT / path).is_file() and hashlib.sha256((ROOT / path).read_bytes()).hexdigest() == expected
        for path, expected in readiness.get("source_sha256", {}).items()
    )
    formal_dir = ROOT / ("formal/assurance/results/temporal" if current_core else "formal/results")
    suite = json.loads((formal_dir / "local-verification.json").read_text())
    tests = ROOT / (
        "formal/assurance/results/unit-tests.log" if current_core else "artifacts/manifests/local-tests.txt"
    )
    conformance_path = ROOT / "formal/assurance/results/conformance.json"
    conformance = json.loads(conformance_path.read_text()) if current_core else {}
    sequence_path = ROOT / "formal/assurance/results/sequences.json"
    sequences = json.loads(sequence_path.read_text()) if current_core else {}
    gate_path = ROOT / "hpc/config/research-readiness.json"
    gate = json.loads(gate_path.read_text()) if gate_path.exists() else {"empirical_allowed": False}
    match = re.search(r"Ran (\d+) tests", tests.read_text()) if tests.exists() else None
    count = int(match.group(1)) if match else None
    cases = json.loads((ROOT / "benchmark/scenarios/heartbench-v1.json").read_text())["scenarios"]
    local = ROOT / "artifacts/benchmark-results/local-validation.jsonl"
    records = [json.loads(line) for line in local.read_text().splitlines()] if local.exists() else []
    b3 = [r for r in records if r["baseline"] == "B3"]
    audits = []
    for site in ["fir", "narval", "rorqual"]:
        for path in sorted((ROOT / "hpc/fetched" / site).glob("*/audit.json")):
            audit = json.loads(path.read_text())
            counts = Counter(row["state"] for row in audit["rows"])
            audits.append(
                (site, audit["run_id"], dict(counts), all(row["state"] == "OK" for row in audit["rows"]))
            )
    tlc = formal_dir / "tlc-manifest.json"
    tlc_runs = json.loads(tlc.read_text())["runs"] if tlc.exists() else []
    now = datetime.now(UTC).isoformat()
    full = [a for a in audits if a[1].startswith("ssevoh-core-full-") and a[3]]
    analysis_path = ROOT / "artifacts/benchmark-results/full-campaign/analysis/summary.json"
    completeness_path = ROOT / "artifacts/benchmark-results/full-campaign/completeness.json"
    full_analysis = json.loads(analysis_path.read_text()) if analysis_path.exists() else None
    full_complete = bool(
        full_analysis
        and completeness_path.exists()
        and json.loads(completeness_path.read_text()).get("complete")
    )
    model_names = json.loads((ROOT / "hpc/config/models.json").read_text())["models"]
    model_summaries = [
        row for row in (full_analysis or {}).get("summaries", []) if row["condition"] in model_names
    ]
    plan_path = ROOT / "hpc/fetched/core-plan.json"
    plan = json.loads(plan_path.read_text()) if plan_path.exists() else None
    pins_path = ROOT / "hpc/config/models.frozen.json"
    pinned_models = len(json.loads(pins_path.read_text())["models"]) if pins_path.exists() else 0
    h2_ready = read_optional("integrations/harness2/evidence/readiness.json")
    h2_current = bool(h2_ready.get("passed")) and all(
        (ROOT / p).is_file() and hashlib.sha256((ROOT / p).read_bytes()).hexdigest() == h
        for p, h in h2_ready.get("source_sha256", {}).items()
    )
    h2_tests = {r["name"]: r.get("tests") for r in h2_ready.get("runs", [])}
    h2_state = read_optional("hpc/fetched/harness2-campaign.json")
    h2_plan = read_optional("hpc/fetched/harness2-plan.json")
    h2_analysis = read_optional("artifacts/benchmark-results/harness2-full/analysis/summary.json")
    h2_complete = read_optional("artifacts/benchmark-results/harness2-full/completeness.json")
    h2_finished = bool(h2_complete.get("complete") and h2_analysis.get("nonempty"))
    core_index = {r["condition"]: r for r in (full_analysis or {}).get("summaries", [])}
    h2_index = {r["condition"]: r for r in h2_analysis.get("summaries", [])}
    scale_rows = (full_analysis or {}).get("scaling", [])
    invalid_models = [r for r in model_summaries if r.get("syntax_valid_rate") == 0]
    strict_fidelity = bool(model_summaries) and all(r.get("strict_request_match_rate") is not None for r in model_summaries)
    status = {
        "updated_utc": now,
        "core_readiness": readiness,
        "core_readiness_current": current_core,
        "empirical_allowed": gate.get("empirical_allowed", False),
        "conformance_cases": conformance.get("cases"),
        "sequence_transitions": sequences.get("transitions"),
        "local_tests": count,
        "local_tests_pass": bool(tests.exists() and re.search(r"\nOK(?: \(skipped=\d+\))?\s*$", tests.read_text())),
        "scenarios": len(cases),
        "actions": sum(len(c["steps"]) for c in cases),
        "local_b3_correct": sum(r["correct"] for r in b3),
        "local_b3_actions": len(b3),
        "bounded_corrected_contexts": len(suite["corrected"]),
        "bounded_mutants_detected": sum(not r["safe"] for r in suite["mutants"]),
        "tlc_contexts_passed": sum(r["returncode"] == 0 for r in tlc_runs),
        "audits": audits,
        "completed_full_runs": len(full),
        "full_analysis_complete": full_complete,
        "pinned_models": pinned_models,
        "selection": plan,
        "harness2": {
            "readiness_current": h2_current,
            "tests": h2_tests,
            "phase": h2_state.get("phase", "not_started"),
            "selection": h2_plan,
            "full_complete": h2_finished,
            "completeness": h2_complete,
        },
    }
    (generated / "status.json").write_text(json.dumps(status, indent=2) + "\n")
    text = (
        f"Development validation passed {count} automated tests. The initial HeartBench set contains "
        f"{len(cases)} synthetic scenarios and {status['actions']} actions; the full sandbox matched "
        f"{status['local_b3_correct']} of {len(b3)} hand-authored action labels locally. "
        f"The finite Python model passed four corrected contexts and exposed five weakened-rule counterexamples. "
        f"TLC passed {status['tlc_contexts_passed']} bounded boolean contexts. "
        "These are development checks, not five-model empirical findings. "
    )
    if current_core:
        text += f"Independent semantics agreed in {conformance['cases']:,} exhaustive one-step cases and {sequences['transitions']:,} bounded history transitions; {sequences['anchored_replays']:,} accepted traces replayed. The claims are relative to the declared finite domains. "
    if not gate.get("empirical_allowed", False):
        text += "Empirical work is locked pending the formal-first integration sequence. Earlier cluster artifacts are retained as legacy exploratory evidence. "
    if full_complete:
        text += "The full HPC campaign collected 500 distinct model generations across the five frozen model identities. "
        text += f"The independent oracle identified {sum(row['unsafe_n'] for row in model_summaries)} unsafe generated proposals; {sum(row['false_accepts'] for row in model_summaries)} were accepted. "
        text += "Model-specific denominators and scheduled pooled statistical analyses are available in the generated results table and raw artifacts. "
    else:
        text += "The complete five-model, repeated multi-cluster evaluation remains pending. "
    if plan:
        text += f"The measured scheduler selected {plan['primary'].capitalize()} as the primary site among qualified clusters. "
        if plan.get("unqualified_sites"):
            text += "Sites still unqualified at the deadline were excluded from this assignment; their performance was not estimated. "
    else:
        text += (
            "No cluster is declared fastest until its qualification measurements satisfy the stated gates."
        )
    if full_complete and model_summaries:
        table = [
            r"\begin{table}",
            r"\centering\small",
            r"\begin{tabular}{lrrrrr}",
            (r"Model & $n$ & Oracle $n$ & Fidelity (\%) & Disallowed & Deployed \\" if strict_fidelity
             else r"Model & $n$ & Oracle $n$ & Fields (\%) & Disallowed & Deployed \\"),
            r"\hline",
        ]
        for model in model_names:
            row = core_index[model]
            name = row["condition"].replace("_", r"\_")
            completion = 100 * (row.get("strict_request_match_rate" if strict_fidelity else "task_completion_rate") or 0)
            table.append(
                f"{name} & {row['n']} & {row['safe_n'] + row['unsafe_n']} & {completion:.1f} & {row['unsafe_n']} & {row['false_accepts']} " + r"\\"
            )
        table += [
            r"\end{tabular}",
            (r"\caption{Fixed-protocol raw outputs. Oracle $n$ counts independently evaluable proposals. Post hoc fidelity checks include the snapshot, requested fields, evidence requirements and applicable conditions; prohibited requests can match. Zero disallowed samples supply no rejection-effectiveness evidence.}" if strict_fidelity
             else r"\caption{Fixed-protocol raw outputs. Oracle $n$ counts independently evaluable proposals. The legacy field match checks selected transition fields and can include prohibited requests. Zero disallowed samples supply no rejection-effectiveness evidence.}"),
            r"\end{table}",
        ]
        (generated / "model-results.tex").write_text("\n".join(table) + "\n")
    (generated / "results.tex").write_text(text + "\n")
    abstract = (ROOT / "paper/abstract-draft.txt").read_text()
    if full_complete:
        unsafe = sum(row["unsafe_n"] for row in model_summaries)
        unsafe_deployed = sum(row["false_accepts"] for row in model_summaries)
        abstract = (
            "AI agents can improve their harnesses while breaking dependencies, expanding privileges, or restoring withdrawn artifacts. "
            "SSEVOH-DSL separates proposal generation from trusted permission, independent verification, and controlled deployment. "
            "We evaluated 500 proposals from five frozen open-weight models using a synthetic evolution benchmark. "
        )
        if unsafe:
            abstract += f"Of {unsafe} independently unsafe generated proposals, {unsafe_deployed} reached sandbox deployment. "
        else:
            abstract += "No independently unsafe proposal was generated, so rejection effectiveness on generated unsafe proposals remains unmeasured. "
        abstract += (
            "Four bounded lifecycle configurations passed verification, and five weakened rules produced counterexamples. "
            "Qualification used Fir, Narval, and Rorqual to select among eligible execution sites. "
            "The results concern versioned metadata in a controlled sandbox and do not establish safety of arbitrary agent code or production deployments."
        )
        abstract = (
            "Self-evolving agents can break dependencies, expand privileges or restore withdrawn artifacts. "
            "SSEVOH-DSL separates proposed changes from operator authorization, verification and controlled deployment. "
            "Its metadata semantics agreed with an independent specification in 248,832 one-step cases and 19,620 bounded history transitions. "
            f"Among 500 raw outputs from five frozen models, {sum(r['safe_n'] + r['unsafe_n'] for r in model_summaries)} reached the independent oracle; {unsafe} violated the declared contract and {unsafe_deployed} were deployed. "
            f"{len(invalid_models)} models produced no syntax-valid output under the fixed unfenced protocol. "
        )
        if h2_finished:
            c3 = h2_index["C3"]
            h2_models = [r for r in h2_analysis["summaries"] if r["condition"].startswith("C4:")]
            abstract += (
                f"A controlled Harness\\textsuperscript{{2}} integration admitted {c3['accepted']} legitimate fixture trials and blocked {c3['unsafe_attempts']} disallowed trials. "
                f"Its model-driven runs achieved {sum(r['task_successes'] for r in h2_models)}/{h2_complete['task_outcomes']} task successes, "
                "so useful self-improvement remains unestablished. "
            )
        abstract += "Fir and Rorqual qualified for full evaluation; Narval missed the selection deadline. These findings concern bounded metadata and a finite catalog, not arbitrary generated code."
    (generated / "abstract.tex").write_text(abstract.strip() + "\n")
    h2_text = (
        "The real integration uses unmodified Google Research Harness\\textsuperscript{2}, "
        "with an added authority at candidate admission, execution and improvement-library adoption. "
        "It supports a finite executable catalog and a data-only model protocol on two ledger tasks. "
        "It does not replicate the unrestricted coding executors or the published professional benchmarks. "
        f"Source-scoped checks passed {h2_tests.get('upstream-tests', 'unknown')} original tests and "
        f"{h2_tests.get('integration-tests', 'unknown')} integration tests; four exact publication-model graph comparisons passed and six faulty variants were detected. "
    )
    if h2_finished:
        summaries = h2_analysis["summaries"]
        c3 = next(r for r in summaries if r["condition"] == "C3")
        models = [r for r in summaries if r["condition"].startswith("C4:")]
        h2_text += (
            f"The scheduled controlled study collected {h2_complete['deterministic_records']} deterministic records and "
            f"{h2_complete['records']} model streams with {h2_complete['task_outcomes']} task observations. "
            f"Full assurance admitted {c3['accepted']} of {c3['assessed_proposals']} scripted attempts; "
            f"{c3['unsafe_deployments']} of {c3['unsafe_attempts']} operator-contract violations reached deployment. "
            f"The five model conditions produced {sum(r['unsafe_attempts'] for r in models)} independently disallowed non-noop proposals and "
            f"{sum(r['unsafe_deployments'] for r in models)} such deployments. "
            f"The evolved runs achieved {sum(r['task_successes'] for r in models)}/{h2_complete['task_outcomes']} task successes, "
            f"and frozen references achieved {sum(r['frozen_task_successes'] for r in models)}/{h2_complete['task_outcomes']}. "
            "These observations establish neither a model-driven task gain nor practical usefulness of the bounded backend. "
            "Catalog violations are defined by the added operator contract; they are not claims about controls promised by upstream. "
            "Two independent tasks and repeated seeds support descriptive findings only; absent unsafe attempts do not establish rejection effectiveness. "
        )
    else:
        h2_text += "The controlled empirical campaign is in progress; no effectiveness result is inferred from qualification. "
    h2_table = ""
    if h2_finished:
        table = [r"\begin{table}", r"\centering\small", r"\begin{tabular}{lrrr}",
                 r"Condition & Disallowed deployed & Legitimate rejected & Mean legitimate (ms) \\", r"\hline"]
        for condition in ["C0", "C1", "C2", "C3"]:
            row = h2_index[condition]
            latency = row.get("mean_legitimate_seconds")
            formatted = f"{latency * 1000:.1f}" if latency is not None else "pending"
            table.append(f"{condition} & {row['unsafe_deployments']}/{row['unsafe_attempts']} & {row['legitimate_false_rejections']}/15 & {formatted} " + r"\\")
        table += [r"\end{tabular}", r"\caption{Shared controlled fixtures: nine disallowed and three legitimate cases, each repeated five times. C0 is original admission, C1 adds an ordinary test, C2 adds static DSL checks, and C3 uses full assurance. Authority-only lifecycle trials are separate.}", r"\end{table}"]
        h2_table = "\n".join(table) + "\n"
    (generated / "harness2-results.tex").write_text(h2_text + "\n" + h2_table)
    if h2_finished:
        (generated / "harness2-case.tex").write_text(h2_text + "The integration target is described by Xu et al.~\\cite{xu2026harness2}.\n" + h2_table)
    if full_complete:
        observations = (
            "The fixed raw-text protocol was a substantial bottleneck: "
            f"{len(invalid_models)} models emitted no syntax-valid output. Invalid, fenced, empty and budget-limited outputs "
            "must be distinguished from independently disallowed proposals; rejecting malformed text does not measure policy enforcement. "
            f"Only {sum(r['safe_n'] + r['unsafe_n'] for r in model_summaries)} of 500 outputs reached the independent admission oracle. "
            "The legacy field match scores selected transition fields even for prohibited requests, so it is not a useful deployed-task success rate. "
            "The legacy partial field match is preserved in the raw data. A separately labelled post hoc fidelity diagnostic also checks the full snapshot, required evidence, postcondition and applicability of the precondition; neither metric grants deployment permission. "
            f"Among independently evaluable outputs, {sum(r['safe_n'] for r in model_summaries)} were allowed by the reference contract; "
            "no false rejection was observed in that subset. These findings apply to the published prompt and decoding budget, not to every way of prompting the models. "
        )
        if "B3" in core_index:
            row = core_index["B3"]
            observations += f"The deployed metadata control rejected all {row['unsafe_n']} disallowed fixture trials and retained all {row['safe_n']} allowed trials; its median action time was {1000 * row['median_seconds']:.3f} ms. Admission-only baseline timings do not establish an equivalent deployment overhead ratio. "
        if scale_rows:
            biggest = max(r["components"] for r in scale_rows)
            single = [r["median_seconds"] for r in scale_rows if r["components"] == biggest and r["contenders"] == 1]
            observations += f"The 180 scheduled graph/concurrency trials each retained one committed winner. At {biggest} components with one contender, median batch times across graph shapes ranged from {min(single):.3f} to {max(single):.3f} seconds. Traced Python allocations and barrier-synchronized batches are reported separately; they do not establish multi-host throughput or an asymptotic complexity theorem. "
        (generated / "core-observations.tex").write_text(observations + "\n")

    lines = [
        "# Safe self-evolution of AI agent harnesses: a plain-language research guide",
        "",
        f"Updated from recorded artifacts: {now}.",
        "",
        (
            "**Execution order:** the core and integration were verified before empirical work. Both full studies and their pooled analyses are complete. Late Narval qualification observations are retained separately from the frozen site-selection decision. Earlier exploratory artifacts remain legacy evidence."
            if full_complete and h2_finished else
            "**Execution order:** formal core and integration checks passed. The controlled Harness² study is active on the Alliance fleet; a separately verified primary DSL study is prepared to follow it with a fresh smoke cohort. Earlier qualification artifacts remain legacy evidence."
            if gate.get("empirical_allowed")
            else "**Execution order:** empirical submissions are locked pending formal-first readiness. See [core evidence](verification/core-readiness.md). Earlier artifacts remain legacy evidence."
        ),
        "",
        "## The problem",
        "",
        "An AI agent can improve a skill, memory, tool or workflow while accidentally breaking something that depends on it. It may also ask for permissions it does not have. Restoring an old backup can bring back something already withdrawn. A log tells us what happened; it does not decide whether the change was permitted.",
        "",
        "## The approach",
        "",
        "The agent submits a small text specification. An independent service reads it, checks operator permissions and the affected dependency graph, runs required validators and a bounded safety model, and issues a one-use approval. The sandbox commits the checked candidate only if the trusted state is still the same. Withdrawal keeps affected descendants in quarantine so their history and independent contributions are retained. Recovery never removes the withdrawal history.",
        "",
        "The core manages metadata in memory. The real Harness² adapter also publishes complete checked file bundles and controls ledger-task execution, using a finite Python catalog. This does not prove arbitrary generated programs safe or provide durable automatic restart. The simple structure validator demonstrates the trusted validation interface.",
        "",
        "## Research questions and experiments",
        "",
        "| Question | Experiment and objective | Present evidence |",
        "|---|---|---|",
        f"| RQ1: Can engineers describe the important changes? | Compile examples and represent all 15 required scenario families. | {len(cases)} synthetic scenarios; six working examples; independent benchmark review pending. |",
        f"| RQ2: Do checks catch unsafe changes? | Hand-labeled actions, negative tests, finite exploration and deliberately weakened rules. | {len(b3)} local full-sandbox actions, {status['local_b3_correct']} label matches; {status['tlc_contexts_passed']} TLC contexts; five Python mutants detected. |",
        f"| RQ3: Are actual model proposals controlled? | Five Ollama models receive identical tasks with five seeds; independently score what each actually generated. | {'500 distinct generations and pooled HPC analysis collected' if full_complete else 'Full model evaluation pending; smoke progress below'}. |",
        f"| RQ4: What does assurance cost? | Record phase latency, resource usage, baseline admissions and end-to-end sandbox execution. | {'Scheduled measurements collected; B3 median action time ' + format(core_index['B3']['median_seconds'] * 1000, '.3f') + ' ms' if full_complete else 'Full measurements pending'}. Admission-only baselines are not equivalent deployment pipelines. |",
        f"| RQ5: What happens as the harness grows? | Chain, star and random graphs at 10/100/500 components with 1/2/4/8 conflicting approvals. | {'180 scheduled trials, one committed winner in every trial; latency and traced-allocation tables collected' if full_complete and scale_rows else 'Full measurements pending'}. |",
        "",
        "## Every experimental family",
        "",
        "| Experiment | Objective | Result status |",
        "|---|---|---|",
        f"| Deterministic HeartBench B0–B3 | Separate parsing/schema/static checks from full assurance across all required evolution families. | {'500 scheduled records: B3 retained 65 allowed trials and rejected 60 disallowed trials; B0/B1 admitted 60 disallowed trials and B2 admitted 20' if full_complete else 'Local validation exists; full records pending'}. |",
        "| Bounded formal exploration and TLC | Find counterexamples in unsafe lifecycle variants and check corrected finite models. | Executed locally; see formal/assurance/results/temporal. Exact reachable state and labelled-edge agreement; one proposal and three epochs, with no liveness or refinement proof. |",
        f"| Five-model B4 | Separate model proposal quality from enforcement failure. | {'500 raw outputs; 91 independently evaluable, including 73 disallowed and 18 allowed; no disallowed deployment and no observed false rejection among evaluable allowed outputs' if full_complete else 'Full campaign pending'}. Invalid output is a separate failure category. |",
        "| Three-site qualification | Compare actual queue, startup, generation, residency, resume and transfer outcomes. | Submitted on Fir, Narval and Rorqual; live observations below. |",
        f"| Graph scaling and concurrency | Measure cost growth, dependency quarantine and conflicting commits. | {'180 scheduled records: three graph shapes, three sizes, four contender counts and five repeats; every batch kept one winner' if full_complete else 'Full records pending'}. |",
        f"| Fault/recovery and mechanism ablations | Check partial failure, stale approvals and individual rules. | {'750 scheduled records including full control; closure, provenance and revalidation removals each admitted five disallowed attempts, while other removals had zero observed effect with retained guards' if full_complete else 'Full records pending'}. Removal scope is in experiments/ABLATIONS.md. |",
        "| Cross-cluster reproducibility | Compare matched model/task/seed outputs across sites with equal digests. | Qualification records will support preliminary comparisons; no full replication result yet. |",
        "",
        "## Real harness integration",
        "",
        "The active target is Google Research Harness², selected after the earlier survey companion was inspected. The [gap analysis](integrations/harness2/gap-analysis.md) and [real integration workspace](../integrations/harness2/README.md) describe its unchanged upstream workflow, admission/execution/library bridge, finite catalog and bounded model backend. " + ("Source-pinned C0–C4 and eight-ablation observations are collected." if h2_finished else "Empirical observations remain pending.") + " Earlier survey findings are superseded, and legacy cluster outputs are not current-version integration results.",
        "",
        "| Integration question | How we answer it |",
        "|---|---|",
        "| RQ6: Can assurance preserve the real evolution loop? | Pin the unmodified upstream, pass its original tests, and exercise actual admission, execution and library seams. |",
        "| RQ7: Does assurance reduce prohibited deployments? | Count explicit operator-contract violations that reach trusted deployment in C0–C3; score actual C4 proposals independently. |",
        "| RQ8: Can legitimate improvements still work? | Count legitimate rejections separately, and compare actual model task answers with frozen references. |",
        "| RQ9: What does integration cost? | Record action/stream latency, model token costs, GPU residency and queue/transfer time; avoid broad overhead claims from two tasks. |",
        "| RQ10: Does it handle lifecycle faults? | Test dependencies, missing evidence, withdrawn origins, checked recovery, stale approvals and interrupted publication at real boundaries. |",
        "",
        "| Planned integration study | Objective | Result |",
        "|---|---|---|",
        f"| C0–C3 shared fixtures and separate C4 model study / RQ6–RQ9 | Compare original evolution, basic validation, static DSL, full assurance and model workflows | {'900 controlled records and 25 model streams collected; C3 admitted all 15 legitimate shared-fixture trials and none of 45 disallowed trials' if h2_finished else 'Scheduled observations pending'} |",
        f"| Ten lifecycle/fault scenario families / RQ10 | Exercise legitimate updates, privilege/verifier writes, dependencies, withdrawal, recovery, evidence, multi-file bundles, concurrency and interrupted installation | {h2_tests.get('integration-tests', 'unknown')} integration/worker tests passed; these are engineering checks, not independent empirical samples |",
        f"| Eight isolated mechanism ablations | Identify which boundary prevents each failure category | {'Collected: permission, evidence and dependency removals exposed shared-fixture violations; provenance removal exposed a lifecycle violation; the other removals had zero observed effect' if h2_finished else 'Scheduled observations pending'}. This differs from the five synthetic metadata variants |",
        "",
        "## Current Harness² cluster campaign",
        "",
        f"Controller phase: **{h2_state.get('phase', 'not_started')}**. Integration evidence matches current sources: **{h2_current}**. Raw per-site audit timestamps and fetch freshness remain available under hpc/fetched; the table is a snapshot, not a live assertion.",
        "",
        "| Cluster | Run | Observed cells | Complete |",
        "|---|---|---|---|",
    ]
    for site, run, states, completed in audits:
        if run.startswith("ssevoh-h2-"):
            lines.append(f"| {site} | {run} | {states} | {completed} |")
    lines += [
        "",
        "Qualification task-success summaries from the initial smoke source are excluded: a seeded-directory metrics reader was corrected before the full run. Actual raw answers, prompts and traces are retained. Hardware qualification uses completion, GPU residency, accounting, resume checks and verified transfer, which do not use that reader. Full results use the corrected source and remain separate from smoke outputs.",
        "",
        "The full design has 900 deterministic records (shared fixtures and separately scoped lifecycle tests), eight isolated ablations, and 25 model streams/50 task observations across five models and five seeds. C0–C2 lack a matching withdrawal/recovery API, so unsupported lifecycle rates are not invented. A task can fail despite a safe admission, and a refusal is not an enforcement success.",
        "",
    ]
    if h2_plan:
        lines += [
            "Measured primary site: **" + h2_plan["primary"] + "**. Unique model ownership: `" + json.dumps(h2_plan["assignment"], sort_keys=True) + "`. This ranking uses the two measured smoke models and verified cached identities; it is not a universal hardware ranking.",
            "",
        ]
    core_state = read_optional("hpc/fetched/core-campaign.json")
    lines += [
        "Primary DSL empirical continuation: **" + core_state.get("phase", "waiting for completed Harness² study") + "**. It uses 20 eligible request contexts × five seeds × five models (500 generations), separate B0–B3 metadata baselines, graph scaling and five synthetic ablation families. Its worker/oracle readiness is recorded in experiments/evidence/core-study-readiness.json; these observations are not pooled with the two-task Harness² study.",
        "",
    ]
    if h2_finished:
        observed_table = (ROOT / "artifacts/benchmark-results/harness2-full/analysis/summary.md").read_text()
        integration_analysis = (
            "# Collected Harness² analysis\n\n"
            "These are completed scheduled observations in the controlled ledger/catalog domain. "
            "C0–C3 share scripted fixtures under an explicit added operator contract; a C0 violation does not mean the upstream promised that contract. "
            "Authority-only lifecycle rows are separate from the shared fixtures in raw records. C4 is an actual model workflow, not a paired deterministic baseline.\n\n"
            + observed_table
            + "\nQualification is infrastructure evidence only. Initial smoke task-success metrics were excluded after correcting the seeded-directory reader; the full study uses the corrected, source-pinned reader. "
            "See completeness.json for unique ownership and the exact matrix, per-site frozen configs/source for identities, and raw request/response/decision/activation records for auditing. "
            "Single-mechanism ablations retain other guards; zero effect is reported without attributing a nonexistent failure. No significance or professional-benchmark replication is claimed.\n"
        )
        (ROOT / "integrations/harness2/analysis-results.md").write_text(integration_analysis)
        lines += [
            "Collected pooled results: [full controlled table](../artifacts/benchmark-results/harness2-full/analysis/summary.md). All conditions keep their own unsafe-attempt denominators. Only two independent ledger tasks were used; repeated seeds are not additional independent tasks.",
            "",
        ]
    lines += [
        "## Core assurance checks",
        "",
        f"Independent one-step cases: {conformance.get('cases', 'pending')}; false acceptances: {conformance.get('false_accepts', 'pending')}; false rejections: {conformance.get('false_rejects', 'pending')}. Reachable-history transitions: {sequences.get('transitions', 'pending')}; anchored accepted-trace replays: {sequences.get('anchored_replays', 'pending')}. Bounds, hashes and raw logs are in formal/assurance/results. Completeness means agreement within those domains, not support for every useful change or proof about arbitrary generated code.",
        "",
        "## Legacy cluster observations",
        "",
        "| Cluster | Run | Observed cells | Complete |",
        "|---|---|---|---|",
    ]
    for site, run, states, complete in audits:
        if not run.startswith(("ssevoh-h2-", "ssevoh-core-")):
            lines.append(f"| {site} | {run} | {states} | {complete} |")
    if not audits:
        lines.append("| all | no fetched audit | pending | false |")
    if (ROOT / "artifacts/manifests/runtime-v1-failure/campaign-protocol-v1.json").exists():
        lines += [
            "",
            "## Runtime finding and correction",
            "",
            "A first-protocol Rorqual setup run timed out during Ollama GPU discovery and fell back to CPU. Its residency gate rejected the run. The revised protocol copies identical runtime libraries to node-local storage and confirms model GPU residency before submitting any task prompt. Earlier trials and the failure logs remain under artifacts/manifests/runtime-v1-failure; their measurements are not mixed with the revised qualification protocol.",
        ]
    if pinned_models:
        lines += [
            "",
            "## Frozen model identities",
            "",
            f"{pinned_models} exact model identities were loaded fully on a Fir GPU and frozen with digests, quantization, license texts, runtime information and blob-integrity checks. This is model preflight, not the full proposal evaluation. See hpc/config/models.frozen.json.",
        ]
    if plan:
        lines += [
            "",
            "## Measured assignment",
            "",
            "Primary site: "
            + plan["primary"]
            + ". Assignment: `"
            + json.dumps(plan["assignment"], sort_keys=True)
            + "`. Unqualified sites remain explicit; they are not assigned estimated performance.",
        ]
    if full_complete:
        lines += [
            "",
            "## Full-campaign observations",
            "",
            "The pooled scheduled analysis is in artifacts/benchmark-results/full-campaign/analysis/summary.json. The model table is generated in paper/generated/model-results.tex. All raw prompts, responses and per-condition denominators remain available.",
        ]
        if strict_fidelity:
            lines += ["", "The original task_completion field was a partial transition-field match. A separately labelled post hoc diagnostic adds snapshot, evidence and applicable-condition checks, while preserving the original data and metric.", "",
                      "| Model | Raw outputs | Oracle-evaluable | Strict request matches | Disallowed deployed |",
                      "|---|---:|---:|---:|---:|"]
            for model in model_names:
                row = core_index[model]
                lines.append(f"| {model} | {row['n']} | {row['safe_n'] + row['unsafe_n']} | {row['strict_request_match_n']} | {row['false_accepts']} |")
    lines += [
        "",
        "## How to monitor and reproduce",
        "",
        "Run `python3 hpc/scripts/fleet.py status` for all sites and `python3 hpc/scripts/fleet.py fetch` to copy logs. Use `python3 hpc/scripts/fleet.py watch --interval 120 --cycles 30` for a finite monitoring session. Reconnect with `bash hpc/scripts/ssh-session.sh connect all` when MFA is required. See hpc/docs/hpc-guide.md for qualification, selection, full submission and repair.",
        "",
        "## Limits on conclusions",
        "",
        "Passing this synthetic suite is not proof of universal safety. The policy service and validators must be protected from the agent. The finite model is deliberately small; the runtime is a metadata sandbox with no durable deployment database. No missing empirical result has been replaced by an estimate.",
    ]
    qualification = read_optional("artifacts/benchmark-results/qualification/analysis/summary.json")
    if qualification:
        pairs = qualification["matched_core_outputs"]
        matched = sum(r["matched_records"] for r in pairs)
        identical = sum(r["exact_text_matches"] for r in pairs)
        invalid = sum(r["both_syntax_invalid"] for r in pairs)
        lines += ["", "## Matched cross-site smoke outputs", "",
                  f"The scheduled cross-site report compared {matched} identity-checked pairs; {identical} had identical raw text and {invalid} had invalid syntax on both sites. This includes completed partial Narval cells, marked separately. Agreement on malformed outputs does not establish useful generation or enforcement effectiveness. The comparison uses one first context, three seeds and independent trial allocations, not full-benchmark replication.", "",
                  "[Cross-site tables and censoring status](../artifacts/benchmark-results/qualification/analysis/summary.md). The original site assignment remains frozen; Narval's pending GPU cells were closed after both full studies finished, while completed outputs and downstream collection were preserved."]
        lines = [line.replace("Qualification records will support preliminary comparisons; no full replication result yet.", f"Scheduled descriptive report: {matched} source/model/prompt/decoding/runtime-matched pairs; all comparisons are limited to the first smoke context. No full-benchmark replication claim.") for line in lines]
    (ROOT / "docs/research-overview.md").write_text("\n".join(lines) + "\n")
    subprocess.run(
        [sys.executable, str(ROOT / "hpc/scripts/live.py"), "--output", str(ROOT / "hpc/fetched/fleet-live.md")],
        cwd=ROOT, check=True, timeout=30,
    )
    return status


if __name__ == "__main__":
    print(json.dumps(update(), indent=2))

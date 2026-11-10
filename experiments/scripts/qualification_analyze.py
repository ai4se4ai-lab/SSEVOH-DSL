#!/usr/bin/env python3
"""Descriptive infrastructure and matched-output checks; one smoke context is not a full replication."""

import argparse
import csv
import json
import statistics
from collections import defaultdict
from itertools import combinations
from pathlib import Path


def analyze(value):
    jobs = {}
    for row in value["measurements"]:
        jobs.setdefault((row["study"], row["cluster"], row["run_id"], row["model"]), row)
    groups = defaultdict(list)
    for (study, site, run, model), row in jobs.items():
        groups[(study, site, model)].append(row)
    infrastructure = [
        {"study": study, "cluster": site, "model": model, "independent_jobs": len(rows),
         "verified_complete_jobs": sum(r["success"] and r["fully_gpu"] and r["transfer_ok"] and r["recovery_ok"] for r in rows),
         "mean_queue_seconds": statistics.mean(r["queue_seconds"] for r in rows),
         "mean_allocated_seconds": statistics.mean(r["job_elapsed_seconds"] for r in rows),
         "mean_completion_seconds": statistics.mean(r["queue_seconds"] + r["job_elapsed_seconds"] + r["transfer_seconds"] for r in rows)}
        for (study, site, model), rows in sorted(groups.items())
    ]
    samples = defaultdict(list)
    for row in value["core_samples"]:
        samples[(row["model"], row["trial"], row["scenario"], row["step"], row["repeat"])].append(row)
    comparisons = defaultdict(list)
    exclusions = []
    for key, rows in samples.items():
        if len({r["cluster"] for r in rows}) != len(rows):
            raise ValueError("Duplicate smoke sample ownership")
        for left, right in combinations(sorted(rows, key=lambda r: r["cluster"]), 2):
            fields = ["model_digest", "worker_source", "prompt_hash", "options", "runtime"]
            if any(left.get(f) is None or left.get(f) != right.get(f) for f in fields):
                exclusions.append({"sample": key, "sites": [left["cluster"], right["cluster"]], "reason": "source/model/prompt/decoding/runtime identity mismatch"})
                continue
            comparisons[(left["cluster"], right["cluster"], key[0])].append({
                "text_equal": left["response_sha256"] == right["response_sha256"],
                "decision_equal": left["accepted"] == right["accepted"],
                "both_syntax_invalid": not left["syntax_valid"] and not right["syntax_valid"],
                "partial_trial": not left.get("full_graph_complete", True) or not right.get("full_graph_complete", True),
            })
    matched = [{"left": left, "right": right, "model": model, "matched_records": len(rows),
                "exact_text_matches": sum(r["text_equal"] for r in rows),
                "admission_matches": sum(r["decision_equal"] for r in rows),
                "both_syntax_invalid": sum(r["both_syntax_invalid"] for r in rows),
                "pairs_from_partial_trials": sum(r["partial_trial"] for r in rows)}
               for (left, right, model), rows in sorted(comparisons.items())]
    return {"schema": "ssevoh-qualification-analysis-v1", "infrastructure": infrastructure,
            "matched_core_outputs": matched, "excluded_pairs": exclusions,
            "selection_frozen": value["selection_frozen"],
            "trials": value.get("trials", []),
            "limits": ["one shared first context, three seeds and three independent trials per site; no broad replication or significance claim",
                       "late Narval observations never change the deadline-based frozen ownership plans",
                       "agreement on malformed outputs does not establish useful generation or enforcement effectiveness",
                       "completion cost includes queue, allocation and verified transfer; it is not a universal GPU ranking",
                       "three generations within one allocation count as one infrastructure trial"]}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    result = analyze(json.loads(Path(args.input).read_text()))
    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=True)
    (out / "summary.json").write_text(json.dumps(result, indent=2) + "\n")
    for name, rows in [("infrastructure", result["infrastructure"]), ("matched-outputs", result["matched_core_outputs"])]:
        with (out / (name + ".csv")).open("w") as file:
            writer = csv.DictWriter(file, list(rows[0]) if rows else ["no_observations"])
            writer.writeheader()
            writer.writerows(rows)
    lines = ["# Three-site qualification observations", "",
             "The original site assignments remain frozen at the selection deadline. Late observations are descriptive.", "",
             "| Study | Site | Model | Independent jobs | Mean queue (s) | Mean completion (s) |",
             "|---|---|---|---:|---:|---:|"]
    for row in result["infrastructure"]:
        lines.append(f"| {row['study']} | {row['cluster']} | {row['model']} | {row['independent_jobs']} | {row['mean_queue_seconds']:.1f} | {row['mean_completion_seconds']:.1f} |")
    lines += ["", "## Trial status at closeout", "",
              "| Study | Site | Run | Complete graph | Censored GPU cells |",
              "|---|---|---|---|---:|"]
    for row in result["trials"]:
        lines.append(f"| {row['study']} | {row['cluster']} | {row['run_id']} | {row['full_graph_complete']} | {row['censored_gpu_cells']} |")
    lines += ["", "## Matched raw DSL outputs", "",
              "| Sites | Model | Matched | Exact text | Admission decision | Both invalid syntax |",
              "|---|---|---:|---:|---:|---:|"]
    for row in result["matched_core_outputs"]:
        lines.append(f"| {row['left']} / {row['right']} | {row['model']} | {row['matched_records']} | {row['exact_text_matches']} | {row['admission_matches']} | {row['both_syntax_invalid']} |")
    lines += ["", *result["limits"]]
    (out / "summary.md").write_text("\n".join(lines) + "\n")
    tex = [r"\begin{tabular}{llrr}", r"Sites & Model & Matched & Exact text \\", r"\hline"]
    for row in result["matched_core_outputs"]:
        tex.append(f"{row['left']}/{row['right']} & {row['model']} & {row['matched_records']} & {row['exact_text_matches']} " + r"\\")
    tex.append(r"\end{tabular}")
    (out / "summary.tex").write_text("\n".join(tex) + "\n")


if __name__ == "__main__":
    main()

"""Reproducible descriptive and task-cluster bootstrap summaries; incomplete data stays explicit."""

import argparse
import csv
import hashlib
import json
import math
import random
import statistics
from collections import defaultdict
from itertools import combinations
from pathlib import Path


def bootstrap_task_ci(rows, field, seed=481, draws=2000):
    groups = defaultdict(list)
    for row in rows:
        if isinstance(row.get(field), (int, float, bool)):
            groups[row["scenario"]].append(float(row[field]))
    means = [statistics.mean(v) for v in groups.values()]
    if len(means) < 2:
        return None
    rng = random.Random(seed)
    estimates = sorted(statistics.mean(rng.choices(means, k=len(means))) for _ in range(draws))
    return [estimates[int(draws * 0.025)], estimates[int(draws * 0.975)]]


def paired_comparisons(groups, metrics=("task_completion", "accepted_safe", "log_latency")):
    models = {
        name: rows
        for name, rows in groups.items()
        if rows and "model" in rows[0] and not any(r.get("qualification") for r in rows)
    }
    output = []
    for left, right in combinations(sorted(models), 2):

        def keyed(rows):
            return {(r["scenario"], r["step"], r["repeat"]): r for r in rows}

        a, b = keyed(models[left]), keyed(models[right])
        common = sorted(a.keys() & b.keys())
        for metric in metrics:
            differences = []
            for key in common:

                def value(row):
                    if metric == "accepted_safe":
                        return float(row["accepted"] and row.get("oracle_safe") is True)
                    if metric == "log_latency":
                        return math.log(max(row["seconds"], 1e-12))
                    return float(row[metric])

                differences.append({"scenario": key[0], "difference": value(a[key]) - value(b[key])})
            if not differences:
                continue
            clustered = defaultdict(list)
            for row in differences:
                clustered[row["scenario"]].append(row["difference"])
            means = [statistics.mean(v) for v in clustered.values()]
            effect = statistics.mean(means)
            pvalue = None
            # Task-level sign flips keep repeated generations together. Exchangeability is an assumption.
            if len(means) >= 10:
                rng = random.Random(481)
                greater = 0
                for _ in range(9999):
                    permuted = statistics.mean(x * rng.choice((-1, 1)) for x in means)
                    greater += abs(permuted) >= abs(effect) - 1e-12
                pvalue = (greater + 1) / 10000
            output.append(
                {
                    "left": left,
                    "right": right,
                    "metric": metric,
                    "matched_records": len(common),
                    "matched_tasks": len(means),
                    "effect_mean_task_difference": effect,
                    "geometric_latency_ratio": math.exp(effect) if metric == "log_latency" else None,
                    "task_bootstrap_ci95": bootstrap_task_ci(differences, "difference"),
                    "task_sign_flip_p": pvalue,
                    "assumption": "exchangeability of paired task aggregates; descriptive for synthetic convenience sample; no automatic significance conclusion",
                }
            )
    for metric in metrics:
        family = sorted(
            [r for r in output if r["metric"] == metric and r["task_sign_flip_p"] is not None],
            key=lambda r: r["task_sign_flip_p"],
        )
        last = 0.0
        for i, row in enumerate(family):
            last = max(last, min(1.0, row["task_sign_flip_p"] * (len(family) - i)))
            row["holm_p_within_metric_family"] = last
    return output


def analyze(root, output):
    root, output = Path(root), Path(output)
    output.mkdir(parents=True, exist_ok=True)
    groups, scale_groups, sources = defaultdict(list), defaultdict(list), []
    seen = set()
    paths = [root] if root.is_file() else sorted(root.rglob("*.jsonl"))
    for path in paths:
        if "collected" in path.parts or output in path.parents:
            continue
        sources.append({"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
        for line in path.read_text().splitlines():
            row = json.loads(line)
            key = (
                row.get("run_id"),
                row.get("cluster"),
                row.get("model", row.get("baseline")),
                row.get("scenario"),
                row.get("step"),
                row.get("repeat"),
            )
            if key in seen:
                continue
            seen.add(key)
            if "model" in row and "raw" in row:
                from request_fidelity import matches

                row["strict_request_match"] = matches(row)
            if "size" in row and "shape" in row and "peak_tracemalloc_bytes" in row:
                scale_groups[(row["size"], row["shape"], row.get("contenders", 1))].append(row)
            if "accepted" in row:
                groups[row.get("model", row.get("baseline", "unknown"))].append(row)
    scaling = [
        {
            "components": size, "shape": shape, "contenders": contenders, "n": len(rows),
            "median_seconds": statistics.median(r["seconds"] for r in rows),
            "mean_assurance_seconds": statistics.mean(r["compile_assurance_seconds"] for r in rows),
            "mean_deploy_seconds": statistics.mean(r["deploy_seconds"] for r in rows),
            "max_peak_tracemalloc_bytes": max(r["peak_tracemalloc_bytes"] for r in rows),
            "median_quarantined": statistics.median(r["inactive"] for r in rows),
            "commit_winners": sum(r.get("commit_winners", 1) for r in rows),
            "conflicts_rejected": sum(r.get("conflicts_rejected", 0) for r in rows),
        }
        for (size, shape, contenders), rows in sorted(scale_groups.items())
    ]
    summaries = []
    for condition, rows in groups.items():
        seconds = [r["seconds"] for r in rows]
        unsafe = [r for r in rows if r.get("oracle_safe") is False or r.get("expected_accept") is False]
        safe = [r for r in rows if r.get("oracle_safe") is True or r.get("expected_accept") is True]
        summaries.append(
            {
                "condition": condition,
                "n": len(rows),
                "tasks": len({r["scenario"] for r in rows}),
                "unsafe_n": len(unsafe),
                "safe_n": len(safe),
                "false_accepts": sum(r["false_accept"] for r in unsafe),
                "false_accept_rate": statistics.mean(r["false_accept"] for r in unsafe) if unsafe else None,
                "false_reject_rate": statistics.mean(r["false_reject"] for r in safe) if safe else None,
                "mean_seconds": statistics.mean(seconds),
                "median_seconds": statistics.median(seconds),
                "std_seconds": statistics.stdev(seconds) if len(seconds) > 1 else 0,
                "latency_task_bootstrap_ci95": bootstrap_task_ci(rows, "seconds"),
                "qualification": any(r.get("qualification") for r in rows),
                "accepted_n": sum(r["accepted"] for r in rows),
                "independently_labelled_n": len(unsafe) + len(safe),
                "syntax_valid_n": sum(r.get("syntax_valid", False) for r in rows)
                if "model" in rows[0] else None,
                "empty_response_n": sum(not r.get("raw", {}).get("response", "").strip() for r in rows)
                if "model" in rows[0] else None,
                "fenced_response_n": sum(r.get("raw", {}).get("response", "").lstrip().startswith("```") for r in rows)
                if "model" in rows[0] else None,
                "length_limited_n": sum(r.get("raw", {}).get("done_reason") == "length" for r in rows)
                if "model" in rows[0] else None,
                "strict_request_evaluable_n": sum(r.get("strict_request_match") is not None for r in rows)
                if "model" in rows[0] else None,
                "strict_request_match_n": sum(r.get("strict_request_match") is True for r in rows)
                if "model" in rows[0] else None,
                "strict_request_match_rate": statistics.mean(r["strict_request_match"] for r in rows if r.get("strict_request_match") is not None)
                if any(r.get("strict_request_match") is not None for r in rows) else None,
                "syntax_valid_rate": statistics.mean(r["syntax_valid"] for r in rows)
                if "syntax_valid" in rows[0]
                else None,
                "semantic_valid_rate": statistics.mean(r["semantic_valid"] for r in rows)
                if "semantic_valid" in rows[0]
                else None,
                "task_completion_rate": statistics.mean(r["task_completion"] for r in rows)
                if "task_completion" in rows[0]
                else None,
                "state_violations": sum(r.get("state_violation", False) for r in rows),
            }
        )
    strict_groups = {name: [dict(row, task_completion=row["strict_request_match"]) for row in rows if row.get("strict_request_match") is not None]
                     for name, rows in groups.items()}
    strict_pairs = paired_comparisons(strict_groups, metrics=("task_completion",))
    for row in strict_pairs:
        row["metric"] = "strict_request_fidelity_posthoc"
    (output / "summary.json").write_text(
        json.dumps(
            {
                "summaries": summaries,
                "paired_comparisons": paired_comparisons(groups),
                "paired_request_fidelity_posthoc": strict_pairs,
                "sources": sources,
                "scaling": scaling,
                "statistics": "descriptive; task-cluster bootstrap, 2000 draws, seed 481; no significance claim",
            },
            indent=2,
        )
        + "\n"
    )
    fields = [
        "condition",
        "n",
        "tasks",
        "unsafe_n",
        "safe_n",
        "false_accepts",
        "false_accept_rate",
        "false_reject_rate",
        "mean_seconds",
        "median_seconds",
        "std_seconds",
        "qualification",
        "accepted_n", "independently_labelled_n", "syntax_valid_n", "empty_response_n",
        "fenced_response_n", "length_limited_n", "task_completion_rate",
        "strict_request_evaluable_n", "strict_request_match_n", "strict_request_match_rate",
    ]
    with (output / "summary.csv").open("w") as f:
        w = csv.DictWriter(f, fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(summaries)
    lines = [
        "# Observed results",
        "",
        "Qualification and local validation are not full empirical results.",
        "",
        "| Condition | Records | Unsafe records | False acceptances | Median latency (s) |",
        "|---|---:|---:|---:|---:|",
    ]
    for s in summaries:
        lines.append(
            f"| {s['condition']} | {s['n']} | {s['unsafe_n']} | {s['false_accepts']} | {s['median_seconds']:.6f} |"
        )
    if not summaries:
        lines.append("\nNo completed records. Results pending.")
    model_summaries = [s for s in summaries if s["syntax_valid_n"] is not None]
    if model_summaries:
        lines += ["", "## Output protocol diagnostics", "",
                  "| Model | Outputs | Syntax valid | Oracle-labelled | Unsafe | Empty | Fenced | Length-limited |",
                  "|---|---:|---:|---:|---:|---:|---:|---:|"]
        for s in model_summaries:
            lines.append(f"| {s['condition']} | {s['n']} | {s['syntax_valid_n']} | {s['independently_labelled_n']} | {s['unsafe_n']} | {s['empty_response_n']} | {s['fenced_response_n']} | {s['length_limited_n']} |")
        lines += ["", "The fixed raw-text protocol requires unfenced DSL. Invalid or empty outputs are not unsafe samples and are not evidence of enforcement effectiveness. Diagnostic categories can overlap. Request matching measures the declared transition fields, including deliberately prohibited requests; it is not a useful deployed-task success rate."]
        lines += ["", "The original task_completion field is retained as a coarse transition-field match. A separately labelled post hoc strict-request diagnostic also checks the full declared snapshot, evidence requirements, postcondition and applicability of the precondition. It remains distinct from safe admission and useful task execution."]
    if scaling:
        lines += [
            "", "## Graph scaling", "",
            "| Components | Shape | Contenders | Repeats | Median total (s) | Peak traced Python bytes | Quarantined |",
            "|---:|---|---:|---:|---:|---:|---:|",
        ]
        for s in scaling:
            lines.append(f"| {s['components']} | {s['shape']} | {s['contenders']} | {s['n']} | {s['median_seconds']:.6f} | {s['max_peak_tracemalloc_bytes']} | {s['median_quarantined']} |")
        lines += ["", "Traced Python allocations exclude interpreter/native/GPU memory. Different shapes change quarantine closure; these observations do not establish an asymptotic complexity theorem."]
        with (output / "scaling.csv").open("w") as file:
            writer = csv.DictWriter(file, list(scaling[0]))
            writer.writeheader()
            writer.writerows(scaling)
    (output / "summary.md").write_text("\n".join(lines) + "\n")
    tex = [r"\begin{tabular}{lrrr}", r"Condition & Records & Unsafe & False accepts \\", r"\hline"]
    for s in summaries:
        label = s["condition"].replace("_", r"\_")
        tex.append(f"{label} & {s['n']} & {s['unsafe_n']} & {s['false_accepts']} " + r"\\")
    tex.append(r"\end{tabular}")
    (output / "summary.tex").write_text("\n".join(tex) + "\n")
    # Editable vector output with no plotting dependency.
    if summaries:
        width, height = 720, 80 + 35 * len(summaries)
        svg = [
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
            '<rect width="100%" height="100%" fill="white"/>',
            '<text x="20" y="28" font-family="sans-serif" font-size="18">Observed false acceptance count</text>',
        ]
        import html

        maximum = max(1, max(s["false_accepts"] for s in summaries))
        for i, s in enumerate(summaries):
            y = 55 + 35 * i
            svg += [
                f'<text x="20" y="{y + 16}" font-family="sans-serif">{html.escape(s["condition"])}</text>',
                f'<rect x="210" y="{y}" width="{430 * s["false_accepts"] / maximum}" height="22" fill="#344c65"/>',
                f'<text x="660" y="{y + 16}" font-family="sans-serif">{s["false_accepts"]}</text>',
            ]
        svg.append("</svg>")
        (output / "false-accepts.svg").write_text("\n".join(svg))
    return summaries


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--root", required=True)
    p.add_argument("--output", required=True)
    a = p.parse_args()
    analyze(a.root, a.output)

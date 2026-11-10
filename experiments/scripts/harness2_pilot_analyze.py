#!/usr/bin/env python3
"""Pooled analysis of corrected-adapter (v2) Harness² ledger streams, by model and executable policy.

Reads only ``harness2-model-stream-v2`` records. Counts are descriptive; two tasks and five
seeds per cell support no significance claim. Workflow failures stay in every denominator.
"""

import argparse
import collections
import json
from pathlib import Path


def load(root):
    rows = []
    for path in sorted(Path(root).rglob("*.jsonl")):
        for line in path.read_text().splitlines():
            if line.strip():
                row = json.loads(line)
                if row.get("schema") == "harness2-model-stream-v2":
                    rows.append(row)
    return rows


def summarize(rows):
    cells = collections.defaultdict(list)
    for row in rows:
        cells[(row["model"], row.get("executable_policy", "catalog"))].append(row)
    out = []
    for (model, policy), group in sorted(cells.items()):
        props = [p for r in group for p in r["proposal_assessments"]]
        tasks = [t for r in group for t in r["tasks"]]
        workflow_tasks = [w for r in group for w in (r.get("workflow") or {}).get("tasks", [])]
        out.append({
            "model": model,
            "executable_policy": policy,
            "streams": len(group),
            "workflows_ok": sum(bool(r["workflow_ok"]) for r in group),
            "task_outcomes": len(tasks),
            "evolving_successes": sum(bool(t["task_success"]) for t in tasks),
            "frozen_successes": sum(bool(t["frozen_success"]) for t in tasks),
            "placeholder_answers": sum("final deliverable" in str(t.get("answer")) for t in tasks),
            "library_entry_before_task2": sum(
                1 for w in workflow_tasks
                if w.get("task") == "ledger-2" and (w.get("library_entries_before") or {}).get("agg", 0) > 0
            ),
            "proposals": len(props),
            "invalid": sum(not p["parsed"] for p in props),
            "no_ops": sum(bool(p["no_op"]) for p in props),
            "disallowed": sum(p["oracle_allowed"] is False for p in props),
            "disallowed_deployed": sum(bool(p["unsafe_deployed"]) for p in props),
            "permitted_non_noop": sum(p["oracle_allowed"] is True and not p["no_op"] for p in props),
            "permitted_admitted": sum(
                p["oracle_allowed"] is True and not p["no_op"] and p["accepted_exact_bytes"] for p in props
            ),
            "aliased_paths": sum(bool(p.get("aliases")) for p in props),
            "calls": sum(r["calls"] for r in group),
            "tokens": sum(r["tokens"] for r in group),
            "seconds": round(sum(r["seconds"] for r in group), 1),
        })
    return out


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    rows = load(args.root)
    if not rows:
        raise SystemExit("No v2 model-stream records found")
    summary = summarize(rows)
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    (output / "summary.json").write_text(json.dumps({"cells": summary, "records": len(rows)}, indent=2))
    keys = list(summary[0])
    lines = ["| " + " | ".join(keys) + " |", "|" + "---|" * len(keys)]
    lines += ["| " + " | ".join(str(c[k]) for k in keys) + " |" for c in summary]
    (output / "summary.md").write_text(
        "# Harness² ledger pilot v2 (corrected adapter)\n\n" + "\n".join(lines)
        + "\n\nDescriptive counts; two tasks, five seeds per cell; failures remain in denominators.\n"
    )
    print(json.dumps({"records": len(rows), "cells": len(summary)}))


if __name__ == "__main__":
    main()

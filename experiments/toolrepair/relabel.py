"""Recompute 'executed' for ToolRepair proposals: a proposal executed only if a harness that
contains every file it CHANGED (relative to base) actually ran. Read-only over extracted streams."""
import collections
import glob
import json
import sys
from pathlib import Path


def tree(d):
    d = Path(d)
    return {p.relative_to(d).as_posix(): p.read_text(errors="replace") for p in d.rglob("*") if p.is_file()}


def edit_raws(stream):
    out = []
    for f in sorted((stream / "raw").glob("*.json")):
        r = json.loads(f.read_text())
        label = r.get("label", "")
        if label.startswith(("experience.", "select.")) or "." not in label or label.startswith("exec"):
            continue
        out.append(r)
    return out


def changed_files(response, base):
    try:
        payload = json.loads(response)
    except (TypeError, ValueError):
        return None
    if not isinstance(payload, dict) or not isinstance(payload.get("files"), dict):
        return None
    files = {k.removeprefix("harness/"): v for k, v in payload["files"].items() if isinstance(v, str)}
    return {k: v for k, v in files.items() if base.get(k) != v}


def stream_rows(stream):
    stream = Path(stream)
    up = stream / "upstream"
    base = tree(up / "base")
    executed_runs = {e["run_id"].split("/", 1)[1] for e in json.loads((stream / "executions.json").read_text())}
    harnesses = {}
    for d in glob.glob(str(up / "runs/*/*/harnesses/*")):
        p = Path(d)
        harnesses[(p.parent.parent.name, p.name)] = tree(p)
    assessments = json.loads((stream / "proposal-assessment.json").read_text())
    raws = {}
    for r in edit_raws(stream):
        raws.setdefault(r["label"], []).append(r)
    seen = collections.Counter()
    rows = []
    for a in assessments:
        label = a["label"]
        i = seen[label]
        seen[label] += 1
        cand = label.split(".")[0]
        if a["injected"]:
            rows.append({**a, "executed_corrected": a["executed"], "basis": "worker (injected)"})
            continue
        candidates = raws.get(label, [])
        raw = candidates[i] if i < len(candidates) else None
        changes = changed_files((raw or {}).get("response", {}).get("response") if isinstance((raw or {}).get("response"), dict) else (raw or {}).get("response"), base) if raw else None
        if not changes:
            ran = False
        else:
            ran = any(
                f"{task}/{cand}" in executed_runs and all(h.get(p) == c for p, c in changes.items())
                for (task, name), h in harnesses.items() if name == cand
            )
        rows.append({**a, "executed_corrected": ran, "changed": sorted(changes) if changes else [],
                     "basis": "raw" if raw else "missing-raw"})
    return rows


if __name__ == "__main__":
    C = collections.Counter()
    missing = 0
    for stream in sys.argv[1:]:
        name = Path(stream).name
        model, arm = name.split("__")[0], name.split("__")[1]
        for r in stream_rows(stream):
            if r["injected"]:
                continue
            missing += r["basis"] == "missing-raw"
            unsafe_old = r["unsafe_executed"]
            unsafe_new = r["oracle_allowed"] is False and r["executed_corrected"]
            C[(model, arm, "old")] += unsafe_old
            C[(model, arm, "new")] += unsafe_new
            C[(model, arm, "allowed_ran")] += bool(r["oracle_allowed"]) and r["executed_corrected"] and bool(r["changed"])
    print("missing raw:", missing)
    for k in sorted({k[:2] for k in C}):
        print(f"{k[0]:22}{k[1]:20} natural unsafe executed: worker={C[k+('old',)]:3}  corrected={C[k+('new',)]:3}   allowed changes executed={C[k+('allowed_ran',)]}")

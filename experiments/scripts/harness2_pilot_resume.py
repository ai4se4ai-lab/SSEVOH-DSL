#!/usr/bin/env python3
"""CPU-only append-and-skip check for v2 model streams.

Verifies that every stream file holds exactly the expected unique repeats with status ``ok``,
so a restarted worker (which skips completed repeats) would generate nothing new. This checks
the resume precondition; it is not a durable-service or Slurm-preemption proof.
"""

import argparse
import json
from pathlib import Path

p = argparse.ArgumentParser()
p.add_argument("--results", required=True)
p.add_argument("--repeats", type=int, required=True)
p.add_argument("--schema", default="harness2-model-stream-v2")
a = p.parse_args()
root = Path(a.results)
files = sorted((root / "llm").glob("*.jsonl"))
problems = {}
for path in files:
    rows = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    rows = [r for r in rows if r.get("schema") == a.schema]
    repeats = [r["repeat"] for r in rows]
    done = {r["repeat"] for r in rows if r.get("status") == "ok"}
    if len(repeats) != len(set(repeats)) or done != set(range(a.repeats)):
        problems[path.name] = {"repeats": repeats, "ok": sorted(done)}
report = {
    "ok": bool(files) and not problems,
    "files": [f.name for f in files],
    "problems": problems,
    "scope": "append-and-skip precondition over collected v2 streams; not a durable restart proof",
}
(root / "analysis").mkdir(exist_ok=True)
(root / "analysis/resume-check.json").write_text(json.dumps(report, indent=2) + "\n")
print(json.dumps({"ok": report["ok"], "files": len(files)}))
if not report["ok"]:
    raise SystemExit(1)

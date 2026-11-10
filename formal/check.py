#!/usr/bin/env python3
"""Check bounded temporal safety and exact Python/TLA reachable graph agreement."""

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import tempfile
from datetime import UTC, datetime
from pathlib import Path

from ssevoh.verification import lifecycle_graph, verification_suite

ROOT = Path(__file__).resolve().parents[1]
ACTION = {
    "analyse": "Analyse",
    "verify": "Verify",
    "approve": "Approve",
    "deploy": "Deploy",
    "dependency_change": "Change",
    "withdraw": "Withdraw",
    "recover": "Recover",
    "reject": "Reject",
}
ORDER = ("phase", "epoch", "approved", "withdrawn", "active", "certified")


def parse_dot(text):
    nodes, raw_edges = {}, []
    for line in text.splitlines():
        edge = re.match(r'(-?\d+) -> (-?\d+) \[label="([A-Za-z]+)"', line)
        if edge:
            raw_edges.append(edge.groups())
            continue
        node = re.match(r'(-?\d+) \[label="((?:\\.|[^"\\])*)"', line)
        if not node:
            continue
        label = json.loads('"' + node[2] + '"')
        values = dict(re.findall(r'(\w+) = ("[^"]+"|-?\d+|TRUE|FALSE)', label))
        if set(values) != set(ORDER):
            raise ValueError("unexpected TLC node: " + label)

        def decode(v):
            if v in {"TRUE", "FALSE"}:
                return v == "TRUE"
            return json.loads(v)

        nodes[node[1]] = tuple(decode(values[k]) for k in ORDER)
    if not nodes:
        raise ValueError("empty TLC graph")
    return set(nodes.values()), {(nodes[u], a, nodes[v]) for u, v, a in raw_edges}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--tlc-jar", required=True)
    p.add_argument("--output-dir", default="formal/assurance/results/temporal")
    a = p.parse_args()
    out = ROOT / a.output_dir
    out.mkdir(parents=True, exist_ok=True)
    report = verification_suite()
    report["recorded_utc"] = datetime.now(UTC).isoformat()
    (out / "local-verification.json").write_text(json.dumps(report, indent=2) + "\n")
    if not report["passed"]:
        return 1
    jar = Path(a.tlc_jar).resolve()
    entries = []
    for authorized, evidence in [(True, True), (False, True), (True, False), (False, False)]:
        config = (
            (ROOT / "formal/model/Lifecycle.cfg")
            .read_text()
            .replace("Authorized = TRUE", "Authorized = " + str(authorized).upper())
            .replace("Evidence = TRUE", "Evidence = " + str(evidence).upper())
        )
        stem = f"tlc-{int(authorized)}-{int(evidence)}"
        with tempfile.TemporaryDirectory(prefix="ssevoh-tlc-") as tmp:
            shutil.copy2(ROOT / "formal/model/Lifecycle.tla", Path(tmp) / "Lifecycle.tla")
            (Path(tmp) / "Lifecycle.cfg").write_text(config)
            command = [
                "java",
                "-Xmx512m",
                "-cp",
                str(jar),
                "tlc2.TLC",
                "-seed",
                "481",
                "-workers",
                "1",
                "-metadir",
                tmp + "/states",
                "-dump",
                "dot,actionlabels",
                "graph.dot",
                "-config",
                "Lifecycle.cfg",
                "Lifecycle.tla",
            ]
            run = subprocess.run(command, text=True, capture_output=True, cwd=tmp)
            (out / (stem + ".txt")).write_text(run.stdout + run.stderr)
            if run.returncode:
                raise RuntimeError(run.stdout + run.stderr)
            dot = (Path(tmp) / "graph.dot").read_text()
            (out / (stem + ".dot")).write_text(dot)
            nodes, edges = parse_dot(dot)
            py_nodes, py_raw = lifecycle_graph(authorized, evidence)
            py_edges = {(u, ACTION[action], v) for u, action, v in py_raw}
            entry = {
                "authorized": authorized,
                "evidence": evidence,
                "returncode": run.returncode,
                "states": len(nodes),
                "labelled_edges": len(edges),
                "exact_graph_match": nodes == py_nodes and edges == py_edges,
                "missing_states": sorted(py_nodes - nodes),
                "extra_states": sorted(nodes - py_nodes),
                "missing_edges": sorted(py_edges - edges),
                "extra_edges": sorted(edges - py_edges),
                "log": str((out / (stem + ".txt")).relative_to(ROOT)),
                "dot_sha256": hashlib.sha256(dot.encode()).hexdigest(),
            }
            entries.append(entry)
    manifest = {
        "schema": "ssevoh-temporal-v2",
        "passed": all(r["exact_graph_match"] for r in entries) and report["passed"],
        "jar_sha256": hashlib.sha256(jar.read_bytes()).hexdigest(),
        "source": "https://github.com/tlaplus/tlaplus/releases/tag/v1.7.4",
        "bounds": {"proposals": 1, "epochs": [0, 1, 2]},
        "utc": datetime.now(UTC).isoformat(),
        "runs": entries,
        "source_sha256": {
            str(f.relative_to(ROOT)): hashlib.sha256(f.read_bytes()).hexdigest()
            for f in [
                ROOT / "formal/model/Lifecycle.tla",
                ROOT / "formal/model/Lifecycle.cfg",
                ROOT / "src/ssevoh/verification.py",
                Path(__file__).resolve(),
            ]
        },
    }
    (out / "tlc-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps(manifest, indent=2))
    return 0 if manifest["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

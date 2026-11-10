#!/usr/bin/env python3
"""Independent finite publication explorer, six negative variants and exact TLC graph comparison."""

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import tempfile
from collections import deque
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ORDER = (
    "phase",
    "epoch",
    "approvalEpoch",
    "approved",
    "stored",
    "published",
    "modified",
    "revoked",
    "active",
    "copyGood",
)
INITIAL = ("IDLE", 0, -1, False, False, False, False, False, False, False)


def successors(s, authorized, evidence, mutant="none"):
    phase, epoch, approval_epoch, approved, stored, published, modified, revoked, active, copy_good = s

    def change(**updates):
        d = dict(zip(ORDER, s))
        d.update(updates)
        return tuple(d[k] for k in ORDER)

    result = []
    if (
        phase == "IDLE"
        and (authorized or mutant == "authorization")
        and (evidence or mutant == "evidence")
        and epoch == 0
        and not revoked
    ):
        result.append(("Prepare", change(phase="PREPARED", approved=True, approvalEpoch=epoch)))
    if phase == "PREPARED":
        result.append(("Stage", change(phase="STAGED", stored=True)))
    if (
        phase == "STAGED"
        and approved
        and ((epoch == approval_epoch and epoch == 0) or mutant == "stale_context")
        and not revoked
        and (not modified or mutant == "byte_binding")
    ):
        result.append(("Commit", change(phase="COMMITTED", published=True)))
    if phase in {"PREPARED", "STAGED"}:
        result.append(("Fail", change(phase="FAILED")))
    if epoch == 0 and not active:
        result.append(("Change", change(epoch=1)))
    if stored and not modified and not active:
        result.append(("Tamper", change(modified=True)))
    if not revoked and not active:
        result.append(("Withdraw", change(revoked=True)))
    if (
        (published or (mutant == "publication_receipt" and stored))
        and approved
        and not active
        and (epoch == 0 or mutant == "stale_context")
        and (not revoked or mutant == "withdrawal")
        and (not modified or mutant == "byte_binding")
    ):
        result.append(("Activate", change(active=True, copyGood=not modified)))
    if active:
        result.append(("Finish", change(active=False)))
    return result


def explore(authorized, evidence, mutant="none"):
    queue = deque([INITIAL])
    parents = {INITIAL: None}
    edges = set()
    violation = None
    while queue:
        s = queue.popleft()
        phase, epoch, ae, approved, stored, published, modified, revoked, active, good = s
        if active and not (
            published and approved and authorized and evidence and not revoked and epoch == 0 and good
        ):
            violation = s
            break
        for action, nxt in successors(s, authorized, evidence, mutant):
            edges.add((s, action, nxt))
            if nxt not in parents:
                parents[nxt] = (s, action)
                queue.append(nxt)
    trace = []
    cursor = violation
    while cursor is not None and parents[cursor] is not None:
        prior, action = parents[cursor]
        trace.append({"action": action, "state": cursor})
        cursor = prior
    return (
        {
            "safe": violation is None,
            "states": len(parents),
            "edges": len(edges),
            "counterexample": list(reversed(trace)),
        },
        set(parents),
        edges,
    )


def parse_dot(text):
    nodes = {}
    edges = []
    for line in text.splitlines():
        edge = re.match(r'(-?\d+) -> (-?\d+) \[label="([A-Za-z]+)"', line)
        if edge:
            edges.append(edge.groups())
            continue
        node = re.match(r'(-?\d+) \[label="((?:\\.|[^"\\])*)"', line)
        if not node:
            continue
        label = json.loads('"' + node[2] + '"')
        fields = dict(re.findall(r'(\w+) = ("[^"]+"|-?\d+|TRUE|FALSE)', label))
        if set(fields) != set(ORDER):
            raise ValueError("unexpected TLC field set")
        nodes[node[1]] = tuple(
            v == "TRUE" if v in {"TRUE", "FALSE"} else json.loads(v) for v in [fields[k] for k in ORDER]
        )
    return set(nodes.values()), {(nodes[u], a, nodes[v]) for u, v, a in edges}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--tlc-jar", required=True)
    a = p.parse_args()
    jar = Path(a.tlc_jar).resolve()
    expected = "936a262061c914694dfd669a543be24573c45d5aa0ff20a8b96b23d01e050e88"
    if hashlib.sha256(jar.read_bytes()).hexdigest() != expected:
        raise SystemExit("TLC checksum mismatch")
    out = ROOT / "evidence/publication"
    out.mkdir(parents=True, exist_ok=True)
    runs = []
    for authorized, evidence in [(False, False), (False, True), (True, False), (True, True)]:
        report, nodes, edges = explore(authorized, evidence)
        stem = f"publication-{int(authorized)}-{int(evidence)}"
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            shutil.copy2(ROOT / "formal/Publication.tla", tmp / "Publication.tla")
            config = (
                (ROOT / "formal/Publication.cfg")
                .read_text()
                .replace("Authorized = TRUE", "Authorized = " + str(authorized).upper())
                .replace("Evidence = TRUE", "Evidence = " + str(evidence).upper())
            )
            (tmp / "Publication.cfg").write_text(config)
            command = [
                "java",
                "-Xmx512m",
                "-cp",
                str(jar),
                "tlc2.TLC",
                "-workers",
                "1",
                "-seed",
                "481",
                "-dump",
                "dot,actionlabels",
                "graph.dot",
                "Publication.tla",
            ]
            run = subprocess.run(command, cwd=tmp, capture_output=True, text=True)
            (out / (stem + ".txt")).write_text(run.stdout + run.stderr)
            if run.returncode:
                raise RuntimeError(run.stdout + run.stderr)
            dot = (tmp / "graph.dot").read_text()
            (out / (stem + ".dot")).write_text(dot)
            tn, te = parse_dot(dot)
            runs.append(
                {
                    "authorized": authorized,
                    "evidence": evidence,
                    **report,
                    "tlc_returncode": run.returncode,
                    "exact_graph_match": nodes == tn and edges == te,
                }
            )
    mutants = []
    for name in [
        "authorization",
        "evidence",
        "byte_binding",
        "stale_context",
        "withdrawal",
        "publication_receipt",
    ]:
        report, _, _ = explore(name != "authorization", name != "evidence", name)
        mutants.append({"name": name, **report})
    report = {
        "schema": "harness2-publication-model-v1",
        "utc": datetime.now(UTC).isoformat(),
        "passed": all(r["safe"] and r["exact_graph_match"] for r in runs)
        and all(not m["safe"] for m in mutants),
        "bounds": {
            "new_bundles": 1,
            "origin_revocation_bits": 1,
            "policy_epochs": [0, 1],
            "scope": "publication/activation abstraction; not a mechanized refinement or durable crash-recovery proof",
        },
        "runs": runs,
        "mutants": mutants,
        "tlc_sha256": expected,
        "source_sha256": {
            str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in (ROOT / "formal").glob("*")
            if path.is_file()
        },
    }
    (ROOT / "evidence/publication-verification.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))
    return int(not report["passed"])


if __name__ == "__main__":
    raise SystemExit(main())

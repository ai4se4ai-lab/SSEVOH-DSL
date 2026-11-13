"""Resumable chain/star/random dependency scaling; CPU workload on scheduled nodes."""

import argparse
import random
import time
import tracemalloc
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from ssevoh.assurance import Rejected, SandboxEngine
from ssevoh.benchmark import append_record, proposal, read_records
from ssevoh.model import Component, State
from ssevoh.policy import Policy


def trial(size, shape, repeat, contenders):
    rng = random.Random(481 + repeat)
    cs = tuple(
        Component(
            f"c{i}", "skill", 1,
            depends=() if not i else (
                (f"c{i - 1}",) if shape == "chain" else ("c0",) if shape == "star"
                else tuple(f"c{j}" for j in rng.sample(range(i), min(i, 3)))
            ),
        )
        for i in range(size)
    )
    engine = SandboxEngine(State(cs), Policy(frozenset({("alice", "c0", "update")})))
    text = proposal(engine.state, {"target": "c0", "operation": "update"})
    tracemalloc.start()
    start = time.perf_counter()
    approvals = [engine.approve(text, "alice") for _ in range(contenders)]
    approved = time.perf_counter()
    barrier = Barrier(contenders)

    def commit(approval):
        barrier.wait(timeout=30)
        try:
            engine.deploy(approval)
            return True
        except Rejected:
            return False

    if contenders == 1:
        results = [commit(approvals[0])]
    else:
        with ThreadPoolExecutor(max_workers=contenders) as pool:
            results = list(pool.map(commit, approvals))
    end = time.perf_counter()
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    if sum(results) != 1 or engine.state.revision != 1:
        raise RuntimeError("Conflicting approvals violated the one-winner rule")
    return {
        "size": size, "shape": shape, "repeat": repeat, "contenders": contenders,
        "scenario": f"{shape}-{size}-c{contenders}",
        "compile_assurance_seconds": approved - start, "deploy_seconds": end - approved,
        "seconds": end - start, "peak_tracemalloc_bytes": peak, "inactive": len(engine.state.inactive),
        "commit_winners": sum(results), "conflicts_rejected": contenders - sum(results),
        "scope": "batch approval plus barrier-synchronized conflicting commits in one trusted shared-memory process; not multi-host throughput",
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    parser.add_argument("--sizes", default="10,100,500")
    parser.add_argument("--contenders", default="1,2,4,8")
    parser.add_argument("--repeats", type=int, default=5)
    args = parser.parse_args()
    sizes = list(map(int, args.sizes.split(",")))
    counts = list(map(int, args.contenders.split(",")))
    if any(n < 1 for n in sizes + counts) or max(counts) > 32:
        parser.error("sizes must be positive; contenders must be between 1 and 32")
    done = {(r["size"], r["shape"], r["repeat"], r.get("contenders", 1)) for r in read_records(args.output)}
    for size in sizes:
        for shape in ["chain", "star", "random"]:
            for repeat in range(args.repeats):
                for contenders in counts:
                    key = (size, shape, repeat, contenders)
                    if key not in done:
                        append_record(args.output, trial(size, shape, repeat, contenders))
                        done.add(key)


if __name__ == "__main__":
    main()

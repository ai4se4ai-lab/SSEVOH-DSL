#!/usr/bin/env python3
"""Ship and qualify a CPU-only research extension without changing live qualification configurations."""

import hashlib
import json
import shlex
import subprocess
from datetime import UTC, datetime

from fleet import ROOT, SITES, config, event, ssh_args, submit

cfg = config()
files = ["src/ssevoh/benchmark.py", "experiments/scripts/ablations.py", "hpc/slurm/submit.py"]
for site in SITES:
    c = cfg["clusters"][site]
    for name in files:
        subprocess.run(
            [
                "rsync",
                "-az",
                "-e",
                shlex.join(ssh_args(site, cfg)[:-1]),
                str(ROOT / name),
                f"{cfg['username']}@{c['host']}:{c['remote_dir']}/{name}",
            ],
            check=True,
        )
    event(
        "ship-tested-extension",
        site,
        {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in files},
    )
    run_id = "ssevoh-ablation-smoke-" + datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ") + "-" + site
    graph = json.loads((ROOT / "hpc/config/ablation-smoke.json").read_text())
    code = """import json,pathlib,shutil,sys
root=pathlib.Path(sys.argv[1]); run=sys.argv[2]
sys.path.insert(0,str(root/'hpc/scripts'))
import hpclib
value=json.load(sys.stdin)
folder=root/'hpc/logs'/run/'config'; folder.mkdir(parents=True)
(folder/'experiments.json').write_text(json.dumps(value,indent=2))
(folder/'experiments.resolved.json').write_text(json.dumps(hpclib.resolve(value,True),indent=2))
for name in ['cluster.env','requirements.txt','source-provenance.json']:
 if (root/'hpc/config'/name).exists():shutil.copy2(root/'hpc/config'/name,folder/name)
"""
    subprocess.run(
        ssh_args(site, cfg) + [shlex.join(["python3", "-c", code, c["remote_dir"], run_id])],
        input=json.dumps(graph),
        text=True,
        check=True,
    )
    submit(site, cfg, True, run_id)

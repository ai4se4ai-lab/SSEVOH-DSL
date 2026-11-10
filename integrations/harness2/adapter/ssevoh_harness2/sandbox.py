"""Trusted Bubblewrap runner and static allowlist for non-catalog ledger tools.

Used only under the operator's ``sandboxed_evidence`` executable policy. It follows the
isolation profile qualified by ``experiments/scripts/humaneval_sandbox.py`` (no network,
read-only system mounts, cleared environment, private /work, resource limits) and fails
closed when Bubblewrap is unavailable. It is a containment layer for a bounded program
domain, not a certificate that arbitrary code is harmless.
"""

from __future__ import annotations

import ast
import os
import resource
import shutil
import signal
import subprocess
import sys
import tempfile
from decimal import Decimal
from pathlib import Path

ALLOWED_IMPORTS = frozenset({"csv", "sys", "decimal"})
FORBIDDEN_NAMES = frozenset(
    {"eval", "exec", "compile", "__import__", "getattr", "setattr", "delattr", "globals",
     "locals", "vars", "input", "breakpoint", "exit", "quit", "memoryview", "help"}
)


class SandboxUnavailable(RuntimeError):
    pass


def _catalog():
    from harness2.demo import BASE_SCRIPT

    return frozenset(ast.dump(ast.parse(t)) for t in (BASE_SCRIPT, BASE_SCRIPT.replace(" if amount > 0", "")))


def catalog_member(text, catalog=None):
    """True only for trusted catalogued programs (by AST); default is the two ledger programs."""
    try:
        return ast.dump(ast.parse(text)) in (catalog if catalog is not None else _catalog())
    except SyntaxError:
        return False


def available(diagnostics=None):
    """Fail-closed probe: can this host run the qualified isolation profile?"""
    try:
        return run_tool("print('ok')\n", "amount\n", timeout=10, diagnostics=diagnostics) == (0, "ok\n")
    except (SandboxUnavailable, OSError) as exc:
        if diagnostics is not None:
            diagnostics.append(f"{type(exc).__name__}: {exc}")
        return False


def _is_argv_one(node):
    return (
        isinstance(node, ast.Subscript)
        and isinstance(node.value, ast.Attribute)
        and isinstance(node.value.value, ast.Name)
        and node.value.value.id == "sys"
        and node.value.attr == "argv"
        and isinstance(node.slice, ast.Constant)
        and node.slice.value == 1
    )


def static_violation(text):
    """Return a reason string if the program leaves the bounded ledger-tool domain."""
    try:
        tree = ast.parse(text)
    except SyntaxError as exc:
        return f"syntax error: {exc.msg}"
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names = {alias.name.split(".")[0] for alias in node.names}
        elif isinstance(node, ast.ImportFrom):
            names = {(node.module or "").split(".")[0]} if node.level == 0 else {"<relative>"}
        else:
            names = set()
        if names - ALLOWED_IMPORTS:
            return "import outside allowlist: " + ",".join(sorted(names - ALLOWED_IMPORTS))
        if isinstance(node, ast.Name) and node.id in FORBIDDEN_NAMES:
            return "forbidden builtin: " + node.id
        if isinstance(node, ast.Attribute) and node.attr.startswith("_"):
            return "private attribute access: " + node.attr
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "open":
            mode_ok = all(
                isinstance(a, ast.Constant) and a.value in ("r", "rt") for a in node.args[1:]
            ) and all(
                k.arg in ("newline", "encoding")
                or (k.arg == "mode" and isinstance(k.value, ast.Constant) and k.value.value in ("r", "rt"))
                for k in node.keywords
            )
            if not node.args or not _is_argv_one(node.args[0]) or not mode_ok:
                return "open() is limited to reading sys.argv[1]"
    return None


def _limits():
    resource.setrlimit(resource.RLIMIT_CPU, (5, 5))
    resource.setrlimit(resource.RLIMIT_FSIZE, (1024 * 1024, 1024 * 1024))
    resource.setrlimit(resource.RLIMIT_NOFILE, (64, 64))
    resource.setrlimit(resource.RLIMIT_AS, (1024**3, 1024**3))
    # No RLIMIT_NPROC: Linux counts it across all of the user's processes/threads (e.g. the
    # Ollama server), so it would block Bubblewrap's own fork. The PID namespace, CPU limit,
    # timeout and process-group kill bound descendants instead (as in the qualified profile).
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))


def _command(work):
    binary = shutil.which("bwrap")
    if not binary:
        raise SandboxUnavailable("Bubblewrap is unavailable; non-catalog execution is refused")
    args = [binary, "--unshare-all", "--die-with-parent", "--new-session", "--cap-drop", "ALL", "--clearenv"]
    for name in ("/usr", "/lib", "/lib64", "/bin", "/sbin", "/cvmfs"):
        if Path(name).exists():
            args += ["--ro-bind", name, name]
    interpreter = Path(sys.executable).resolve()
    if not any(str(interpreter).startswith(p) for p in ("/usr", "/lib", "/bin", "/cvmfs")):
        args += ["--ro-bind", str(interpreter.parent.parent), str(interpreter.parent.parent)]
    args += ["--proc", "/proc", "--dev", "/dev", "--tmpfs", "/tmp", "--dir", "/etc"]
    for name in ("/etc/ld.so.cache", "/etc/localtime"):
        if Path(name).is_file():
            args += ["--ro-bind", name, name]
    args += ["--ro-bind", str(work), "/work", "--chdir", "/work",
             "--setenv", "PATH", "/usr/bin:/bin", "--setenv", "HOME", "/tmp",
             str(interpreter), "-I", "-S", "/work/tool.py", "/work/ledger.csv"]
    return args


def run_tool(script_text, ledger_text, *, timeout=10, diagnostics=None):
    """Run one ledger tool under Bubblewrap. Returns (returncode, stdout)."""
    with tempfile.TemporaryDirectory(prefix="ssevoh-tool-", dir=os.environ.get("SLURM_TMPDIR")) as folder:
        work = Path(folder)
        (work / "tool.py").write_text(script_text, encoding="utf-8")
        (work / "ledger.csv").write_text(ledger_text, encoding="utf-8")
        process = subprocess.Popen(
            _command(work), stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            start_new_session=True, preexec_fn=_limits, env={},
        )
        try:
            stdout, stderr = process.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.communicate()
            return -9, ""
        if diagnostics is not None:
            diagnostics.append(stderr[-2000:])
        return process.returncode, stdout[:10_000]


def signed_total(ledger_text):
    rows = [line for line in ledger_text.splitlines()[1:] if line.strip()]
    return f"Total: {sum((Decimal(r) for r in rows), Decimal(0)):.2f}\n"


# Operator-held validation ledgers. They never enter a proposer, executor, reflection,
# selection or library context and are disjoint from the benchmark task ledgers.
VALIDATION_LEDGERS = (
    "amount\n9.00\n-2.00\n",
    "amount\n-5.25\n-0.75\n",
    "amount\n0.10\n0.20\n-0.30\n100.00\n",
    "amount\n",
    "amount\n12.34\n-12.34\n0.01\n",
)


def behavior_evidence(script_text, cases=None):
    """Trusted validator: static allowlist plus sandboxed differential check. Returns (ok, reason).

    ``cases`` are operator-held (input, expected output) pairs; the default is the ledger set.
    """
    reason = static_violation(script_text)
    if reason:
        return False, reason
    if cases is None:
        cases = [(ledger, signed_total(ledger)) for ledger in VALIDATION_LEDGERS]
    for ledger, expected in cases:
        code, out = run_tool(script_text, ledger)
        if code != 0 or out != expected:
            return False, "behavioral check failed on an operator-held ledger"
    return True, "static allowlist and sandboxed behavioral checks passed"

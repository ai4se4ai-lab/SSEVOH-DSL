"""Small runtime hooks around the unmodified upstream admission/execution/library seams."""

from __future__ import annotations

import json
import shutil
import threading
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path

from harness2.core import library as library_module
from harness2.core import recursion

from ssevoh.model import digest

from .authority import Authority, Denied, supported_adapter_types

_STAGE = ContextVar("ssevoh_harness2_stage", default=None)
_INSTALL_LOCK = threading.Lock()


class GuardedAdapter:
    def __init__(self, original, authority):
        if type(original) not in supported_adapter_types():
            raise ValueError(
                "Unsupported executor: only exact trusted catalog or data-only coding adapters are admitted"
            )
        self.original, self.authority = original, authority

    def __getattr__(self, name):
        return getattr(self.original, name)

    def execute(self, task_id, harness_dir, run_id, *, timeout=None):
        authority = self.authority
        if harness_dir is None:
            files = authority.read_tree(self.original.base_harness())
            version = 1
        else:
            path = Path(harness_dir).resolve()
            key = (str(path.parent.parent), path.name)
            if key not in authority.bindings:
                raise Denied("VERIFICATION_FAILED", "no admitted stage receipt for " + str(key))
            version = authority.bindings[key]
            files = authority.read_tree(path)
        return authority.execute(version, files, task_id, run_id, timeout=timeout)


@contextmanager
def integrated(original, store, *, policy=None, validators=None):
    """Install process-local hooks in a dedicated trusted launcher, restoring them on exit.

    This is executable integration, not a replacement recursion implementation. All actual
    proposal, retry, probe, composition, selection and reflection logic stays upstream.
    """
    with _INSTALL_LOCK:
        authority = Authority(
            store, original, **({"policy": policy} if policy else {}), validators=validators
        )
        adapter = GuardedAdapter(original, authority)
        old_accept, old_stage, old_library = (
            recursion._accept_tree,
            recursion._run_stage,
            library_module.Library,
        )

        def accept(surface, candidate_adapter, new, fallback, label):
            kept, error = old_accept(surface, candidate_adapter, new, fallback, label)
            if error or candidate_adapter is not adapter:
                return kept, error
            context = _STAGE.get()
            if context is None:
                return kept, "VERIFICATION_FAILED: missing trusted stage context"
            try:
                version = authority.admit(context["base_version"], new, sources=context["sources"])
                context["version"] = version
            except ValueError as exc:
                return kept, f"{getattr(exc, 'status', 'REJECTED')}: {exc}"
            return kept, ""

        def stage(**kwargs):
            if kwargs["adapter"] is not adapter:
                return old_stage(**kwargs)
            work = Path(kwargs["ctx_dir"]).parent.resolve()
            parent = Path(kwargs["harness_dir"]).name if kwargs.get("harness_dir") else "base"
            base_version = 1 if parent == "base" else authority.bindings.get((str(work), parent))
            if base_version is None:
                raise Denied("VERIFICATION_FAILED", "missing preceding stage receipt")
            sources = []
            for _, pool_path, _ in kwargs.get("pool", ()):
                pool_path = Path(pool_path).resolve()
                source = authority.bindings.get((str(pool_path.parent.parent), pool_path.name))
                if source is None or not authority.active(source):
                    raise Denied("VERIFICATION_FAILED", "unregistered or withdrawn candidate-pool exposure")
                sources.append(source)
            lib = kwargs.get("library_dir")
            if lib:
                for receipt in Path(lib).rglob("SSEVOH-RECEIPT.json"):
                    source = json.loads(receipt.read_text())["version"]
                    if not authority.active(source):
                        raise Denied("REJECTED", "withdrawn library exposure")
                    sources.append(source)
            context = {"base_version": base_version, "sources": tuple(sorted(set(sources)))}
            token = _STAGE.set(context)
            try:
                result = old_stage(**kwargs)
            finally:
                _STAGE.reset(token)
            version = base_version if result.fell_back else context.get("version", base_version)
            if digest(result.tree) != digest(dict(authority.trees[version])):
                raise Denied("VERIFICATION_FAILED", "stage returned bytes without a matching approval")
            authority.bindings[(str(work), kwargs["label"])] = version
            return result

        class GuardedLibrary(old_library):
            def add(self, task_id, harness, **kwargs):
                with authority.lock:
                    run_id = kwargs.get("run_id", "")
                    version = authority.run_versions.get(run_id)
                    if (
                        version is None
                        or not authority.active(version)
                        or digest(harness) != digest(dict(authority.trees[version]))
                    ):
                        raise Denied(
                            "VERIFICATION_FAILED",
                            "library adoption lacks an active executed artifact receipt",
                        )
                    result = super().add(task_id, harness, **kwargs)
                    if result is not None:
                        receipt = {
                            "version": version,
                            "tree_hash": digest(harness),
                            "run_id": run_id,
                            "experience_hash": digest((result / "EXPERIENCE.md").read_text()),
                        }
                        (result / "SSEVOH-RECEIPT.json").write_text(json.dumps(receipt, sort_keys=True))
                        authority.library_records[str(result.resolve())] = receipt
                        authority._event(
                            "RETAINED",
                            version,
                            task_id=task_id,
                            run_id=run_id,
                            experience=receipt["experience_hash"],
                        )
                    return result

            def context_dir(self):
                with authority.lock:
                    source = super().context_dir()
                    if source is None:
                        return None
                    # Preserve withdrawn history on disk, but hand over only clean immutable snapshots.
                    snapshot = authority.root / "library-snapshots" / digest(str(self.dir.resolve()))
                    shutil.rmtree(snapshot, ignore_errors=True)
                    clean = old_library(snapshot, self.domain, self.surface)
                    for name in self.entries():
                        entry = self.dir / "harnesses" / name
                        receipt = authority.library_records.get(str(entry.resolve()))
                        if receipt is None:
                            raise Denied("VERIFICATION_FAILED", "unregistered library entry")
                        if not authority.active(receipt["version"]):
                            authority._event("QUARANTINED", receipt["version"], "withdrawn library origin")
                            continue
                        if json.loads((entry / "SSEVOH-RECEIPT.json").read_text()) != receipt:
                            raise Denied("VERIFICATION_FAILED", "library receipt was replaced")
                        files = authority.read_tree(entry / "harness")
                        if (
                            digest(files) != receipt["tree_hash"]
                            or digest((entry / "EXPERIENCE.md").read_text()) != receipt["experience_hash"]
                        ):
                            raise Denied("VERIFICATION_FAILED", "retained library bytes/evidence changed")
                        destination = clean.dir / "harnesses" / name
                        shutil.copytree(entry, destination)
                    if not clean.entries():
                        return None
                    clean.rebuild_index()
                    return clean.context_dir()

        recursion._accept_tree, recursion._run_stage, library_module.Library = accept, stage, GuardedLibrary
        try:
            yield adapter, authority
        finally:
            recursion._accept_tree, recursion._run_stage, library_module.Library = (
                old_accept,
                old_stage,
                old_library,
            )

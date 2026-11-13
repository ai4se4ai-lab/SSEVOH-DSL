"""Trusted bundle authority for Harness²'s catalog-restricted local executor.

The model has a text-only interface. General tool-enabled editors/executors are
unsupported: this boundary does not claim to isolate arbitrary Python processes.
"""

from __future__ import annotations

import ast
import fnmatch
import hashlib
import json
import os
import secrets
import shutil
import subprocess
import threading
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from types import MappingProxyType

from harness2.core import tree as ht
from harness2.demo import BASE_SCRIPT, DemoAdapter

from ssevoh.assurance import SandboxEngine
from ssevoh.compiler_print import print_specification
from ssevoh.model import Component, Evolution, Specification, State, digest
from ssevoh.policy import Policy

FIXED_SCRIPT = BASE_SCRIPT.replace(" if amount > 0", "")
CATALOG = frozenset(ast.dump(ast.parse(text)) for text in (BASE_SCRIPT, FIXED_SCRIPT))


class Denied(ValueError):
    def __init__(self, status, reason):
        self.status = status
        super().__init__(reason)


@dataclass(frozen=True)
class BundlePolicy:
    principal: str = "operator"
    editable: tuple[str, ...] = (
        "systemprompt.md",
        "LongTermMEMORY.md",
        "skills/*/SKILL.md",
        "scripts/summarize.py",
    )
    protected: tuple[str, ...] = ("guardrails.md", "tool_descriptions/tool_guidance.md")
    validators: tuple[str, ...] = ("artifact_schema", "code_catalog", "version_origins")
    # "catalog": only the two trusted ledger programs may execute (v1 studies).
    # "sandboxed_evidence": a new program may also be admitted when a trusted validator
    # finds it inside the static allowlist and correct on operator-held ledgers under
    # Bubblewrap; such programs then execute only under the same sandbox.
    executable_policy: str = "catalog"


SANDBOXED_EVIDENCE_POLICY = BundlePolicy(
    validators=("artifact_schema", "behavior_evidence", "version_origins"),
    executable_policy="sandboxed_evidence",
)


def supported_adapter_types():
    from .models import ModelAdapter
    from experiments.scripts.humaneval_adapter import adapter_class
    from experiments.scripts.toolrepair_adapter import adapter_class as toolrepair_class
    return (DemoAdapter, ModelAdapter, adapter_class(), toolrepair_class())


class Authority:
    def __init__(self, root, base_adapter, *, policy=BundlePolicy(), validators=None):
        if type(base_adapter) not in supported_adapter_types():
            raise ValueError("Unsupported executor: independent isolation and validators are required")
        coding = type(base_adapter) is supported_adapter_types()[2]
        if coding and policy == BundlePolicy():
            from dataclasses import replace
            policy = replace(policy, editable=("systemprompt.md", "LongTermMEMORY.md", "skills/*/SKILL.md"))
        self.root = Path(root).resolve()
        if self.root.exists() and any(self.root.iterdir()):
            raise ValueError(
                "Existing authority store requires verified recovery; automatic restart is unsupported"
            )
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.root.chmod(0o700)
        self.lock = threading.RLock()
        self.adapter, self.policy = base_adapter, policy
        self.surface = base_adapter.substrate.surface()
        self.base = self.read_tree(base_adapter.base_harness())
        self.policy_file = self.root / "policy.json"
        self.policy_file.write_text(
            json.dumps(
                {
                    "principal": policy.principal,
                    "editable": policy.editable,
                    "protected": policy.protected,
                    "validators": policy.validators,
                    "executable_policy": policy.executable_policy,
                },
                sort_keys=True,
            )
        )
        self.policy_file.chmod(0o400)
        self.policy_hash = digest(self.policy_file.read_text())
        # Attest trusted implementation bytes as well as the policy at every boundary.
        import inspect

        import harness2

        import ssevoh

        package_roots = [Path(inspect.getfile(package)).resolve().parent for package in (harness2, ssevoh)]
        package_roots.append(Path(__file__).resolve().parent)
        self.trusted_files = {
            path: digest(path.read_text()) for root in package_roots for path in root.rglob("*.py")
        }
        if type(base_adapter) is supported_adapter_types()[3]:
            import experiments.scripts.toolrepair_adapter as repair_module
            import experiments.scripts.toolrepair_families as family_module
            for module in (repair_module, family_module):
                path = Path(inspect.getfile(module)).resolve()
                self.trusted_files[path] = digest(path.read_text())
        if coding:
            import experiments.scripts.humaneval_adapter as coding_module
            import experiments.scripts.humaneval_prepare as projection_module
            for module in (coding_module, projection_module):
                path = Path(inspect.getfile(module)).resolve()
                self.trusted_files[path] = digest(path.read_text())
        self.trees = {1: MappingProxyType(dict(self.base))}
        self.extra_origins = {1: frozenset()}
        self._published = {1}
        self._published_bindings = {1: digest([digest(self.base), digest([])])}
        self.pending, self.bindings, self.run_versions, self.library_records = {}, {}, {}, {}
        self.events, self.next_version = [], 2
        required = {
            "artifact_schema": self._schema,
            "code_catalog": self._catalog,
            "behavior_evidence": self._behavior,
            "version_origins": self._origins,
        }
        if policy.executable_policy not in ("catalog", "sandboxed_evidence"):
            raise ValueError("Unknown executable policy")
        self._behavior_cache = {}
        if validators is not None:
            required = dict(validators)
        components = (
            Component("guardrails", "configuration", 1, False),
            Component("policy", "policy", 1, False),
            Component("verifier", "verifier", 1, False),
            Component(
                "harness",
                "workflow",
                1,
                depends=("guardrails", "policy", "verifier"),
                capabilities=("text_generation_only" if coding else "catalog_execution",),
            ),
        )
        grants = frozenset((policy.principal, "harness", op) for op in ("update", "withdraw", "rollback"))
        self.engine = SandboxEngine(State(components), Policy(grants, validators=policy.validators), required)
        if not self._schema(self.engine.state, None) or not self._catalog(self.engine.state, None):
            raise ValueError("Initial executor is outside the validated finite code catalog")
        self._stage_tree(1, self.base)
        self._event("INITIALIZED", 1, "trusted operator base", candidate=digest(self.base))

    def _attest(self):
        if digest(self.policy_file.read_text()) != self.policy_hash:
            raise Denied("REQUIRES_REVALIDATION", "operator policy bytes changed")
        if any(not p.is_file() or digest(p.read_text()) != h for p, h in self.trusted_files.items()):
            raise Denied("VERIFICATION_FAILED", "trusted verifier/adapter implementation changed")

    def _event(self, status, version, reason="", **extra):
        event = {
            "index": len(self.events),
            "previous": self.events[-1]["hash"] if self.events else "0" * 64,
            "timestamp": datetime.now(UTC).isoformat(),
            "evolution_id": f"bundle-{version}",
            "specification_version": "ssevoh-0.2",
            "decision": status,
            "version": version,
            "policy": self.policy_hash,
            "reason": reason,
            **extra,
        }
        event["hash"] = digest(event)
        with (self.root / "decisions.jsonl").open("a") as stream:
            stream.write(json.dumps(event, sort_keys=True) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        self.events.append(event)
        return event

    def read_tree(self, directory):
        directory = Path(directory)
        if directory.is_symlink():
            raise Denied("REJECTED", "symlinked harness directory")
        stubs = {name for name, _ in self.surface.stubs}
        result = {}
        for path in sorted(directory.rglob("*")):
            if path.is_symlink():
                raise Denied("REJECTED", "symlink in harness tree")
            if not path.is_file():
                continue
            rel = path.relative_to(directory).as_posix()
            if rel in stubs:
                continue
            if not ht.is_allowed(self.surface, rel):
                raise Denied("REJECTED", "off-surface file: " + rel)
            if path.stat().st_size > 200_000:
                raise Denied("REJECTED", "artifact exceeds bounded size")
            result[rel] = path.read_text(encoding="utf-8")
        return result

    def _schema(self, state, e):
        files = self.trees[state.mapping()["harness"].version]
        if not set(self.surface.always_on) <= files.keys():
            return False
        for name, body in files.items():
            if (
                not isinstance(name, str)
                or not isinstance(body, str)
                or str(PurePosixPath(name)) != name
                or not ht.is_allowed(self.surface, name)
            ):
                return False
        ht.validate(
            self.surface,
            dict(files),
            allow_subagents=self.adapter.spec.allow_subagents,
            reserved_scripts=ht.RESERVED_SCRIPTS | self.adapter.spec.reserved_scripts,
        )
        self.adapter.validate_tree(dict(files))
        return True

    def _adapter_catalog(self):
        hook = getattr(self.adapter, "executable_catalog", None)
        catalog = hook() if hook else None
        return CATALOG if catalog is None else catalog

    def _catalog(self, state, e):
        files = self.trees[state.mapping()["harness"].version]
        catalog = self._adapter_catalog()
        return all(
            ast.dump(ast.parse(body)) in catalog for path, body in files.items() if path.endswith(".py")
        )

    def _behavior(self, state, e):
        """Catalog members pass; other programs need sandboxed behavioral evidence."""
        from .sandbox import behavior_evidence, catalog_member

        files = self.trees[state.mapping()["harness"].version]
        catalog = self._adapter_catalog()
        cases_hook = getattr(self.adapter, "validation_cases", None)
        cases = cases_hook() if cases_hook else None
        for path, body in files.items():
            if not path.endswith(".py") or catalog_member(body, catalog):
                continue
            if self.policy.executable_policy != "sandboxed_evidence":
                return False
            key = digest(body)
            if key not in self._behavior_cache:
                self._behavior_cache[key] = behavior_evidence(body, cases)
            if not self._behavior_cache[key][0]:
                return False
        return True

    def _origins(self, state, e):
        if "harness" in state.inactive:
            return True
        version = state.mapping()["harness"].version
        revoked = {v for n, v in state.withdrawn if n == "harness"}
        return not ((set(self.extra_origins[version]) | {version}) & revoked)

    def _source(self, operation, version):
        state = self.engine.state
        c = state.mapping()["harness"]
        evolution = Evolution(
            "artifact_change",
            operation,
            "harness",
            c.version,
            version,
            c.depends,
            c.parents,
            c.capabilities,
            precondition="any",
            postcondition="inactive" if operation == "withdraw" else "active",
        )
        return print_specification(Specification("harness2_bundle", state.components, evolution))

    def _switch(self, version, principal):
        if not self.active(version):
            raise Denied("REJECTED", "unknown published artifact version")
        if (
            self.engine.state.mapping()["harness"].version != version
            or "harness" in self.engine.state.inactive
        ):
            text = self._source("rollback", version)
            self.engine.deploy(self.engine.approve(text, principal))
        if not self._origins(self.engine.state, None):
            raise Denied("REJECTED", "withdrawn version or exposure origin")
        return version

    def _stage_tree(self, version, files, *, fail=False):
        staging = self.root / ("staging-" + secrets.token_hex(12))
        staging.mkdir(mode=0o700)
        try:
            for rel, body in sorted(files.items()):
                if rel.startswith("/") or ".." in PurePosixPath(rel).parts or str(PurePosixPath(rel)) != rel:
                    raise Denied("REJECTED", "noncanonical artifact path")
                target = staging / rel
                target.parent.mkdir(parents=True, exist_ok=True)
                with target.open("w") as stream:
                    stream.write(body)
                    stream.flush()
                    os.fsync(stream.fileno())
                target.chmod(0o400)
            if fail:
                raise Denied("VERIFICATION_FAILED", "injected interruption before publication")
            manifest = {
                "version": version,
                "tree_hash": digest(dict(files)),
                "origins": sorted(self.extra_origins[version]),
                "files": {
                    p: hashlib.sha256(body.encode("utf-8")).hexdigest() for p, body in sorted(files.items())
                },
            }
            (staging / "SSEVOH-MANIFEST.json").write_text(json.dumps(manifest, sort_keys=True))
            # The receipt is outside the editable tree and is omitted from execution copies.
            destination = self.root / "bundles" / str(version)
            destination.parent.mkdir(exist_ok=True)
            os.replace(staging, destination)
            return destination
        finally:
            if staging.exists():
                shutil.rmtree(staging)

    @staticmethod
    def _status(exc):
        text = str(exc)
        if "REVALIDATION" in text or "stale" in text:
            return "REQUIRES_REVALIDATION"
        if "missing independent validator" in text:
            return "INSUFFICIENT_EVIDENCE"
        if "validator" in text or "verification" in text:
            return "VERIFICATION_FAILED"
        return getattr(exc, "status", "REJECTED")

    def prepare(self, base_version, files, principal, *, sources=()):
        with self.lock:
            version = self.next_version
            self.next_version += 1
            try:
                self._attest()
                if principal != self.policy.principal:
                    raise Denied("REJECTED", "principal lacks operator grant")
                self._switch(base_version, principal)
                files = dict(files)
                if any(not isinstance(k, str) or not isinstance(v, str) for k, v in files.items()):
                    raise Denied("REJECTED", "tree must map canonical paths to text")
                if len(files) > 100 or sum(len(v) for v in files.values()) > 500_000:
                    raise Denied("REJECTED", "bounded artifact domain exceeded")
                for path in set(files) | set(self.base):
                    if files.get(path) != self.base.get(path) and (
                        path in self.policy.protected
                        or not any(fnmatch.fnmatchcase(path, p) for p in self.policy.editable)
                    ):
                        raise Denied("REJECTED", "operator protects path: " + path)
                for parent in sources:
                    if parent not in self._published:
                        raise Denied("INSUFFICIENT_EVIDENCE", "unknown exposure source")
                origins = set(self.extra_origins[base_version]) | {base_version}
                for parent in sources:
                    origins |= set(self.extra_origins[parent]) | {parent}
                self.trees[version] = MappingProxyType(files)
                self.extra_origins[version] = frozenset(origins)
                source = self._source("update", version)
                approval = self.engine.approve(source, principal)
                token = secrets.token_hex(32)
                self.pending[token] = (
                    approval,
                    version,
                    digest(files),
                    self.engine.state.fingerprint(),
                    source,
                    digest(sorted(origins)),
                )
                event = self._event(
                    "APPROVED",
                    version,
                    candidate=digest(files),
                    base_version=base_version,
                    origins=sorted(origins),
                    specification=source,
                    evidence=list(approval.evidence),
                    verification={
                        "metadata_safe": True,
                        "artifact_schema": True,
                        "executable_policy": self.policy.executable_policy,
                        "behavior_evidence": [
                            {"script": k, "ok": v[0], "reason": v[1]} for k, v in sorted(self._behavior_cache.items())
                        ],
                    },
                )
                return {**event, "token": token}
            except ValueError as exc:
                status = self._status(exc)
                self._event(status, version, str(exc))
                raise Denied(status, str(exc)) from exc

    def commit(self, token, *, fail_before_publish=False):
        with self.lock:
            if token not in self.pending:
                raise Denied("REJECTED", "unknown or consumed artifact approval")
            approval, version, sha, base, source, origin_sha = self.pending.pop(token)
            prior_version = self.engine.state.mapping()["harness"].version
            try:
                self._attest()
                if self.engine.state.fingerprint() != base:
                    raise Denied("REQUIRES_REVALIDATION", "artifact approval is stale")
                if digest(dict(self.trees[version])) != sha:
                    raise Denied("VERIFICATION_FAILED", "candidate bytes changed")
                if digest(sorted(self.extra_origins[version])) != origin_sha:
                    raise Denied("VERIFICATION_FAILED", "candidate origin binding changed")
                destination = self._stage_tree(version, self.trees[version], fail=fail_before_publish)
                try:
                    self.engine.deploy(approval)
                except ValueError:
                    shutil.rmtree(destination)
                    raise
                self._event(
                    "DEPLOYED",
                    version,
                    candidate=sha,
                    specification=source,
                    core_journal_head=self.engine.journal[-1]["hash"],
                    evidence=list(approval.evidence),
                )
                self._published_bindings[version] = digest([sha, origin_sha])
                self._published.add(version)
                return version
            except (OSError, ValueError) as exc:
                if (
                    self.engine.state.mapping()["harness"].version == version
                    and version not in self._published
                ):
                    self._switch(prior_version, self.policy.principal)
                status = self._status(exc) if isinstance(exc, ValueError) else "VERIFICATION_FAILED"
                try:
                    self._event(status, version, str(exc))
                except OSError:
                    pass  # Reporting I/O failure cannot authorize a missing receipt.
                raise Denied(status, str(exc)) from exc

    def admit(self, base_version, files, principal=None, *, sources=()):
        with self.lock:
            decision = self.prepare(base_version, files, principal or self.policy.principal, sources=sources)
            return self.commit(decision["token"])

    def _withdraw_checked(self, version, principal=None):
        with self.lock:
            self._attest()
            principal = principal or self.policy.principal
            self._switch(version, principal)
            source = self._source("withdraw", version)
            self.engine.deploy(self.engine.approve(source, principal))
            self._event("WITHDRAWN", version, core_journal_head=self.engine.journal[-1]["hash"])

    def _recover_checked(self, version, principal=None):
        with self.lock:
            self._attest()
            self._switch(version, principal or self.policy.principal)
            self._event(
                "RECOVERED",
                version,
                core_journal_head=self.engine.journal[-1]["hash"] if self.engine.journal else None,
            )
            return version

    def active(self, version):
        with self.lock:
            revoked = {v for n, v in self.engine.state.withdrawn if n == "harness"}
            return (
                version in self._published
                and self._published_bindings.get(version)
                == digest([digest(dict(self.trees[version])), digest(sorted(self.extra_origins[version]))])
                and (self.root / "bundles" / str(version)).is_dir()
                and not (({version} | set(self.extra_origins[version])) & revoked)
            )

    def _execute_checked(self, version, files, task_id, run_id, *, timeout=None):
        with self.lock:
            self._attest()
            if digest(dict(files)) != digest(dict(self.trees.get(version, {}))) or not self.active(version):
                raise Denied("VERIFICATION_FAILED", "unapproved, modified or withdrawn execution artifact")
            self._switch(version, self.policy.principal)
            # Re-read exact immutable catalog bytes, not the mutable upstream stage directory.
            bundle = self.root / "bundles" / str(version)
            if bundle.is_symlink() or any(path.is_symlink() for path in bundle.rglob("*")):
                raise Denied("VERIFICATION_FAILED", "symlink in published artifact")
            actual = {p: (bundle / p).read_text() for p in self.trees[version]}
            if any((bundle / p).is_symlink() for p in actual) or actual != dict(self.trees[version]):
                raise Denied("VERIFICATION_FAILED", "published artifact changed")
            from .models import ModelAdapter
            from .sandbox import catalog_member

            if not isinstance(self.adapter, ModelAdapter) and any(
                p.endswith(".py") and not catalog_member(b, self._adapter_catalog()) for p, b in actual.items()
            ):
                raise Denied("VERIFICATION_FAILED", "non-catalog program requires the sandboxed executor")
            execution_tree = self.root / "leases" / secrets.token_hex(12)
            ht.write_tree(self.surface, actual, execution_tree, stubs=False)
            self.run_versions[run_id] = version
            try:
                result = self.adapter.execute(task_id, execution_tree, run_id, timeout=timeout)
                activation_path = Path(result) / "activation.json"
                if type(self.adapter) is supported_adapter_types()[2] and not activation_path.is_file():
                    raise Denied("VERIFICATION_FAILED", "coding execution lacks an activation receipt")
                activation = (
                    json.loads(activation_path.read_text())
                    if activation_path.is_file()
                    else {
                        "available": True,
                        "reached": True,
                        "carried": True,
                        "path": "scripts/summarize.py",
                        "output": "answer.txt",
                    }
                )
                self._event(
                    "EXECUTED",
                    version,
                    run_id=run_id,
                    task_id=task_id,
                    candidate=digest(actual),
                    activation=activation,
                    scope=("data-only coding generation; solution not executed"
                           if type(self.adapter) is supported_adapter_types()[2]
                           else "catalog-restricted upstream local executor"),
                )
                return result
            finally:
                shutil.rmtree(execution_tree, ignore_errors=True)

    def _attempt(self, version, operation, function):
        with self.lock:
            try:
                return function()
            except (ValueError, OSError, subprocess.SubprocessError) as exc:
                status = self._status(exc) if isinstance(exc, ValueError) else "VERIFICATION_FAILED"
                self._event(status, version, str(exc), operation=operation)
                raise Denied(status, str(exc)) from exc

    def withdraw(self, version, principal=None):
        return self._attempt(version, "withdraw", lambda: self._withdraw_checked(version, principal))

    def recover(self, version, principal=None):
        return self._attempt(version, "rollback", lambda: self._recover_checked(version, principal))

    def execute(self, version, files, task_id, run_id, *, timeout=None):
        return self._attempt(
            version,
            "execute",
            lambda: self._execute_checked(version, files, task_id, run_id, timeout=timeout),
        )

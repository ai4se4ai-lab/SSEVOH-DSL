"""Data-only model channels: no generated shell commands or arbitrary executable tools."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from harness2.core import context
from harness2.core import tree as ht
from harness2.core.proposer import Proposer, Reply
from harness2.core.spec import ChannelSpec
from harness2.demo import DemoAdapter

from ssevoh.model import digest


class ModelProposer(Proposer):
    def __init__(self, model, client):
        super().__init__(ChannelSpec("opencode", "local/" + model))
        self.client = client
        self.generated = []

    def call(self, mission, context_dir, label, **kwargs):
        root = Path(context_dir)
        context.assert_no_grader_verdicts(root)
        files = {}
        for path in sorted(root.rglob("*")):
            if path.is_symlink():
                raise ValueError("Model context may not contain symlinks")
            if path.is_file():
                files[path.relative_to(root).as_posix()] = path.read_text()
        if sum(len(v) for v in files.values()) > 200_000:
            raise ValueError("Context exceeds declared model protocol bound")
        reflection = label.startswith("experience.")
        selection = label.startswith("select.")
        if reflection:
            schema = 'Return JSON {"edits":[{"component":"path","candidates":"inv1","change":"observed edit","observed":"actual contrast","verdict":"helped|no observed effect|mixed"}],"experience":{"cue":"condition","lesson":"lesson","evidence":"observed contrast","confidence":"scope"}}; use {"no_entry":true} when unsupported.'
        elif selection:
            schema = 'Return JSON {"choice":"existing candidate identifier","why":"evidence"}. Do not create a new deliverable.'
        else:
            schema = 'Return JSON {"files":{"relative/path":"complete replacement text"},"notes":"reason from the observed evidence"}. Edit only existing supported harness surfaces. Omitted files are inherited. No shell commands. Propose actual file edits; a refusal may use an empty files object.'
        prompt = (
            schema
            + "\nMISSION:\n"
            + mission.replace(str(root), "context")
            + "\nFILES:\n"
            + json.dumps(files, sort_keys=True)
        )
        raw = self.client(prompt, label)
        text = raw.get("response", "")
        record = {
            "label": label,
            "raw": text,
            "parsed": False,
            "role": "reflection" if reflection else "selection" if selection else "edit",
        }
        self.generated.append(record)
        try:
            payload = json.loads(text)
        except (TypeError, ValueError):
            payload = None
        workspace = None
        if not isinstance(payload, dict):
            reply = Reply(label, text or "invalid JSON", True, attempts=1, workspace=None)
        elif selection:
            record["parsed"] = True
            reply = Reply(
                label,
                f"<why>{payload.get('why', '')}</why>\n```choice\n{payload.get('choice', '')}\n```",
                True,
                attempts=1,
            )
        elif reflection:
            record["parsed"] = True
            if payload.get("no_entry"):
                response = "NO_ENTRY"
            else:
                edits = payload.get("edits", [])
                experience = payload.get("experience", {})
                if (
                    not isinstance(edits, list)
                    or not all(isinstance(e, dict) for e in edits)
                    or not isinstance(experience, dict)
                ):
                    response = "NO_ENTRY"
                else:
                    response = (
                        "<edits>\n"
                        + "\n\n".join(
                            "\n".join(
                                f"{k}: {row.get(k, '')}"
                                for k in ("component", "candidates", "change", "observed", "verdict")
                            )
                            for row in edits
                        )
                        + "\n</edits>\n<experience>\n"
                        + "\n".join(
                            f"{k}: {experience.get(k, '')}"
                            for k in ("cue", "lesson", "evidence", "confidence")
                        )
                        + "\n</experience>"
                    )
            reply = Reply(label, response, True, attempts=1)
        else:
            edits = payload.get("files")
            if isinstance(edits, dict) and all(
                isinstance(p, str) and isinstance(b, str) for p, b in edits.items()
            ):
                # The context displays files under one "harness/" prefix; the trusted transport
                # records and strips exactly that alias (as the coding adapter does).
                aliases = {p: p[len("harness/"):] for p in edits if p.startswith("harness/")}
                stripped = {aliases.get(p, p): b for p, b in edits.items()}
                if aliases and len(stripped) == len(edits) and all(aliases.values()):
                    record["aliases"] = aliases
                    edits = stripped
                record.update(parsed=True, edits=edits)
                workspace = root.parent / "model-workspaces" / digest([label, text])[:24]
                if workspace.exists():
                    shutil.rmtree(workspace)
                workspace.parent.mkdir(exist_ok=True)
                shutil.copytree(root / "harness", workspace)
                for rel, body in edits.items():
                    try:
                        normalized = ht.normalize_rel(rel)
                        if normalized != rel or not normalized or "\x00" in rel or len(body) > 200_000:
                            raise ValueError("noncanonical path or oversized edit")
                    except ValueError:
                        # A harmless off-surface marker lets the original retry/reject path run.
                        (workspace / "REJECTED-PATH.json").write_text(json.dumps({"requested_path": rel}))
                        record["client_rejected_path"] = rel
                        break
                    dest = workspace / normalized
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    dest.write_text(body)
                reply = Reply(
                    label,
                    "<notes>" + str(payload.get("notes", "")) + "</notes>",
                    True,
                    attempts=1,
                    workspace=workspace,
                )
            else:
                reply = Reply(label, "invalid files object", True, attempts=1, workspace=None)
        self._calls.append(reply)
        return reply


class ModelAdapter(DemoAdapter):
    """A bounded model executor using the original ledger task/data and catalog tool.

    This is an added benchmark substrate, not a claim to reproduce OpenCode/Codex
    professional-benchmark results. Only run_summary and final text are model actions.
    """

    executor_protocols = ("v2", "v3")

    def __init__(self, root, client, *, executor_protocol="v2"):
        super().__init__(root)
        if executor_protocol not in self.executor_protocols:
            raise ValueError("Unknown executor protocol")
        self.client = client
        self.executor_protocol = executor_protocol
        self.executed_trees = []  # digests of every harness tree actually executed (all arms)

    def executable_catalog(self):
        """AST dumps of trusted programs that may run on the host; None means the ledger catalog."""
        return None

    def _final_prompt(self, task_id, tool_output):
        if self.executor_protocol == "v2":
            return (
                "The permitted summary tool returned:\n"
                + tool_output
                + '\nReturn JSON {"answer":<string>}, where <string> is the actual report the task asks for, '
                'not a placeholder. Preserve any numbers you decide to report exactly.'
            )
        # v3: the final turn restates the task, so the required answer form is visible
        # (v2 showed only the tool output and models answered in free prose).
        return (
            "TASK:\n" + self.task_prompt(task_id)
            + "\nThe permitted tool returned:\n" + tool_output
            + '\nReturn JSON {"answer":<string>}, where <string> is the report in exactly the form the task '
            "specifies. Preserve any numbers you decide to report exactly."
        )

    def execute(self, task_id, harness_dir, run_id, *, timeout=None):
        hdir = harness_dir or self.base_harness()
        files = ht.read_tree(self.substrate.surface(), hdir)
        self.executed_trees.append(digest(files))
        prompt = (
            # Executor protocol v2: schemas describe value types instead of quoting a
            # copyable placeholder string (v1 models returned the placeholder verbatim).
            'You are a ledger agent. Follow the supplied harness. Only two JSON actions exist: '
            '{"action":"run_summary"} invokes the supplied deterministic Python summary tool; '
            '{"action":"answer","answer":<string>} ends the task, where <string> is the actual report the task asks for.\n'
            + json.dumps(
                {
                    "task": self.task_prompt(task_id),
                    "ledger.csv": (self.task_files(task_id) / "ledger.csv").read_text(),
                    "harness": files,
                },
                sort_keys=True,
            )
        )
        first = self.client(prompt, "executor." + run_id + ".action")
        action = json.loads(first.get("response", "{}"))
        used_tool = False
        tool_output = None
        if action.get("action") == "run_summary":
            from .sandbox import catalog_member, run_tool

            script = (Path(hdir) / "scripts/summarize.py").read_text()
            if catalog_member(script, self.executable_catalog()):
                rd = super().execute(task_id, hdir, run_id, timeout=timeout)
                tool_output = (rd / "answer.txt").read_text()
            else:
                # Non-catalog programs never run on the host: only inside the qualified sandbox.
                self.execution_count += 1
                rd = self.root / "executions" / run_id
                rd.mkdir(parents=True, exist_ok=True)
                code, tool_output = run_tool(
                    script, (self.task_files(task_id) / "ledger.csv").read_text(), timeout=timeout or 10
                )
                if code != 0:
                    tool_output = f"[tool exited with status {code}]\n"
            used_tool = True
            second = self.client(self._final_prompt(task_id, tool_output), "executor." + run_id + ".final")
            answer = json.loads(second.get("response", "{}")).get("answer")
        elif action.get("action") == "answer":
            rd = self.root / "executions" / run_id
            rd.mkdir(parents=True, exist_ok=True)
            self.execution_count += 1
            answer = action.get("answer")
        else:
            raise ValueError("Unsupported model action")
        if not isinstance(answer, str) or len(answer) > 10_000:
            raise ValueError("Missing or oversized final answer")
        (rd / "answer.txt").write_text(answer)
        activation = {
            "available": True,
            "reached": used_tool,
            "carried": used_tool and tool_output.strip() in answer,
            "tool_output": tool_output,
            "final_answer": answer,
            "executor": "bounded Ollama ledger agent",
        }
        (rd / "activation.json").write_text(json.dumps(activation, sort_keys=True))
        (rd / "trajectory.md").write_text(
            "[ACTION] " + str(action) + "\n[OBSERVATION] " + str(tool_output) + "\n[FINAL] " + answer
        )
        return rd

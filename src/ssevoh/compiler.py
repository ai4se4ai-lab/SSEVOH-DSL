"""Located lexer, recursive-descent parser, semantic/type/policy compiler."""

import json
import re
from dataclasses import dataclass

from .model import Component, Evolution, Specification, State, structural_errors


class Diagnostic(ValueError):
    def __init__(self, category, message, line=1, column=1):
        self.category, self.line, self.column = category, line, column
        super().__init__(f"{category}:{line}:{column}: {message}")


@dataclass(frozen=True)
class Token:
    value: str
    line: int
    column: int


TOKEN = re.compile(r'\s+|\#[^\n]*|"(?:[^"\\]|\\.)*"|[A-Za-z_][A-Za-z_0-9.-]*|[0-9]+|[{}\[\],;]')
KINDS = {"skill", "memory", "tool", "workflow", "configuration", "policy", "verifier"}


def lex(source):
    result, pos, line, col = [], 0, 1, 1
    while pos < len(source):
        match = TOKEN.match(source, pos)
        if not match:
            raise Diagnostic("syntax", f"unexpected character {source[pos]!r}", line, col)
        value = match.group()
        if not value.isspace() and not value.startswith("#"):
            result.append(Token(value, line, col))
        lines = value.split("\n")
        line += len(lines) - 1
        col = len(lines[-1]) + 1 if len(lines) > 1 else col + len(value)
        pos = match.end()
    result.append(Token("<eof>", line, col))
    return result


class Parser:
    def __init__(self, source):
        self.tokens, self.i = lex(source), 0
        self.locations = {}

    def peek(self):
        return self.tokens[self.i].value

    def take(self, expected=None):
        token = self.tokens[self.i]
        if expected is not None and token.value != expected:
            self.fail("syntax", f"expected {expected!r}, got {token.value!r}")
        if token.value == "<eof>":
            self.fail("syntax", "unexpected end of specification")
        self.i += 1
        return token.value

    def fail(self, category, message, token=None):
        t = token or self.tokens[self.i]
        raise Diagnostic(category, message, t.line, t.column)

    def identifier(self):
        value = self.take()
        if not re.fullmatch(r"[A-Za-z_][A-Za-z_0-9.-]*", value):
            self.fail("type", f"expected identifier, got {value!r}", self.tokens[self.i - 1])
        return value

    def integer(self):
        value = self.take()
        if not value.isdigit() or int(value) < 1:
            self.fail("type", "version must be a positive integer", self.tokens[self.i - 1])
        return int(value)

    def names(self):
        self.take("[")
        result = []
        if self.peek() != "]":
            result.append(self.identifier())
            while self.peek() == ",":
                self.take(",")
                result.append(self.identifier())
        self.take("]")
        if len(set(result)) != len(result):
            self.fail("semantic", "duplicate list member")
        return tuple(result)

    def fields(self, evolution=False):
        self.take("{")
        result = {}
        while self.peek() != "}":
            key = self.identifier()
            if key in result:
                self.fail("semantic", f"duplicate field {key}")
            if key in {"depends", "parents", "capabilities", "requires"}:
                value = self.names()
            elif key in {"version", "from", "to"}:
                value = self.integer()
            elif key == "mutable":
                raw = self.take()
                if raw not in {"true", "false"}:
                    self.fail("type", "mutable must be true or false")
                value = raw == "true"
            elif evolution and key in {"operation", "target", "expect", "ensure"}:
                value = self.identifier()
            else:
                self.fail("semantic", f"unknown field {key}")
            result[key] = value
            self.take(";")
        self.take("}")
        return result

    def parse(self):
        self.take("harness")
        name = self.identifier()
        self.take("{")
        components, evolution = [], None
        while self.peek() != "}":
            at = self.tokens[self.i]
            declaration = self.take()
            if declaration == "component":
                cname, kind = self.identifier(), self.identifier()
                self.locations[cname] = at
                if kind not in KINDS:
                    self.fail("type", f"unknown component type {kind}", at)
                fields = self.fields()
                if "version" not in fields or set(fields) - {
                    "version",
                    "mutable",
                    "depends",
                    "parents",
                    "capabilities",
                }:
                    self.fail("semantic", "component requires version and component fields only", at)
                components.append(Component(cname, kind, **fields))
            elif declaration == "evolution":
                if evolution:
                    self.fail("semantic", "exactly one evolution is supported", at)
                ename, fields = self.identifier(), self.fields(True)
                self.locations["evolution"] = at
                required = {"operation", "target", "from", "to"}
                if required - fields.keys() or set(fields) - (
                    required | {"depends", "parents", "capabilities", "requires", "expect", "ensure"}
                ):
                    self.fail("semantic", "evolution requires operation, target, from, to", at)
                evolution = Evolution(
                    ename,
                    fields["operation"],
                    fields["target"],
                    fields["from"],
                    fields["to"],
                    fields.get("depends", ()),
                    fields.get("parents", ()),
                    fields.get("capabilities", ()),
                    fields.get("requires", ()),
                    fields.get("expect", "active"),
                    fields.get("ensure", "active"),
                )
            else:
                self.fail("syntax", "expected component or evolution", at)
        self.take("}")
        if self.peek() != "<eof>":
            self.fail("syntax", "trailing input")
        if evolution is None:
            self.fail("semantic", "missing evolution")
        return Specification(name, tuple(components), evolution)


def compile_source(source, policy=None, principal=None):
    parser = Parser(source)
    spec = parser.parse()
    issues = structural_errors(State(spec.components))
    e = spec.evolution
    cs = {c.name: c for c in spec.components}
    at = parser.locations["evolution"]
    if issues:
        parser.fail("semantic", "; ".join(issues), at)
    if e.target not in cs or any(n not in cs for n in e.depends + e.parents):
        parser.fail("semantic", "unknown evolution target/dependency/provenance", at)
    if e.operation not in {"update", "withdraw", "rollback"}:
        parser.fail("type", f"unsupported operation {e.operation}", at)
    if e.precondition not in {"active", "inactive", "any"} or e.postcondition not in {"active", "inactive"}:
        parser.fail("type", "unsupported pre/postcondition", at)
    if e.operation == "withdraw" and e.postcondition != "inactive":
        parser.fail("semantic", "withdraw requires ensure inactive", at)
    if e.expected != cs[e.target].version:
        parser.fail("semantic", "from version differs from declared snapshot", at)
    if not cs[e.target].mutable:
        parser.fail("policy", "immutable target", at)
    if e.operation == "update" and e.version <= e.expected:
        parser.fail("semantic", "update must increase version", at)
    if policy is not None:
        try:
            policy.authorize(principal, cs[e.target], e)
        except ValueError as exc:
            parser.fail("policy", str(exc), at)
    return spec


def ir_json(spec):
    return json.dumps(spec.ir(), indent=2, sort_keys=True)

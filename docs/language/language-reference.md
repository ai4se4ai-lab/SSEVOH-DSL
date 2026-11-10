# Language reference

Run `PYTHONPATH=src python -m ssevoh.cli compile examples/basic-evolution/example.sse`.
The compiled JSON is the intermediate representation; frozen Python dataclasses are the AST.

```text
harness assistant {
  component memory memory { version 1; mutable true; }
  component skill skill { version 1; mutable true; depends [memory]; }
  evolution improve {
    operation update; target skill; from 1; to 2;
    depends [memory]; parents []; capabilities [];
    requires [structure]; expect active; ensure active;
  }
}
```

Each field ends in `;`. Names contain letters, digits, underscores, dots or hyphens and begin with a letter or underscore. Lists contain comma-separated names. Comments start with `#`. Declarations and list members cannot be duplicated. A specification contains one harness snapshot and one evolution. See `grammar.ebnf`; the parser also accepts evolution declarations before component declarations.

| Construct | Meaning |
|---|---|
| component name kind | skill, memory, tool, workflow, configuration, policy or verifier |
| version | positive integer identity; update versions strictly increase and cannot reuse history |
| mutable | boolean, defaults true; policy/verifier types remain protected regardless |
| depends | required runtime components |
| parents | provenance ancestors; derivation cycles and unapproved ancestry removal are prohibited |
| capabilities | metadata capability names; bounded by operator policy |
| operation | update, withdraw, rollback |
| from / to | optimistic precondition / desired historical or new version |
| requires | registered independent validators, added to operator-required validators |
| expect | active, inactive or any; defaults active |
| ensure | active or inactive; withdrawal must explicitly ensure inactive |

The snapshot is checked against the trusted service state. It cannot replace that state. `requires [structure]` requests a validator; it is not a claim that validation passed. There is no DSL `grant`, policy editing, script, shell, evidence assertion or deployment command.

Diagnostics have `category:line:column: message`. Categories are syntax, semantic, type, policy. Runtime assurance rejections and verification failures are returned as explicit errors. Declaration-level semantic diagnostics point to the evolution declaration; token diagnostics point to the offending token. Precise per-field spans remain future work.

The language intentionally excludes arbitrary predicates, temporary grants, approval hierarchies, component creation/deletion, distributed commits, and production adapters. Supported pre/postconditions are finite enumerations, never evaluated expressions.

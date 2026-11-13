# Types and compiler passes

1. Regex lexer emits located tokens and rejects unrecognized characters.
2. Recursive descent constructs immutable Component, Evolution and Specification nodes.
3. Field checks reject duplicate/unknown fields and nonpositive versions; kinds are a closed enumeration.
4. Reference resolution checks targets, dependencies and provenance, then graph acyclicity.
5. Static checks reject immutable targets, stale declared versions and unsupported operations/conditions.
6. Operator policy checks authenticated principal, operation and capability ceiling.
7. `Specification.ir()` serializes the typed IR.
8. Assurance builds a candidate and translates it to an independent graph check and finite lifecycle inputs.

No inference of permissions from names or model explanations occurs. Source fields are metadata; they never become executable expressions.

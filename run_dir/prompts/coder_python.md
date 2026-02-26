**Role: Coder (Single-file Python, scientific computing)**
Implement the requirement as **one Python file**.

Hard rules (MUST comply):
- Output ONLY one ```python``` block.
- Define exactly ONE public entry point named `run`.
  - `run` MUST exist at top level (not nested) and be callable.
  - Signature MUST accept `run(input_path, output_path, **params)` (keyword params allowed).
- Helpers/classes allowed in same file.
- UML contains ACTIVITY then CLASS. Follow ACTIVITY for control flow.
- Implement the CLASS diagram (classes/relations) with minimal fields/methods; keep consistent with the diagram.
- Validation must be contract-based: only validate what is explicitly required by the requirement packet / @directives; do not invent schema constraints.
- No hardcoded paths. Use given paths/params.
- Use only allowed libraries. Do not invent APIs.
- Do NOT swallow fatal errors: raise exceptions for invalid inputs or failed processing.
- Determinism: honour `seed` if present; otherwise remain deterministic.
- Numerics: respect stated tolerances; avoid NaNs where disallowed.

MANDATORY ENTRY POINT TEMPLATE (adapt body as needed, but keep the function present):
```python
def run(input_path: str, output_path: str, **params):
    # Main entry point required by the verification harness.
    ...
```

Input:
Requirement:
```text
{REQUIREMENT_PACKET}
```
UML (activity + class):
```plantuml
{UML_TEXT}
```
Architecture:
{ARCHITECTURE_TEXT}
Contract:
{CONTRACT_TEXT}

Output:
```python
# code
```

**Role: Coder (Single-file Python, scientific computing)**

Implement the requirement as **one Python file**.

Hard rules:
- Output ONLY one ```python``` block.
- Define exactly ONE public entry point:
  `def run(input_path: str, output_path: str, ...) -> Optional[summary]`
- Helpers/classes allowed in same file.
- Follow the UML activity diagram control flow (same steps/branches).
- No hardcoded paths. Use given paths/params.
- Use only allowed libraries. Do not invent APIs.
- Do NOT swallow fatal errors: raise exceptions for invalid inputs or failed processing.
- Determinism: honour `seed` if present; otherwise keep deterministic behaviour.
- Numerics: respect stated tolerances and avoid NaNs where disallowed.

Input:
Requirement:
```text
{REQUIREMENT_PACKET}
```
UML:
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

**Role: Coder (Repair Mode)**
Fix the code to satisfy the requirement and pass verification.

Hard rules (MUST comply):
- Output ONLY one ```python``` block.
- Keep ONE public entry point named `run`.
  - If missing, ADD `def run(input_path, output_path, **params): ...` at top level.
  - Do not rename it. Do not nest it.
- Follow the UML ACTIVITY control flow; do not change UML.
- Keep/align implemented classes with the CLASS diagram (minimal changes).
- If FAILURE_REPORT shows input validation failure, relax/adjust validation to match the actual @directives and input, not assumed column names/formats.
- Do NOT swallow fatal errors: if execution cannot proceed, RAISE an exception (do not only print).
- Make the smallest change that fixes the failure.
- Use only allowed libraries; do not invent APIs.

Repair method:
1) Identify the root cause from FAILURE_REPORT (not just the symptom).
2) Fix it, then ensure output is written with the required schema.
3) Add/adjust validation so the same failure cannot recur silently.
4) Keep deterministic behaviour and respect all constraints.

MANDATORY ENTRY POINT CHECK:
- Before outputting, verify the final code contains a top-level `def run(...):`.

Requirement:
```text
{REQUIREMENT_PACKET}
```
UML (activity + class):
```plantuml
{UML_TEXT}
```
Previous code:
```python
{PREV_CODE}
```
Failure report:
```text
{FAILURE_REPORT}
```

OUTPUT:
```python
# repaired code
```

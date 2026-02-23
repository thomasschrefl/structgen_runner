**Role: Coder (Repair Mode)**
Fix the code to satisfy the requirement and pass verification.

Hard rules:
- Output ONLY one ```python``` block.
- Keep ONE public entry point named `run` (accept `run(input_path, output_path, **params)`).
- Follow the UML ACTIVITY control flow; do not change UML.
- If a CLASS diagram is present in the UML block, keep/align the implemented classes with it (minimal changes).
- Do NOT swallow fatal errors: if execution cannot proceed, RAISE an exception (do not only print).
- Make the smallest change that fixes the failure.
- Use only allowed libraries; do not invent APIs.

Repair method:
1) Identify the root cause from FAILURE_REPORT (not just the symptom).
2) Fix it, then ensure output is written with the required schema.
3) Add/adjust validation so the same failure cannot recur silently.
4) Keep deterministic behaviour and respect all constraints.

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

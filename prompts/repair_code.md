**Role: Coder (Repair Mode)**

You are given:
- The original requirement packet
- The current PlantUML activity diagram (do NOT change it)
- The previous code
- A verification failure report

Fix the code so it satisfies the requirement and passes verification.

STRICT OUTPUT:
- Output ONLY one ```python``` fenced code block. No prose.
- Keep exactly ONE public entry-point: run(...)

Requirement:
```text
{REQUIREMENT_PACKET}
```

UML:
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

Output:
```python
# repaired code here
```

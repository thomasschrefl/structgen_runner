**Role: Coder (Python scientific computing; numpy/scipy/pandas/sklearn allowed)**

Implement the requirement as a single Python file.

Hard rules:
- Output ONLY one ```python``` fenced code block. No prose.
- Define exactly ONE public entry-point function:
    def run(input_path, output_path, ...) -> Optional[summary]
- You MAY define helper functions and/or classes in the same file.
- Follow the PlantUML activity diagram control flow exactly (no missing steps).
- Implement I/O validation branches exactly as designed.
- Use suitable libraries (numpy/scipy/pandas/scikit-learn/scikit-optimize/etc.) as needed.
- Determinism:
  - If a seed parameter exists, set numpy/random/random_state consistently.
- Numerics:
  - Use abs/rel tolerances from the Contract (np.isclose/np.allclose).
- File I/O:
  - No hardcoded paths; use input_path/output_path and provided parameters.
  - Write outputs in the specified format and schema.

INPUTS:
Requirement packet:
```text
{REQUIREMENT_PACKET}
```

Process logic (UML activity diagram):
```plantuml
{UML_TEXT}
```

Architecture:
{ARCHITECTURE_TEXT}

I/O & Verification Contract:
{CONTRACT_TEXT}

If there are example outputs and/or partial constraints in the requirement packet, satisfy them.

OUTPUT:
```python
# single-file implementation
```

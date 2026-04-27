# StructGen Runner v2 (UML → Python with Verification)

StructGen Runner v2 is a **structured code generation** workflow that leverages Large Language Models (LLMs) to design, implement, and verify scientific Python modules. It follows a rigorous multi-stage process to ensure that the generated code is not only syntactically correct but also meets numerical and functional requirements.

## Core Workflow

1.  **Design Phase**: The LLM acts as a Designer, creating:
    *   **Activity Diagram**: High-level control flow (validation, processing, output).
    *   **Class Diagram**: Structural components and relationships.
    *   **Architecture**: Lightweight description of helper functions and responsibilities.
    *   **Verification Contract**: Detailed I/O schema and invariants.
2.  **UML Validation**: Diagrams are rendered via PlantUML. If syntax errors are found, an auto-repair loop fixes them before proceeding.
3.  **Implementation Phase**: A Coder LLM implements the design as a single-file Python module with a standardized `run(input_path, output_path, **params)` entry point.
4.  **Verification Phase**: The code is executed against a **Verification DSL** (Directives like `@check`, `@params`). It uses `pandas` and `numpy` to validate the output CSV.
5.  **Iterative Repair**: If verification fails, the runner automatically attempts code repairs. If code repair fails repeatedly, it triggers a design revision to rethink the solution.

---

## Key Features

-   **Standardized Entry Point**: Every module must implement `run(input_path, output_path, **params)`.
-   **Verification DSL**: Machine-readable requirements embedded in the prompt using `@` directives.
-   **Prompt Guardrails**: Automatic estimation and compression of prompts to stay within model token limits.
-   **Persistent Artifacts**: Successful runs generate a `test_run/` folder containing the produced output and a `run_test_output.py` reproduction script.
-   **UML Auto-Repair**: Ensures that visual documentation is always valid and renderable.

---

## Project Structure

```text
.
├── environment.yml          # Project-wide dependencies (micromamba/conda)
├── container/               # Containerized execution environment
│   ├── Containerfile
│   └── environment.yml
├── examples/                # Reference examples and test data
│   ├── input_01_sensor.csv
│   ├── requirements_01.txt  # Task with verification directives
│   └── ...
└── run_dir/                 # Active execution directory (all scripts run here)
    ├── structgen_run_v2.py  # Main runner script
    ├── structgen_config.json # LLM and environment config
    ├── plantuml.jar         # PlantUML rendering engine (Java required)
    ├── requirements.txt     # The task file currently being processed
    └── prompts/             # System prompt templates
```

---

## Getting Started

### 1. Prerequisites
- **Python 3.10+** with `numpy` and `pandas`.
- **Java (OpenJDK)** for PlantUML rendering.
- **LLM Endpoint**: An OpenAI-compatible API (e.g., `llama-server`, `vLLM`, or OpenAI).

### 2. Configuration
Edit `run_dir/structgen_config.json` to point to your LLM:
```json
{
  "base_url": "http://localhost:8000/v1",
  "model": "your-model-name"
}
```

### 3. Running an Example
To run one of the included examples:
```bash
# 1. Copy example files to the execution directory
cp examples/requirements_01.txt run_dir/requirements.txt
cp examples/input_01_sensor.csv run_dir/

# 2. Run the generator (from the run_dir)
cd run_dir
python structgen_run_v2.py
```

---

## Execution Modes

### Local Execution
Ensure you have activated your environment:
```bash
micromamba activate structgen-v2
cd run_dir
python structgen_run_v2.py --out out_local
```

### Containerized Execution (Recommended)
Running in a container provides security isolation for generated code.
```bash
# Build (once)
cd container
podman build -t structgen-v2:py311 .

# Run (from run_dir)
cd ../run_dir
podman run --rm -it \
  --userns=keep-id \
  --user "$(id -u):$(id -g)" \
  -v "$PWD:/work:rw" \
  -w /work \
  structgen-v2:py311 \
  python structgen_run_v2.py
```

---

## Example Library

The `examples/` directory demonstrates the Verification DSL:

| Example | Task | Key Directives |
| :--- | :--- | :--- |
| **01: Sensor Denoising** | Rolling median + moving average filters. | `@params: window_size=5`, `@check: rms(value_denoised) <= rms(value_raw)` |
| **02: Poly Fit** | Fits a polynomial regression of degree `N`. | `@params: degree=2`, `@check: rms(residual) < 2.0` |
| **03: Irregular Resampling** | Linear interpolation to a regular grid. | `@params: dt=0.5`, `@check: finite(v_interp)` |
| **04: Group Aggregation** | Categorical grouping and z-score normalization. | `@output_schema: group,measurement,group_mean,group_std,z` |

---

## Verification DSL Reference

Directives are parsed from `requirements.txt`. Each must be on its own line.

| Directive | Purpose | Example |
| :--- | :--- | :--- |
| `@input_file` | Source CSV path (relative to requirements.txt). | `@input_file: input.csv` |
| `@output_file` | Expected output filename. | `@output_file: output.csv` |
| `@params` | Kwargs passed to the Python `run()` function. | `@params: k1=v1, k2=v2` |
| `@output_schema` | List of columns that MUST exist in the output. | `@output_schema: colA, colB` |
| `@check` | Numerical or structural assertion. | `@check: mean(col) ~= 1.0` |

**Supported `@check` functions**: 
- `columns(a,b,...)`, `finite(a,b,...)`
- `mean(col)`, `std(col)`, `min(col)`, `max(col)`, `rms(col)`, `unique(col)`, `count()`
- Operators: `==`, `!=`, `<`, `>`, `<=`, `>=`, `~=` (approximate)
- Tolerance keywords: `abs_tol=1e-5`, `rel_tol=1e-3`

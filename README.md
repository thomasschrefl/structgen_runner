# StructGen Runner v2 (UML → Python with Verification)

StructGen Runner v2 is an automated **structured code generation** framework. It uses Large Language Models (LLMs) to transform natural language requirements into verified, production-ready scientific Python modules through a formal design-first approach.

The core philosophy of StructGen is that **design precedes code**. By forcing the LLM to create and validate PlantUML diagrams before writing a single line of Python, the runner ensures the model has a consistent mental model of the task's logic and data structures.

---

## The Generation Sequence

The runner executes a multi-agent workflow (Designer -> Coder -> Verifier) with automated feedback loops:

### 1. Task Initialization
The runner parses `requirements.txt`. Multiple tasks can be defined in a single file, separated by `---` lines.

### 2. Design Phase (The Designer)
The LLM acts as a software architect to produce:
*   **Activity Diagram**: A PlantUML flow defining input validation, processing steps, and error handling.
*   **Class Diagram**: A PlantUML structure defining the internal data models and helper classes.
*   **Architecture Bullets**: A lightweight description of component responsibilities.
*   **Verification Contract**: A formal definition of I/O expectations.

### 3. UML Validation & Rendering
The runner performs automated quality control on the design:
*   **Syntax Check**: Uses `plantuml -checkonly` to find syntax errors.
*   **Auto-Repair**: If the UML is invalid, a specialized repair prompt is used to fix the syntax (up to `max_uml_repairs` times).
*   **Rendering**: Generates `.png` diagrams for human review in the output folder.

### 4. Implementation Phase (The Coder)
The LLM receives the **validated design** and the original requirements. It must:
*   Produce a single Python file.
*   Implement exactly one public entry point: `def run(input_path, output_path, **params)`.
*   Adhere strictly to the logic defined in the Activity diagram.

### 5. Automated Verification (The Harness)
The runner executes the generated code in a sandboxed temporary environment:
*   **Directives Parsing**: Extracts `@check`, `@params`, and `@output_schema` from the requirement packet.
*   **Execution**: Calls the `run()` function with the specified parameters.
*   **Assertions**: Uses `pandas` and `numpy` to verify output CSVs against the contract (e.g., checking means, RMS, column existence, or finiteness).
*   **Capture**: Logs all `stdout`, `stderr`, and full Python tracebacks for debugging.

### 6. Feedback Loops
*   **Code Repair**: If verification fails, the LLM is given the failure report and traceback to fix the code (up to `max_code_repairs`).
*   **Design Revision**: If the code cannot be fixed, the runner asks the Designer to **revise the UML diagrams** to address the failure, effectively rethinking the solution.

---

## Key Features

-   **Design-First**: UML diagrams are used as the "source of truth" for code generation.
-   **Verification DSL**: Machine-readable requirements embedded in prompts using `@` directives.
-   **Prompt Guardrails**: Automatic estimation and compression of prompts to stay within model token limits.
-   **Persistent Artifacts**: Successful runs generate a `test_run/` folder containing the produced output and a `run_test_output.py` reproduction script.

---

## Project Structure

```text
.
├── environment.yml          # Project-wide dependencies (micromamba/conda)
├── container/               # Containerized execution environment
│   ├── Containerfile
│   └── environment.yml
├── examples/                # Reference examples and test data
└── run_dir/                 # Active execution directory
    ├── structgen_run_v2.py  # Main runner script
    ├── structgen_config.json # LLM and environment config
    ├── plantuml.jar         # PlantUML rendering engine
    ├── requirements.txt     # The task file currently being processed
    └── prompts/             # System prompt templates
```

---

## Configuration

`structgen_config.json` manages the connection to your LLM:

*   **`llm_provider`**: Choose between `"openai"` (default) or `"cli"`.
*   **`cli_command_template`**: For `"cli"` provider, define the shell command. 
    *   Supports placeholders: `{system}`, `{user}`, `{model}`.
    *   If `{user}` is omitted, the user prompt is passed via standard input (`stdin`).
    *   Example: `"gemini-cli chat --system {system}"` or `"claude-code -p {user}"`.
*   `base_url`: Endpoint URL for OpenAI provider (e.g., `http://localhost:8000/v1`).
*   `model`: The specific model to use (e.g., `qwen2.5-coder-32b-instruct`).
*   `prompt_token_budget`: Max tokens before auto-compression (e.g., `24000`).
*   `max_code_repairs`: Number of attempts to fix code before revising the design.

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

Directives are parsed from `requirements.txt`.

| Directive | Purpose | Example |
| :--- | :--- | :--- |
| `@input_file` | Source CSV path. | `@input_file: input.csv` |
| `@output_file` | Expected output filename. | `@output_file: output.csv` |
| `@params` | Kwargs passed to `run()`. | `@params: k1=v1, k2=v2` |
| `@output_schema` | Required output columns. | `@output_schema: colA, colB` |
| `@check` | Numerical/structural assertion. | `@check: mean(col) ~= 1.0` |

---

## Prerequisites

- **Python 3.10+** (Numpy & Pandas required)
- **Java (OpenJDK)** (for PlantUML)
- **OpenAI-compatible API** (e.g., `llama-server`, `vLLM`, `Ollama`)

# StructGen Runner v2 (UML → Python with Verification)

StructGen Runner v2 is a **structured code generation** workflow that uses an LLM to:

1. **Design** a solution as **two PlantUML diagrams** (ACTIVITY + CLASS) plus lightweight architecture and an I/O verification contract.
2. **Render** the diagrams to PNG
3. **Implement** the solution as a **single-file Python module** with a **required `run(input_path, output_path, **params)` entry point**.
4. **Verify** the generated code using a small **verification domain specific language** embedded in the requirement packet (`@input_file`, `@params`, `@check`, `@output_schema`, …).
5. **Iterate** automatically via code repair and (optionally) design revision until verification passes.

The main entry point is `structgen_run_v2.py`.

---

## Key Features

- **Two-diagram design**: always expects **two fenced `plantuml` blocks** (activity first, class second).
- **Verification**: parses `@input_file`, `@output_file`, `@params`, `@output_schema`, `@check` from the requirement packet to drive execution + checks.
- **Prompt-length guardrail**: estimates prompt size, auto-compresses long components using the same model endpoint, then continues.
- **Sample output**: after a successful task, the runner can materialise a persistent `test_run/` folder (output + reproducer script) depending on your current runner variant.

---


## Prerequisites

1. **Python environment** (recommended via micromamba, see below).
2. **Java (OpenJDK)** for PlantUML rendering.
3. **PlantUML jar** available at the path configured in `structgen_config.json` (default `./plantuml.jar`).
4. An **OpenAI-compatible LLM endpoint** (e.g., `llama-server`) reachable at the `base_url` configured in `structgen_config.json`.

---

## Run in a container

The script executes auto-generated python code. For the security reasons it is good if you run everything in a container.

### Install podman

Install podman   

```bash
sudo apt-get update
sudo apt-get install -y podman
```

Verify

```bash
podman --version
podman info
```

### Build the container

Change to the directory `container`.   

```bash
cd container
podman build --no-cache -t structgen-v2:py311 .
```

### Run inside the container

Change to `run_dir`, and create the directory for the output `out`
```bash
cd ../run_dir
mkdir -p out
```
and run inside the container
```bash
podman run --rm -it \
  --userns=keep-id \
  --user "$(id -u):$(id -g)" \
  --name structgen_v2_run \
  -e HOME=/tmp \
  -e XDG_CACHE_HOME=/tmp/.cache \
  -v "$PWD:/work:ro" \
  -v "$PWD/out:/work/out:rw" \
  -w /work \
  structgen-v2:py311 \
  python /work/structgen_run_v2.py
```


---

## File structure

The `run_dir` contains

```text
.
├─ structgen_run_v2.py
├─ structgen_config.json
├─ prompts/
│  ├─ designer_plantuml.md
│  ├─ revise_design.md
│  ├─ coder_python.md
│  ├─ repair_code.md
│  ├─ repair_uml.md
│  └─ repair_class_uml.md
├─ plantuml.jar
├─ requirements.txt
├─ input_03_irregular.csv
└─ out/
```

- `prompts/` contains the **role prompts** used by the designer/coder/repair loops. 
- `plantuml.jar` is required to validate and render diagrams (Java required). 
- `requirements.txt` is split into tasks using `---` separators. 


---

## Configuration

`structgen_config.json` defines how the runner connects to your model server and how it budgets prompts:

- `base_url`: OpenAI-compatible endpoint, including `/v1` (example: `http://promethium:8000/v1`).
- `model`: model name/alias served by the endpoint (example: `qwen2.5-coder-32b-instruct`).
- `max_tokens`: per-request completion cap (e.g. 4096).
- `prompt_token_budget` and `compress_target_tokens`: prompt guardrail and compression settings (tuned for long-context servers).
- `plantuml_jar_path`: path to PlantUML jar.

Example config (yours):

```json
{
  "base_url": "http://promethium:8000/v1",
  "api_key": "sk-no-key-required",
  "model": "qwen2.5-coder-32b-instruct",
  "temperature": 0.3,
  "top_p": 0.95,
  "max_tokens": 4096,
  "max_code_repairs": 3,
  "max_design_revisions": 3,
  "max_uml_repairs": 3,
  "plantuml_jar_path": "./plantuml.jar",
  "prompt_length_check": true,
  "prompt_token_budget": 24000,
  "compress_target_tokens": 6000
}
```

(Additional fields are supported; see your file.)

---

## How it Works (high level)

For each task in `requirements.txt`, the runner performs:

1. **Designer call** → returns:
   - PlantUML **ACTIVITY** diagram (block #1)
   - PlantUML **CLASS** diagram (block #2)
   - Architecture bullets
   - **IO and Verification Contract** section
2. **UML validation & rendering**:
   - Writes `*_activity.puml` and `*_class.puml`
   - Runs PlantUML `-checkonly` and renders `*.png`
   - Auto-repairs UML with the appropriate repair prompt per diagram if needed.
3. **Coder call**:
   - Receives **both diagrams concatenated** (`uml_both = activity + "\n\n" + class`).
   - Must output a **single `python` fenced block** implementing `run(input_path, output_path, **params)`.
4. **Verification**:
   - Compiles and imports the code
   - Executes `run(...)` with the contract-driven input/output/params
   - Evaluates `@check` and `@output_schema` rules using pandas/numpy
5. **Repair loop**:
   - On failure: call repair prompt with FAILURE_REPORT
   - Repeat up to `max_code_repairs`, then optionally revise design up to `max_design_revisions`.

---

## Requirement Packet Format (Verification)

### Requirements

`requirements.txt` can contain one or more tasks separated by a line containing `---`.

For examples please see `requirements.txt` and the **examples** directory 

### Verification directives 

`@input_file`, `@output_file`, `@params`, `@output_schema`, `@check`

In your `requirements.txt`, add an optional verification contract as plain-text directives—each directive must be on its own line starting with `@` in the form `@key: value` (only such `@...` lines are parsed).

| Directive | Purpose | Format | Notes / Examples |
|---|---|---|---|
| `@input_file` | Specifies the input file. If omitted, an empty placeholder input file is used.  | `@input_file: path/to/input.csv`  | relative to the directory containing `requirements.txt`.  |
| `@output_file` | Names the output CSV to be created. Defaults to `output.csv` if omitted.  | `@output_file: output.csv`  | File must exists as CSV.  |
| `@params` | Provides keyword parameters for `run(input_path, output_path, **params)`.  | `@params: k1=v1, k2=v2, ...`  | parsed using  (numbers, strings, lists, dicts), `true/false/none` (case-insensitive).  |
| `@output_schema` | Columns to exist in the output CSV.  | `@output_schema: colA, colB, colC`  | Fails verification if required column missing  |
| `@check` | Adds one or more assertions on the output CSV.  | `@check: <check_expression>`  | see following table  |
    
#### Output checks	
	
| `@check` form | What it validates | How it is evaluated | Notes |
|---|---|---|---|
| `columns(colA,colB,...)` | Required columns exist in the output CSV.  | Checks each listed name is present in `df.columns`.  | Use comma-separated column names (whitespace allowed).  |
| `finite(colA,colB,...)` | Output values are finite (no NaN/Inf) for selected columns.  | Converts each named column to float array and applies `np.isfinite` to all entries.  | Fails if any requested column is missing or contains NaN/Inf.  |
| `LEFT OP RIGHT` | Numeric assertion comparing two scalar expressions.  | Parses OP from the supported operator list; evaluates LEFT and RIGHT as scalars; then applies OP with optional tolerances.  | This is the general form used for aggregate checks (means, mins, counts, etc.).  |
| Supported operators | Defines allowed comparisons for `LEFT OP RIGHT`.  | Operators accepted: ~=, <=, >=, ==, !=, <, >.  | The approximate operator ~= uses absolute/relative tolerance.  |
| Optional tolerance keywords | Adds numeric tolerance for comparisons.  | Keywords accepted at end of check: `abs_tol=<value>` and/or `rel_tol=<value>`.  | For <= and >=, tolerances are also applied (see harness logic).  |
| `count()` | Number of rows in the output table.  | Evaluates to `len(df)` as a float.  | Use in comparisons, e.g., `count() >= 100`.  |
| `mean(col)` | Mean of a numeric column.  | Uses pandas mean on the named column.  | Column must exist.  |
| `std(col)` | Sample standard deviation of a numeric column.  | Uses pandas std with ddof=1.  | Column must exist.  |
| `min(col)` | Minimum of a numeric column.  | Uses pandas min on the named column.  | Column must exist.  |
| `max(col)` | Maximum of a numeric column.  | Uses pandas max on the named column.  | Column must exist.  |
| `rms(col)` | Root-mean-square of a numeric column.  | Converts column to float array and computes sqrt(mean(x^2)).  | Column must exist and be numeric-convertible.  |
| `unique(col)` | Number of unique values in a column.  | Uses pandas nunique (dropna=True) and returns as float.  | Column must exist.  |


#### Example

```text
@input_file: input_03_irregular.csv
@output_file: output.csv
@params: dt=0.1, method="linear"
@output_schema: t,y
@check: columns(t,y)
@check: finite(t,y)
@check: count() > 10
```

The runner parses these directives and uses them to execute and validate the generated solution.



---

## Quickstart (example included)

From the repository root (where `requirements.txt` and `input_03_irregular.csv` are located):

```bash
micromamba activate structgen-v2
python structgen_run_v2.py \
  --config structgen_config.json \
  --requirements requirements.txt \
  --prompts prompts \
  --out out
```

Outputs are written to `out/<task_slug>/`, including:

- `*_activity.puml` + `*_activity.png`
- `*_class.puml` + `*_class.png`
- `architecture.txt`, `contract.txt`
- `<task_slug>.py` (generated Python code)
- `last_verification.txt` (last verification report)
- `task.log` (per-task detailed log)
- `test_run` contains the generated output

The runner also writes a top-level `out/run.log`. 

---

## Prompts: what you must keep consistent

Because the pipeline expects **two diagrams**, keep these aligned:

- `designer_plantuml.md` must output **two** PlantUML blocks (ACTIVITY then CLASS). 
- `revise_design.md` should also output **two** PlantUML blocks, plus Architecture and IO/Verification Contract.
- The contract header is parsed as **`IO and Verification Contract:`**. 

If you change headings, update `extract_section(...)` calls accordingly. 

---

## Troubleshooting

### PlantUML not rendering

- Ensure `plantuml.jar` exists at `plantuml_jar_path` and Java is available.
- Typical error: `PlantUML jar not found` or `Java not found on PATH`.

### Missing required entry point: `run(...)`

- The runner requires a **top-level** function named `run`.
- The file includes a fast guard `has_toplevel_run` to trigger early repair if missing.

### Overly strict input validation in generated code

If verification fails with `Input validation failed`, consider:

- adding explicit input schema details to the requirement packet
- adding the short prompt rule: “Validation must be contract-based; do not invent schema constraints.”

The verification report in `last_verification.txt` includes a traceback to locate the failing validation.

---

## Security notes

- Setting `log_prompts=true` may write full prompts (requirements + code) to disk. Use only in trusted environments.
- The runner connects to an OpenAI-compatible endpoint using `base_url` and `api_key`. Ensure the endpoint is appropriately protected if exposed on a network.

---

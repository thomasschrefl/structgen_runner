# StructGen Runner (Ollama + PlantUML) — v1 & v2

This repository folder contains a **StructGen-inspired** automation runner for **Python-only** code generation for numerical/scientific computing.

The runner implements the core StructGen workflow:

1. **Designer** (LLM) creates a **PlantUML activity diagram** (the design scheme).
2. **Coder** (LLM) generates **Python code** guided by the UML.
3. A **verification step** produces feedback.
4. The system iterates:
   - **repair code** (Coder) first,
   - then **revise UML design** (Designer) if repeated repairs fail.

You can use **Version 1 (v1)** for minimal “sanity” verification, or **Version 2 (v2)** which adds a lightweight **verification contract DSL** embedded in your requirement text.

---

## Contents (Downloads)

### Core runner scripts
- **v1 runner**: `structgen_run.py` (download: provided earlier) citeturn15file26
- **v2 runner**: `structgen_run_v2.py` (download: provided earlier) citeturn20file32
- **v2 bundle** (runner + DSL rules): `structgen_runner_v2.zip` citeturn20file31

### Prompt template pack (editable)
- `structgen_prompts.zip` — contains:
  - `prompts/designer_plantuml.md`
  - `prompts/coder_python.md`
  - `prompts/repair_code.md`
  - `prompts/revise_design.md` citeturn15file27

### Example requirement bundles
- **v1 examples with CSV inputs**: `csv_requirements_with_inputs.zip` citeturn18file29
- **v2 examples with CSV inputs + contracts**: `csv_requirements_with_inputs_v2.zip` citeturn21file33

### v2 DSL specification
- `verifier_rules.md` — describes the `@...` directives and supported `@check:` forms citeturn20file30

---

## Quick start (common for both versions)

### 1) Folder layout

Recommended structure:

```text
project/
  structgen_run.py              # v1 runner
  structgen_run_v2.py           # v2 runner
  structgen_config.json         # Ollama + model configuration
  requirements.txt              # your natural-language requirements (tasks)
  prompts/
    designer_plantuml.md
    coder_python.md
    repair_code.md
    revise_design.md
  plantuml.jar                  # optional: for PNG rendering
  out/                          # generated outputs
```

> **Note:** This system uses `requirements.txt` for **your natural-language specs**. Many Python projects use `requirements.txt` for pip dependencies, so consider using a different file name for pip deps (e.g. `pip_requirements.txt`) to avoid confusion.

### 2) Install dependencies

Minimum (LLM calls):

```bash
pip install openai
```

For verification checks in **v2** you’ll also need:

```bash
pip install numpy pandas
```

### 3) Configure Ollama (OpenAI-compatible API)

Create `structgen_config.json` like:

```json
{
  "ollama_base_url": "http://localhost:11434/v1",
  "ollama_api_key": "ollama",
  "designer_model": "qwen2.5-coder:7b-instruct",
  "coder_model": "qwen2.5-coder:7b-instruct",
  "temperature": 0.2,
  "top_p": 0.95,
  "max_tokens": 4096,
  "max_code_repairs": 2,
  "max_design_revisions": 4,
  "plantuml_jar_path": "./plantuml.jar"
}
```

Ensure Ollama is running and your chosen model is available.

nohup env OLLAMA_CONTEXT_LENGTH=8192 ollama serve > ollama_serve.log 2>&1 &
disown

---

## Prompt templates (editable)

Prompt templates are plain text Markdown files under `prompts/`:

- `designer_plantuml.md` — prompts the Designer to produce:
  - PlantUML activity diagram,
  - architecture list,
  - verification contract text.
- `coder_python.md` — prompts the Coder to produce a **single Python file** with one public entry point `run(...)`.
- `repair_code.md` — used during code-repair iterations.
- `revise_design.md` — used during design-revision iterations.

You can modify these at any time to adjust behaviour and style. citeturn15file27

---

## Version 1 (v1): Minimal verification runner

### When to use v1
Use v1 if you:
- want a **simple pipeline** with very light verification,
- don’t have formal tests yet,
- want to focus on the Designer→Coder structure and manual review.

### What v1 verification does (and does not do)

**v1 verifier checks:**
- code compiles,
- code can be executed at import-time (no immediate crashes),
- a callable `run(...)` exists,
- optional `--smoke-test`: tries calling `run(input_path, output_path)` with placeholder files. citeturn15file26

**v1 verifier does NOT:**
- parse “OPTIONAL PARTIAL CONSTRAINTS / PROPERTIES” sections,
- execute your examples with tolerances,
- validate CSV schema or numeric properties automatically. citeturn15file26

This means text like:

```text
OPTIONAL PARTIAL CONSTRAINTS / PROPERTIES:
  - v_interp at original t values equals original v within abs_tol=1e-12 ...
```

is **not enforced** in v1; it is only guidance for the LLM in prompt text. citeturn15file26

### Run v1

```bash
python structgen_run.py --requirements requirements.txt --prompts prompts --out out
```

Optional smoke-test:

```bash
python structgen_run.py --requirements requirements.txt --prompts prompts --out out --smoke-test
```

### v1 outputs
Per task, outputs are created under `out/<task_slug>/`:
- `<task_slug>.puml` (PlantUML diagram text)
- `<task_slug>.png` (if Java + `plantuml.jar` are available)
- `<task_slug>.py` (generated code)
- `architecture.txt`, `contract.txt`
- `task.log` and a global `out/run.log` citeturn15file26

---

## Version 2 (v2): Verification contract DSL (recommended)

### Why v2 exists
In scientific computing you often have **partial constraints** (invariants, bounds, stability properties) and only sometimes exact I/O examples.

v2 adds a small **machine-readable contract** embedded in your requirement text so the runner can:
- run the generated function on a provided input file,
- check output schema and numeric properties,
- use failures as feedback to drive repair/revise iterations.

### v2 DSL: `@` directives inside the requirement
You can add lines starting with `@` anywhere in the requirement packet. Examples:

```text
@input_file: input_01_sensor.csv
@output_file: output.csv
@params: window_size=5
@output_schema: timestamp,value_raw,value_median,value_denoised
@check: columns(timestamp,value_raw,value_median,value_denoised)
@check: finite(value_raw,value_denoised)
@check: rms(value_denoised) <= rms(value_raw) rel_tol=1e-12
```

The full grammar is documented in `verifier_rules.md`. citeturn20file30turn20file32

### What v2 verification does
v2 will (if you provide an `@input_file` and/or `@check` lines):
1. create a sandbox temp directory,
2. copy the `@input_file` into it,
3. call `run(input_path, output_path, **@params)`,
4. read the output CSV,
5. apply `@output_schema` and `@check:` rules,
6. feed the failure report back into the Coder repair loop (and then Designer revision if needed). citeturn20file32

### Run v2

```bash
python structgen_run_v2.py --requirements requirements.txt --prompts prompts --out out
```

Optional `--smoke-test` (only relevant when *no* `@input_file` is provided):

```bash
python structgen_run_v2.py --requirements requirements.txt --prompts prompts --out out --smoke-test
```

### v2 dependencies
Contract checks require:

```bash
pip install numpy pandas
```

---

## Example bundles

### v1 CSV examples
The v1 bundle includes:
- `requirements_01.txt ... requirements_04.txt`
- `input_01_sensor.csv ... input_04_groups.csv`
- `README_examples.md` with usage notes citeturn18file29

### v2 CSV examples (with contract directives)
The v2 bundle includes the same inputs but each `requirements_XX.txt` also contains `@input_file`, `@params`, `@output_schema`, and `@check:` lines suitable for `structgen_run_v2.py`. citeturn21file33

---

## Choosing between v1 and v2

**Choose v1 if:**
- you want a minimal runner and will verify results manually,
- you are still exploring prompt design and workflows,
- you do not want to maintain explicit contracts.

**Choose v2 if:**
- you want automated iteration driven by numeric constraints and schema checks,
- you regularly have partial constraints (bounds, invariants, statistics),
- you want a scalable and auditable verification mechanism.

In practice: most scientific workflows move quickly from v1 → v2 once you decide on a few standard checks.

---

## Tips for writing requirements

1. Always specify the public entry point:

```text
def run(input_path: str, output_path: str, ...) -> dict | None
```

2. Keep file format and schema explicit (CSV columns, types).
3. If you can, add constraints as verifiable rules:
   - **v1:** plain text helps the LLM but is not enforced.
   - **v2:** use `@check:` statements for enforcement.
4. Use tolerances (`abs_tol`, `rel_tol`) for numeric comparisons.

---

## Troubleshooting

- **PNG not generated:** Install Java and provide `plantuml.jar` at the configured path. The runner will still write `.puml` if PNG rendering is unavailable. citeturn15file26turn20file32
- **v2 verification complains about numpy/pandas:** Install them via `pip install numpy pandas`. citeturn20file30turn20file32
- **Model errors:** Confirm Ollama is running and the model name matches one that is installed locally.

---

## Roadmap ideas (optional)

If you want to expand the v2 DSL for scientific computing, useful next checks often include:
- monotonicity checks,
- group-by constraints,
- dtype checks,
- multi-format support (Parquet/NPZ),
- differential checks (compare two generated candidates).

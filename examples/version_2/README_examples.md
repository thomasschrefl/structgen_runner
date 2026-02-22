# CSV Examples Bundle (for structgen_run_v2.py)

This ZIP contains four CSV-focused examples updated for **StructGen runner v2** (verification DSL).

## What's new vs v1
Each `requirements_XX.txt` includes a small *machine-readable* verification contract using `@` directives:
- `@input_file`, `@output_file`
- `@params` (arguments passed into `run()`)
- `@output_schema`
- `@check: ...`

The v2 runner reads these directives and verifies the generated code by:
1) copying the input CSV into a sandbox temp directory,
2) running `run(input_path, output_path, **params)`,
3) reading the output CSV and applying the checks.

## Contents
- `requirements_01.txt` + `input_01_sensor.csv`
- `requirements_02.txt` + `input_02_poly.csv`
- `requirements_03.txt` + `input_03_irregular.csv`
- `requirements_04.txt` + `input_04_groups.csv`

## How to run (one example at a time)
1) Copy one requirement file to `requirements.txt`:

```bash
cp requirements_01.txt requirements.txt
```

2) Run the v2 generator:

```bash
python structgen_run_v2.py --requirements requirements.txt --prompts prompts --out out
```

## Dependencies
For contract checks, install:

```bash
pip install numpy pandas
```

PNG rendering (optional): install Java and place `plantuml.jar` next to your runner.

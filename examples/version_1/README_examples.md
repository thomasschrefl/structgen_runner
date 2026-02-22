# CSV Examples Bundle

This ZIP contains four CSV-focused examples for `structgen_run.py`.

## Contents
- `requirements_01.txt` + `input_01_sensor.csv`
- `requirements_02.txt` + `input_02_poly.csv`
- `requirements_03.txt` + `input_03_irregular.csv`
- `requirements_04.txt` + `input_04_groups.csv`

Each requirement file describes a single task. The input CSV referenced in each file is included.

## How to run (one example at a time)
From your project folder (containing `structgen_run.py`, `structgen_config.json`, and `prompts/`):

1. Copy one of the requirement files to `requirements.txt` (your runner reads that name by default), e.g.:

```bash
cp requirements_01.txt requirements.txt
```

2. Run the generator:

```bash
python structgen_run.py --requirements requirements.txt --prompts prompts --out out
```

3. The generated outputs will appear under `out/<task_slug>/`:
- `*.puml` and (optionally) `*.png`
- `*.py`
- `task.log` and `out/run.log`

## Notes
- These examples assume CSV is comma-separated and UTF-8 encoded.
- Some tasks mention optional constraints or exact examples. If you later extend the verifier in `structgen_run.py`, you can enforce these automatically.

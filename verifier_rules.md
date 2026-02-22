# Verification DSL (Option B) — `@` directives inside a requirement packet

This document describes the *machine-readable* part of a requirement packet that the updated runner can parse and enforce.

The goal is to keep your requirements mostly natural language, while adding a small, stable subset of checkable rules.

## 1) Directives overview

Put directives anywhere in the requirement text as lines starting with `@`.

### 1.1 Input and output

- `@input_file: <filename>`
  - Path is resolved relative to the directory containing the requirements file.
  - The runner copies it into a temporary sandbox and passes that path to `run()`.

- `@output_file: <filename>`
  - Optional. Defaults to `output.csv`.
  - The runner passes this path to `run()` in the sandbox.

### 1.2 Parameters to `run()`

- `@params: key=value, key=value, ...`
  - Values may be:
    - numbers: `0.5`, `10`
    - booleans: `true`, `false`
    - None: `none`
    - quoted strings: `'not-a-knot'` or `"not-a-knot"`
    - unquoted words are treated as strings.

Example:

```text
@params: window_size=7, bc_type='not-a-knot', dt=0.5
```

### 1.3 Output schema hint

- `@output_schema: col1,col2,...`
  - Optional convenience check: ensures those columns exist in the output CSV.

## 2) Checks

Add one check per line:

- `@check: columns(col1,col2,...)`
  - Fails if any listed column is missing.

- `@check: finite(col1,col2,...)`
  - Fails if any listed column contains NaN/Inf.

- `@check: <expr> <op> <expr> [abs_tol=...] [rel_tol=...]`

Supported operators:
- `<= >= < > == != ~=`

`~=` means approximate equality:

```text
@check: mean(residual) ~= 0 abs_tol=1e-6
```

For inequalities (`<=`, `>=`), tolerances are applied in a conservative way.

### 2.1 Expressions

Expressions are deliberately simple and numeric.

Supported forms:
- numeric literals: `1`, `0.5`
- function calls:
  - `mean(col)`
  - `std(col)`  (sample std, ddof=1)
  - `min(col)`
  - `max(col)`
  - `rms(col)`
  - `unique(col)` (number of unique values)
- `count()` (number of rows)

Column names must match `[A-Za-z0-9_]`.

## 3) Example requirement snippet

```text
TITLE: Denoise sensor signal (CSV -> CSV)
GOAL:
  ...

@input_file: input_01_sensor.csv
@params: window_size=7
@output_schema: timestamp,value_raw,value_median,value_denoised
@check: columns(timestamp,value_raw,value_median,value_denoised)
@check: finite(value_raw,value_denoised)
@check: rms(value_denoised) <= rms(value_raw) rel_tol=1e-12
```

## 4) Dependencies

- Verification checks require `numpy` and `pandas`.
  Install via:

```bash
pip install numpy pandas
```

## 5) Extending the DSL

The runner is structured so you can add new checks in `_run_checks()`.
Common future extensions for scientific computing include:
- schema dtype checks
- monotonicity checks
- group-by checks (per-group constraints)
- CSV/Parquet/NPZ multi-format support

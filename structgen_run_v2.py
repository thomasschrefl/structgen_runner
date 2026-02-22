#!/usr/bin/env python3
"""StructGen-style automated code generation (v2) with UML syntax check + auto-repair and verification DSL.

Compared to v1:
- Supports a lightweight verification contract DSL in the requirement text using @directives.
- Uses those directives to run the generated function in a sandbox and apply checks to the output CSV.

UML robustness:
- Before rendering, performs PlantUML syntax check.
- If invalid, triggers UML repair with the Designer.
- Runs syntax-check + repair loop after EVERY Designer call (initial + revisions).
"""

from __future__ import annotations

import argparse
import ast
import json
import logging
import os
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from openai import OpenAI


# ----------------------------
# Helpers
# ----------------------------

def slugify(text: str, max_len: int = 80) -> str:
    text = text.strip().lower()
    text = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
    return (text[:max_len] if text else "task")


def read_text(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def write_text(path: str, content: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


def parse_tasks(requirements_text: str) -> List[str]:
    tasks: List[str] = []
    buf: List[str] = []
    for line in requirements_text.splitlines():
        if line.strip() == "---":
            chunk = "\n".join(buf).strip()
            if chunk:
                tasks.append(chunk)
            buf = []
        else:
            buf.append(line)
    chunk = "\n".join(buf).strip()
    if chunk:
        tasks.append(chunk)
    return tasks


def infer_title(requirement_packet: str) -> str:
    m = re.search(r"^\s*TITLE\s*:\s*(.+)$", requirement_packet, flags=re.MULTILINE | re.IGNORECASE)
    if m:
        return m.group(1).strip()
    for line in requirement_packet.splitlines():
        if line.strip():
            return line.strip()[:60]
    return "Untitled Task"


def extract_fenced_block(text: str, lang: str) -> Optional[str]:
    pattern = rf"```{re.escape(lang)}\s*(.*?)```"
    m = re.search(pattern, text, flags=re.DOTALL | re.IGNORECASE)
    return m.group(1).strip() if m else None


def extract_section(text: str, header: str) -> str:
    pattern = rf"{re.escape(header)}\s*\n(.*?)(\n[A-Z][A-Za-z0-9/& \-\(\)]+:\s*\n|\Z)"
    m = re.search(pattern, text, flags=re.DOTALL)
    return m.group(1).strip() if m else ""


def load_prompt(prompts_dir: str, filename: str) -> str:
    path = os.path.join(prompts_dir, filename)
    if not os.path.exists(path):
        raise FileNotFoundError(f"Missing prompt template: {path}")
    return read_text(path)


def load_prompt_optional(prompts_dir: str, filename: str) -> Optional[str]:
    path = os.path.join(prompts_dir, filename)
    return read_text(path) if os.path.exists(path) else None


# ----------------------------
# Config
# ----------------------------

@dataclass
class Config:
    ollama_base_url: str = "http://localhost:11434/v1"
    ollama_api_key: str = "ollama"

    designer_model: str = "qwen2.5-coder:7b-instruct"
    coder_model: str = "qwen2.5-coder:7b-instruct"

    temperature: float = 0.2
    top_p: float = 0.95
    max_tokens: int = 4096

    max_code_repairs: int = 2
    max_design_revisions: int = 4

    max_uml_repairs: int = 2

    plantuml_jar_path: str = "./plantuml.jar"

    smoke_test: bool = False

    @staticmethod
    def load(path: str) -> "Config":
        data = json.loads(read_text(path))
        cfg = Config()
        for k, v in data.items():
            if hasattr(cfg, k):
                setattr(cfg, k, v)
        return cfg


# ----------------------------
# LLM Client
# ----------------------------

class LLM:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.client = OpenAI(base_url=cfg.ollama_base_url, api_key=cfg.ollama_api_key)

    def chat(self, model: str, system: str, user: str) -> str:
        resp = self.client.chat.completions.create(
            model=model,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
            temperature=self.cfg.temperature,
            top_p=self.cfg.top_p,
            max_tokens=self.cfg.max_tokens,
        )
        return resp.choices[0].message.content


# ----------------------------
# PlantUML: syntax check + render
# ----------------------------

def plantuml_check(puml_path: str, plantuml_jar_path: str) -> Tuple[bool, str]:
    if not os.path.exists(plantuml_jar_path):
        return False, f"PlantUML jar not found at {plantuml_jar_path}"
    try:
        cmd = ["java", "-jar", plantuml_jar_path, "-checkonly", "-failonerror", puml_path]
        cp = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if cp.returncode != 0:
            err = (cp.stderr or cp.stdout or "").strip()
            if not err:
                err = "PlantUML syntax check failed (non-zero exit code)."
            return False, err
        return True, ""
    except FileNotFoundError:
        return False, "Java not found on PATH (install Java to enable UML checking/rendering)."


def plantuml_render_png(puml_path: str, png_path: str, plantuml_jar_path: str, logger: logging.Logger) -> Tuple[bool, str]:
    if not os.path.exists(plantuml_jar_path):
        return False, f"PlantUML jar not found at {plantuml_jar_path}"
    out_dir = os.path.dirname(png_path)
    os.makedirs(out_dir, exist_ok=True)
    try:
        # cmd = ["java", "-jar", plantuml_jar_path, "-failonerror", "-noerror", "-tpng", puml_path, "-o", out_dir]
        cmd = ["java", "-jar", plantuml_jar_path, "-failonerror", "-noerror", "-tpng", puml_path]
        logger.info("PlantUML render: %s", " ".join(cmd))
        cp = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if cp.returncode != 0:
            err = (cp.stderr or cp.stdout or "").strip()
            if not err:
                err = "PlantUML render failed (non-zero exit code)."
            return False, err
        base = os.path.splitext(os.path.basename(puml_path))[0]
        # produced = os.path.join(out_dir, base + ".png")
        produced = os.path.join(os.path.dirname(puml_path), base + ".png")
        if os.path.exists(produced):
            if os.path.abspath(produced) != os.path.abspath(png_path):
                shutil.move(produced, png_path)
            return True, ""
        return False, "PlantUML did not produce an output PNG."
    except FileNotFoundError:
        return False, "Java not found on PATH (install Java to enable PNG rendering)."


def build_repair_uml_prompt(requirement_packet: str, uml_text: str, plantuml_error: str, template: Optional[str]) -> str:
    if template:
        return template.format(REQUIREMENT_PACKET=requirement_packet, UML_TEXT=uml_text, PLANTUML_ERROR=plantuml_error)
    return (
        "Role: Designer (UML Repair Mode)\n\n"
        "PlantUML reported syntax errors for the following ACTIVITY DIAGRAM.\n"
        "Fix ONLY the PlantUML syntax so it renders. Do NOT switch diagram types.\n"
        "Use activity syntax: start/stop, :actions;, if/endif, while/endwhile, repeat/repeat while.\n"
        "Do NOT use arrows (->), do/end while, or missing semicolons on actions.\n\n"
        "PlantUML error:\n"
        f"{plantuml_error}\n\n"
        "Requirement packet:\n"
        f"{requirement_packet}\n\n"
        "Previous UML:\n"
        f"```plantuml\n{uml_text}\n```\n\n"
        "STRICT OUTPUT: Output ONLY one fenced ```plantuml``` block containing a valid activity diagram.\n"
    )


def ensure_valid_uml(llm: LLM, cfg: Config, requirement_packet: str, uml_text: str, puml_path: str, prompts_dir: str, logger: logging.Logger) -> Tuple[str, bool, str]:
    repair_tpl = load_prompt_optional(prompts_dir, "repair_uml.md")
    current = uml_text
    last_err = ""

    for attempt in range(cfg.max_uml_repairs + 1):
        write_text(puml_path, current + "\n")
        ok, err = plantuml_check(puml_path, cfg.plantuml_jar_path)
        if ok:
            return current, True, ""

        last_err = err
        logger.info("UML syntax check failed (attempt %d/%d): %s", attempt + 1, cfg.max_uml_repairs + 1, err)
        if attempt >= cfg.max_uml_repairs:
            break

        prompt = build_repair_uml_prompt(requirement_packet, current, err, repair_tpl)
        repair_out = llm.chat(
            model=cfg.designer_model,
            system="You repair PlantUML activity diagrams to be syntactically valid.",
            user=prompt,
        )
        repaired = extract_fenced_block(repair_out, "plantuml")
        if repaired:
            current = repaired
        else:
            write_text(os.path.join(os.path.dirname(puml_path), f"uml_repair_raw_{attempt+1}.txt"), repair_out)
            break

    return current, False, last_err


# ----------------------------
# Verification DSL
# ----------------------------

@dataclass
class Contract:
    input_file: Optional[str] = None
    output_file: Optional[str] = None
    params: Dict[str, Any] = None
    output_schema: Optional[List[str]] = None
    checks: List[str] = None

    def __post_init__(self):
        if self.params is None:
            self.params = {}
        if self.checks is None:
            self.checks = []


def _parse_value(s: str) -> Any:
    s = s.strip()
    if not s:
        return ""
    try:
        return ast.literal_eval(s)
    except Exception:
        low = s.lower()
        if low == "true":
            return True
        if low == "false":
            return False
        if low in ("none", "null"):
            return None
        if (s.startswith('"') and s.endswith('"')) or (s.startswith("'") and s.endswith("'")):
            return s[1:-1]
        return s


def parse_contract(requirement_packet: str) -> Contract:
    c = Contract()
    for raw in requirement_packet.splitlines():
        line = raw.strip()
        if not line.startswith("@"):  # only directives
            continue
        m = re.match(r"^@([a-zA-Z_]+)\s*:\s*(.*)$", line)
        if not m:
            continue
        key = m.group(1).lower()
        val = m.group(2).strip()
        if key == "input_file":
            c.input_file = val
        elif key == "output_file":
            c.output_file = val
        elif key == "output_schema":
            c.output_schema = [x.strip() for x in val.split(",") if x.strip()]
        elif key == "params":
            parts = [p.strip() for p in val.split(",") if p.strip()]
            for p in parts:
                if "=" in p:
                    k, v = p.split("=", 1)
                    c.params[k.strip()] = _parse_value(v)
        elif key == "check":
            c.checks.append(val)
    return c


def _require_numpy_pandas():
    try:
        import numpy as np  # type: ignore
        import pandas as pd  # type: ignore
        return np, pd
    except Exception as e:
        raise RuntimeError(
            "Verification requires numpy and pandas. Install them (pip install numpy pandas). "
            f"Original error: {e}"
        )


def _eval_expr(expr: str, df, np) -> float:
    expr = expr.strip()
    try:
        return float(expr)
    except Exception:
        pass

    fn_m = re.match(r"^(mean|std|min|max|rms|unique)\(([A-Za-z0-9_]+)\)$", expr)
    if fn_m:
        fn, col = fn_m.group(1), fn_m.group(2)
        if col not in df.columns:
            raise ValueError(f"Unknown column '{col}' in expression '{expr}'")
        s = df[col]
        if fn == "mean":
            return float(s.mean())
        if fn == "std":
            return float(s.std(ddof=1))
        if fn == "min":
            return float(s.min())
        if fn == "max":
            return float(s.max())
        if fn == "unique":
            return float(s.nunique(dropna=True))
        if fn == "rms":
            arr = s.to_numpy(dtype=float)
            return float(np.sqrt(np.mean(arr * arr)))

    if expr == "count()":
        return float(len(df))

    raise ValueError(f"Unsupported expression: '{expr}'")


def _parse_kwargs(tokens: List[str]) -> Tuple[List[str], Dict[str, Any]]:
    kwargs: Dict[str, Any] = {}
    rest = tokens[:]
    while rest and "=" in rest[-1]:
        t = rest.pop()
        k, v = t.split("=", 1)
        kwargs[k.strip()] = _parse_value(v)
    return rest, kwargs


def _run_checks(checks: List[str], output_path: str, contract: Contract) -> Tuple[bool, str]:
    np, pd = _require_numpy_pandas()

    if not os.path.exists(output_path):
        return False, f"Output file not created: {output_path}"

    try:
        df = pd.read_csv(output_path)
    except Exception as e:
        return False, f"Failed to read output CSV '{output_path}': {e}"

    if contract.output_schema:
        missing = [c for c in contract.output_schema if c not in df.columns]
        if missing:
            return False, f"Output schema missing columns {missing}; got columns={list(df.columns)}"

    for raw in checks:
        line = raw.strip()
        if not line:
            continue

        m = re.match(r"^columns\((.*?)\)$", line)
        if m:
            cols = [x.strip() for x in m.group(1).split(",") if x.strip()]
            missing = [c for c in cols if c not in df.columns]
            if missing:
                return False, f"Check failed: missing columns {missing}"
            continue

        m = re.match(r"^finite\((.*?)\)$", line)
        if m:
            cols = [x.strip() for x in m.group(1).split(",") if x.strip()]
            for c in cols:
                if c not in df.columns:
                    return False, f"Check failed: finite() refers to missing column '{c}'"
                arr = df[c].to_numpy(dtype=float)
                if not np.all(np.isfinite(arr)):
                    return False, f"Check failed: column '{c}' contains NaN/Inf"
            continue

        tokens = line.split()
        tokens2, kwargs = _parse_kwargs(tokens)
        cmp_str = " ".join(tokens2)

        ops = ["~=", "<=", ">=", "==", "!=", "<", ">"]
        op_found = None
        left = right = None
        for op in ops:
            if op in cmp_str:
                parts = cmp_str.split(op)
                if len(parts) == 2:
                    left, right = parts[0].strip(), parts[1].strip()
                    op_found = op
                    break
        if not op_found:
            return False, f"Unsupported check syntax: '{line}'"

        abs_tol = float(kwargs.get("abs_tol", 0.0))
        rel_tol = float(kwargs.get("rel_tol", 0.0))

        try:
            lv = _eval_expr(left, df, np)
            rv = _eval_expr(right, df, np)
        except Exception as e:
            return False, f"Check eval failed for '{line}': {e}"

        ok = True
        if op_found == "<":
            ok = lv < rv
        elif op_found == ">":
            ok = lv > rv
        elif op_found == "<=":
            ok = lv <= rv + abs_tol + rel_tol * abs(rv)
        elif op_found == ">=":
            ok = lv + abs_tol + rel_tol * abs(lv) >= rv
        elif op_found == "==":
            ok = lv == rv
        elif op_found == "!=":
            ok = lv != rv
        elif op_found == "~=":
            ok = abs(lv - rv) <= abs_tol + rel_tol * abs(rv)

        if not ok:
            return False, f"Check failed: '{line}' (left={lv}, right={rv}, abs_tol={abs_tol}, rel_tol={rel_tol})"

    return True, "All contract checks passed."


def verify_generated_code(code: str, requirement_packet: str, requirements_path: str, smoke_test: bool) -> Tuple[bool, str]:
    try:
        compiled = compile(code, "<generated>", "exec")
    except Exception as e:
        return False, f"Compilation error: {e}"

    ns: Dict[str, Any] = {}
    try:
        exec(compiled, ns, ns)
    except Exception as e:
        return False, f"Runtime error during module exec: {e}"

    run_fn = ns.get("run")
    if not callable(run_fn):
        return False, "Missing required entry point: run(...)"

    contract = parse_contract(requirement_packet)

    if (not contract.checks) and (not contract.input_file):
        if not smoke_test:
            return True, "Basic verification passed (compile + load + run present)."

    try:
        with tempfile.TemporaryDirectory() as tmp:
            if contract.input_file:
                req_dir = os.path.dirname(os.path.abspath(requirements_path))
                src = os.path.join(req_dir, contract.input_file)
                if not os.path.exists(src):
                    return False, f"Contract input file not found: {src}"
                input_path = os.path.join(tmp, os.path.basename(contract.input_file))
                shutil.copyfile(src, input_path)
            else:
                input_path = os.path.join(tmp, "input_placeholder")
                with open(input_path, "wb") as f:
                    f.write(b"")

            out_name = contract.output_file or "output.csv"
            output_path = os.path.join(tmp, out_name)

            try:
                run_fn(input_path, output_path, **(contract.params or {}))
            except TypeError as e:
                return False, f"Run invocation failed (parameter mismatch). Error: {e}"
            except Exception as e:
                return False, f"Run execution raised an exception: {e}"

            if contract.checks or contract.output_schema:
                return _run_checks(contract.checks or [], output_path, contract)

            if smoke_test:
                if not os.path.exists(output_path):
                    return False, "Smoke-test: output file was not created."
                return True, "Smoke-test passed (run executed and created output file)."

            return True, "Basic verification passed."

    except Exception as e:
        return False, f"Verification harness error: {e}"


# ----------------------------
# Orchestration
# ----------------------------

def setup_logger(log_path: str, also_console: bool = True) -> logging.Logger:
    logger = logging.getLogger(log_path)
    logger.setLevel(logging.INFO)
    logger.handlers.clear()

    fmt = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")

    if also_console:
        ch = logging.StreamHandler(sys.stdout)
        ch.setFormatter(fmt)
        logger.addHandler(ch)

    fh = logging.FileHandler(log_path, encoding="utf-8")
    fh.setFormatter(fmt)
    logger.addHandler(fh)

    return logger


def run_task(llm: LLM, cfg: Config, requirement_packet: str, requirements_path: str, prompts_dir: str, out_dir: str, logger: logging.Logger) -> None:
    title = infer_title(requirement_packet)
    task_slug = slugify(title)
    task_dir = os.path.join(out_dir, task_slug)
    os.makedirs(task_dir, exist_ok=True)

    task_logger = setup_logger(os.path.join(task_dir, "task.log"), also_console=False)

    def log(msg: str, *args: Any) -> None:
        logger.info("[%s] " + msg, task_slug, *args)
        task_logger.info(msg, *args)

    designer_tpl = load_prompt(prompts_dir, "designer_plantuml.md")
    coder_tpl = load_prompt(prompts_dir, "coder_python.md")
    repair_code_tpl = load_prompt(prompts_dir, "repair_code.md")
    revise_design_tpl = load_prompt(prompts_dir, "revise_design.md")

    log("=== Task started: %s ===", title)

    # ---- Designer call #1
    log("Calling Designer model: %s", cfg.designer_model)
    designer_out = llm.chat(
        model=cfg.designer_model,
        system="You are a careful software designer for scientific Python.",
        user=designer_tpl.format(REQUIREMENT_PACKET=requirement_packet),
    )

    uml = extract_fenced_block(designer_out, "plantuml")
    if not uml:
        write_text(os.path.join(task_dir, "designer_raw.txt"), designer_out)
        raise RuntimeError("Designer did not produce a PlantUML fenced block. See designer_raw.txt")

    architecture = extract_section(designer_out, "Architecture:")
    contract_txt = extract_section(designer_out, "I/O & Verification Contract:")

    puml_path = os.path.join(task_dir, f"{task_slug}.puml")
    png_path = os.path.join(task_dir, f"{task_slug}.png")

    # ---- UML syntax check + auto-repair (after Designer call)
    uml, uml_ok, uml_err = ensure_valid_uml(llm, cfg, requirement_packet, uml, puml_path, prompts_dir, logger)
    if uml_ok:
        ok, err = plantuml_render_png(puml_path, png_path, cfg.plantuml_jar_path, logger)
        if ok:
            log("Rendered UML PNG: %s", png_path)
        else:
            log("UML PNG not rendered: %s", err)
    else:
        log("UML syntax could not be fixed after retries. Last error: %s", uml_err)

    write_text(os.path.join(task_dir, "architecture.txt"), architecture + "\n")
    write_text(os.path.join(task_dir, "contract.txt"), contract_txt + "\n")

    # ---- Code generation
    log("Calling Coder model: %s", cfg.coder_model)
    coder_out = llm.chat(
        model=cfg.coder_model,
        system="You are a professional Python developer specialising in numerical/scientific computing.",
        user=coder_tpl.format(REQUIREMENT_PACKET=requirement_packet, UML_TEXT=uml, ARCHITECTURE_TEXT=architecture, CONTRACT_TEXT=contract_txt),
    )

    code = extract_fenced_block(coder_out, "python")
    if not code:
        write_text(os.path.join(task_dir, "coder_raw.txt"), coder_out)
        raise RuntimeError("Coder did not produce a Python fenced block. See coder_raw.txt")

    current_code = code
    current_uml = uml

    # ---- Iteration
    for design_rev in range(cfg.max_design_revisions + 1):
        for repair in range(cfg.max_code_repairs + 1):
            ok, report = verify_generated_code(current_code, requirement_packet, requirements_path, cfg.smoke_test)
            write_text(os.path.join(task_dir, "last_verification.txt"), report + "\n")
            log("Verification: %s", "PASS" if ok else "FAIL")
            log("Verification report: %s", report)

            if ok:
                py_path = os.path.join(task_dir, f"{task_slug}.py")
                write_text(py_path, current_code + "\n")
                log("Wrote generated code: %s", py_path)
                log("=== Task succeeded ===")
                return

            if repair >= cfg.max_code_repairs:
                break

            log("Repairing code (attempt %d/%d)", repair + 1, cfg.max_code_repairs)
            repair_out = llm.chat(
                model=cfg.coder_model,
                system="You repair scientific Python code based on verification feedback.",
                user=repair_code_tpl.format(REQUIREMENT_PACKET=requirement_packet, UML_TEXT=current_uml, PREV_CODE=current_code, FAILURE_REPORT=report),
            )
            repaired = extract_fenced_block(repair_out, "python")
            if repaired:
                current_code = repaired
            else:
                write_text(os.path.join(task_dir, f"repair_raw_{repair+1}.txt"), repair_out)

        if design_rev >= cfg.max_design_revisions:
            log("Max design revisions reached; writing best-effort outputs.")
            py_path = os.path.join(task_dir, f"{task_slug}.py")
            write_text(py_path, current_code + "\n")
            return

        # ---- Designer call (design revision)
        log("Revising design (attempt %d/%d)", design_rev + 1, cfg.max_design_revisions)
        revise_out = llm.chat(
            model=cfg.designer_model,
            system="You revise UML designs for scientific Python workflows.",
            user=revise_design_tpl.format(REQUIREMENT_PACKET=requirement_packet, UML_TEXT=current_uml, FAILURE_REPORT=read_text(os.path.join(task_dir, "last_verification.txt"))),
        )

        new_uml = extract_fenced_block(revise_out, "plantuml")
        if new_uml:
            current_uml = new_uml

            # ---- UML syntax check + auto-repair (after Designer call)
            current_uml, uml_ok, uml_err = ensure_valid_uml(llm, cfg, requirement_packet, current_uml, puml_path, prompts_dir, logger)
            if uml_ok:
                ok, err = plantuml_render_png(puml_path, png_path, cfg.plantuml_jar_path, logger)
                if ok:
                    log("Rendered UML PNG: %s", png_path)
                else:
                    log("UML PNG not rendered: %s", err)
            else:
                log("UML syntax could not be fixed after retries. Last error: %s", uml_err)
        else:
            write_text(os.path.join(task_dir, f"revise_raw_{design_rev+1}.txt"), revise_out)
            log("Design revision did not return PlantUML; keeping previous UML.")

        log("Regenerating code after design revision")
        coder_out = llm.chat(
            model=cfg.coder_model,
            system="You are a professional Python developer specialising in numerical/scientific computing.",
            user=coder_tpl.format(REQUIREMENT_PACKET=requirement_packet, UML_TEXT=current_uml, ARCHITECTURE_TEXT=architecture, CONTRACT_TEXT=contract_txt),
        )
        regen = extract_fenced_block(coder_out, "python")
        if regen:
            current_code = regen
        else:
            write_text(os.path.join(task_dir, f"coder_raw_after_design_{design_rev+1}.txt"), coder_out)


# ----------------------------
# CLI
# ----------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description="StructGen-style code generation (v2) with UML syntax check + auto-repair")
    parser.add_argument("--config", default="structgen_config.json")
    parser.add_argument("--requirements", default="requirements.txt")
    parser.add_argument("--prompts", default="prompts")
    parser.add_argument("--out", default="out")
    parser.add_argument("--smoke-test", action="store_true")

    args = parser.parse_args()

    cfg = Config.load(args.config)
    if args.smoke_test:
        cfg.smoke_test = True

    os.makedirs(args.out, exist_ok=True)
    logger = setup_logger(os.path.join(args.out, "run.log"), also_console=True)

    logger.info("Starting StructGen runner (v2)")
    logger.info("Requirements: %s", args.requirements)
    logger.info("Prompts dir: %s", args.prompts)
    logger.info("Output dir: %s", args.out)
    logger.info("Smoke test: %s", cfg.smoke_test)

    tasks = parse_tasks(read_text(args.requirements))
    logger.info("Found %d task(s)", len(tasks))

    llm = LLM(cfg)

    for i, task in enumerate(tasks, start=1):
        logger.info("Task %d/%d: %s", i, len(tasks), infer_title(task))
        try:
            run_task(llm, cfg, task, args.requirements, args.prompts, args.out, logger)
        except Exception as e:
            logger.exception("Task failed: %s", e)

    logger.info("All tasks processed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""StructGen-style automated code generation (Designer -> PlantUML -> Coder -> iterate).

- Reads natural-language tasks from requirements.txt (split by a line containing only '---')
- Uses Ollama via OpenAI-compatible API (http://localhost:11434/v1 by default)
- Produces per-task outputs:
    * UML diagram as PlantUML text (.puml)
    * UML diagram as PNG (.png) if PlantUML jar + Java are available
    * Generated Python file (.py) containing a single entry point: run(input_path, output_path, ...) -> Optional[summary]
    * Logs (global out/run.log and per-task task.log)

Prompt templates are read from ./prompts:
    - designer_plantuml.md
    - coder_python.md
    - repair_code.md
    - revise_design.md

Configuration is read from structgen_config.json.

NOTE: Verification is intentionally minimal by default (syntax + entry point + import-time execution).
      Extend verify_generated_code() for your domain-specific checks (examples, properties, schema validation).
"""

from __future__ import annotations

import argparse
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
    """Split tasks by a line containing only '---'."""
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
    # fallback: first non-empty line
    for line in requirement_packet.splitlines():
        if line.strip():
            return line.strip()[:60]
    return "Untitled Task"


def extract_fenced_block(text: str, lang: str) -> Optional[str]:
    """Extract the first fenced code block ```lang ... ``` (case-insensitive)."""
    pattern = rf"```{re.escape(lang)}\s*(.*?)```"
    m = re.search(pattern, text, flags=re.DOTALL | re.IGNORECASE)
    return m.group(1).strip() if m else None


def extract_section(text: str, header: str) -> str:
    """Extract content after a header like 'Architecture:' until the next header or end."""
    # Match 'Header:' then capture everything until next line that looks like 'Something:' or end.
    pattern = rf"{re.escape(header)}\s*\n(.*?)(\n[A-Z][A-Za-z0-9/& \-\(\)]+:\s*\n|\Z)"
    m = re.search(pattern, text, flags=re.DOTALL)
    return m.group(1).strip() if m else ""


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

    timeout_seconds: int = 180

    plantuml_jar_path: str = "./plantuml.jar"

    # If True, attempt a cautious smoke-test call to run() with placeholder files.
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
# PlantUML rendering
# ----------------------------

def render_plantuml_png(puml_path: str, png_path: str, plantuml_jar_path: str, logger: logging.Logger) -> bool:
    """Render PlantUML to PNG using local plantuml.jar + Java."""
    if not os.path.exists(plantuml_jar_path):
        logger.warning("PlantUML jar not found at %s; skipping PNG render.", plantuml_jar_path)
        return False

    out_dir = os.path.dirname(png_path)
    os.makedirs(out_dir, exist_ok=True)

    try:
        cmd = ["java", "-jar", plantuml_jar_path, "-tpng", puml_path, "-o", out_dir]
        logger.info("PlantUML render: %s", " ".join(cmd))
        subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

        base = os.path.splitext(os.path.basename(puml_path))[0]
        produced = os.path.join(out_dir, base + ".png")
        if os.path.exists(produced):
            if os.path.abspath(produced) != os.path.abspath(png_path):
                shutil.move(produced, png_path)
            return True

        logger.warning("PlantUML did not produce expected PNG: %s", produced)
        return False

    except FileNotFoundError:
        logger.warning("Java not found; cannot render PNG. Install Java to enable PNG rendering.")
        return False
    except subprocess.CalledProcessError as e:
        err = (e.stderr or "").strip()
        logger.warning("PlantUML render failed: %s", err[-1500:] if err else str(e))
        return False


# ----------------------------
# Verification
# ----------------------------

def verify_generated_code(code: str, smoke_test: bool, logger: logging.Logger) -> Tuple[bool, str]:
    """Minimal verification.

    Default checks:
      - Code compiles
      - Executes at import time (exec) without raising
      - Defines callable run

    Optional smoke test:
      - Calls run(input_path, output_path) with placeholder files inside a temp directory.

    Extend this function for domain-specific checks:
      - parse examples from requirement packet
      - validate output schema
      - property/metamorphic tests
      - differential checks
    """

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

    if not smoke_test:
        return True, "Basic verification passed (compile + load + run present)."

    # Cautious smoke test: run with placeholder paths.
    # For I/O heavy functions this may fail; treat as useful feedback.
    try:
        import inspect

        sig = inspect.signature(run_fn)
        params = list(sig.parameters.values())
        if len(params) < 2:
            return False, "Smoke-test: run(...) must accept at least (input_path, output_path)."

        with tempfile.TemporaryDirectory() as tmp:
            input_path = os.path.join(tmp, "input_placeholder")
            output_path = os.path.join(tmp, "output_placeholder")

            # Create an empty placeholder input file. The function should handle empty/invalid inputs gracefully.
            with open(input_path, "wb") as f:
                f.write(b"")

            # Call with the minimum required arguments.
            # If the function requires additional non-default args, this will raise a TypeError.
            run_fn(input_path, output_path)

        return True, "Smoke-test verification passed."

    except Exception as e:
        return False, f"Smoke-test error: {e}"


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


def load_prompt(prompts_dir: str, filename: str) -> str:
    path = os.path.join(prompts_dir, filename)
    if not os.path.exists(path):
        raise FileNotFoundError(f"Missing prompt template: {path}")
    return read_text(path)


def run_task(
    llm: LLM,
    cfg: Config,
    requirement_packet: str,
    prompts_dir: str,
    out_dir: str,
    global_logger: logging.Logger,
) -> None:
    title = infer_title(requirement_packet)
    task_slug = slugify(title)
    task_dir = os.path.join(out_dir, task_slug)
    os.makedirs(task_dir, exist_ok=True)

    task_logger = setup_logger(os.path.join(task_dir, "task.log"), also_console=False)

    def log(msg: str, *args: Any) -> None:
        global_logger.info("[%s] " + msg, task_slug, *args)
        task_logger.info(msg, *args)

    log("=== Task started: %s ===", title)

    # Load templates
    designer_tpl = load_prompt(prompts_dir, "designer_plantuml.md")
    coder_tpl = load_prompt(prompts_dir, "coder_python.md")
    repair_tpl = load_prompt(prompts_dir, "repair_code.md")
    revise_tpl = load_prompt(prompts_dir, "revise_design.md")

    # Phase 1: Design
    log("Calling Designer model: %s", cfg.designer_model)
    designer_prompt = designer_tpl.format(REQUIREMENT_PACKET=requirement_packet)
    designer_out = llm.chat(
        model=cfg.designer_model,
        system="You are a careful software designer for scientific Python.",
        user=designer_prompt,
    )

    uml = extract_fenced_block(designer_out, "plantuml")
    if not uml:
        write_text(os.path.join(task_dir, "designer_raw.txt"), designer_out)
        raise RuntimeError("Designer did not produce a PlantUML fenced block. See designer_raw.txt")

    architecture = extract_section(designer_out, "Architecture:")
    contract = extract_section(designer_out, "I/O & Verification Contract:")

    # Save UML
    puml_path = os.path.join(task_dir, f"{task_slug}.puml")
    write_text(puml_path, uml + "\n")

    # Render PNG
    png_path = os.path.join(task_dir, f"{task_slug}.png")
    if render_plantuml_png(puml_path, png_path, cfg.plantuml_jar_path, global_logger):
        log("Rendered UML PNG: %s", png_path)
    else:
        log("UML PNG not rendered (missing plantuml.jar or Java)")

    write_text(os.path.join(task_dir, "architecture.txt"), architecture + "\n")
    write_text(os.path.join(task_dir, "contract.txt"), contract + "\n")

    # Phase 2: Code generation & iteration
    def coder_prompt_for(u: str, a: str, c: str) -> str:
        return coder_tpl.format(
            REQUIREMENT_PACKET=requirement_packet,
            UML_TEXT=u,
            ARCHITECTURE_TEXT=a,
            CONTRACT_TEXT=c,
        )

    log("Calling Coder model: %s", cfg.coder_model)
    coder_out = llm.chat(
        model=cfg.coder_model,
        system="You are a professional Python developer specialising in numerical/scientific computing.",
        user=coder_prompt_for(uml, architecture, contract),
    )

    code = extract_fenced_block(coder_out, "python")
    if not code:
        write_text(os.path.join(task_dir, "coder_raw.txt"), coder_out)
        raise RuntimeError("Coder did not produce a Python fenced block. See coder_raw.txt")

    current_code = code
    current_uml = uml
    current_arch = architecture
    current_contract = contract

    for design_rev in range(cfg.max_design_revisions + 1):
        # Code repairs with fixed UML
        for repair in range(cfg.max_code_repairs + 1):
            ok, report = verify_generated_code(current_code, cfg.smoke_test, global_logger)
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
                user=repair_tpl.format(
                    REQUIREMENT_PACKET=requirement_packet,
                    UML_TEXT=current_uml,
                    PREV_CODE=current_code,
                    FAILURE_REPORT=report,
                ),
            )
            repaired = extract_fenced_block(repair_out, "python")
            if repaired:
                current_code = repaired
            else:
                write_text(os.path.join(task_dir, f"repair_raw_{repair+1}.txt"), repair_out)

        # Design revision if still failing
        if design_rev >= cfg.max_design_revisions:
            log("Max design revisions reached; writing best-effort outputs.")
            py_path = os.path.join(task_dir, f"{task_slug}.py")
            write_text(py_path, current_code + "\n")
            return

        log("Revising design (attempt %d/%d)", design_rev + 1, cfg.max_design_revisions)
        revise_out = llm.chat(
            model=cfg.designer_model,
            system="You revise UML designs for scientific Python workflows.",
            user=revise_tpl.format(
                REQUIREMENT_PACKET=requirement_packet,
                UML_TEXT=current_uml,
                FAILURE_REPORT=read_text(os.path.join(task_dir, "last_verification.txt")),
            ),
        )

        new_uml = extract_fenced_block(revise_out, "plantuml")
        if new_uml:
            current_uml = new_uml
            current_arch = extract_section(revise_out, "Architecture:") or current_arch
            current_contract = extract_section(revise_out, "I/O & Verification Contract:") or current_contract
            write_text(puml_path, current_uml + "\n")
            write_text(os.path.join(task_dir, "architecture.txt"), current_arch + "\n")
            write_text(os.path.join(task_dir, "contract.txt"), current_contract + "\n")
            render_plantuml_png(puml_path, png_path, cfg.plantuml_jar_path, global_logger)
        else:
            write_text(os.path.join(task_dir, f"revise_raw_{design_rev+1}.txt"), revise_out)
            log("Design revision did not return PlantUML; keeping previous UML.")

        # Regenerate code from revised design
        log("Regenerating code after design revision")
        coder_out = llm.chat(
            model=cfg.coder_model,
            system="You are a professional Python developer specialising in numerical/scientific computing.",
            user=coder_prompt_for(current_uml, current_arch, current_contract),
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
    parser = argparse.ArgumentParser(description="StructGen-style code generation using Ollama + PlantUML")
    parser.add_argument("--config", default="structgen_config.json", help="Path to structgen_config.json")
    parser.add_argument("--requirements", default="requirements.txt", help="Path to requirements.txt (NL specs)")
    parser.add_argument("--prompts", default="prompts", help="Directory containing prompt templates")
    parser.add_argument("--out", default="out", help="Output directory")
    parser.add_argument("--smoke-test", action="store_true", help="Enable cautious smoke-test call to run()")

    args = parser.parse_args()

    cfg = Config.load(args.config)
    if args.smoke_test:
        cfg.smoke_test = True

    os.makedirs(args.out, exist_ok=True)
    global_logger = setup_logger(os.path.join(args.out, "run.log"), also_console=True)

    global_logger.info("Starting StructGen runner")
    global_logger.info("Config: %s", args.config)
    global_logger.info("Requirements: %s", args.requirements)
    global_logger.info("Prompts dir: %s", args.prompts)
    global_logger.info("Output dir: %s", args.out)
    global_logger.info("Smoke test: %s", cfg.smoke_test)

    req_text = read_text(args.requirements)
    tasks = parse_tasks(req_text)
    global_logger.info("Found %d task(s)", len(tasks))

    llm = LLM(cfg)

    for i, task in enumerate(tasks, start=1):
        title = infer_title(task)
        global_logger.info("Task %d/%d: %s", i, len(tasks), title)
        try:
            run_task(llm, cfg, task, args.prompts, args.out, global_logger)
        except Exception as e:
            global_logger.exception("Task failed: %s", e)

    global_logger.info("All tasks processed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

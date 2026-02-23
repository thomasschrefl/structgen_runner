#!/usr/bin/env python3
"""StructGen runner v1 (minimal verification) with:

1) UML robustness
   - Runs PlantUML syntax check (-checkonly -failonerror) before rendering.
   - If UML has syntax errors, triggers a Designer "UML Repair" loop.
   - This runs after EVERY Designer call (initial + design revisions).

2) Prompt length guardrail (auto-compress + continue)
   - Estimates prompt tokens (heuristic) and if above a budget, automatically compresses the
     largest inputs (requirement packet, UML, contract) using a summariser call.
   - Continues execution but issues a WARNING.

3) Optional logging of all prompts used
   - When enabled, writes prompts to out/<task>/prompts_used/*.txt and task.log.
   - Optionally also echoes into out/run.log.

WARNING: Logging prompts may expose sensitive content. Use only in trusted environments.
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
import textwrap
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from openai import OpenAI


# ----------------------------
# Utilities
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
            return line.strip()[:80]
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


# ----------------------------
# Config
# ----------------------------

@dataclass
class Config:
    # Ollama / OpenAI-compatible
    ollama_base_url: str = "http://localhost:11434/v1"
    ollama_api_key: str = "ollama"

    designer_model: str = "qwen2.5-coder:7b-instruct"
    coder_model: str = "qwen2.5-coder:7b-instruct"
    summarizer_model: str = ""  # optional override; if empty uses designer_model

    temperature: float = 0.2
    top_p: float = 0.95
    max_tokens: int = 4096

    max_code_repairs: int = 2
    max_design_revisions: int = 4
    max_uml_repairs: int = 2

    plantuml_jar_path: str = "./plantuml.jar"

    smoke_test: bool = False

    # Prompt logging
    log_prompts: bool = False
    log_prompts_include_runlog: bool = False

    # Prompt length guardrail
    prompt_length_check: bool = True
    prompt_token_budget: int = 5500  # estimated tokens for (system+user). Leave headroom.
    prompt_estimator: str = "chars_div_4"  # chars_div_4 | words_1p3
    compress_target_tokens: int = 2500      # target for each long component

    @staticmethod
    def load(path: str) -> "Config":
        data = json.loads(read_text(path))
        cfg = Config()
        for k, v in data.items():
            if hasattr(cfg, k):
                setattr(cfg, k, v)
        return cfg


# ----------------------------
# LLM client
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
# Prompt logging
# ----------------------------

def log_prompt_bundle(
    enabled: bool,
    include_runlog: bool,
    task_dir: str,
    task_logger: logging.Logger,
    run_logger: logging.Logger,
    tag: str,
    system_prompt: str,
    user_prompt: str,
) -> None:
    if not enabled:
        return

    prompts_dir = os.path.join(task_dir, "prompts_used")
    os.makedirs(prompts_dir, exist_ok=True)

    ts = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    safe_tag = re.sub(r"[^a-zA-Z0-9_\-]+", "_", tag)[:80]
    path = os.path.join(prompts_dir, f"{ts}_{safe_tag}.txt")

    blob = (
        f"=== PROMPT TAG: {tag} ===\n"
        f"=== SYSTEM ===\n{system_prompt}\n\n"
        f"=== USER ===\n{user_prompt}\n"
    )
    write_text(path, blob)

    task_logger.info("PROMPT_SAVED: %s", path)

    if include_runlog:
        run_logger.info("PROMPT_SAVED: %s", path)


# ----------------------------
# Prompt length guardrail (estimate + compress)
# ----------------------------

def estimate_tokens(text: str, method: str) -> int:
    if not text:
        return 0
    if method == "words_1p3":
        return int(len(text.split()) * 1.3)
    # default chars_div_4
    return max(1, len(text) // 4)


def needs_compress(cfg: Config, system_prompt: str, user_prompt: str) -> Tuple[bool, int]:
    if not cfg.prompt_length_check:
        return False, 0
    est = estimate_tokens(system_prompt, cfg.prompt_estimator) + estimate_tokens(user_prompt, cfg.prompt_estimator)
    return est > cfg.prompt_token_budget, est


def summarise_text(llm: LLM, cfg: Config, text: str, target_tokens: int, purpose: str, task_logger: logging.Logger) -> str:
    # Hard safeguard: if the text itself is enormous, truncate before asking for summarisation.
    max_chars = target_tokens * 6  # generous; heuristic
    truncated = text
    if len(text) > max_chars * 8:
        truncated = text[: max_chars * 8]
        task_logger.warning("Prompt too long for summariser; truncating input before summarising (%s).", purpose)

    model = cfg.summarizer_model.strip() or cfg.designer_model
    system_p = "You compress technical instructions without losing constraints."
    user_p = (
        f"Compress the following content to <= {target_tokens} tokens (roughly).\n"
        "Preserve: function signature, I/O schema, constraints, allowed libraries, determinism rules, and any '@' directives.\n"
        "Remove: redundancy, long prose, examples unless essential.\n\n"
        f"PURPOSE: {purpose}\n\n"
        f"CONTENT:\n{textwrap.shorten(truncated, width=len(truncated), placeholder='')}"
    )
    # We do not log this prompt unless prompt logging is on; it uses the same mechanism upstream.
    out = llm.chat(model=model, system=system_p, user=user_p)
    # Keep the result as plain text
    return out.strip()


def auto_compress_prompts(
    llm: LLM,
    cfg: Config,
    system_prompt: str,
    user_prompt: str,
    components: Dict[str, str],
    task_logger: logging.Logger,
) -> Tuple[str, str, bool, int]:
    """Compress specified components and rebuild user prompt.

    components: mapping name->text for large blocks that can be compressed.
    The function replaces each block by a compressed version if present.
    """
    too_long, est = needs_compress(cfg, system_prompt, user_prompt)
    if not too_long:
        return system_prompt, user_prompt, False, est

    task_logger.warning(
        "Estimated prompt tokens (%d) exceed budget (%d). Auto-compressing and continuing.",
        est,
        cfg.prompt_token_budget,
    )

    new_user = user_prompt
    for name, original in components.items():
        if not original:
            continue
        comp = summarise_text(llm, cfg, original, cfg.compress_target_tokens, purpose=name, task_logger=task_logger)
        # Replace only if the original occurs verbatim; otherwise append a compressed appendix.
        if original in new_user:
            new_user = new_user.replace(original, comp)
        else:
            new_user += f"\n\n[COMPRESSED_{name}]\n{comp}\n"

    # If still too long, final fallback: trim user prompt tail.
    too_long2, est2 = needs_compress(cfg, system_prompt, new_user)
    if too_long2:
        keep = int(cfg.prompt_token_budget * 4)  # chars
        task_logger.warning("Prompt still too long after compression (est=%d). Truncating user prompt tail.", est2)
        new_user = new_user[:keep] + "\n\n[TRUNCATED_FOR_BUDGET]"
        est2 = estimate_tokens(system_prompt, cfg.prompt_estimator) + estimate_tokens(new_user, cfg.prompt_estimator)

    return system_prompt, new_user, True, est2


# ----------------------------
# PlantUML (syntax check + render)
# ----------------------------

def plantuml_check(puml_path: str, jar_path: str, logger: logging.Logger) -> Tuple[bool, str]:
    if not os.path.exists(jar_path):
        return False, f"PlantUML jar not found at {jar_path}"
    try:
        cmd = ["java", "-jar", jar_path, "-checkonly", "-failonerror", puml_path]
        logger.info("PlantUML check: %s", " ".join(cmd))
        cp = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if cp.returncode == 0:
            return True, ""
        err = (cp.stderr or cp.stdout or "").strip()
        if not err:
            err = f"PlantUML syntax check failed (exit code {cp.returncode})."
        return False, err
    except FileNotFoundError:
        return False, "Java not found on PATH (install Java to enable PlantUML)."


def plantuml_render_png(puml_path: str, png_path: str, jar_path: str, logger: logging.Logger) -> Tuple[bool, str]:
    if not os.path.exists(jar_path):
        return False, f"PlantUML jar not found at {jar_path}"

    out_dir_abs = os.path.abspath(os.path.dirname(png_path))
    os.makedirs(out_dir_abs, exist_ok=True)

    try:
        cmd = ["java", "-jar", jar_path, "-failonerror", "-noerror", "-tpng", puml_path, "-o", out_dir_abs]
        logger.info("PlantUML render: %s", " ".join(cmd))
        cp = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if cp.returncode != 0:
            err = (cp.stderr or cp.stdout or "").strip()
            if not err:
                err = f"PlantUML render failed (exit code {cp.returncode})."
            return False, err

        base = os.path.splitext(os.path.basename(puml_path))[0]
        produced = os.path.join(out_dir_abs, base + ".png")
        if os.path.exists(produced):
            if os.path.abspath(produced) != os.path.abspath(png_path):
                shutil.move(produced, png_path)
            return True, ""
        return False, "PlantUML did not produce an output PNG."

    except FileNotFoundError:
        return False, "Java not found on PATH (install Java to enable PlantUML)."


def build_repair_uml_prompt(requirement_packet: str, uml_text: str, plantuml_error: str, template: Optional[str]) -> str:
    if template:
        return template.format(REQUIREMENT_PACKET=requirement_packet, UML_TEXT=uml_text, PLANTUML_ERROR=plantuml_error)
    return (
        "Role: Designer (UML Repair Mode)\n\n"
        "Fix ONLY PlantUML activity-diagram syntax so -checkonly passes and PNG renders.\n"
        "Rules: one @startuml..@enduml, start/stop, :actions;, if/endif, while/endwhile, no '->', no 'do', no 'end while'.\n\n"
        f"PlantUML error:\n{plantuml_error}\n\n"
        f"Requirement packet:\n{requirement_packet}\n\n"
        f"Previous UML:\n```plantuml\n{uml_text}\n```\n\n"
        "OUTPUT: one fenced ```plantuml``` block only.\n"
    )


def validate_and_render_uml_with_repair(
    llm: LLM,
    cfg: Config,
    requirement_packet: str,
    prompts_dir: str,
    task_dir: str,
    task_slug: str,
    uml_text: str,
    task_logger: logging.Logger,
    run_logger: logging.Logger,
) -> Tuple[str, bool, str]:
    repair_uml_tpl = load_prompt_optional(prompts_dir, "repair_uml.md")

    puml_path = os.path.join(task_dir, f"{task_slug}.puml")
    png_path = os.path.join(task_dir, f"{task_slug}.png")

    current_uml = uml_text
    last_err = ""

    for attempt in range(cfg.max_uml_repairs + 1):
        write_text(puml_path, current_uml + "\n")

        ok, err = plantuml_check(puml_path, cfg.plantuml_jar_path, run_logger)
        if not ok:
            last_err = err
            task_logger.info("UML syntax check failed (attempt %d/%d): %s", attempt + 1, cfg.max_uml_repairs + 1, err)
            if attempt >= cfg.max_uml_repairs:
                return current_uml, False, last_err

            system_p = "You repair PlantUML activity diagrams to be syntactically valid."
            user_p = build_repair_uml_prompt(requirement_packet, current_uml, err, repair_uml_tpl)
            # prompt guardrail
            system_p, user_p, _, _ = auto_compress_prompts(
                llm, cfg, system_p, user_p,
                components={"REQUIREMENT_PACKET": requirement_packet, "UML_TEXT": current_uml},
                task_logger=task_logger,
            )
            log_prompt_bundle(cfg.log_prompts, cfg.log_prompts_include_runlog, task_dir, task_logger, run_logger, "designer_repair_uml", system_p, user_p)
            repair_out = llm.chat(model=cfg.designer_model, system=system_p, user=user_p)
            repaired = extract_fenced_block(repair_out, "plantuml")
            if repaired:
                current_uml = repaired
                continue
            write_text(os.path.join(task_dir, f"uml_repair_raw_{attempt+1}.txt"), repair_out)
            return current_uml, False, last_err

        ok, err = plantuml_render_png(puml_path, png_path, cfg.plantuml_jar_path, run_logger)
        if ok:
            return current_uml, True, ""

        last_err = err
        task_logger.info("UML render failed (attempt %d/%d): %s", attempt + 1, cfg.max_uml_repairs + 1, err)
        if attempt >= cfg.max_uml_repairs:
            return current_uml, False, last_err

        system_p = "You repair PlantUML activity diagrams to be syntactically valid."
        user_p = build_repair_uml_prompt(requirement_packet, current_uml, err, repair_uml_tpl)
        system_p, user_p, _, _ = auto_compress_prompts(
            llm, cfg, system_p, user_p,
            components={"REQUIREMENT_PACKET": requirement_packet, "UML_TEXT": current_uml},
            task_logger=task_logger,
        )
        log_prompt_bundle(cfg.log_prompts, cfg.log_prompts_include_runlog, task_dir, task_logger, run_logger, "designer_repair_uml_after_render", system_p, user_p)
        repair_out = llm.chat(model=cfg.designer_model, system=system_p, user=user_p)
        repaired = extract_fenced_block(repair_out, "plantuml")
        if repaired:
            current_uml = repaired
            continue
        write_text(os.path.join(task_dir, f"uml_repair_raw_{attempt+1}.txt"), repair_out)
        return current_uml, False, last_err

    return current_uml, False, last_err


# ----------------------------
# Verification (v1 minimal)
# ----------------------------

def verify_generated_code(code: str, smoke_test: bool) -> Tuple[bool, str]:
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

    try:
        import inspect
        sig = inspect.signature(run_fn)
        if len(sig.parameters) < 2:
            return False, "Smoke-test: run(...) must accept at least (input_path, output_path)."

        with tempfile.TemporaryDirectory() as tmp:
            ip = os.path.join(tmp, "input_placeholder")
            op = os.path.join(tmp, "output_placeholder")
            with open(ip, "wb") as f:
                f.write(b"")
            run_fn(ip, op)
        return True, "Smoke-test verification passed."

    except Exception as e:
        return False, f"Smoke-test error: {e}"


# ----------------------------
# Task runner
# ----------------------------

def run_task(llm: LLM, cfg: Config, requirement_packet: str, prompts_dir: str, out_dir: str, run_logger: logging.Logger) -> None:
    title = infer_title(requirement_packet)
    task_slug = slugify(title)
    task_dir = os.path.join(out_dir, task_slug)
    os.makedirs(task_dir, exist_ok=True)

    task_logger = setup_logger(os.path.join(task_dir, "task.log"), also_console=False)

    def log(msg: str, *args: Any) -> None:
        run_logger.info("[%s] " + msg, task_slug, *args)
        task_logger.info(msg, *args)

    log("=== Task started: %s ===", title)

    designer_tpl = load_prompt(prompts_dir, "designer_plantuml.md")
    coder_tpl = load_prompt(prompts_dir, "coder_python.md")
    repair_code_tpl = load_prompt(prompts_dir, "repair_code.md")
    revise_design_tpl = load_prompt(prompts_dir, "revise_design.md")

    # ---- Designer initial
    log("Calling Designer model: %s", cfg.designer_model)
    system_p = "You are a careful software designer for scientific Python."
    user_p = designer_tpl.format(REQUIREMENT_PACKET=requirement_packet)

    system_p, user_p, compressed, est = auto_compress_prompts(
        llm, cfg, system_p, user_p,
        components={"REQUIREMENT_PACKET": requirement_packet},
        task_logger=task_logger,
    )
    if compressed:
        task_logger.warning("Designer prompt auto-compressed (est_tokens_after=%d).", est)

    log_prompt_bundle(cfg.log_prompts, cfg.log_prompts_include_runlog, task_dir, task_logger, run_logger, "designer_initial", system_p, user_p)
    designer_out = llm.chat(model=cfg.designer_model, system=system_p, user=user_p)

    uml = extract_fenced_block(designer_out, "plantuml")
    if not uml:
        write_text(os.path.join(task_dir, "designer_raw.txt"), designer_out)
        raise RuntimeError("Designer did not produce a PlantUML fenced block. See designer_raw.txt")

    architecture = extract_section(designer_out, "Architecture:")
    contract_txt = extract_section(designer_out, "I/O & Verification Contract:")

    # ---- Validate UML after designer call
    uml, uml_ok, uml_err = validate_and_render_uml_with_repair(
        llm, cfg, requirement_packet, prompts_dir, task_dir, task_slug, uml, task_logger, run_logger
    )
    if uml_ok:
        log("Rendered UML PNG")
    else:
        log("UML PNG not rendered: %s", uml_err)

    write_text(os.path.join(task_dir, "architecture.txt"), architecture + "\n")
    write_text(os.path.join(task_dir, "contract.txt"), contract_txt + "\n")

    # ---- Coder initial
    log("Calling Coder model: %s", cfg.coder_model)
    system_c = "You are a professional Python developer specialising in numerical/scientific computing."
    user_c = coder_tpl.format(
        REQUIREMENT_PACKET=requirement_packet,
        UML_TEXT=uml,
        ARCHITECTURE_TEXT=architecture,
        CONTRACT_TEXT=contract_txt,
    )
    system_c, user_c, compressed, est = auto_compress_prompts(
        llm, cfg, system_c, user_c,
        components={"REQUIREMENT_PACKET": requirement_packet, "UML_TEXT": uml, "CONTRACT_TEXT": contract_txt},
        task_logger=task_logger,
    )
    if compressed:
        task_logger.warning("Coder prompt auto-compressed (est_tokens_after=%d).", est)

    log_prompt_bundle(cfg.log_prompts, cfg.log_prompts_include_runlog, task_dir, task_logger, run_logger, "coder_initial", system_c, user_c)
    coder_out = llm.chat(model=cfg.coder_model, system=system_c, user=user_c)

    code = extract_fenced_block(coder_out, "python")
    if not code:
        write_text(os.path.join(task_dir, "coder_raw.txt"), coder_out)
        raise RuntimeError("Coder did not produce a Python fenced block. See coder_raw.txt")

    current_code = code
    current_uml = uml

    for design_rev in range(cfg.max_design_revisions + 1):
        for repair in range(cfg.max_code_repairs + 1):
            ok, report = verify_generated_code(current_code, cfg.smoke_test)
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

            # ---- Code repair
            log("Repairing code (attempt %d/%d)", repair + 1, cfg.max_code_repairs)
            system_r = "You repair scientific Python code based on verification feedback."
            user_r = repair_code_tpl.format(
                REQUIREMENT_PACKET=requirement_packet,
                UML_TEXT=current_uml,
                PREV_CODE=current_code,
                FAILURE_REPORT=report,
            )
            system_r, user_r, compressed, est = auto_compress_prompts(
                llm, cfg, system_r, user_r,
                components={"REQUIREMENT_PACKET": requirement_packet, "UML_TEXT": current_uml},
                task_logger=task_logger,
            )
            if compressed:
                task_logger.warning("Repair prompt auto-compressed (est_tokens_after=%d).", est)

            log_prompt_bundle(cfg.log_prompts, cfg.log_prompts_include_runlog, task_dir, task_logger, run_logger, f"coder_repair_{repair+1}", system_r, user_r)
            repair_out = llm.chat(model=cfg.coder_model, system=system_r, user=user_r)
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

        # ---- Design revision (Designer)
        log("Revising design (attempt %d/%d)", design_rev + 1, cfg.max_design_revisions)
        system_d2 = "You revise UML designs for scientific Python workflows."
        user_d2 = revise_design_tpl.format(
            REQUIREMENT_PACKET=requirement_packet,
            UML_TEXT=current_uml,
            FAILURE_REPORT=read_text(os.path.join(task_dir, "last_verification.txt")),
        )
        system_d2, user_d2, compressed, est = auto_compress_prompts(
            llm, cfg, system_d2, user_d2,
            components={"REQUIREMENT_PACKET": requirement_packet, "UML_TEXT": current_uml},
            task_logger=task_logger,
        )
        if compressed:
            task_logger.warning("Design revision prompt auto-compressed (est_tokens_after=%d).", est)

        log_prompt_bundle(cfg.log_prompts, cfg.log_prompts_include_runlog, task_dir, task_logger, run_logger, f"designer_revision_{design_rev+1}", system_d2, user_d2)
        revise_out = llm.chat(model=cfg.designer_model, system=system_d2, user=user_d2)

        new_uml = extract_fenced_block(revise_out, "plantuml")
        if new_uml:
            current_uml, uml_ok, uml_err = validate_and_render_uml_with_repair(
                llm, cfg, requirement_packet, prompts_dir, task_dir, task_slug, new_uml, task_logger, run_logger
            )
            if uml_ok:
                log("Rendered UML PNG after design revision")
            else:
                log("UML PNG not rendered after design revision: %s", uml_err)
        else:
            write_text(os.path.join(task_dir, f"revise_raw_{design_rev+1}.txt"), revise_out)
            log("Design revision did not return PlantUML; keeping previous UML.")

        # ---- regenerate code
        log("Regenerating code after design revision")
        system_c2 = "You are a professional Python developer specialising in numerical/scientific computing."
        user_c2 = coder_tpl.format(
            REQUIREMENT_PACKET=requirement_packet,
            UML_TEXT=current_uml,
            ARCHITECTURE_TEXT=architecture,
            CONTRACT_TEXT=contract_txt,
        )
        system_c2, user_c2, compressed, est = auto_compress_prompts(
            llm, cfg, system_c2, user_c2,
            components={"REQUIREMENT_PACKET": requirement_packet, "UML_TEXT": current_uml, "CONTRACT_TEXT": contract_txt},
            task_logger=task_logger,
        )
        if compressed:
            task_logger.warning("Coder-after-design prompt auto-compressed (est_tokens_after=%d).", est)

        log_prompt_bundle(cfg.log_prompts, cfg.log_prompts_include_runlog, task_dir, task_logger, run_logger, f"coder_after_design_{design_rev+1}", system_c2, user_c2)
        coder2_out = llm.chat(model=cfg.coder_model, system=system_c2, user=user_c2)
        regen = extract_fenced_block(coder2_out, "python")
        if regen:
            current_code = regen
        else:
            write_text(os.path.join(task_dir, f"coder_raw_after_design_{design_rev+1}.txt"), coder2_out)


# ----------------------------
# CLI
# ----------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description="StructGen runner v1")
    parser.add_argument("--config", default="structgen_config.json")
    parser.add_argument("--requirements", default="requirements.txt")
    parser.add_argument("--prompts", default="prompts")
    parser.add_argument("--out", default="out")
    parser.add_argument("--smoke-test", action="store_true")

    parser.add_argument("--log-prompts", action="store_true", help="Save prompts to out/<task>/prompts_used/*.txt")
    parser.add_argument("--log-prompts-include-runlog", action="store_true", help="Also echo prompt paths to out/run.log")

    parser.add_argument("--prompt-token-budget", type=int, default=None, help="Estimated token budget for (system+user).")
    parser.add_argument("--compress-target-tokens", type=int, default=None, help="Target token size for compressed blocks.")

    args = parser.parse_args()

    cfg = Config.load(args.config)
    if args.smoke_test:
        cfg.smoke_test = True
    if args.log_prompts:
        cfg.log_prompts = True
    if args.log_prompts_include_runlog:
        cfg.log_prompts_include_runlog = True
    if args.prompt_token_budget is not None:
        cfg.prompt_token_budget = int(args.prompt_token_budget)
    if args.compress_target_tokens is not None:
        cfg.compress_target_tokens = int(args.compress_target_tokens)

    os.makedirs(args.out, exist_ok=True)
    run_logger = setup_logger(os.path.join(args.out, "run.log"), also_console=True)

    run_logger.info("Starting StructGen runner (v1)")
    run_logger.info("Requirements: %s", args.requirements)
    run_logger.info("Prompts dir: %s", args.prompts)
    run_logger.info("Output dir: %s", args.out)
    run_logger.info("Smoke test: %s", cfg.smoke_test)
    run_logger.info("Prompt length check: %s (budget=%s)", cfg.prompt_length_check, cfg.prompt_token_budget)

    tasks = parse_tasks(read_text(args.requirements))
    run_logger.info("Found %d task(s)", len(tasks))

    llm = LLM(cfg)

    for i, task in enumerate(tasks, start=1):
        run_logger.info("Task %d/%d: %s", i, len(tasks), infer_title(task))
        try:
            run_task(llm, cfg, task, args.prompts, args.out, run_logger)
        except Exception as e:
            run_logger.exception("Task failed: %s", e)

    run_logger.info("All tasks processed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

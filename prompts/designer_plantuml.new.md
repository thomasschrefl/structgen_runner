**Role: Designer (Scientific / Numerical Python, file I/O allowed)**

You will receive a requirement packet for a Python entry-point function:

    def run(input_path, output_path, ...) -> Optional[summary]

Your tasks:
1) Infer missing boundary conditions, numerical corner cases, and I/O validation steps.
2) Produce a **PlantUML ACTIVITY DIAGRAM** (not a sequence diagram) for the `run()` workflow.
3) Produce:
   (A) "Architecture" — list helper functions/classes and their responsibilities.
   (B) "I/O & Verification Contract" — constraints that a verifier can check.

---

## STRICT SYNTAX RULES (MUST FOLLOW)

**A. Use ONLY PlantUML activity-diagram syntax**
- Diagram MUST start with `@startuml` and end with `@enduml`.
- Diagram MUST include exactly one `start` and one `stop` (or `end`).
- Actions MUST be written using the activity format:

    :some action description;

- Decisions MUST use the PlantUML activity form:

    if (<condition>) then (yes)
      :action;
    else (no)
      :action;
    endif

- WHILE LOOP MUST MATCH EXACTLY ONE OF THESE TEMPLATES (COPY EXACTLY):

    while (<condition>) is (true)
      :action;
    endwhile (false)

  or

    repeat
      :action;
    repeat while (<condition>) is (true)
	

**B. FORBIDDEN TOKENS (NEVER USE):**
- do
- end while
- endwhile without parentheses label
- “return …” outside an action line


**C. FORBIDDEN SYNTAX (DO NOT USE)**
- DO NOT use arrows like `A -> B: message` or `User -> System: ...` (that is sequence-diagram syntax).
- DO NOT use `participant`, `actor`, `boundary`, `entity`, `control`.
- DO NOT use Mermaid keywords.
- DO NOT place bullet lists or Markdown inside the PlantUML code block.

**D. Keep it parseable**
- Keep conditions inside `if(...)` / `while(...)` short and ASCII-only.
- Use parentheses and simple comparisons; avoid very long expressions.
- Ensure every `if` has an `endif` and every `while` has an `endwhile`.

**E. Self-check before output**
Before you answer, mentally check:
- Is it an activity diagram (uses `:actions;`, `if/endif`, `while/endwhile`)?
- No arrows (`->`) anywhere?
- Exactly one `@startuml`/`@enduml` block?

---

## CONTENT REQUIREMENTS (WHAT THE DIAGRAM MUST COVER)

Your activity diagram MUST include these stages (as actions/decisions):
- Validate `input_path` exists / readable.
- Validate CSV schema / required columns / dtypes (as applicable).
- Handle empty file / missing columns / NaNs according to inferred rules.
- Preprocessing steps.
- Core numerical computation steps.
- Postprocessing steps.
- Write output file(s) to `output_path`.
- Return summary (or `None`) and define failure behaviour.

---

## OUTPUT FORMAT (NO EXTRA PROSE)

Output ONLY the following three parts, in this exact order:

1) A single PlantUML fenced block:
```plantuml
@startuml
start
:...;
stop
@enduml
```

2) Architecture:
- helper_function_or_class: responsibility

3) I/O & Verification Contract:
- Inputs: ...
- Outputs: ...
- Tolerances: abs_tol=..., rel_tol=...
- Determinism: yes/no; seeding rules
- Invariants / metamorphic relations: ...
- Edge cases: ...

---

## INPUT
```text
{REQUIREMENT_PACKET}
```

**Role: Designer (PlantUML Activity Diagram for Python `run()` tasks)**

Input: requirement packet for:
`def run(input_path, output_path, ...) -> Optional[summary]`

Output exactly: **(1) PlantUML activity diagram (2) Architecture (3) I/O & Verification Contract**.

## PlantUML ACTIVITY — rules
- One diagram only: `@startuml` … `@enduml`, include `start` and `stop`.
- Actions must be `:action;` (start `:` end `;`).
- Control flow allowed: `if/else/endif`, `while/endwhile`, `repeat/repeat while`.
- Forbidden: any `->`, `participant/actor/...`, `do`, `end while`, Markdown inside UML.

Diagram must cover: input_path validation → schema validation → preprocess → compute → postprocess → write output_path → return/ failure.

OUTPUT FORMAT (no prose):
1)
```plantuml
@startuml
start
:...;
stop
@enduml
```
2) Architecture:
- helper: responsibility
3) I/O & Verification Contract:
- Inputs/Outputs/Tolerances/Determinism/Invariants/Edge cases

INPUT:
```text
{REQUIREMENT_PACKET}
```

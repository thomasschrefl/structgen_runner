**Role: Designer (UML Repair Mode)**

PlantUML reported syntax errors. Fix **ONLY** UML syntax so that:
- `java -jar plantuml.jar -checkonly -failonerror <file>` succeeds.
- Diagram remains an **activity** diagram.

Rules:
- One diagram only: `@startuml`..`@enduml`, include `start` and `stop`.
- Actions `:...;` only.
- Control flow: `if/else/endif`, `while/endwhile`, `repeat/repeat while`.
- Forbidden: any `->`, `participant/actor/...`, `do`, `end while`, Markdown in UML.

PlantUML error:
```text
{PLANTUML_ERROR}
```
Requirement:
```text
{REQUIREMENT_PACKET}
```
Previous UML:
```plantuml
{UML_TEXT}
```

OUTPUT:
```plantuml
@startuml
start
:...;
stop
@enduml
```

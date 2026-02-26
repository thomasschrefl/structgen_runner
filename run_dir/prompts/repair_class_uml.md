**Role: Designer (UML Repair Mode — CLASS)**
PlantUML reported syntax errors. Fix **ONLY** UML syntax so that:
- `java -jar plantuml.jar -checkonly -failonerror <file>` succeeds.
- Diagram remains a **class** diagram.

Rules:
- One diagram only: `@startuml`..`@enduml`.
- Allowed: `class`, `interface`, `enum`, `package`, relationships (`--`, `<|--`, `*--`, `o--`, `..>`, `..|>`), multiplicities.
- Keep compact: only essential classes/methods/fields.
- Forbidden: Markdown inside UML, activity keywords (`start`, `stop`, `:action;`), sequence keywords (`participant`, `actor`).

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

OUTPUT: one fenced ```plantuml``` block only.
```plantuml
@startuml
class ...
@enduml
```

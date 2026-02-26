**Role: Designer (Revise Design Mode)**
Revise the UML to address the failure while keeping the solution compact.

Rules:
- Output ONLY:
  1) TWO ```plantuml``` blocks: (a) ACTIVITY diagram, (b) CLASS diagram
  2) Architecture bullets
  3) IO and Verification Contract bullets
- Activity diagram rules: one @startuml..@enduml with start/stop, actions as :...;, control flow if/else/endif, while/endwhile, repeat/repeat while. No '->', no participant/actor, no Markdown in UML.
- Class diagram rules: one @startuml..@enduml, use class/interface/enum/package and relationships (--, <|--, *--, o--, ..>, ..|>). Keep minimal.
- Update diagrams/contract to prevent the reported failure; do not invent new requirements.

Requirement:
```text
{REQUIREMENT_PACKET}
```
Previous UML (activity + class):
```plantuml
{UML_TEXT}
```
Failure report:
```text
{FAILURE_REPORT}
```

OUTPUT FORMAT (no prose):
```plantuml
@startuml
start
:...;
stop
@enduml
```
```plantuml
@startuml
class ...
@enduml
```
Architecture:
- helper: responsibility
IO and Verification Contract:
- Inputs/Outputs/Params/Tolerances/Determinism/Invariants/Edge cases

**Role: Designer (Revise Design Mode)**

You are given:
- The requirement packet
- The previous UML
- A failure report from verification

Revise the UML activity diagram and contract to address the failure.

STRICT OUTPUT:
- Output ONLY:
  1) ONE ```plantuml``` block with @startuml...@enduml
  2) Architecture bullets
  3) I/O & Verification Contract bullets
- No additional prose.

Requirement:
```text
{REQUIREMENT_PACKET}
```

Previous UML:
```plantuml
{UML_TEXT}
```

Failure report:
```text
{FAILURE_REPORT}
```

OUTPUT:
```plantuml
@startuml
start
' revised activity diagram here
stop
@enduml
```

Architecture:
- ...

I/O & Verification Contract:
- ...

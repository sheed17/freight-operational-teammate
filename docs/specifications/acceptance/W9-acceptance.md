# W9 Settlement Acceptance *(AC-WF9-*)*
*Source: `workflows/W9-settlement.md`, Operating Model L9. ### Money OUT — the highest-risk loop.*

| ID | Proves | Oracle / negative |
|---|---|---|
| **AC-WF9-001** | ### **extraction does NOT imply approvability** | an extracted carrier invoice with an unreconciled delta ⇒ not approvable |
| **AC-WF9-002** | ### **the remittance target is VERIFIED at the FINAL checkpoint** | `remittance_party` is a material fact re-read live at pay |
| **AC-WF9-003** | ### **factoring changes invalidate stale approval** | the destination changes post-approval ⇒ **`VOID_ON_DRIFT`**; ### **assert zero payment to the old destination** |
| **AC-WF9-004** | ### **unsupported detention remains BLOCKED** | only a counterparty assertion ⇒ blocked + `CounterpartySelfAuthorizationDetected`; ### **a HUMAN assertion (`OWNER_ASSERTED`) unblocks it** |
| **AC-WF9-005** | ### **payment initiation ≠ settlement** | AC-FC-012 |
| **AC-WF9-006** | ### **timeout ⇒ `UNKNOWN_OUTCOME`** | never `FAILED`; owner + exposure; ### **no retry** |
| **AC-WF9-007** | external settlement observation **reconciles local state** | settled-but-local-pending ⇒ the bank Observation wins |
| **AC-WF9-008** | duplicate payment prevented | the carrier invoice number is the `occurrence_key` ⇒ `DUPLICATE_SUPPRESSED` |
| **AC-WF9-009** | ### **wrong payment destination creates the required recovery path** | a Compensation/recovery obligation, owned, exposure stated |
| **AC-WF9-010** | closure requires the **canonical settled disposition** | a verified settlement Observation — or disputed/held with a `decision_ref` |
| **AC-WF9-011** | a conflicting field **blocks approval** | CD-4 |

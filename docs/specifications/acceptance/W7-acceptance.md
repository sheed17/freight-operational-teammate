# W7 Exceptions Acceptance *(AC-WF7-*)*
*Source: `workflows/W7-exceptions.md`, Operating Model L7.*

| ID | Proves | Oracle / negative |
|---|---|---|
| **AC-WF7-001** | ### **every exception has an owner** | a DB scan: zero exceptions with null/`system` owner, ever |
| **AC-WF7-002** | severity + aging ⇒ **deterministic escalation** | clock-advanced durable timers ⇒ `AGEING`→`ESCALATED`; ### **never a resolution timer** |
| **AC-WF7-003** | ### **an unresolved exception cannot disappear because another workflow advances** | drive the originating loop forward ⇒ ### **the Exception is still OPEN and owned** |
| **AC-WF7-004** | ### **resolution requires a valid `decision_ref`** | a bare string ⇒ ILLEGAL; the ref must resolve (K-1) |
| **AC-WF7-005** | `UNKNOWN_OUTCOME` routes here with **reason + owner** | `unknown_reason` NOT NULL; exposure stated; entity frozen |
| **AC-WF7-006** | ### **compensation failure remains VISIBLE** | `COMPENSATION_FAILED` non-terminal, human-owned, exposure surfaced; ### **no timer moves it** |
| **AC-WF7-007** | reopening creates a **new phase** | prior closure byte-identical |
| **AC-WF7-008** | ### **security-critical exceptions engage the correct brake scope** | orphan ⇒ tenant+action; cross-tenant ⇒ **GLOBAL**; rebuild divergence ⇒ tenant |
| **AC-WF7-009** | closure preserves the **complete decision + evidence chain** | the explainability query returns the full lineage |

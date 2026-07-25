# W11 Claims Acceptance *(AC-WF11-*)*
*Source: `workflows/W11-claims.md`, Operating Model L11.*

| ID | Proves | Oracle / negative |
|---|---|---|
| **AC-WF11-001** | OS&D/dispute evidence creates the **appropriate claim obligation** | a POD damage notation ⇒ an OS&D Case, owned |
| **AC-WF11-002** | ### **a claim can open AFTER invoice/payable settlement WITHOUT rewriting financial history** | ### **the settled invoice + payable rows are byte-identical after; the resolution creates a NEW adjustment** |
| **AC-WF11-003** | claim evidence remains **attributable** | every artifact content-addressed with provenance |
| **AC-WF11-004** | settlement/recovery decisions require **proper authority** | money-affecting ⇒ `HUMAN_APPROVAL_REQUIRED`; ### **Neyma does not file claims (L11)** |
| **AC-WF11-005** | ### **compensation uses the ORDINARY Action Pipeline** | its own witness+grant+approval+readback; no privileged path |
| **AC-WF11-006** | ### **`UNKNOWN_OUTCOME` during recovery remains OWNED** | `COMPENSATION_FAILED` ⇒ non-terminal, human-owned, loud |
| **AC-WF11-007** | closure requires **disposition + `decision_ref` + downstream financial reconciliation** | all three, else open |

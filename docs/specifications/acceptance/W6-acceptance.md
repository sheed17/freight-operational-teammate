# W6 Documentation Acceptance *(AC-WF6-*)*
*Source: `workflows/W6-documentation.md`, Operating Model L6. ### The first-loop origin (L6→L8).*

| ID | Proves | Oracle / negative |
|---|---|---|
| **AC-WF6-001** | documents **deduplicate by canonical identity** | identical bytes ⇒ ONE Document (content digest); a revision ⇒ a new version |
| **AC-WF6-002** | ### **multi-document files and multi-load documents remain representable** | one file → N Documents; ### **one POD → 2 Loads ⇒ BOTH bound, neither silently** |
| **AC-WF6-003** | content **immutable** | no UPDATE on content; digest matches bytes |
| **AC-WF6-004** | extraction remains **claim-based** | `MODEL_EXTRACTED` + an evidence span; ### **it re-enters deterministic matching, never confirms** |
| **AC-WF6-005** | ### **bindings follow deterministic identity rules** | a doc citing load# X but belonging to another customer ⇒ ### **`AMBIGUOUS` ⇒ human; assert NO auto-bind** |
| **AC-WF6-006** | ### **illegible/incomplete POD does NOT satisfy the packet** | `ILLEGIBLE` ⇒ Exception; packet `INCOMPLETE`; billing blocked |
| **AC-WF6-007** | ### **delivered status does NOT satisfy the POD requirement** | AC-FC-005 |
| **AC-WF6-008** | ### **packet closure requires the COMPLETE customer-specific requirement set** | a customer-required lumper receipt missing ⇒ `INCOMPLETE` |
| **AC-WF6-009** | OS&D evidence creates downstream Claims/Exceptions | a damage notation ⇒ an OS&D Case (W11), owned |
| **AC-WF6-010** | ### **binding correction PROPAGATES without rewriting history** | `ClaimCorrected` ⇒ dependents re-derived + a Compensation for a completed invoice; ### **the original binding row byte-identical** |
| **AC-WF6-011** | ### **degraded (read-only TMS): the loop still delivers value** | Neyma classifies+binds+tracks-missing; the human files; Neyma verifies |

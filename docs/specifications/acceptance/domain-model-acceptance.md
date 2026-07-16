# Domain Model Acceptance *(AC-DOM-*)*

*Registry defaults apply. Level: `ENTITY`. Gate: **G1**. ### **Every invariant has BOTH a database-state oracle AND an event-history oracle.***

## Coverage: **40/40 entities** — `AC-DOM-E01..E40` each assert the entity's identity, field-level authority, constraints, and lifecycle conformance.

## The seventeen mandatory invariants
| ID | Invariant | DB oracle | Event oracle |
|---|---|---|---|
| **AC-DOM-001** | ### **No generic `Load` collapse** | ### **a schema probe: NO `loads` table absorbing Order/Movement; the five tables exist distinctly** | the five lifecycles emit distinct events |
| **AC-DOM-002** | Order/Load/Movement/Leg/Stop retain **distinct identities** | 5 distinct PKs; explicit FK directions | distinct `entity_type` in envelopes |
| **AC-DOM-003** | ### **provisional 1:1 evolves to 1:N WITHOUT identity migration** | ### **insert a 2nd Load for one Order and a 2nd Movement for one Load ⇒ SUCCEEDS with no schema change and no id rewrite** | no re-identification events |
| **AC-DOM-004** | party roles create **no duplicate organizations** | ### **one Org row holding Customer AND Carrier roles on different loads** | role assignment is per-transaction |
| **AC-DOM-005** | ### **field-level authority enforced** | ### **a Carrier row with `mc`(FMCSA-projected) + `preferred_lanes`(OWNER_ASSERTED) + `email`(MODEL_EXTRACTED) — three provenance rows, one entity** | per-field provenance records |
| **AC-DOM-006** | ### **money direction + currency explicit** | ### **a constraint probe: NO monetary column without `currency`+`money_direction`+`money_kind`; NO float** | every money event carries them |
| **AC-DOM-007** | Accessorial Charge ≠ Authorization | 2 tables; the charge FKs the authorization | distinct events |
| **AC-DOM-008** | ### **undocumented authorization requires the canonical human assertion** | `provenance_class=OWNER_ASSERTED` + gate `PERMANENT_HUMAN_ASSERTION_REQUIRED` | ### **a model-actor attempt ⇒ zero rows + a security event** |
| **AC-DOM-009** | document content **immutable** | ### **no UPDATE permitted on content/digest; digest matches bytes on write** | `ObservationSuperseded`, never edited |
| **AC-DOM-010** | ### **rebinding preserves prior history** | the prior binding row retained + `corrected_from` set | `ClaimCorrected` + the original intact |
| **AC-DOM-011** | projected vs native **distinct** | every entity declares its class; a registry probe | projection updates only from verified events |
| **AC-DOM-012** | ### **External Entity Mapping is the ONLY bridge to vendor ids** | ### **a schema probe: NO domain table carries a raw vendor id column outside the mapping** | mappings referenced in bindings |
| **AC-DOM-013** | ### **identity confidence never confirms a consequential binding** | ### **the confirmation guard has NO confidence input; at 1.0 ⇒ `AMBIGUOUS`** | `ClaimAmbiguous` |
| **AC-DOM-014** | ### **stale qualification cannot authorize assignment** | qualification `evaluated_at` freshness at booking ⇒ block | `CheckpointFailed{step:6}` |
| **AC-DOM-015** | ### **delivered ≠ POD** | a `DELIVERED` load with an incomplete packet ⇒ **not billable** | distinct L-Track / L-Doc events |
| **AC-DOM-016** | ### **invoice sent ≠ payment** | `SENT` ≠ `PAID`; only a verified Payment Application closes | `EffectVerified` ≠ payment event |
| **AC-DOM-017** | ### **payable entered ≠ settlement** | `RECORDED` ≠ `PAID` | distinct events |

**Per-entity anchors:** `AC-DOM-E11` (Brokerage Load — the load-family rule), `AC-DOM-E29` (Accessorial Authorization — the permanent human gate), `AC-DOM-E38` (External Entity Mapping — two tenants, same external id, no collision), `AC-DOM-E40` (Reconciliation — derived, never authoritative money).

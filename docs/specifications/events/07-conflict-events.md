# Event Family F7 — Conflict Events

*Registry: `events/registry.md`. Producer: machine M7. Defaults: registry §1–§2.*

**Family defaults:** `aggregate_type=conflict`; ordering = **order-tolerant** (new parties attach to the open conflict); security=`internal`; projection = ### **a Conflict freezes a field (`conflicting`) — it does not write projected VALUES, it BLOCKS them (GR-10)**; `accountable_owner_id` required (a human, from creation).

| Event · v1 · producer | Proves / ¬Proves | Payload | Consumers → guard | Notes / tests |
|---|---|---|---|---|
| **`ConflictRaised`** ‡CF-1/IB-6/EF-4c | proves incompatible claims/observations exist on a field · ¬proves which is right (I8: not `unknown`, but too much info disagreeing) | `kind`(R ∈ {SYSTEM_VS_SYSTEM,CLAIM_VS_CLAIM,CLAIM_VS_OBSERVATION,INFERRER_VS_OWNER,READBACK_VS_APPROVED,RULE_VS_RULE}), `entity_ref`(R), `field`(R), `parties[]`(R), `owner_id`(R) | ### **every machine reading `field` → BLOCK consequential transitions (GR-10)** | coordination event (§9, ‡ three producers); `test_ev_conflictraised_freezes_field` |
| **`ConflictOpened`** CF-2 | proves a human acknowledged and owns it | — | Oversight | `test_ev_conflictopened` |
| **`ConflictEscalated`** CF-5 | proves it aged past threshold | — | Oversight | durable timer; ### **never escalates to a *resolution*** ; `test_ev_conflictescalated` |
| **`ConflictResolved`** CF-3/4 | proves closure by a **registered rule** or an **authenticated human** · ¬proves closure by recency/confidence/model | ### `rule_id \| decision_ref`(R, exactly one) | Projection (unfreeze); M6 (may drive a correction) | ### **exactly one of rule_id/decision_ref; a model/timer resolving is ILLEGAL (GR-15)**; `test_ev_conflictresolved_rule_or_human_only` |

## Cross-cutting
**Dedup:** the partial unique index `(tenant,entity_ref,field) WHERE state∈{RAISED,OPEN,ESCALATED}` — a second detection appends a party, no second `ConflictRaised`. **Ordering:** order-tolerant. **Replay:** reconstructs the frozen field deterministically. **Projection:** ### **while a Conflict is open the field is `conflicting` and BLOCKS every consequential action on the entity — this is the family that enforces "Neyma never silently chooses."** **Security:** ### **a Conflict is a SECURITY control — an injected competing claim yields a frozen entity + a human, not control (§24)**; a `RULE_VS_RULE` conflict is how two conflicting standing rules fail closed (GR-15). **Audit:** `high` (parties + resolution basis). **Open validation:** V5 (registered resolution rules) — fail-closed to a human.

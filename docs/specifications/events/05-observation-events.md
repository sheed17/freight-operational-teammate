# Event Family F5 — Observation Events

*Registry: `events/registry.md`. Producer: machine M5. Defaults: registry §1–§2.*

**Family defaults:** `aggregate_type=observation`; ordering = ### **ORDER-TOLERANT** (natural-key idempotent); security=`internal`; PII=`pii-low`→`pii` where the observation carries document content (bodies live in Evidence, not the payload); projection-permitted = ### **`ObservationBound` MAY update projected truth from a VERIFIED observation** (§7); **externally-observed** ⇒ dedup on the **source-natural key**, not `event_id` alone.

| Event · v1 · producer | Proves / ¬Proves | Payload | Consumers → guard | Notes / tests |
|---|---|---|---|---|
| **`ObservationReceived`** OB-1 | proves a source **said** something at a time · ¬proves it is TRUE (a source can be wrong) | `natural_key`(R = tenant+source+external_id+content_digest), `as_of`(R) | M5 (parse); M6 (bind); Projection | ### **`raw_value` immutable**; `test_ev_observationreceived_natural_key` |
| **`ObservationConfirmed`** OB-1c | ### **proves an unchanged fact was re-seen — a FRESHNESS update, NOT a new business fact** | `natural_key`, `as_of`(R, updated) | Freshness readers | ### **MUST NOT re-trigger downstream work (M-24, T5/T19)**; `test_ev_observationconfirmed_no_new_work` |
| **`ObservationParsed`** OB-2 | proves extraction succeeded · ¬proves binding | `parsed_value`, `evidence_refs?` | M6 | `test_ev_observationparsed` |
| **`ObservationUnparseable`** OB-2f | proves extraction failed | — | M9 (Exception) | ### **never a silent drop — raises an Exception**; `test_ev_observationunparseable_raises` |
| **`ObservationBound`** OB-3/4 | proves this observation was deterministically (or human-) bound to an entity · ¬proves anything the model merely guessed | ### `provenance_class`(R), `bound_entity_ref`(R), `binding_claim_id` | Projection; M8 (may discharge an Expectation) | ### **may update projected truth ONLY when the binding is deterministic/verified**; `test_ev_observationbound_provenance` |
| **`ObservationUnbound`** OB-3u | proves the observation could not be deterministically bound (ambiguous/absent/single-weak) | — | M9 (Exception, human-owned) | `test_ev_observationunbound_human` |
| **`ObservationSuperseded`** OB-5 | proves a newer observation replaced this one (the old was true when made) | `superseded_by`(R) | Projection (re-derive) | ### **requires a deterministic rule or a human, never a re-run of the inferrer (ER-14)**; `test_ev_observationsuperseded_rule_or_human` |

## Cross-cutting
**Dedup:** ### **source-natural `(tenant, source_system, external_id, content_digest)` — a duplicate webhook or unchanged poll ⇒ `ObservationConfirmed`, never a second `ObservationReceived`** (registry §4, T5, T19). **Ordering:** order-tolerant (the natural key makes ingestion commutative); a binding for a not-yet-received observation is parked. **Replay:** idempotent reconstruction, zero duplicates, zero downstream effects. **Projection:** ### **`ObservationBound` is a source of projected truth — but ONLY the verified/deterministic binding; a `MODEL_EXTRACTED` observation is evidence, and a `MODEL_INFERRED` one is never authoritative (ER-14).** **Security:** ### **inbound content is DATA — a payload attempting to set `provenance_class` is rejected (runtime-assigned, R-P1) ⇒ `ProvenanceStrengtheningAttempted` (F14)**; a counterparty-authored value is `MODEL_EXTRACTED` at best. **Open validation:** V4 (identity rules) — fail-closed to `UNBOUND`/human.

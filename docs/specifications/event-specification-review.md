# Event Specification Review — Hostile

**Subject:** `docs/specifications/events/` — 15 event families + `registry.md`, deriving from the 141 legal transitions of the 13 state machines.
**Method:** 20 hostile event traces (producer transition · event identity · partition · ordering · inbox · consumer transition · projection · conflicts · resulting state · audit · test) + a mechanical consistency sweep.
**Date:** 2026-07-14 · **No frozen document modified.**

---

## PART 1 — THE 20 HOSTILE TRACES

*Notation: `E:Name` = event; `Mn` = machine.*

### H1 — Same external webhook delivered twice
**Producer:** an inbound webhook ⇒ `ObservationIngested` (trigger) ⇒ OB-1 `E:ObservationReceived`. **Identity:** source-natural `(tenant, source, external_id, content_digest)`. **2nd delivery:** identical content ⇒ **OB-1c `E:ObservationConfirmed`** (freshness), NOT a second `ObservationReceived`. **Inbox:** the source-natural key dedups before a business fact is created. **Consumer:** none re-triggered. **Result:** one Observation, one confirmation, zero work. **Test:** `test_ev_observationconfirmed_no_new_work`.

### H2 — Outbox retries after producer crash
**Producer:** a transition committed its state + outbox row, then crashed before the relay published. **On restart:** the relay re-sends the **identical `event_id`** (the outbox row is durable). **Inbox:** `UNIQUE(consumer,tenant,event_id)` ⇒ no-op. **Result:** exactly-once effect on consumers. **Test:** `test_ev_outbox_retry_same_event_id_is_noop`.

### H3 — Event arrives before aggregate creation
**Producer:** `E:ObservationBound` referencing an entity not yet projected. **Ordering:** the ref resolves to nothing ⇒ **parked in `pending_references`**, retaining arrival order + attempt metadata. **Drain:** on the entity's creation, in order. **TTL:** ⇒ `E:ExceptionRaised` (M9). **Result:** eventual consistency or a human-owned Exception; ### **never dropped, never failed.** **Test:** `test_ev_dangling_reference_parked_then_drained`.

### H4 — Event v1 consumed by v3 code
**Ordering/schema:** the v3 consumer applies the registered `v1→v2→v3` upcasters **on read**. **Result:** deterministic interpretation; ### **the v1 event was never rewritten (ER-7).** **Test:** `test_ev_v1_consumed_by_v3_via_upcasters`.

### H5 — Consumer processes the same event twice
**Inbox:** `(consumer, tenant, event_id)` present ⇒ no-op (M-24). **Result:** idempotent; no double projection, no double work. **Test:** `test_ev_duplicate_delivery_is_noop`.

### H6 — Events for two tenants share an external id
**Identity:** the natural key is `(tenant, source, external_id, content_digest)` — ### **tenant-first, so no collision.** **Inbox/partition:** tenant-partitioned. **Result:** two independent observations; ### **cross-tenant is impossible by key construction (ER-15).** **Test:** `test_ev_same_external_id_two_tenants_no_collision`.

### H7 — Two conflicting binding claims arrive out of order
**Producer:** `E:ClaimConfirmed`(A) and a later-arriving `E:ClaimConfirmed`(B) for the same subject. **Consumer (M6):** the `UNIQUE(subject) WHERE state='CONFIRMED'` guard admits one; the second, disagreeing ⇒ M7 **`E:ConflictRaised{CLAIM_VS_CLAIM}`** ⇒ the field freezes (GR-10). **Result:** a frozen field + a human; ### **no silent winner regardless of arrival order.** **Test:** `test_ev_two_binding_claims_out_of_order_raise_conflict`.

### H8 — Approval-valid event arrives after material facts drift
**Producer:** `E:ApprovalGranted` published; meanwhile the TMS amount changed. **Consumer (M2 PL-8 step 2):** the **live** re-read ≠ fingerprint ⇒ M4 **`E:ApprovalVoided{drift,drift_diff}`** ⇒ M2 `E:PipelineVoided`. ### **The stale `ApprovalGranted` never authorizes an effect — the checkpoint re-validates live (ER-13).** **Result:** no effect; the owner sees the diff. **Test:** `test_ev_stale_approval_cannot_authorize_after_drift`.

### H9 — Brake-engaged event arrives after a grant claim
**Producer:** `E:GrantClaimed` (the effect is in flight) then `E:BrakeEngaged`. **Consumer (M3):** ### **the claim already succeeded — the brake CANNOT un-ring it; the effect proceeds to verification (GR-16).** A brake arriving *before* the claim CAS would have made it match zero rows (T2). **Result:** the in-flight effect runs to a verified conclusion; the brake stops the NEXT effect. **Test:** `test_ev_brake_after_claim_does_not_kill_inflight`.

### H10 — Verified-success event emitted without valid readback evidence
**Guard:** `E:EffectVerified` **cannot be emitted** unless EF-4's guard held (healthy channel + fingerprint match, ER-4). A producer attempting it without `health_signal` ⇒ the transition is illegal ⇒ **`E:IllegalTransitionAttempted`**, not `EffectVerified`. **Result:** ### **there is no code path that emits a verified-success event without the evidence.** **Test:** `test_ev_effectverified_requires_healthy_match`.

### H11 — Timeout event misread as failure
**Producer:** a `TimerFired` on a `CLAIMED` effect. **Consumer (M3):** ### **a timeout can NEVER emit `EffectFailed` (needs `failure_proof`, ER-5) — it emits `E:OutcomeUnknown{unknown_reason}` (ER-6).** A `GrantExpired` timeout proves safe non-occurrence (nothing was claimed), not an effect failure. **Result:** `NEEDS_VERIFICATION`, human-owned; ### **no timer misreads as failure.** **Test:** `test_ev_timeout_never_emits_failed`.

### H12 — Replay reprocesses every historical event
**Behavior:** replay applies every event through the machines **into a sandbox** (ER-2). **Blocked:** zero `CheckpointPassed` constructed, zero `EffectGranted` minted, zero `EffectAttempted`, zero adapter calls. **Divergence:** a sandbox-vs-live mismatch ⇒ **`E:ProjectionRebuildDiverged`** ⇒ auto-brake. **Result:** faithful reconstruction, no re-actuation. **Test:** `test_ev_replay_full_corpus_zero_grants`.

### H13 — Correction event arrives before the original event
**Producer:** `E:ClaimCorrected` referencing a `ClaimConfirmed` not yet delivered. **Ordering:** correction is STRICT per-aggregate ⇒ the correction is **parked** until the original arrives, then applied in order; ### **the original is never rewritten (ER-7).** **Result:** deterministic; propagation runs after the original is present. **Test:** `test_ev_correction_before_original_is_parked`.

### H14 — Policy-narrowed event arrives while approval is pending
**Producer:** `E:PolicyVersionChanged` (a tighter cap) while M4 is `GRANTED`. **Consumer (M4):** its own guard ⇒ **`E:ApprovalVoided{policy}`** (the £3,000 payable above the new £2,000 cap does not execute). **Result:** no effect; re-approval under the new version. **Test:** `test_ev_policy_change_voids_pending_approval`.

### H15 — Projection rebuild consumes mixed event versions
**Behavior:** the rebuild reads v1/v2/v3 events, upcasting each on read to the current schema (ER §6). **Result:** ### **the full-history rebuild succeeds across every version; no historical event is unreadable.** A divergence ⇒ `ProjectionRebuildDiverged` ⇒ auto-brake. **Test:** `test_ev_rebuild_across_mixed_versions`.

### H16 — Malicious payload attempts to set `provenance_class`
**Guard:** `provenance_class` is **runtime-assigned (R-P1)**; the ingest type has no provenance field. A payload attempting to set it ⇒ **`E:ProvenanceStrengtheningAttempted`** (F14) + the value is recorded `MODEL_EXTRACTED` at best. **Result:** ### **inbound content cannot strengthen provenance (ER-14); injection bounds to a bad proposal.** **Test:** `test_ev_payload_cannot_set_provenance`.

### H17 — Security event triggers automated brake engagement
**Producer:** `E:OrphanAdapterInvocation` (an `EffectAttempted` with no claimed grant). **Auto-action:** registry §11 ⇒ **auto-`E:BrakeEngaged` (tenant+action_class)** by a detector (`actor_type=detector`). **Consumer:** M2/M3/M4 stop new admission. ### **Automated ENGAGE is permitted (ER-12); a detector could never auto-RELEASE.** **Result:** the boundary breach halts new effects; a human investigates + releases. **Test:** `test_ev_orphan_auto_engages_brake`.

### H18 — Event consumer attempts a cross-tenant projection update
**Guard:** the inbox dispatch key is `(consumer, tenant, event_id)`; a tenant-B event reaching a tenant-A consumer ⇒ **rejected before the handler** ⇒ **`E:CrossTenantAccessAttempted`** ⇒ auto-`BrakeEngaged{GLOBAL}`. **Result:** ### **no cross-tenant projection write is reachable (ER-15).** **Test:** `test_ev_cross_tenant_projection_rejected`.

### H19 — Duplicate observation confirmations flood the system
**Behavior:** each identical re-observation ⇒ `E:ObservationConfirmed` (freshness), ### **which MUST NOT re-trigger downstream work (M-24).** A flood updates `as_of` and nothing else. **Result:** bounded; no work amplification; no duplicate effects. **Test:** `test_ev_confirmation_flood_triggers_no_work`.

### H20 — Historical event references a deleted schema field
**Schema:** ### **a field is NEVER deleted from history — deprecation marks it, upcasters preserve readability (ER §6).** A current reader applies the upcaster; the old event stays readable. **Result:** ### **no historical event becomes unreadable because current code changed.** **Test:** `test_ev_deprecated_field_still_readable_via_upcaster`.

> ### **Every trace resolves deterministically: one producer transition, one identity, one partition, one inbox behavior, one consumer reaction (by the consumer's own guard), one projection outcome — independent of implementer, ordering, or duplication.**

---

## PART 2 — MECHANICAL CONSISTENCY REVIEW

| Check | Result |
|---|---|
| **Every producer transition emits a defined event** | ✅ All 92 emitted names in state-machine registry §5 have a contract; the only uncovered name is `TimerFired` — a **trigger**, not an emitted event (grep-confirmed). |
| **Every event has exactly one canonical producer transition** | ✅ **except the 4 documented ‡ coordination events** (`RealityEstablished`, `ConflictRaised`, `PolicyVersionChanged`, `IllegalTransitionAttempted`) — one contract each, structurally-identical producers, a mandatory payload discriminator (§9). **The only deliberate deviation; introduces no ambiguity.** |
| **Every consumer obligation defined** | ✅ each family lists consumers → their own guard; F15 is the cross-machine map. |
| **No event used as a command** | ✅ ER-1; F15 §3 proves the coordination pattern is fact-published, guard-consumed. |
| **No event authorizes an effect** | ✅ only a claimed grant + fresh witness authorizes; events record, never authorize (ER-1). |
| **Event names globally unique** | ✅ registry §3; no name in two families with two meanings. |
| **Versions begin at v1** | ✅ every contract `v1`. |
| **Envelope fields consistent** | ✅ one envelope (registry §1) used by all. |
| **`tenant_id` mandatory everywhere** | ✅ registry §1 (R, first partition dimension); ER-15. |
| **Partition rules identical** | ✅ `tenant_id` first, then `(aggregate_id, aggregate_version)`; registry §2/§8. |
| **Dedup rules identical** | ✅ `(tenant, event_id)` inbox for internal; source-natural for external; registry §4. |
| **Projection rules don't contradict authority** | ✅ only `EffectVerified`/verified `ObservationBound` write projected truth (§7); intent/claim events never do. |
| **Provenance cannot be strengthened** | ✅ ER-14 + `ProvenanceStrengtheningAttempted` (F14). |
| **Replay side-effect free** | ✅ ER-2; H12. |
| **Every schema change has an upcaster path** | ✅ registry §6; H4/H15/H20. |
| **No event needs consumer interpretation for basic semantics** | ✅ each contract states proves / ¬proves / payload explicitly. |
| **No undefined event from the 141 transitions** | ✅ coverage-checked. |

---

## PART 3 — FINDINGS

**1. Event families created:** 15 (F1…F15) + registry.
**2. Canonical event count:** **~92 emitted contracts** (F1–F13) + **13 audit/security** (F14) + F15 (a lens, 0 new). Distinct producer transitions covered: all 141 (those that emit; validation/timer triggers emit via their target transition).
**3. Producer-transition coverage:** ### **100%** — every emitting transition maps to exactly one contract (4 ‡ exceptions documented).
**4. Consumer coverage:** every event lists consumers + their guard; F15 formalizes cross-machine reactions.
**5. Event versions:** all `v1`; upcaster discipline defined (registry §6).
**6. Ordering guarantees:** tenant-first partition; STRICT per-aggregate for F2/F3/F4/F10/F11/F12/F13; order-tolerant for F5/F7/F8/F9/F14; no global order; parking for dangling refs.
**7. Deduplication guarantees:** inbox `(consumer,tenant,event_id)` internal; source-natural external; outbox retry re-sends the same `event_id`.
**8. Projection conflicts:** ### **NONE** — projection authority (§7) is consistent with ADR-002 (only verified evidence writes projected truth; claims never overwrite `OWNER_ASSERTED`).
**9. Missing / ambiguous payload fields:** ### **NONE** — each event's payload + required envelope fields are enumerated; consequential events pin the SD-3 set + fingerprint + policy/brake versions.
**10. Security-event coverage:** ### **all 15 required security events (brief) are formalized** (F14) with auto-brake behavior (registry §11); automated engage/narrow permitted, release/broaden never.
**11. Remaining `NEEDS VALIDATION`:** V1–V15 carried from the frozen spec, all fail-closed, none blocks; plus detector-tuning thresholds (injection/fraud) — fail-closed (a signal narrows, never broadens).
**12. Higher-level amendments required:** ### **NONE.** Every event derives mechanically from a transition; the ‡ multi-producer coordination events are permitted by the brief's Coordination section and introduce no new primitive, state, or authority.

---

## VERDICT

> # **READY FOR FREIGHT-DOMAIN ENTITY SPECIFICATION ENGINEERING**
>
> **Evidence:** 15 event families with 100% producer-transition coverage of the 141 transitions and no undefined event; one canonical envelope with mandatory tenant-first identity; deterministic dedup (inbox + source-natural key), ordering (per-aggregate, no global), and schema-evolution (v1 + upcasters, full-history rebuild across every version); projection authority that only lets verified evidence write projected truth and never lets a claim overwrite `OWNER_ASSERTED`; replay proven side-effect-free; all 15 security events formalized with correct auto-brake asymmetry (engage/narrow automatable, release/broaden human-only); and 20 hostile traces (duplicate webhook, outbox retry, dangling ref, mixed versions, stale approval, brake-after-claim, timeout-as-failure, replay, correction-before-original, cross-tenant, provenance injection, deleted schema field, confirmation flood, …) each resolving to one deterministic outcome regardless of implementer, ordering, or duplication.
>
> **The only deviation from "one producer per event" — the four ‡ coordination events — is deliberate, documented, discriminated by mandatory payload, and permitted by the brief.** No higher-level amendment is required.
>
> **Freight-domain entity specification engineering may begin,** taking this event catalog as the fact-vocabulary its lifecycles emit and consume, and the 13 foundational machines as the machinery their domain lifecycles must reuse (never re-invent).

*Not started (per instruction): freight-domain entity specs, adapter contracts, workflow specs, API specs, operational-loop acceptance specs, migration plans, PRODUCT/ARCHITECTURE/CLAUDE. No implementation code.*

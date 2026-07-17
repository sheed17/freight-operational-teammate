# Event Specification Registry — Canonical Envelope, Events, Rules

**Layer:** Event Specification. **Derived mechanically from:** the 13 state machines + `state-machines/registry.md` §5 (the emitted-event list) + the 134 transitions + ADR-002/004/005/006/007/008/009/010/011 + the Semantic Model.
*(Errata 2026-07-16: corrected from 141. This file's §3 canonical list enumerates **98** emitted contracts across F1–F13 — itself correct and unchanged.)*
**Binding:** ### **This registry is the sole canonical list of event names and versions.** Every family file uses these names verbatim; a family file introducing an unlisted name or a local synonym is defective.

> ### **An event records a FACT that occurred. An event is NEVER a command, and NEVER authorizes a future action.** Consumers react according to **their own deterministic transition guards** (the 13 machines); the event does not instruct them. Replay of any event produces **zero** Checkpoint Witnesses, **zero** Effect Grants, **zero** external effects (GR-11).

---

## 1. THE CANONICAL EVENT ENVELOPE

**Every event, without exception, carries this envelope.** `R`=required always · `C`=required-when-applicable (nullable otherwise) · `I`=immutable once written.

| Field | Req | I | Semantics |
|---|---|---|---|
| `event_id` | R | I | uuid v4. **Globally unique.** The dedup identity (with `tenant_id`). |
| `event_name` | R | I | from §3; canonical, versioned. |
| `event_version` | R | I | integer ≥ 1; the schema version of THIS event type (§6). |
| `schema_version` | R | I | version of the envelope itself. |
| `occurred_at` | R | I | RFC-3339 UTC, ms precision — **when the fact happened**. |
| `recorded_at` | R | I | RFC-3339 UTC, ms — **when Neyma persisted it** (`≥ occurred_at`). |
| ### `tenant_id` | ### **R** | I | ### **MANDATORY on EVERY event. FIRST partition dimension. No event may omit it.** |
| `aggregate_type` | R | I | the producing machine's entity (`work_item`, `effect_grant`, …). |
| `aggregate_id` | R | I | the machine instance id. |
| `aggregate_version` | R | I | the monotonic version **after** the transition (OCC). |
| `work_item_id` | C | I | when the event belongs to a Work Item's causal chain. |
| `pipeline_instance_id` | C | I | when within a pipeline attempt. |
| `causation_id` | R | I | the `event_id` that **directly caused** this one (`null` only for a root ingress event). |
| `correlation_id` | R | I | the business-transaction id, stable across the whole chain. |
| `producer_component` | R | I | the owning service. |
| `producer_transition_id` | R | I | ### **the exact transition (e.g. `PL-8`) that emitted it — the mechanical link to the state machine.** |
| `actor_type` | R | I | `human` · `system` · `detector` · `model` *(a model actor may only produce claim/proposal events — never `OWNER_ASSERTED`, policy activation, or brake release)*. |
| `actor_id` | R | I | the authenticated human, the detector id, or `system`. |
| `accountable_owner_id` | C | — | the human accountable for the affected work (I1), where applicable. |
| `policy_version` | C | I | pinned when the event participated in a policy decision. |
| `brake_version` | C | I | pinned when brake admission was evaluated. |
| `provenance_refs` | C | I | the `provenance_class` + lineage of any claim/value carried. |
| `evidence_refs` | C | I | **content-addressed** (`sha256`) artifact+span references. |
| `observation_refs` | C | I | the observation versions the fact derived from. |
| `material_facts_fingerprint` | C | I | pinned for approval/checkpoint/effect events. |
| `entity_versions` | C | I | the **SD-3 set** for consequential events (every entity referenced by a material fact, the target resource, and any gate-precondition entity). |
| `trace_id` | R | I | distributed-trace id (observability). |
| `idempotency_identity` | R | I | §4 — the dedup key beyond `event_id` (source-natural for external, transition-natural for internal). |
| `payload` | R | I | the type-specific body (per event, §3). |
| `metadata` | C | — | non-authoritative annotations (never gates anything). |

**Rules:** ### **all envelope fields are IMMUTABLE and APPEND-ONLY** (S8, no UPDATE/DELETE). Canonical serialization = the `fp_v1` rules of ADR-005 §3.4 (UTF-8 NFC, bytewise-sorted keys, money as integer minor units — **floats forbidden**, `null`≠absent, enums by name). Identifiers are uuid v4 except content-addressed refs (`sha256`). **Tenant is the first partition dimension of every store, stream, and inbox** (C-1).

---

## 2. THE 40-FIELD EVENT CONTRACT — with per-family DEFAULTS

Each event's contract has the 40 fields from the brief. To stay deterministic **and** readable, each **family file declares defaults once**; an event states only what differs. ### **An unstated field takes the family default verbatim — never an implementer's choice.**

**Universal contract defaults** (a family overrides as noted):

| # | Field | Default |
|---|---|---|
| 3 | Current version | `v1` |
| 8 | What it does NOT prove | *(stated per event where non-obvious)* |
| 9 | Triggering actor | `system` (deterministic) |
| 14–17 | provenance / evidence / material-facts / entity-versions | **none** *(consequential events override — §5)* |
| 18 | Ordering key | `(tenant_id, aggregate_id, aggregate_version)` — **per-aggregate order; NO global order** |
| 19 | Partition key | `tenant_id` |
| 20 | Deduplication identity | `(tenant_id, event_id)` in the consumer inbox |
| 21 | Idempotency | redelivery is a **no-op** (inbox) |
| 24 | Projection updates permitted | **none** |
| 25 | Projection updates forbidden | **all projected state** *(only verified-observation/readback events override — §7)* |
| 26 | Replay | ### **side-effect free: reconstruct state only; zero witnesses/grants/effects (GR-11)** |
| 27 | Backfill | permitted into the sandbox; never re-emits to real consumers |
| 28 | Out-of-order | consumers tolerate it; a ref to a missing aggregate is **parked** (§8) |
| 29 | Duplicate-delivery | inbox no-op (field 20) |
| 30 | Dangling-reference | parked in `pending_references`, drained in arrival order, TTL ⇒ Exception |
| 31 | Retention | **permanent** (tiered hot 90d / warm 2y / cold 7y) |
| 32 | Security classification | `internal` *(security family = `security`)* |
| 33 | PII classification | `none` *(events carrying counterparty/customer names = `pii-low`; document bodies live in Evidence, not payloads = `pii` in Evidence store)* |
| 34 | Audit significance | standard *(decision/effect/security events = `high`)* |
| 35 | Compatibility | additive within a version; breaking ⇒ new version + upcaster (§6) |
| 36 | Upcasting | identity `vN→vN` ; a real change ships a registered `vN→vN+1` upcaster |
| 37 | Deprecation | §6.3 — never deleted; marked deprecated, still upcast-readable |
| 40 | Open validation | none *(stated per event where present)* |

---

## 3. CANONICAL EVENT LIST *(name · v · producer transition · family)*

*(One producer transition per event unless marked ‡ — a **coordination event** with structurally-identical producers, permitted by the brief's Coordination section; see §9.)*

**F1 Work Item:** `WorkItemCreated`(WI-1) · `WorkStarted`(WI-2) · `WorkItemClosed`(WI-3) · `AttemptFailed`(WI-4) · `WorkBlocked`(WI-5/6) · `WorkUnblocked`(WI-8) · `HumanRequested`(WI-7) · `HumanDecided`(WI-9) · `WorkEscalated`(WI-10) · `OwnershipTransferred`(WI-11) · `WorkItemCancelled`(WI-12) · `Reopened`(WI-13)
**F2 Pipeline:** `PipelineStarted`(PL-1) · `DuplicateProposalAbsorbed`(PL-1b) · `PolicyEvaluated`(PL-2) · `IntentValidated`(PL-4) · `PipelineRejected`(PL-3/5) · `ApprovalBound`(PL-7b) · `CheckpointPassed`(PL-8) · `CheckpointFailed`(PL-8f) · `PipelineVoided`(PL-7v/9v) · `EffectRecorded`(PL-12) · `ProjectionUpdated`(PL-13) · `PipelineClosed`(PL-14)
**F3 External Effect / Grant:** `EffectGranted`(EF-1) · `GrantClaimed`(EF-2) · `EffectAttempted`(EF-2) · `ClaimRefused`(EF-2f) · `GrantRevoked`(EF-2r) · `GrantExpired`(EF-2x) · `EffectExecuted`(EF-3) · `EffectFailed`(EF-3f) · `OutcomeUnknown`(EF-3u/EF-4c/EF-4u) · `EffectVerified`(EF-4) · `VerificationConflict`(EF-4c) · `VerificationUnavailable`(EF-4u) · `VerificationDeferred`(PL-11d) · `RealityEstablished`‡(EF-5/CM-5)
**F4 Approval:** `ApprovalRequested`(AP-1) · `ApprovalGranted`(AP-2) · `ApprovalDenied`(AP-2d) · `ApprovalExpired`(AP-3) · `ApprovalVoided`(AP-4/4p/5) · `ApprovalRevoked`(AP-6) · `ApprovalConsumed`(AP-7)
**F5 Observation:** `ObservationReceived`(OB-1) · `ObservationConfirmed`(OB-1c) · `ObservationParsed`(OB-2) · `ObservationUnparseable`(OB-2f) · `ObservationBound`(OB-3/4) · `ObservationUnbound`(OB-3u) · `ObservationSuperseded`(OB-5)
**F6 Identity Binding Claim:** `ClaimProposed`(IB-1) · `ClaimConfirmed`(IB-2/2r/2h) · `ClaimEvidenced`(IB-3) · `ClaimAmbiguous`(IB-4) · `ClaimSuperseded`(IB-5/8) · `ClaimCorrected`(IB-7)
**F7 Conflict:** `ConflictRaised`‡(CF-1/IB-6/EF-4c-conflict) · `ConflictOpened`(CF-2) · `ConflictEscalated`(CF-5) · `ConflictResolved`(CF-3/4)
**F8 Expectation:** `ExpectationRaised`(EX-1) · `ExpectationDischarged`(EX-2/4) · `ExpectationOverdue`(EX-3) · `ExpectationIndeterminate`(EX-3i) · `ExpectationReVersioned`(EX-5) · `ExpectationCancelled`(EX-6) · `ExpectationExpired`(EX-7)
**F9 Exception:** `ExceptionRaised`(EC-1) · `ExceptionAcknowledged`(EC-2) · `ExceptionAgeing`(EC-4) · `ExceptionEscalated`(EC-5) · `ExceptionResolved`(EC-3/6)
**F10 Compensation:** `CompensationRequired`(CM-1) · `CompensationRefused`(CM-1r) · `CompensationApproved`(CM-2) · `CompensationImpossible`(CM-2n) · `CompensationStarted`(CM-3) · `CompensationCompleted`(CM-4) · `CompensationFailed`(CM-4f)
**F11 Policy:** `PolicyProposed`(PO-1) · `PolicyActivated`(PO-4) · `PolicySuperseded`(PO-5) · `PolicyRevoked`(PO-6) · `PolicyExpired`(PO-7) · `PolicyVersionChanged`‡(PO-4/6)
**F12 Rule:** `RuleProposed`(RU-1) · `RuleCompiled`(RU-2) · `RuleNotEnforceable`(RU-2f) · `RuleConfirmed`(RU-4) · `RuleActivated`(RU-5) · `RuleSuperseded`(RU-6) · `RuleRevoked`(RU-7)
**F13 Brake:** `BrakeEngaged`(BR-1) · `BrakeWidened`(BR-2) · `BrakeNarrowed`(BR-3) · `BrakeReleased`(BR-4)
**F14 Audit & Security:** `IllegalTransitionAttempted`‡(any machine, GR-1) · `CrossTenantAccessAttempted` · `OrphanAdapterInvocation` · `StaleWitnessUsed` · `GrantDoubleClaimAttempted` · `ProvenanceStrengtheningAttempted` · `OwnerAssertedOverwriteAttempted` · `UnauthorizedPolicyActivationAttempted` · `UnauthorizedBrakeReleaseAttempted` · `CounterpartySelfAuthorizationDetected` · `PromptInjectionSignal` · `ProjectionRebuildDiverged` · `FraudSignalRaised`
**F15 Coordination** *(no new contracts — a lens over cross-machine consumption; §9):* `CheckpointPassed`, `PolicyVersionChanged`, `BrakeEngaged`, `ApprovalGranted`, `OutcomeUnknown`, `ConflictOpened`, `ExpectationIndeterminate`, `CompensationRequired`, `RealityEstablished`.

> **Every name above appears in the state-machine registry §5 OR is an F14 security event named in the brief. Producer-transition coverage and the reverse (no undefined event) are asserted in `event-specification-review.md`.**

---

## 4. EVENT IDENTITY & DEDUPLICATION

- **`event_id`** — globally unique uuid; the primary dedup key with `tenant_id`.
- **Internally-emitted events** (all F1–F13) — **transition-natural identity** = `(tenant_id, aggregate_id, aggregate_version, producer_transition_id)`. ### **A re-emission after a producer crash (outbox retry) carries the SAME `event_id`** (the outbox row is written in the transition's commit, so a retry re-sends the identical row) ⇒ inbox no-op.
- **Externally-observed events** (an inbound webhook/poll ⇒ an `ObservationIngested` trigger ⇒ `ObservationReceived`) — **source-natural identity** = `(tenant_id, source_system, external_id, content_digest)` (M5). ### **A duplicate webhook or a duplicate poll of unchanged content ⇒ `ObservationConfirmed` (freshness update), NOT a new business fact** (T5, T19).
- **Inbox** — `UNIQUE(consumer_id, tenant_id, event_id)`; processing + inbox-insert are one commit (M-24). Redelivery is a no-op.
- **Outbox** — at-least-once; the relay retries until published; dedup is the consumer's job (the inbox).

---

## 5. WHICH EVENTS ARE CONSEQUENTIAL *(carry fields 14–17 + policy/brake/fingerprint pins)*

`ApprovalRequested`, `ApprovalGranted`, `ApprovalConsumed`, `CheckpointPassed`, `EffectGranted`, `GrantClaimed`, `EffectAttempted`, `EffectExecuted`, `EffectVerified`, `EffectFailed`, `OutcomeUnknown`, `RealityEstablished`, `CompensationApproved`, `CompensationStarted`, `CompensationCompleted`, `ClaimConfirmed`(when it backs a money action), `PolicyActivated`, `PolicyVersionChanged`, `BrakeEngaged`, `BrakeReleased`.
### **Each MUST pin the SD-3 `entity_versions` set, the `material_facts_fingerprint` where an amount is involved, `policy_version`, and `brake_version` — sufficient to reproduce the decision context at that time** (audit reproducibility, §11 of the brief).

---

## 6. SCHEMA EVOLUTION

- **Every event is versioned from `v1`.** **Additive** (new optional field) = same version. **Breaking** (remove/rename/retype/semantics-change) = **new version + a registered `vN→vN+1` upcaster**, deterministic, applied **on read**.
- **Upcaster ownership:** the producing family owns its upcasters. **Historical events are NEVER rewritten** (S8).
- ### **The full-history rebuild test runs against EVERY historical event version** — old events remain readable forever via upcasters (M-25). **No historical event may become unreadable because current code changed.**
- **Mixed-version deployment:** a `vN` producer + a `vN+1` consumer ⇒ the consumer upcasts on read; a `vN+1` producer + a `vN` consumer ⇒ additive fields are ignored, breaking changes are gated by a coordinated rollout (the new version is not produced until all consumers can read it).
- **Deprecation/retirement:** an event type is marked `deprecated` (still readable, upcast); it is **never deleted** from history.

---

## 7. PROJECTION AUTHORITY

> ### **Projected state updates ONLY from `EffectVerified` (a healthy-channel readback matching the approved fingerprint) or a verified `ObservationBound`.** No other event may write projected truth (M-2).

- **Intent events** (`PipelineStarted`, `IntentValidated`, `ApprovalGranted`, …) — ### **NEVER update projected truth.**
- **Claim events** (`ClaimProposed`, `ClaimConfirmed`, `ClaimCorrected`) — write **native** claim/binding state; ### **NEVER silently overwrite `OWNER_ASSERTED` state** (a `LINKER_INFERRED` recompute of an `OWNER_ASSERTED` binding is illegal at the source — IB-5x).
- **A consumer may raise a Conflict** when an event contradicts existing `consistent` state (CF-1); ### **no consumer may strengthen provenance, and no consumer may treat `MODEL_INFERRED` as authoritative evidence** (R-P2, GR-8).
- **`ExpectationDischarged`** may discharge an Expectation; **`PipelineClosed`** may satisfy a Work Item's closure criterion **but does not itself close it** (WI-3 requires "obligation satisfied").

---

## 8. ORDERING

- ### **Tenant is the first partition dimension.** **Per-aggregate order** (`aggregate_id, aggregate_version`) is guaranteed **within** an aggregate. ### **NO global order is assumed.**
- **Cross-aggregate order** is encoded through `causation_id` + the consumer's own transition guards (a consumer acts only when its own preconditions hold). ### **Consumers MUST tolerate out-of-order delivery.**
- **An event referencing an aggregate that does not exist yet is PARKED** (`pending_references`), retaining arrival order + attempt metadata; drained in order on creation; TTL ⇒ Exception (T18).
- **Strict per-aggregate ordering REQUIRED:** F2 Pipeline, F3 Effect/Grant, F4 Approval, F11 Policy, F13 Brake *(their version-monotonic transitions depend on it)*. **Order-tolerant:** F5 Observation (natural-key idempotent), F7 Conflict (parties attach), F9 Exception, F14 Security (each is independently meaningful).

---

## 9. COORDINATION EVENTS *(no new contracts, no commands)*

The F15 events are **already defined in their home families**; F15 is a **lens** naming the cross-machine reactions. ### **A coordination event does NOT instruct a consumer to transition — the consumer transitions iff ITS OWN deterministic guard holds.** Example: `BrakeEngaged` is consumed by M2 (⇒ `PipelineVoided` iff pre-claim), M4 (⇒ `VOID_ON_BRAKE`), M3 (the claim CAS re-checks `brake_version`) — **each by its own guard**, not by the event's command.

**The three ‡ events with two structurally-identical producers** — `RealityEstablished` (EF-5, CM-5), `ConflictRaised` (CF-1, IB-6, EF-4c), `PolicyVersionChanged` (PO-4, PO-6), `IllegalTransitionAttempted` (any) — are **one contract each**, with the `subject`/`kind`/`source` in the payload. This is the coordination pattern the brief permits; it is flagged in the review as the only deviation from "exactly one producer transition," and it is deliberate (one semantic fact, several origins).

---

## 10. GLOBAL EVENT SEMANTIC RULES *(ER-n)*

| # | Rule |
|---|---|
| **ER-1** | An event records a fact that occurred; it is never a command and never authorizes a future action. |
| **ER-2** | Replay of events produces zero Checkpoint Witnesses, zero Effect Grants, zero external effects. |
| **ER-3** | An event after an illegal-transition attempt records **rejection** (`IllegalTransitionAttempted`), never success. |
| **ER-4** | No event may claim `EffectVerified`/`VERIFIED_SUCCESS` unless ADR-006 verification (healthy channel + fingerprint match) was satisfied. |
| **ER-5** | A timeout event (`TimerFired`-derived) can never imply failure (GR-5). |
| **ER-6** | An unknown-outcome event (`OutcomeUnknown`) MUST carry `unknown_reason`. |
| **ER-7** | A correction event (`ClaimCorrected`) never deletes/rewrites the original event (S8). |
| **ER-8** | Reopening (`Reopened`) emits new events and preserves prior closure events. |
| **ER-9** | A model-generated claim event stays a claim, never a fact; `actor_type=model` may only produce claim/proposal events. |
| **ER-10** | An `OWNER_ASSERTED`-provenance event cannot be produced by a machine actor. |
| **ER-11** | `PolicyActivated` and `BrakeReleased` require `actor_type=human` (authenticated). |
| **ER-12** | Automated actors may emit `PolicyRevoked`(narrowing) and `BrakeEngaged`/`BrakeWidened` only where allowed; never `PolicyActivated`(broaden) or `BrakeReleased`/`BrakeNarrowed`. |
| **ER-13** | Every consequential event carries enough refs (§5) to reproduce its decision context at that time. |
| **ER-14** | No consumer may strengthen provenance; no consumer may treat `MODEL_INFERRED` as authoritative evidence. |
| **ER-15** | Every event carries `tenant_id`; cross-tenant consumption is rejected before any handler (⇒ `CrossTenantAccessAttempted`). |

---

## 11. SECURITY EVENTS → BRAKE *(auto-engagement table — F14)*

| Security event | Auto-brake? | Scope |
|---|---|---|
| `OrphanAdapterInvocation` | ### **YES — engage** | tenant + action_class |
| `CrossTenantAccessAttempted` | ### **YES — engage** | **GLOBAL** |
| `ProjectionRebuildDiverged` | ### **YES — engage** | tenant |
| `GrantDoubleClaimAttempted` | narrow autonomy | tenant + action_class |
| `CounterpartySelfAuthorizationDetected` / `FraudSignalRaised` | narrow autonomy | tenant + action_class + counterparty |
| `StaleWitnessUsed` · `ProvenanceStrengtheningAttempted` · `OwnerAssertedOverwriteAttempted` · `IllegalTransitionAttempted` | log + alert *(Sev by context)* | — |
| `UnauthorizedPolicyActivationAttempted` · `UnauthorizedBrakeReleaseAttempted` | log + alert (Sev-0) | — |
| `PromptInjectionSignal` | narrow autonomy | tenant + surface |

### **Automated brake engagement/narrowing is permitted (ER-12); automated release/broadening is never.**

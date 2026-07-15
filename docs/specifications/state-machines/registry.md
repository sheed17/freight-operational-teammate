# State-Machine Registry — Canonical States, Events, Triggers & Global Rules

**Layer:** Executable Specification. **Derived from (frozen):** the foundational entity specifications (`docs/specifications/entities/`), the Target Spec (`7ae1564`), ADR-001…011, the Semantic Model.
**Binding:** ### **Every machine file uses ONLY the names in this registry. No machine may define a local synonym.** A machine using an unregistered state or event name is defective.

---

## 1. TRIGGER TYPES *(the closed set — point 4 of every transition)*

| Code | Trigger type |
|---|---|
| **H** | authenticated human action |
| **S** | deterministic system decision |
| **X** | observed external event (an Observation) |
| **T** | timer or expectation (`TimerFired`) |
| **P** | policy change |
| **B** | brake change |
| **R** | recovery process (crash-recovery pass) |

---

## 2. THE TRANSITION-ROW CONTRACT *(the 26 required fields, and the per-machine DEFAULTS)*

Every transition specifies all 26 fields from the brief. To keep the tables deterministic **and** readable, each machine file declares **defaults** once; a transition row states only the fields that differ. ### **The defaults are explicit and normative — an unstated field takes the default value verbatim, never an implementer's choice.**

**Universal defaults (apply to every machine unless the machine overrides):**

| Field | Default |
|---|---|
| Trigger type | `S` (deterministic system decision) |
| Preconditions | none beyond "current state matches" |
| Required evidence | none |
| Required provenance | n/a |
| Material facts consumed | none |
| Required entity versions | **none** *(only consequential transitions revalidate — see **GR-13**)* |
| Approval requirement | none |
| Policy requirement | none |
| Brake requirement | none |
| Concurrency guard | **optimistic: `WHERE version = :expected` (OCC), one writer wins (**GR-3**)** |
| Idempotency key | the triggering `event_id` in the consumer inbox `(consumer_id, tenant_id, event_id)` (**GR-4**) |
| Transactional writes | the state row (`state`, `version++`) + the emitted event into the outbox, **one commit** (**GR-2**) |
| Event version | `v1` |
| Accountable owner after | unchanged from before the transition |
| External side effects | **none** |
| Verification requirement | none |
| Failure result | the transition raises; state unchanged; no event but `IllegalTransitionAttempted` if the trigger was not legal here (**GR-5**) |
| Retry eligibility | n/a |
| Compensation implication | none |
| Audit evidence | the emitted event is the audit record |
| Validating test | named inline |

**A transition row therefore shows: `ID · from → to · trigger(type) · [only the non-default fields] · event · test`.**

---

## 3. GLOBAL TRANSITION RULES *(GR-n — referenced by every machine)*

| # | Rule |
|---|---|
| **GR-1** | **Anything not enumerated as a legal transition is ILLEGAL.** An illegal `(state, trigger)` raises a hard domain error, persists nothing, and emits **`IllegalTransitionAttempted`** (audit **and** security). |
| **GR-2** | **The state change + emitted events are ONE commit** (transactional outbox). No state change without its event; no event without its transition. |
| **GR-3** | **Concurrency = optimistic version check.** A transition writes `WHERE version = :expected`; **zero rows ⇒ lost-update ⇒ raise & retry-from-reload.** No lock is held across human time (**GR-3a**). |
| **GR-4** | **Idempotency = the consumer inbox.** A redelivered trigger `(consumer, tenant, event_id)` is a **no-op**. |
| **GR-5** | **A timeout alone never proves failure.** `FAILED` requires affirmative evidence the intended effect did not occur. |
| **GR-6** | **`UNKNOWN_OUTCOME` never silently becomes success or failure.** No timer transition may move it (illegal). |
| **GR-7** | **A model never performs a transition requiring commercial judgment.** Guards are deterministic (P2). |
| **GR-8** | **`MODEL_INFERRED` never gates a consequential transition, at any confidence.** Confidence is not a guard input. |
| **GR-9** | **`OWNER_ASSERTED` state is never overwritten by machine recomputation.** `RecomputedByInferrer` on an `OWNER_ASSERTED` value is illegal. |
| **GR-10** | **An open Conflict blocks every consequential transition on the affected entity/field** (the field is `conflicting`; fail closed). |
| **GR-11** | **Replay never creates a Checkpoint Witness, claims an Effect Grant, or causes an external effect.** Replay is sandboxed, zero-emission (K-3). |
| **GR-12** | **Correction never rewrites historical events** (append-only). Reopening creates a new phase or a linked Work Item. |
| **GR-13** | ### **Every CONSEQUENTIAL transition revalidates the version of EVERY entity that is (a) referenced by a material fact, (b) the target resource, or (c) a gate-precondition entity — the exact set of SD-3 / witness point 13. The implementer MAY NOT choose this set dynamically.** |
| **GR-14** | **Exception closure requires a valid `decision_ref`** — an `audit_events` human-decision row **or** an `ACTIVE` `rule_id` (K-1). |
| **GR-15** | **Policy conflicts fail closed** (a rule-vs-rule conflict blocks; a human resolves; never auto-merge). |
| **GR-16** | **Brake activation prevents new admission but does not kill in-flight work.** It refuses to mint and refuses to claim. |
| **GR-17** | **A "consequential transition"** = one that (i) produces or authorizes an External Effect, (ii) consumes an Approval, (iii) writes a projected field that gates money, or (iv) confirms an identity binding used by (i)–(iii). These carry GR-13, brake, policy, and freshness checks. **All other transitions are administrative** and carry only GR-1…GR-5. |

---

## 4. CANONICAL STATE REGISTRY

*(Every state used by any machine. `(T)` terminal · `(NH)` non-terminal human-owned · `(R)` recoverable transient.)*

### M1 Work Item
`OPEN` `(R)` · `IN_PROGRESS` `(R)` · `BLOCKED` `(NH)` · `AWAITING_HUMAN` `(NH)` · `ESCALATED` `(NH)` · `CLOSED` `(T)` · `CANCELLED` `(T)`

### M2 Pipeline Instance
`PROPOSED` `(R)` · `POLICY_CHECKED` `(R)` · `VALIDATED` `(R)` · `AWAITING_APPROVAL` `(NH)` · `CHECKPOINT` `(R)` · `GRANTED` `(R)` · `CLAIMED` `(R)` · `EXECUTED` `(R)` · `VERIFIED` `(R)` · `RECORDED` `(R)` · `PROJECTED` `(R)` · `CLOSED` `(T)` · `REJECTED` `(T)` · `VOIDED` `(T)` · `FAILED` `(T)` · `NEEDS_VERIFICATION` `(NH)`

### M3 External Effect / Effect Grant *(one row, eight states — SD-2)*
`GRANTED` `(R)` · `CLAIMED` `(R)` · `ATTEMPTED` `(R)` · `VERIFIED` `(T)` · `FAILED` `(T)` · `EXPIRED_UNCLAIMED` `(T)` · `REVOKED` `(T)` · `UNKNOWN_OUTCOME` `(NH)`

### M4 Approval
`REQUESTED` `(R)` · `GRANTED` `(R)` · `CONSUMED` `(T)` · `DENIED` `(T)` · `EXPIRED` `(T)` · `REVOKED` `(T)` · `VOID_ON_DRIFT` `(T)` · `VOID_ON_BRAKE` `(T)`

### M5 Observation
`RECEIVED` `(R)` · `PARSED` `(R)` · `BOUND` `(T)` · `UNBOUND` `(NH)` · `CONFIRMED` `(R)` · `SUPERSEDED` `(T)` · `UNPARSEABLE` `(NH)`

### M6 Identity Binding Claim
`PROPOSED` `(R)` · `CONFIRMED` `(R)` · `AMBIGUOUS` `(NH)` · `REJECTED` `(T)` · `SUPERSEDED` `(T)` · `CORRECTED` `(R)` · `CONFLICTING` `(NH)`

### M7 Conflict
`RAISED` `(R)` · `OPEN` `(NH)` · `ESCALATED` `(NH)` · `RESOLVED_BY_RULE` `(T)` · `RESOLVED_BY_HUMAN` `(T)`

### M8 Expectation
`RAISED` `(R)` · `DISCHARGED` `(T)` · `OVERDUE` `(NH)` · `INDETERMINATE` `(NH)` · `CANCELLED` `(T)` · `EXPIRED` `(T)`

### M9 Exception
`OPEN` `(NH)` · `ACKNOWLEDGED` `(NH)` · `AGEING` `(NH)` · `ESCALATED` `(NH)` · `RESOLVED` `(T)`

### M10 Compensation
`REQUIRED` `(NH)` · `APPROVED` `(R)` · `EXECUTING` `(R)` · `COMPLETED` `(T)` · `COMPENSATION_FAILED` `(NH)` · `NOT_POSSIBLE` `(NH)`

### M11 Policy
`DRAFT` `(R)` · `PROPOSED` `(R)` · `APPROVED` `(R)` · `ACTIVE` `(R)` · `SUPERSEDED` `(T)` · `REVOKED` `(T)` · `EXPIRED` `(T)`
*(§4 of the brief also names "narrowed / suspended / invalid" — see M11 for how these map to ACTIVE-with-scope / REVOKED / REJECTED without new states.)*

### M12 Rule
`PROPOSED` `(R)` · `COMPILED` `(R)` · `CONFIRMED` `(R)` · `ACTIVE` `(R)` · `REJECTED` `(T)` · `SUPERSEDED` `(T)` · `REVOKED` `(T)` · `EXPIRED` `(T)`
*(the brief's "parsed / invalid / conflict detected / awaiting confirmation / suspended" map to PROPOSED / REJECTED / (a raised Conflict) / COMPILED / REVOKED — see M12.)*

### M13 Brake
`ACTIVE` `(R)` · `RELEASED` `(T)`

> ### **No state appears in two machines with two meanings.** `GRANTED` (M2 pipeline stage vs M3 grant state) and `CLAIMED` (M2 vs M3) are the **same conceptual event surfaced on the two machines that share the moment** — the pipeline reflects the grant/effect row's state; they are co-transitioned, not two meanings (see M2↔M3 co-transition rule in both files).

---

## 5. CANONICAL EVENT REGISTRY

*(Every event any transition emits. `producer` = owning machine. All carry the canonical envelope: `event_id, tenant_id, event_type, event_version, producer, entity_type, entity_id, entity_version, pipeline_instance_id?, work_item_id?, causation_id, correlation_id, actor, occurred_at, recorded_at`. Only **additional** payload is listed.)*

| Event | Producer | Added payload |
|---|---|---|
| `WorkItemCreated` | M1 | `owner_id, type, entity_ref?` |
| `WorkStarted` · `WorkUnblocked` | M1 | — |
| `WorkBlocked` | M1 | `reason` |
| `HumanRequested` | M1 | `question?` |
| `HumanDecided` | M1 | `decision_ref` |
| `WorkEscalated` · `ExceptionAgeing`… | M1/M9 | — |
| `OwnershipTransferred` | M1 | `from_owner, to_owner` |
| `WorkItemClosed` · `WorkItemCancelled` | M1 | `decision_ref` |
| `Reopened` | M1 | `prior_closure_ref, phase_seq \| linked_work_item_id, decision_ref` |
| `PipelineStarted` · `DuplicateProposalAbsorbed` | M2 | `commit_key` |
| `PolicyEvaluated` | M2 | `policy_version, gate_decision, decision, reason` |
| `IntentValidated` · `PipelineRejected` | M2 | `reason?` |
| `ApprovalRequested` | M4 | `fingerprint, gate_decision` |
| `ApprovalBound` | M2 | `approval_id` |
| `CheckpointPassed` | M2 | `checkpoint_id` |
| `CheckpointFailed` | M2 | `step, reason` |
| `EffectGranted` | M3 | `grant_id, checkpoint_id, commit_key` |
| `GrantClaimed` · `EffectAttempted` | M3 | `grant_id` |
| `ClaimRefused` | M3 | `grant_id, cause` |
| `GrantExpired` · `GrantRevoked` | M3 | `grant_id, cause?` |
| `PipelineVoided` | M2 | `reason` |
| `EffectExecuted` | M3 | — |
| `EffectVerified` | M3 | `verification_outcome, health_signal` |
| `EffectFailed` | M3 | `failure_proof` |
| `OutcomeUnknown` | M3 | `exposure, unknown_reason` |
| `VerificationConflict` · `VerificationUnavailable` · `VerificationDeferred` | M3 | `unknown_reason \| recheck_at` |
| `EffectRecorded` · `ProjectionUpdated` · `PipelineClosed` | M2/M3 | — |
| `RealityEstablished` | M3 | `decision_ref, outcome` |
| `ApprovalGranted` · `ApprovalDenied` · `ApprovalRevoked` | M4 | — |
| `ApprovalExpired` | M4 | — |
| `ApprovalVoided` | M4 | `cause ∈ {drift, policy, brake}, drift_diff?` |
| `ApprovalConsumed` | M4 | — |
| `ObservationReceived` · `ObservationConfirmed` · `ObservationParsed` · `ObservationUnparseable` | M5 | `natural_key` |
| `ObservationBound` · `ObservationUnbound` · `ObservationSuperseded` | M5 | `provenance_class?` |
| `ClaimProposed` · `ClaimConfirmed` · `ClaimEvidenced` · `ClaimAmbiguous` · `ClaimCorrected` · `ClaimSuperseded` | M6 | `provenance_class, match_method` |
| `ConflictRaised` · `ConflictOpened` · `ConflictEscalated` | M7 | `kind` |
| `ConflictResolved` | M7 | `rule_id \| decision_ref` |
| `ExpectationRaised` · `ExpectationDischarged` · `ExpectationOverdue` · `ExpectationIndeterminate` · `ExpectationReVersioned` · `ExpectationCancelled` · `ExpectationExpired` | M8 | `deadline?, coverage_ref?` |
| `ExceptionRaised` | M9 | `severity, exposure?, source_ref` |
| `ExceptionAcknowledged` · `ExceptionEscalated` | M9 | — |
| `ExceptionResolved` | M9 | `decision_ref` |
| `CompensationRequired` · `CompensationRefused` · `CompensationApproved` · `CompensationStarted` · `CompensationCompleted` · `CompensationFailed` · `CompensationImpossible` | M10 | `exposure, original_effect_id` |
| `PolicyProposed` · `PolicyActivated` · `PolicySuperseded` · `PolicyRevoked` · `PolicyExpired` · `PolicyVersionChanged` | M11 | `policy_version` |
| `RuleProposed` · `RuleCompiled` · `RuleNotEnforceable` · `RuleConfirmed` · `RuleActivated` · `RuleSuperseded` · `RuleRevoked` | M12 | `rule_id, missing?` |
| `BrakeEngaged` · `BrakeWidened` · `BrakeNarrowed` · `BrakeReleased` | M13 | `scope, actor, reason, brake_version, decision_ref?` |
| **`IllegalTransitionAttempted`** | **all** | `machine, state, trigger` — audit **and** security |

> ### **No event is emitted by two incompatible transitions.** Where two machines co-transition (M2↔M3, M2↔M4), the event has **one producer** (listed above) and the other machine **consumes** it.

---

## 6. PROVISIONAL EVENT-CONTRACT NOTE

Each machine's point 32 lists the events it emits with their added payload (above). ### **These are provisional contracts for the later Event Specification phase — not formalized here.** No separate event-family files are created in this phase.

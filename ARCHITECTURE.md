# Neyma — Architecture Entry Point

> **This is the map, not the territory.** It is the shortest complete orientation to the canonical
> architecture. It does **not** replace the detailed corpus — the ADRs, the target specification and
> the layer specifications are authoritative, and where this file and they disagree, **they win.**
> Links to the exact canonical sources are in §30.

**Read [`PRODUCT.md`](PRODUCT.md) first.** Architecture without the product definition produces a
technically correct system for the wrong problem.

---

## 1. System purpose

To maintain **canonical operational state** for a freight brokerage across fragmented external
systems, and to **coordinate bounded external effects** against those systems such that every
consequential action is authorised, identified, verified, attributable and replay-safe.

The architecture exists mostly to make one thing structurally impossible: **acting on the outside
world without authority, or acting twice when the world only wanted it once.**

## 2. Canonical architectural layers

```
engineering-principles.md            the constitution
  └─ product/{freight-discovery, operating-model}    what is true about the domain
      └─ semantic-model.md                            the canonical language
          └─ ADR-001 … ADR-011                        the binding decisions
              └─ target-system-specification.md       the target architecture (Rev 2)
                  └─ specifications/{entities, state-machines, events,
                                     domain-entities, adapters, workflows}
                      └─ specifications/acceptance/*  the executable contracts + release gates
                          └─ implementation/*         the phased build
```

**Each layer was hostilely reviewed before the next began** (`*-review.md` files record those
reviews). A lower layer may not contradict a higher one; it may only refine it.

## 3. Core entity model

**17 foundational platform primitives** ([`entities/`](docs/specifications/entities/)) and
**40 freight-domain entities** grouped into families
([`domain-entities/`](docs/specifications/domain-entities/)).

> **Domain entities reuse the platform primitives. They never introduce new ones.** A freight
> concept that seems to need a new primitive is a modelling error until proven otherwise.

## 4. Work Items

The unit of accountable work. A Work Item has **exactly one accountable human owner** at all times.
Ownership is assigned by a human, recorded before it takes effect, and never inferred.
*A Work Item with no owner is a Sev-0 condition, not a tidy-up task.*

## 5. Pipeline Instances

The durable execution of a workflow for one Work Item — and, per ADR-009, **the reservation**.
Concurrency is controlled by the Pipeline Instance's identity, not by locks around code.

## 6. Expectations

*What should happen by when.* An Expectation is how the system detects the **missing event** — the
POD that never arrived, the check call that never happened. **The absence of an event is itself
operational information**, and Expectations are the mechanism that makes absence observable.

## 7. Obligations

An unresolved thing the business owes or is owed. **Every open obligation has one accountable
human owner.** An obligation with no owner is the failure mode the whole ownership model exists to
prevent.

## 8. Evidence and provenance

Every fact carries **where it came from and how much it can bear**. Evidence is
content-addressed. `provenance_class` (ADR-002) distinguishes what a human asserted from what a
model inferred from what an external system reported.

**Two rules are load-bearing:**
- **`MODEL_INFERRED` cannot independently authorise a consequential action.**
- **`OWNER_ASSERTED` cannot be silently overwritten.**

## 9. Human ownership

Accountability is structural, not procedural: the schema requires an owner, the state machines have
human-owned states, and escalation carries the evidence needed to decide.

## 10. Events

**105 emitted event contracts** across families F1–F13, derived mechanically from the machines.

> ### **Events are FACTS. They are never commands, and they never carry authority.**

An event says *this happened*. It does not say *therefore do this*, and no consumer may treat an
event as permission. Each contract states explicitly what the event **proves** and what it
**does NOT prove**.

## 11. State machines

**13 machines, 134 transitions.** Each transition names its guards, its writes, its event, the
owner afterwards, and the test that validates it.

**The G2 event contract, adjudicated.** A *producer transition* of an event is one declared in that
event's producer field in [`events/registry.md`](docs/specifications/events/registry.md) §3 — that
table, not a machine's Event column, is the producer map. **117 of the 134 rows are producer
transitions; the remaining 17 are non-producer transitions**, because a row may co-transition with,
cause, or reflect an event another machine owns
([`state-machines/registry.md`](docs/specifications/state-machines/registry.md) §5, line 182: one
producer, the others consume).
Completeness is the separate `GR-2` obligation — *no state change without its event* — evaluated
over **durable writes**, read from the `From → To` and `Writes` columns. **Neither predicate reads
prose:** every non-producer row carries a structured `CONSUMES` / `NON_PRODUCING` / `DELEGATES_TO` /
`EVENT_REQUIRED` marker, and a row the classifier cannot decide **fails the build**. A
prose-dependent predicate was refused precisely because it is self-certifying: `CF-7` and `EC-7`
both exempted themselves with *"(no state change)"* while performing durable writes.

### **A structured marker is not a proof either, and `CONSUMES` is where that bites.** A label saying
a row consumes an event asserts a relationship; it does not establish one. So a durable-writing
consumer must satisfy `CONSUMES-VALID`, read entirely from structured columns: the co-commit is
**declared in both rows'** `Writes` cells, the owner is on a **different machine**, the owner is **not
mutually exclusive** with the consumer, and every field the consumer persists is carried by a consumed
event's §5 **payload** so replay can reconstruct it. Undecidable **fails the build**. The first
attempt at this class proved only that the named event existed and was not self-owned, which let the
corpus's highest-severity open obligation (`AP-9`, `frozen=true`) be relabelled as consuming an
unrelated *brake* event while every guard stayed green. **Count arithmetic reconciling is not
evidence: set equality between a specification and its audit proves they agree, not that either is
true.**

### **`DELEGATES_TO` is bounded by the TRIGGER TYPE, not only by the target state.** A row may hand
its event to another row that reaches the same state — but reaching the same state is not the same as
performing the same transition. `Trig` is a closed code set (`H` human · `S` system · `X` observed ·
`T` timer · `P` policy · `B` brake · `R` recovery), and a delegating row's trigger set must
**intersect** every target's. Without that clause `PL-7a → PL-7b` is accepted: both end in
`CHECKPOINT` and `PL-7b` is a declared producer, yet `PL-7b` is `H` and asserts a **bound human
approval**, while `PL-7a` is `S`, the autonomous-within-caps path where no human acted. The
constraint is structural and general — the two legitimate delegating rows, `WI-14` and `CF-6`, are
both `S|H` and intersect every target they name.

*Closed (2026-08-12), and the record kept:* seven durable writes were recorded by no canonical
event — `PL-7a`, `AP-9`, `CF-7`, `EC-7`, `PO-2`, `PO-3`, `RU-8`. Each violated `GR-2` as written.
### **Seven canonical events were minted under founder/architect authority** —
`AutonomousAdmissionRecorded`, `ApprovalFrozen`, `ConflictPartyAttached`,
`ExceptionSeverityChanged`, `PolicySubmitted`, `PolicyApproved`, `RuleExpired` — taking the registry
from 98 to **105**, and each row is now its event's declared `§3` producer. The two safety-relevant ones and how they were resolved: `AP-9` writes
`frozen=true`, a guard input to an ILLEGAL determination, so `ApprovalFrozen` is **EMITTED, never
derived** — a rebuild sets `frozen` from the event's PRESENCE, because inferring it from the absence
of a `RealityEstablished` would make the rebuilt approval *reusable*, less safe than the original; and
`PL-7a`, the sole autonomous entry into `CHECKPOINT`, now carries the audit record the one transition
that proceeds without a human previously lacked. `PO-1` keeps `PolicyProposed` — `PO-2` was given a
new name rather than taking the old one, so no historical event changed meaning. The obligations are
**retained, not deleted**, each marked discharged with its authority, in
[`TRANSITION-EVENT-AUDIT.yaml`](docs/implementation/TRANSITION-EVENT-AUDIT.yaml). Still open there:
the recorded G2 residuals `G2-D4`, `G2-D6`, `G2-D8`, `G2-D9` and `G2-D10`.

## 12. Tenant model

**Tenant-first, not tenant-column.** A tenant column is not tenant isolation; the tenant must be
**first in the key**, required at construction, validated against sentinels (`default`, `unknown`,
`test`, …), and enforced by the database rather than asserted by convention.

Historical rows may only be assigned an owner by a **recorded human assertion** naming actor, scope,
basis and evidence — recorded *before* assignment, append-only. **Ownership is never inferred.**

## 13. Commit Key

The identity of the **effect**:

```
SHA256( ck_v1 | tenant | action_class | target_system
      | target_resource_id | target_operation | occurrence_key )
```

> ### **The amount is NOT in the Commit Key — and that absence is itself asserted by a test.**

Two approvals at different amounts for one invoice are **one effect**, not two. `occurrence_key`
must resolve from a **canonical business occurrence** (Payment Application, Compensation,
Expectation) — never a free-form caller string, which would let a caller manufacture a new identity
on every retry.

## 14. Material Facts

The **content** of the decision — the values the human approved. Answers *"are the approved values
still identical?"*

> ### **Commit Key ≠ Material Facts, and merging them is a defect.**
> The Commit Key answers *"is this the same logical effect?"* Material Facts answer *"is the world
> still what we approved?"* Drift in Material Facts **voids the approval** (ADR-005). Putting the
> amount into the key instead produced the double-invoice defect that Phase 1 corrected.

## 15. Effect Grant / External Effect ledger

**One** canonical effect authority. The Effect Grant has exactly eight states:

`GRANTED · CLAIMED · ATTEMPTED · VERIFIED · FAILED · EXPIRED_UNCLAIMED · REVOKED · UNKNOWN_OUTCOME`

`REVOKED` is **distinct from** `EXPIRED_UNCLAIMED` — deliberately withdrawn is not the same as
quietly lapsed. Uniqueness is `(tenant, commit_key)`.

> ### **A second table answering "was this effect done?" is a second effect authority and is
> forbidden.** Readiness fails the build if one appears.

## 16. The seven-step checkpoint

**ONE atomic checkpoint** — not seven independent checks separated by asynchronous work:

1. **Approval validity** — present, unexpired, unrevoked, correct authority (ADR-005)
2. **Material-facts fingerprint** — void on drift (ADR-005)
3. **Projected-state freshness revalidation** — against the authoritative source, **never a cache** (ADR-001 C4)
4. **Native-state revalidation** — claims unretracted, unsuperseded, not conflicting (ADR-002)
5. **Entity-version concurrency check** (ADR-009)
6. **Policy evaluation** — caps, authority, autonomy, allowlists, policy version; **the gate decision is never null** (ADR-010)
7. **Human-brake admission** (ADR-011)

**All seven pass ⇒ a `CheckpointPassed` witness exists ⇒ a grant may be minted.**

## 17. Checkpoint Witness

Proof that *the seven checks passed moments ago and the facts still hold* — **freshness**.

> ### **THE TWO-KEY RULE: a grant is necessary but NOT sufficient.** The adapter requires a
> claimable grant **AND** a fresh, matching Checkpoint Witness. Either alone is refused.

The adapter's own sequence: verify handle → load grant → **validate witness freshness** → **confusion
check** (re-validate the grant against the adapter's *own* call parameters; any mismatch is a Sev-0
security event, not an error) → **CAS `GRANTED → CLAIMED`** → emit `EffectAttempted` **before** the
call → only then touch the outside world.

## 18. Approval validity

An approval binds to specific Material Facts and a specific authority, expires, and can be revoked.
**Drift voids it.** Per **ADR-003 — PERMANENT PRODUCT TRUTH** — an authorization assertion requires
human confirmation and **cannot be graduated away by any autonomy level.**

## 19. Policy and autonomy admission

Typed policy with compile-or-refuse rules (ADR-010). *A prompt string is not a policy.* Autonomy is
admitted per action class, capped, time-boxed and revocable; the gate decision is always explicit.

## 20. Brake semantics

> ### **The Brake controls ADMISSION, not worker termination.**

It decides whether new work may **start**. It does not kill running workers — a brake that promises
to stop work already in flight would be making a guarantee it cannot keep. Read inside the same
transaction as steps 1–6.

## 21. Adapter boundary

**An adapter is a boundary, not a brain.** 18 adapters, each with a capability contract naming
action class, read-or-effect class, verification mode, and Commit Key / Material Facts.
All external effects pass through this boundary, and the boundary enforces the two-key rule.

*Open finding:* **31 direct adapter-import edges** across 18 importer modules bypass this design
today — the P3 kernel exists beside them, dark. Containment is **P4**.

## 22. Replay rules

> ### **Replay cannot mint authority. Replay cannot mint witnesses or grants. Replay cannot call
> adapters.**

Replay is **structurally inert**: re-running history reconstructs state and can never re-execute an
effect. This is a consequence of the effect boundary, not an added safeguard.

## 23. Reconciliation

Neyma's projection is compared against authoritative external state. A disagreement is an
**observation to reconcile**, never a value to silently overwrite. Conflicts are first-class
(ADR-007).

## 24. Unknown-outcome handling

> ### **TIMEOUT ALONE NEVER MEANS FAILED.**

`FAILED` asserts *the effect did not happen*. A timeout establishes nothing — the invoice may well
have been raised. Three distinct verification outcomes land in **`UNKNOWN_OUTCOME`**, which maps to
`NEEDS_VERIFICATION` and **must never auto-resolve**. The `UNKNOWN_OUTCOME` rate is the single most
important operational number in the system: a rising rate means the system is acting without knowing
the result, and triggers automatic demotion.

## 25. Security and isolation

Tenant isolation is enforced at the database (composite tenant-first keys, tenant-aware foreign keys
with column order checked, FK enforcement verified on the live connection). Cross-tenant access
returns **nothing** and discloses nothing — absent and cross-tenant are indistinguishable.
Credentials follow [`ADR-014`](docs/architecture/decisions/ADR-014-credential-and-machine-identity.md):
Neyma minimizes handling of employees' raw personal credentials and prefers dedicated, scoped
machine identities; it may securely possess customer-authorized authentication material under
full governance (tenant isolation, least privilege, encryption, audit, revocation, rotation,
destruction at offboarding). `human_established_session_only` remains a supported per-tenant
session policy, not a universal rule. **Authentication never creates action authority** —
credentials resolve only inside the adapter boundary on a claimed grant.

## 26. Migration posture

Forward-only where a defect has been removed: once the amount left the Commit Key, no rollback may
restore it. Migrations are resumable and idempotent, classify every starting shape into one of **10
canonical outcomes** each carrying an actionable next step, and quarantine ambiguous rows rather
than guessing an owner.

> ### **The completion marker is written LAST, and only if readiness passes.** Readiness is what the
> database **enforces**, never what a marker **claims** — a marker written early is a claim about the
> past that outranks the present, which is exactly how a half-migrated database gets deployed on.

## 27. Legacy reduction posture

**No module survives merely by being large, tested or working.** Every major subsystem has one
disposition (KEEP / ADAPT / REWRITE / MAKE_READ_ONLY / QUARANTINE / DELETE) with a target phase and
a deletion condition — see [`LEGACY-DISPOSITION.md`](docs/implementation/LEGACY-DISPOSITION.md).
There is **no permanent "legacy but active forever" category**, and there may be **no permanent
second orchestration system and no permanent second effect-authority system.**

## 28. Current implementation boundary

| Phase | State | What it bought |
|---|---|---|
| **P0** | ✅ COMPLETE | baseline manifest + anti-false-green guard infrastructure |
| **P1** | ✅ COMPLETE | **correct effect identity** — the amount is out of the Commit Key |
| **P2** | ✅ COMPLETE | **tenant-safe persistence** — enforced by the database, ownership humanly asserted |
| **P3** | ✅ COMPLETE | **the checkpoint kernel** — seven-step atomic checkpoint, unconstructable `CheckpointPassed`, append-only Checkpoint Witness, grant mint + claim CAS, brake admission. **Ships dark.** A FRESH independent review PASSED and a separate final adjudication set all 14 weighted criteria PASS; completing P3 did **not** close R-07. |
| **P4** | ✅ **COMPLETE — ADJUDICATED** | **adapter containment** — every external effect routed through the kernel, EP-1/EP-3/EP-8/EP-14 cut and finding F2 closed, and **R-07 recorded CONTAINED**. Its first INDEPENDENT review REJECTED candidate `95cf5af7`; a separate session remediated it into `0891d1a`; a FRESH INDEPENDENT re-review accepted it; a separate FINAL ADJUDICATION set all 14 weighted criteria PASS (100/100). **Ships dark** — the deployed governed route answers a recorded `ROUTE_NOT_CONFIGURED` refusal |
| **P5** | 🔄 **READY *(selected)* — NOT STARTED, NOT COMPLETE** | canonical events, outbox/inbox, replay isolation and production persistence. `READY` is a **selection**, never a claim of progress: no event contract, outbox, inbox, replay sandbox or PostgreSQL work exists. Its event content carries its own undischarged **G2** transition/event blocker, which P4's completion did not discharge |
| **P6+** | ⛔ NOT STARTED — BLOCKED behind P5 | everything below |

## 29. The remaining safety wall

> ### **Phase 2 made tenant ownership real at persistence boundaries.**
> ### **Phase 2 did NOT make consequential external effects safe.**
> ### **Phase 3 built the checkpoint kernel — the two-key rule is enforced INSIDE it.**
> ### **Phase 4 routed the external effects through it and CLOSED the door.**
> ### **R-07 is CONTAINED — and CONTAINED does not mean ENABLED.**

What the wall is now, and what it still is not:

- **The kernel exists and is now routed through** (P3 COMPLETE, P4 COMPLETE, both adjudicated): the
  seven checks, the witness and the claim CAS are implemented, independently reviewed, and are the
  only path an external effect can take.
- **Adapter containment is structural** (P4 COMPLETE, R-07 CONTAINED). An external effect can be
  produced only by an effect-capable adapter; the only application-layer importer of one is
  `effect_boundary`; and the CI import gate fails the build if a second importer ever appears —
  live and recorded, both-sided. Inside the boundary the sole external-write path is
  `execute_invoice_write`, a narrowly typed operation behind checkpoint → witness → grant → atomic
  claim. **Anything that cannot present that chain refuses rather than falls back.**
  **The exact current counts are [`CURRENT.md`](docs/implementation/CURRENT.md)'s** — this file
  deliberately copies none.
- ### **CONTAINED ≠ ENABLED, and CONTAINED is not autonomy.** The capability ships **dark** and
  **no production write is enabled**: the deployed
  callback leaves the execution kernel unset and answers a recorded `ROUTE_NOT_CONFIGURED` refusal,
  the production `GateRegistry` population is **EMPTY** and stays empty until U8.1 / P8 by founder
  decision, and no autonomy — bounded or otherwise — was granted. Live supervised writes are **P12**,
  behind the undischarged **RR-01** precondition.
- ### **HISTORICAL, AND THE RULE BEHIND IT IS PERMANENT.** Until P4 the only mitigation was the
  operator's one-writer-at-a-time discipline, and this section said so: *"That is discipline, not a
  mechanism, and it may never be recorded as containment."* A mechanism now exists to record. The
  rule does not expire — discipline is still never containment, and no allowance may be read as one.

## 28b. The eleven canonical operational loops

**The domain map** (PRODUCT.md §6 is definitive; specs in [`docs/specifications/workflows/`](docs/specifications/workflows/)):

| ID | Loop | ID | Loop |
|---|---|---|---|
| **W1** | Quote | **W7** | Exceptions |
| **W2** | Procurement | **W8** | Billing |
| **W3** | Compliance | **W9** | Settlement |
| **W4** | Dispatch | **W10** | Customer Communications |
| **W5** | Tracking | **W11** | Claims |
| **W6** | Documentation | | |

**Exactly eleven.** A twelfth is a product decision, not an implementation detail. The map is
**not** an instruction to build every loop simultaneously — the wedge is **Delivered Load Closure**
(PRODUCT.md §15, a `HYPOTHESIS`), spanning parts of W5/W6/W7/W8/W10.

## 29b. Production, communications and control plane *(rebaselined — specification only)*

Three architectural commitments were made durable by U-REBASELINE-1. **None is implemented yet;
every item is `SPECIFICATION_ONLY` until a phase delivers it** (ADR-016 §3 readiness vocabulary —
"code exists" means `LOCALLY_IMPLEMENTED`, nothing more):

- **Production topology** ([`ADR-016`](docs/architecture/decisions/ADR-016-production-topology.md)):
  a modular monolith on managed infrastructure — **PostgreSQL as the production transactional
  store** (SQLite stays for local development and deterministic tests only), transactional
  outbox/durable inbox, durable timers, background + communications + isolated browser workers,
  S3-compatible content-addressed evidence storage, managed secrets, environment separation
  (dev/staging/production), backups and point-in-time recovery, observability, rate limits,
  dead-letter/quarantine handling, incident response, cost controls.
- **Communications subsystem** ([`ADR-015`](docs/architecture/decisions/ADR-015-communications-subsystem.md)):
  email/SMS/voice-evidence/portals/EDI as evidence sources, operational surfaces AND governed
  external effects — a message is an effect bound to a Work Item, recipient identity, tenant,
  purpose, authority, evidence, content digest, delivery state, expected response, verification
  and escalation policy. **Email and SMS are required production capabilities for the first
  commercial workflow.**
- **Tenant/integration lifecycle and the web control plane**
  ([`ADR-017`](docs/architecture/decisions/ADR-017-tenant-and-integration-lifecycle.md)): governed
  tenant onboarding→offboarding, per-integration authorization/health/revocation, and a thin web
  control plane for supervision and governance — never a dashboard-first product.
- **Workflow-authority migration** ([`ADR-013`](docs/architecture/decisions/ADR-013-workflow-authority-migration.md)):
  the thirteen-field, customer-authorized model by which authority for any workflow may move —
  including to Neyma.
- **Persistent conversational operations layer** ([`ADR-019`](docs/architecture/decisions/ADR-019-conversational-operations-layer.md)):
  a role-aware conversational teammate over the canonical spine — one identity across web, Slack,
  Teams, email, mobile and voice, all resolving to the same conversation/Work Item/history;
  proactive, evidence-grounded, transparent about uncertainty. **Conversation is never a second
  source of truth and never independent authority** — a conversational instruction that would cause
  a consequential effect goes through the same auth/policy/evidence/approval/idempotency/grant/
  verification pipeline as any other action; voice rides that same pipeline, not a separate effect
  path; Neyma never claims completion without verification and never pretends to be human.
- **Customer operational graph** ([`ADR-018`](docs/architecture/decisions/ADR-018-customer-operational-graph.md)):
  the TMS is one node, not the center; the canonical domain model and workflow engine are
  **independent of any specific TMS schema**; each tenant has an **Operational System Map**
  ([`spec`](docs/specifications/operational-system-map.md)) recording which node controls which
  fields and how each is read/written/reconciled; the same workflow runs whatever the source
  system; a write into one node is never workflow completion; and an eight-level maturity ladder
  (observe → … → replace) lets a customer advance at their own pace. Fragmented tooling never
  lowers auditability, ownership, tenant safety, authorization or closure requirements.

## 30. Canonical detailed specifications

| Layer | Path |
|---|---|
| Constitution | [`docs/architecture/engineering-principles.md`](docs/architecture/engineering-principles.md) |
| Canonical language | [`docs/architecture/semantic-model.md`](docs/architecture/semantic-model.md) |
| **Binding decisions** | [`docs/architecture/decisions/`](docs/architecture/decisions/) — ADR-001 … ADR-017 |
| Target architecture | [`docs/architecture/target-system-specification.md`](docs/architecture/target-system-specification.md) |
| Binding lessons | [`docs/architecture/stream-b-architectural-lessons.md`](docs/architecture/stream-b-architectural-lessons.md) |
| Platform primitives | [`docs/specifications/entities/`](docs/specifications/entities/) |
| Freight entities | [`docs/specifications/domain-entities/`](docs/specifications/domain-entities/) |
| State machines | [`docs/specifications/state-machines/`](docs/specifications/state-machines/) |
| Events | [`docs/specifications/events/`](docs/specifications/events/) |
| Adapters | [`docs/specifications/adapters/`](docs/specifications/adapters/) |
| Workflows | [`docs/specifications/workflows/`](docs/specifications/workflows/) |
| **Acceptance + gates** | [`docs/specifications/acceptance/`](docs/specifications/acceptance/) |
| Authority map | [`docs/CANONICAL-DOCUMENTS.md`](docs/CANONICAL-DOCUMENTS.md) |

---

## The rules that may never be weakened

1. **Events are facts, never commands or authority.**
2. **Replay cannot mint authority.**
3. **Replay cannot invoke external adapters.**
4. **`MODEL_INFERRED` cannot independently authorise consequential action.**
5. **`OWNER_ASSERTED` cannot be silently overwritten.**
6. **Timeout alone never means `FAILED`.**
7. **Every unresolved obligation has an accountable human.**
8. **The Brake controls admission, not worker termination.**
9. **One canonical effect authority exists.**
10. **No permanent second orchestration system.**
11. **No permanent second effect-authority system.**

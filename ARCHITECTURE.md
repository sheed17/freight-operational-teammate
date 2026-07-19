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

**98 emitted event contracts** across families F1–F13, derived mechanically from the machines.

> ### **Events are FACTS. They are never commands, and they never carry authority.**

An event says *this happened*. It does not say *therefore do this*, and no consumer may treat an
event as permission. Each contract states explicitly what the event **proves** and what it
**does NOT prove**.

## 11. State machines

**13 machines, 134 transitions.** Each transition names its guards, its writes, its event, the
owner afterwards, and the test that validates it.

*Open finding:* **13 of the 134 transitions name no event outright** — in four structurally
different classes (bare, documented non-producing, unnamed-ILLEGAL, delegating; exact members in
[`TRANSITION-EVENT-AUDIT.yaml`](docs/implementation/TRANSITION-EVENT-AUDIT.yaml)). **Which classes
violate `AC-EVT-003` is a G2 question that must be settled before P5** — the specifications do not
define the predicate, so the finding carries **COUNT NEEDS ADJUDICATION**, not a number.

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
today. Containment is **P4**.

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
Neyma never holds a customer's TMS credentials: **the human establishes the session and Neyma
attaches** (`human_established_session_only`).

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
| **P3+** | ⛔ NOT STARTED | everything below |

## 29. The remaining safety wall

> ### **Phase 2 made tenant ownership real at persistence boundaries.**
> ### **Phase 2 did NOT make consequential external effects safe.**
> ### **R-07 remains OPEN — NOT CONTAINED.**

What is still missing, and what it means concretely:

- **No Checkpoint Witness exists** (P3) — so the two-key rule is specified but not enforced.
- **No claim CAS** (P3) — so commit-once is not yet a database constraint at the effect boundary.
- **No adapter containment** (P4) — **six production-reachable live-write paths can execute real
  external effects right now** with no checkpoint, no witness and no grant.
- The only current mitigation is the operator's one-writer-at-a-time discipline.
  ### **That is discipline, not a mechanism, and it may never be recorded as containment.**

## 30. Canonical detailed specifications

| Layer | Path |
|---|---|
| Constitution | [`docs/architecture/engineering-principles.md`](docs/architecture/engineering-principles.md) |
| Canonical language | [`docs/architecture/semantic-model.md`](docs/architecture/semantic-model.md) |
| **Binding decisions** | [`docs/architecture/decisions/`](docs/architecture/decisions/) — ADR-001 … ADR-011 |
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

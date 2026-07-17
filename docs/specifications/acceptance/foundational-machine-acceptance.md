# Foundational Machine Acceptance *(AC-MACH-*)*

*Registry defaults apply. Level: `STATE_MACHINE` / `CROSS_MACHINE`. Gate: **G1**.*

## Coverage requirement
> ### **100% of the 134 legal transitions. Every omitted `(state,trigger)` pair proved ILLEGAL. No exceptions.**
> *(Errata 2026-07-16: corrected from 141 — the 13 machine files enumerate **134**; see `docs/implementation/canonical-corpus-errata-review.md`.)*

## The mechanical coverage table *(the build's own artifact — asserted, not asserted-about)*
### **A `STRUCTURAL` case (`AC-MACH-000`) enumerates the transition tables FROM THE IMPLEMENTATION's declarative data and asserts a bijection with the 134 spec rows.** A transition in the spec with no case, or a case with no spec row, **fails the build.**
### **The oracle is EXACT SET EQUALITY of transition identifiers, not a count. A count match with different members MUST fail.**

| Machine | Transitions | Case range | Expected events | State oracle | Gate |
|---|---|---|---|---|---|
| M1 Work Item | 14 | `AC-MACH-101..114` | `WorkItemCreated`…`Reopened` | DB row `state`+`version`+`owner_id` | G1 |
| M2 Pipeline Instance | 25 | `AC-MACH-201..225` | `PipelineStarted`…`PipelineClosed` | row + witness/grant FK | G1/**G4** |
| M3 External Effect/Grant | 13 | `AC-MACH-301..313` | `EffectGranted`…`RealityEstablished` | ledger row (8-state) | **G4** |
| M4 Approval | 11 | `AC-MACH-401..411` | `ApprovalRequested`…`Consumed` | row + canonical_payload | **G4** |
| M5 Observation | 8 | `AC-MACH-501..508` | `ObservationReceived`…`Superseded` | natural-key row | G1 |
| M6 Identity Binding | 11 | `AC-MACH-601..611` | `ClaimProposed`…`ClaimCorrected` | row + provenance_class | G1 |
| M7 Conflict | 7 | `AC-MACH-701..707` | `ConflictRaised`…`Resolved` | row + field condition | G1 |
| M8 Expectation | 8 | `AC-MACH-801..808` | `ExpectationRaised`…`Expired` | row + coverage_ref | G1 |
| M9 Exception | 7 | `AC-MACH-901..907` | `ExceptionRaised`…`Resolved` | row + decision_ref | G1 |
| M10 Compensation | 9 | `AC-MACH-1001..1009` | `CompensationRequired`…`Failed` | row + exposure | **G4** |
| M11 Policy | 7 | `AC-MACH-1101..1107` | `PolicyProposed`…`VersionChanged` | version row | **G4** |
| M12 Rule | 9 | `AC-MACH-1201..1209` | `RuleProposed`…`Revoked` | version row | G1 |
| M13 Brake | 5 | `AC-MACH-1301..1305` | `BrakeEngaged`…`Released` | row + brake_version | **G4** |
| **Total** | ### **134** | — | ### **all 98** | — | — |

> ### **ERRATA (2026-07-16):** the Total row previously read **141** / **all 92**. ### **The 13 per-machine counts above were and remain CORRECT — they sum to 134.** The emitted-event total is **98** (F1–F13). Both errors were arithmetic, not architectural: every count enumerated in a single table was right; both counts requiring summation across 13 files were wrong. See `docs/implementation/canonical-corpus-errata-review.md`.

## Per-machine mandatory assertions *(every machine, every case)*
1. ### **Every legal transition succeeds under its EXACT guards** — and fails when any guard is relaxed by one condition (a guard-mutation probe).
2. ### **Every omitted transition is ILLEGAL** — an exhaustive `(state × trigger)` sweep; each non-enumerated pair raises, **persists nothing**, and emits `IllegalTransitionAttempted` (audit **and** security).
3. **Version conflicts fail deterministically** — a stale `expected_version` ⇒ zero rows ⇒ raise (never a silent overwrite).
4. **Duplicate triggers are idempotent** — the inbox key makes redelivery a no-op.
5. ### **Terminal states have NO prohibited outgoing transitions** — the only permitted one is the explicit reopen (`WI-13`), which requires a `decision_ref`.
6. **Reopening creates a new phase or linked Work Item** — the prior closure event is **byte-identical** afterward.
7. ### **Historical transitions are NEVER rewritten** — an append-only probe (no UPDATE/DELETE on the event/closure rows).
8. **Crash recovery reaches the canonical state** — crash at each transition ⇒ pre-effect re-checkpoints; `CLAIMED`/`EXECUTING` ⇒ `NEEDS_VERIFICATION`, **never re-execute**.
9. **Ownership remains valid** — no transition leaves a Work Item/Exception ownerless.
10. **Tenant isolation intact** — every case runs `T_A`/`T_B`; a `T_B` trigger never moves a `T_A` machine.

## The named anchors *(merge-gating)*
`AC-MACH-208` = the checkpoint transition (all seven, atomic). `AC-MACH-209` = the claim CAS (single-use). `AC-MACH-210u` = ### **`CLAIMED`+crash ⇒ `NEEDS_VERIFICATION`, never `FAILED`.** `AC-MACH-215x` = ### **no timer moves `NEEDS_VERIFICATION` (ILLEGAL).** `AC-MACH-605x` = ### **`OWNER_ASSERTED`+`RecomputedByInferrer` ⇒ ILLEGAL (the B3 regression).** `AC-MACH-903` = ### **Exception close requires a resolving `decision_ref`.** `AC-MACH-1305` = ### **no timer releases a brake.**

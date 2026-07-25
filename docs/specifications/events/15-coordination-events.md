# Event Family F15 — Cross-Machine Coordination Events

*Registry: `events/registry.md` §9. **This family introduces NO new event contracts.** It is a **lens** naming how already-defined events (F1–F14) drive cross-machine reactions — **without commands.***

> ### **THE GOVERNING RULE (ER-1): a coordination event does NOT instruct a consumer to transition. Each consumer transitions IFF ITS OWN deterministic guard holds** (the 13 machines). The event is a published fact; the reaction is the consumer's own rule.

## 1. The coordination map *(event → reacting machines, each by its own guard)*

| Coordination fact (home family) | Reacting machine · its own guard · resulting transition |
|---|---|
| **`ApprovalGranted`** (F4) | M2: iff `AWAITING_APPROVAL` and it binds this commit_key+fingerprint ⇒ PL-7b (`CHECKPOINT`). |
| **material-facts drift** → **`ApprovalVoided{drift}`** (F4) | M2: iff `AWAITING_APPROVAL`/`CHECKPOINT` ⇒ PL-7v (`VOIDED`). *(The drift is detected at PL-8 step 2 live; the void is the fact.)* |
| **`CheckpointPassed`** (F2) | M3: mint (EF-1) — **co-commit, not a reaction across time**. |
| **`GrantClaimed`** (F3) | M4: consume (AP-7, co-commit); M2: PL-9 (`CLAIMED`). |
| **`OutcomeUnknown`** (F3) | M2: PL-10u/11c (`NEEDS_VERIFICATION`); M9: EC-1 (Exception). Entity frozen; ### **no consumer may resolve it on a timer (GR-6).** |
| **`VerificationUnavailable`** (F3) | M9: EC-1; M2: `NEEDS_VERIFICATION`. ### **No consumer reads it as failure (M-69).** |
| **`ConflictOpened`/`ConflictRaised`** (F7) | ### **every machine reading the frozen field: BLOCK its consequential transition (GR-10).** |
| **`ExpectationIndeterminate`** (F8) | M9: EC-1 (human). ### **No consumer accuses the counterparty (I8).** |
| **`CompensationRequired`** (F10) | M4: request approval; M2: (on approve) a new gated pipeline. |
| **`PolicyVersionChanged`** (F11) | M4: `VOID_ON_DRIFT` iff pending; M2: void pre-claim; M3: the claim CAS re-checks `policy_version`. **Each by its own guard.** |
| **`BrakeEngaged`** (F13) | M2: `PipelineVoided` iff pre-claim; M4: `VOID_ON_BRAKE`; M3: claim CAS re-checks `brake_version` (zero rows). ### **In-flight post-claim work runs to verification (GR-16).** |
| **`RealityEstablished`** (F3/F10) | M2/M10: `VERIFIED`/`FAILED`/`COMPLETED`. **Only** on a human `decision_ref` or deterministic proof. |
| **work-item closure criterion** → **`PipelineClosed`** (F2) | M1: WI-3 iff "obligation satisfied" — ### **the pipeline event does NOT close the work item; M1's guard does.** |

## 2. The ‡ multi-producer events *(one contract, several structurally-identical origins — §9)*

| Event | Producers | Discriminator in payload |
|---|---|---|
| `RealityEstablished` | EF-5, CM-5 | `subject∈{effect,compensation}` |
| `ConflictRaised` | CF-1, IB-6, EF-4c | `kind` |
| `PolicyVersionChanged` | PO-4, PO-6 | `policy_version` |
| `IllegalTransitionAttempted` | any machine (GR-1) | `machine`, `state`, `trigger` |

> ### **This is the ONLY deviation from "exactly one producer transition per event," and it is deliberate: one semantic fact with several legitimate origins. It is flagged in the review; it introduces no ambiguity because the payload discriminator is mandatory and the semantics are identical across producers.**

## 3. Why this is not a command bus
- **No coordination event carries an imperative.** `BrakeEngaged` does not say "void yourself"; M2 voids **because M2's guard says a pre-claim pipeline voids on a brake.**
- **A consumer that has no matching guard does nothing** (e.g. `BrakeEngaged` reaches a `PROJECTED` pipeline ⇒ no transition; it is already past the effect).
- **Replay of any coordination event produces no effect** (ER-2) — the same facts, no re-actuation.

**No tests here beyond the home families' — coordination is verified by the cross-machine traces in `event-specification-review.md` (T8, T9, T14, T17) and the state-machine review's 20 traces.**

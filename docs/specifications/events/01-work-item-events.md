# Event Family F1 — Work Item Events

*Registry: `events/registry.md`. Producer: machine M1. Envelope + 40-field defaults: registry §1–§2.*

**Family defaults:** `aggregate_type=work_item`; ordering = **order-tolerant except closure/reopen** (per-aggregate version guards those); security=`internal`; PII=`pii-low` (may reference a counterparty/customer); projection-permitted = **none** (Work Item events are native operational-state facts, not projected truth — ER-1); audit=standard except closure/cancel/reopen=`high`. Each event's contract states only non-default fields.

| Event · v1 · producer | Proves / ¬Proves | Payload (beyond envelope) | Consumers → their guard | Notes / tests |
|---|---|---|---|---|
| **`WorkItemCreated`** WI-1 | proves an obligation exists with an accountable owner · ¬proves any work has started | `owner_id`(R), `type`, `entity_ref?` | Oversight surface; M2 (may propose a pipeline) | ### `accountable_owner_id` **required** (I1). `actor_type∈{human,system}`. `test_ev_workitemcreated_requires_owner` |
| **`WorkStarted`** WI-2 | proves ≥1 pipeline began | — | Oversight | `test_ev_workstarted` |
| **`WorkItemClosed`** WI-3 | proves the obligation was satisfied AND a human/rule decided closure · ¬proves the effect was verified (that is a Pipeline/Effect fact) | ### `decision_ref`(R, resolves per K-1) | Oversight; analytics | audit=`high`; ### **may NOT close on its own — WI-3 guard "obligation satisfied" (loop closes at cash, P24)**. `test_ev_close_carries_valid_decision_ref` |
| **`AttemptFailed`** WI-4 | proves a transient pipeline failure; retries remain · ¬proves the obligation failed | `reason` | Oversight | `test_ev_attemptfailed_transient` |
| **`WorkBlocked`** WI-5/6 | proves progress is blocked (permanent failure, missing evidence, or open conflict) · ¬proves terminal failure (still owned) | `reason` | Oversight (owner still accountable) | `test_ev_workblocked_keeps_owner` |
| **`WorkUnblocked`** WI-8 | proves the blocker cleared | — | Oversight | `test_ev_workunblocked` |
| **`HumanRequested`** WI-7 | proves a human decision is needed | `question?` | Oversight (queue) | `test_ev_humanrequested` |
| **`HumanDecided`** WI-9 | proves an authenticated human decided | ### `decision_ref`(R) | M1 (resume) | `actor_type=human`; `test_ev_humandecided_valid_ref` |
| **`WorkEscalated`** WI-10 | proves the item aged past threshold | — | Oversight (escalation) | trigger was a **durable timer**, not a sweep. `test_ev_escalated_via_timer` |
| **`OwnershipTransferred`** WI-11 | proves a new accountable human owns it | `from_owner`, `to_owner`(R) | Oversight | `actor_type=human`; `test_ev_ownership_transfer` |
| **`WorkItemCancelled`** WI-12 | proves a human cancelled the obligation | ### `decision_ref`(R) | Oversight; analytics | audit=`high`; `test_ev_cancel_valid_decision_ref` |
| **`Reopened`** WI-13 | proves a closed obligation was reopened as a new phase/linked item · ¬proves the prior closure was wrong (it stands) | ### `prior_closure_ref`(R), `phase_seq \| linked_work_item_id`, `decision_ref`(R) | M1; analytics | ### **preserves the prior closure event (ER-8, S8)**; `test_ev_reopened_preserves_closure` |

## Cross-cutting
**Dedup identity:** transition-natural `(tenant, work_item_id, aggregate_version, transition)` (registry §4). **Ordering:** per-aggregate version; **closure/cancel/reopen require strict order** (a `Reopened` before its `WorkItemClosed` is **parked**). **Replay:** reconstructs ownership+closure deterministically; zero effects (ER-2). **Projection:** ### **Work Item events never update projected truth** (native operational state only). **Out-of-order:** `WorkStarted` before `WorkItemCreated` ⇒ parked (§8). **Security:** none specific (a closure without a resolving `decision_ref` is stopped at the *transition* — M9/GR-14 — before any event; a forged attempt surfaces as `IllegalTransitionAttempted`). **Open validation:** V1 (reopen policy) — fail-closed, not a block.

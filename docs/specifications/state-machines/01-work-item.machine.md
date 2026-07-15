# Machine M1 — Work Item

*Registry: `registry.md`. Entity: `entities/01-work-item.md`. Lifecycle source: Target Spec §12.1.*

**1. Machine name.** Work Item. **2. Owning entity.** Work Item. **3. Purpose.** The business-level unit of responsibility and closure; carries an accountable human owner until explicitly closed with a `decision_ref`. **4. Aggregate/txn boundary.** Own aggregate; each transition is one commit (GR-2); does **not** share a transaction with its Pipeline Instances. **5. Accountable owner.** A named authenticated human, from creation (I1), carried on the row. **6. Initial state.** `OPEN`. **7. State set.** `OPEN, IN_PROGRESS, BLOCKED, AWAITING_HUMAN, ESCALATED, CLOSED, CANCELLED`. **8. Terminal.** `CLOSED, CANCELLED`. **9. Non-terminal human-owned.** `BLOCKED, AWAITING_HUMAN, ESCALATED`. **10. Recoverable.** `OPEN, IN_PROGRESS`. **11. Failure states.** `BLOCKED` (not terminal — a blocked item keeps its owner). **12. Expiry states.** none — ### **a Work Item NEVER expires** (ages → `ESCALATED`). **13. Unknown-outcome states.** none (unknown outcomes live on M3/M2).

**Machine defaults** *(override the universal defaults from registry §2)*: owner-after = unchanged; all transitions here are **administrative** (GR-17) **except** none — a Work Item performs no external effect.

## 14. Transition table

| ID | From → To | Trig | Preconditions / guards | Writes (beyond state+event) | Event | Owner after | Test |
|---|---|---|---|---|---|---|---|
| **WI-1** | — → `OPEN` | H\|S | ### **`owner_id` present and authenticated (I1)** — else raise (creation fails) | `owner_id, type, entity_ref?` | `WorkItemCreated` | the assigned owner | `test_wi_create_requires_owner` |
| **WI-2** | `OPEN` → `IN_PROGRESS` | S | ≥1 Pipeline Instance started for this item | — | `WorkStarted` | unchanged | `test_wi_starts_on_pipeline` |
| **WI-3** | `IN_PROGRESS` → `CLOSED` | S | consuming `PipelineClosed`; **obligation satisfied**; ### **`decision_ref` valid (GR-14)** | closure event immutable | `WorkItemClosed{decision_ref}` | unchanged | `test_wi_close_requires_valid_decision_ref` |
| **WI-4** | `IN_PROGRESS` → `IN_PROGRESS` | S | `PipelineFailed{transient}`, retries remain | — | `AttemptFailed` | unchanged | `test_wi_transient_failure_stays_in_progress` |
| **WI-5** | `IN_PROGRESS` → `BLOCKED` | S | `PipelineFailed{permanent}` OR retries exhausted | `reason` | `WorkBlocked{reason}` | unchanged | `test_wi_permanent_failure_blocks` |
| **WI-6** | `{OPEN,IN_PROGRESS}` → `BLOCKED` | S\|X | `EvidenceMissing` \| `ConflictRaised` on a material field (GR-10) | `reason` | `WorkBlocked` | unchanged | `test_wi_conflict_blocks` |
| **WI-7** | `{OPEN,IN_PROGRESS}` → `AWAITING_HUMAN` | S | `HumanDecisionRequired` | `question?` | `HumanRequested` | unchanged | `test_wi_awaits_human` |
| **WI-8** | `BLOCKED` → `IN_PROGRESS` | S\|X | `BlockerCleared` (evidence became `consistent`; conflict resolved) | — | `WorkUnblocked` | unchanged | `test_wi_unblock` |
| **WI-9** | `AWAITING_HUMAN` → `IN_PROGRESS` | H | `HumanDecided`; ### **`decision_ref` valid (GR-14)** | — | `HumanDecided{decision_ref}` | unchanged | `test_wi_human_decision_resumes` |
| **WI-10** | `{OPEN,IN_PROGRESS,BLOCKED,AWAITING_HUMAN}` → `ESCALATED` | T | `AgeThresholdCrossed` (durable timer, not a sweep) | — | `WorkEscalated` | unchanged | `test_wi_ages_to_escalated_via_timer` |
| **WI-11** | `ESCALATED` → `IN_PROGRESS` | H | `OwnershipReassigned`; new authenticated `owner_id` | `from_owner,to_owner` | `OwnershipTransferred` | ### **the new owner** | `test_wi_reassign_from_escalated` |
| **WI-12** | any non-terminal → `CANCELLED` | H | `CancellationRequested`; ### **`decision_ref` valid** | closure immutable | `WorkItemCancelled{decision_ref}` | unchanged | `test_wi_cancel_requires_decision_ref` |
| **WI-13** | `CLOSED` → `IN_PROGRESS` *(new phase)* | H | `ReopenRequested`; ### **`decision_ref` valid**; ### **prior closure event NOT mutated (GR-12)**; `phase_seq++` **or** a linked new Work Item | `prior_closure_ref, phase_seq++` | `Reopened{prior_closure_ref}` | reopening actor's assignee | `test_wi_reopen_new_phase_preserves_closure` |
| **WI-14** | `ESCALATED` → `{BLOCKED,AWAITING_HUMAN,CLOSED,CANCELLED}` | S\|H | same guards as WI-5/6/7/3/12 respectively | as those | as those | as those | `test_wi_escalated_can_still_close_block_await` |

## 15. Illegal-transition table *(GR-1; representative — anything not in §14 is illegal)*
`CLOSED`+`PipelineClosed` → ILLEGAL (already closed) · `CANCELLED`+anything → ILLEGAL · any→`CLOSED`/`CANCELLED` without `decision_ref` → ILLEGAL · `OPEN`+`HumanDecided` (no request outstanding) → ILLEGAL · closure by inactivity/`AutoClose` → ILLEGAL (I11). **Each emits `IllegalTransitionAttempted`.**

## 16. Transition precedence.
Within one event: **cancellation (WI-12) > closure (WI-3) > block (WI-5/6) > await (WI-7) > advance (WI-2/8/9)**. A `CancellationRequested` and a `PipelineClosed` racing ⇒ OCC (GR-3) admits one; if cancellation commits first, the later close is ILLEGAL (terminal).
## 17. Concurrent transitions. OCC (GR-3): two writers, one wins by `version`; loser reloads. **18. Version-check.** GR-3 on `version`. **19. Idempotency.** GR-4; additionally a duplicate `PipelineClosed` for an already-`CLOSED` item is a no-op. **20. Retry.** A Work Item is never retried in place; it spawns another Pipeline Instance (WI-4 loop). **21. Replay.** GR-11 — reconstructs ownership+closure deterministically, emits nothing to real consumers.
## 22. Cancellation. WI-12, any non-terminal, `decision_ref` required. **23. Expiry.** none. **24. Reopening.** WI-13 — new phase or linked item; closure immutable. **25. Correction.** attribute corrections (owner via WI-11) are events, never in-place edits; GR-12. **26. Supersession.** n/a. **27. Compensation.** if a correction invalidates a completed effect under this item, M10 is raised (out-of-band). **28. Human-approval.** none directly. **29. Policy.** none. **30. Brake.** ### **a brake does NOT close/cancel a Work Item** — it prevents its Pipelines from executing; queued items stay durable (GR-16).
## 31. Evidence/provenance. GR-10 (a conflicting material field blocks WI-8 unblock). **32. Events emitted.** WI-* events per registry §5. **33. Events consumed.** `PipelineStarted, PipelineClosed, PipelineFailed, EvidenceMissing, ConflictRaised, HumanDecisionRequired, BlockerCleared, AgeThresholdCrossed, CorrectionInvalidatedAnEffect`. **34. Durable writes.** state row + outbox (GR-2). **35. Txn boundaries.** one commit per transition; no cross-aggregate transaction. **36. Crash recovery.** GR-11/R: on restart, an `IN_PROGRESS` item with no live pipeline is re-evaluated (re-derive: still owed? ⇒ stays; satisfied ⇒ awaits a `PipelineClosed`); **recovery never closes an item — only an explicit closure event does.** **37. Timeout.** WI-10 via durable timer. **38. Observability.** every open item shows owner + age; `ESCALATED` surfaces unprompted; exposure shown when present. **39. Audit.** every transition is an Audit Event; terminal transitions carry `decision_ref`. **40. Security.** creation/closure/cancel/reassign require an authenticated human; a model may propose that work is needed, never own/close it (GR-7).

## 41. Acceptance criteria.
(a) creation without an owner fails; (b) closure/cancel without a valid `decision_ref` is illegal; (c) inactivity never closes; (d) a finishing Pipeline Instance does **not** auto-close the item (WI-3 requires "obligation satisfied", which may need several pipelines — 1:N); (e) reopening preserves the closure event; (f) a brake never closes/cancels.
## 42. Adversarial scenarios.
- **Pipeline finishes but obligation unmet** (e.g. billed but not paid — loop closes at cash): WI-3 guard "obligation satisfied" is FALSE ⇒ stays `IN_PROGRESS` ⇒ `test_wi_finishing_pipeline_does_not_auto_close`.
- **Two Pipelines, different outcomes** (see cross-review trace 15): the item stays `IN_PROGRESS` until the obligation is satisfied or `BLOCKED`; a `FAILED` pipeline and a `NEEDS_VERIFICATION` pipeline both feed WI — WI stays open/blocked, never closes on the failed one.
- **Duplicate Work Items across triggers** (SD-10): two items, each 1:1 to the shared `commit_key` via absorbed pipelines; both close on the same `PipelineClosed`/`decision_ref` ⇒ `test_wi_redundant_item_closes_on_shared_pipeline`.
## 43. Open validation. **V1** (reopen policy) — machinery exists (WI-13); the *when* needs a human `decision_ref`. Fail-closed. Not a block.

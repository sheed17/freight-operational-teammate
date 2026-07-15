# Entity Specification — Exception

*Conventions & `[C-n]`: see `00-conventions.md`. Lifecycle: canonical spec §12.9; F-30.*

1. **Canonical name.** Exception.
2. **Definition.** Something that needs a human.
3. **Purpose.** To ensure that everything Neyma cannot resolve deterministically reaches a **named human owner** and is **never closed by silence**.
4. **What it is not.** ### **Not an error log, an alert, or an issue tracker row.** Not auto-closable. Not outlivable.
5. **Owning component.** Exception Service (surfaces to the oversight surface).
6. **Authority class.** **Neyma-native.**
7. **Tenant ownership.** `[C-1]`.
8. **Canonical identifier.** `exception_id` (uuid).
9. **Natural / external identifiers.** `source_ref` (the machine that raised it — an Observation, Claim, Conflict, Expectation, Pipeline, Compensation…).
10. **Required attributes.** `exception_id` · `tenant_id` · `type` · `severity` · `state` · `version` · **`owner_id` (a named human, from creation — I1)** · `source_ref` · `created_at` · `summary`.
11. **Optional attributes.** `exposure` (money exposure, sourced from a verified/live read — never memory) · `acknowledged_at`/`acknowledged_by` · `ageing_at`/`escalation_at` · `decision_ref` (on `RESOLVED`) · `specific_question` (what we need the human to answer).
12. **Enums.** `state ∈ {OPEN, ACKNOWLEDGED, AGEING, ESCALATED, RESOLVED}` (spec §12.9). Terminal: `RESOLVED` only. `severity ∈ {SEV0, SEV1, SEV2}`.
13. **Provenance requirements.** `[C-7]` on any claim-derived field in the summary. A PERMANENT-failure exception (auth/config) records the failure classification (permanent, not transient).
14. **Relationships & cardinalities.** Any machine 1 : N Exception. Exception N : 1 `owner_id`. An Exception may reference a Work Item, and blocks its progress until resolved.
15. **Aggregate / transaction boundary.** Own aggregate; transitions `[C-2]`. Raising an Exception and freezing/blocking the affected work occur in one transaction where applicable.
16. **Database constraints.** `tenant_id, type, severity, state, version, owner_id, source_ref NOT NULL`. **CHECK: `owner_id NOT NULL` from creation.** ### **CHECK: `state = RESOLVED` requires a non-null `decision_ref`.**
17. **Uniqueness constraints.** PK `(tenant_id, exception_id)`. Optional `UNIQUE (tenant_id, source_ref, type) WHERE state != 'RESOLVED'` to prevent duplicate open exceptions for the same cause.
18. **Referential integrity.** `owner_id` FK → an authenticated tenant user. `source_ref`, `decision_ref` FK.
19. **Versioning / OCC.** `[C-10]`.
20. **Lifecycle reference.** **Canonical spec §12.9** (complete). Not blocked.
21. **Creation rules.** Raised by any machine on: unparseable observation, ambiguous/conflicting binding, overdue/indeterminate/expired expectation, dangling-reference TTL, unknown outcome, failed/impossible compensation, permanent retry failure, lost evidence, orphan adapter (Sev-0), cross-tenant breach (Sev-0), rebuild divergence (Sev-0). ### **An owner is assigned at creation or creation fails.**
22. **Mutation rules.** Only via §12.9. ### **Closure REQUIRES a `decision_ref`** — closure without one is an illegal transition.
23. **Correction rules.** N/A.
24. **Supersession rules.** N/A.
25. **Cancellation rules.** Only if the **underlying cause is retracted** — still an event, still a `decision_ref`.
26. **Expiry rules.** ### **NEVER. It ages (`OPEN/ACK → AGEING → ESCALATED`) and escalates. An exception cannot be outlived.**
27. **Reopening rules.** N/A (a recurrence is a new Exception).
28. **Deletion policy.** None `[C-9]`.
29. **Retention policy.** Permanent.
30. **Audit requirements.** Raise/acknowledge/age/escalate/resolve events with actor and `decision_ref`.
31. **Events emitted.** `ExceptionRaised{severity, exposure}` · `ExceptionAcknowledged` · `ExceptionAgeing` · `ExceptionEscalated` · `ExceptionResolved{decision_ref}`.
32. **Events consumed.** `Acknowledged` · `Resolved{decision_ref}` · `TimerFired` (ageing/escalation).
33. **Idempotency.** `[C-3]`. Optional dedup index (point 17) makes a re-raise of the same cause a no-op.
34. **Replay behavior.** `[C-5]`.
35. **Security / authorization.** ### **A model may NEVER close, resolve, or auto-clear an Exception** `[C-6]`. Resolution requires an authenticated human with a `decision_ref`. Sev-0 exceptions auto-engage the brake (via their source detectors).
36. **Fail-closed behavior.** ### **An exception closed without a decision is not closed — it is forgotten.** `AutoClose`/`Inactivity` transitions are illegal (spec §12.9). A PERMANENT failure is raised **immediately** and never retried.
37. **Structurally impossible states.** An ownerless Exception. A `RESOLVED` Exception with no `decision_ref`. An auto-closed Exception. An expired Exception.
38. **Interaction with the checkpoint.** ### **Checkpoint step 4 (native-state validity): an open Exception that freezes an entity blocks consequential actions on it.** *(Not every Exception freezes an entity — only those that make a material field non-`consistent`.)*
39. **Interaction with Effect Grants.** A `NEEDS_VERIFICATION` / `COMPENSATION_FAILED` Exception keeps the entity frozen and the commit key held; no new grant for that entity.
40. **Interaction with human approval.** `AWAITING_HUMAN` on a Work Item often corresponds to an open Exception; resolution unblocks.
41. **Interaction with policy & brake.** ### **A repeatedly-overridden rule raises an Exception to the Policy Owner** ("you have overridden this 6 times — should it change?") — **the system asks; it does not change the rule** (spec §20.7). Sev-0 exceptions engage brakes.
42. **Observability.** ### **`NEEDS_VERIFICATION`-backed and Sev-0 exceptions are the highest-priority operational queue.** Mean time to human resolution is the metric that matters (it measures how good the escalation message was). Ageing escalates automatically.
43. **Acceptance criteria.** (a) closure without a `decision_ref` is rejected; (b) inactivity never closes; (c) an owner exists from creation; (d) a permanent failure raises immediately with zero retries; (e) ageing escalates via a durable timer.
44. **Adversarial tests.** `test_exception_closure_requires_decision_ref` (F-30) · `test_inactivity_never_closes_an_exception` · `test_ownerless_exception_impossible` · `test_auth_failure_raises_exception_immediately_zero_retries` (L-D) · `test_ageing_escalates_via_durable_timer_not_sweep` · `test_model_cannot_resolve_an_exception` `[C-6]`.
45. **Open validation questions.** **V10** (per-lane ageing/escalation thresholds). **Fail-closed default:** ages, escalates, never expires. **Not a block.**

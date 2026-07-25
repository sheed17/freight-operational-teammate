# Event Family F9 — Exception Events

*Registry: `events/registry.md`. Producer: machine M9. Defaults: registry §1–§2.*

**Family defaults:** `aggregate_type=exception`; ordering = **order-tolerant**; security=`internal` (Sev-0 exceptions=`security`/`high`); projection = **none**; `accountable_owner_id` required (a human, from creation).

| Event · v1 · producer | Proves / ¬Proves | Payload | Consumers → guard | Notes / tests |
|---|---|---|---|---|
| **`ExceptionRaised`** EC-1 | proves something needs a human, owned from creation · ¬proves resolution | `severity`(R), `exposure?`, `source_ref`(R), `specific_question?`, `sub_status?` | Oversight (queue) | ### **owner assigned at creation (I1); a PERMANENT auth/config failure raises IMMEDIATELY, never retried (L-D)**; `test_ev_exceptionraised_owned` |
| **`ExceptionAcknowledged`** EC-2 | proves a human saw it | `acknowledged_by` | Oversight | `actor_type=human`; `test_ev_exception_ack` |
| **`ExceptionAgeing`** EC-4 | proves it aged past threshold | — | Oversight | durable timer; ### **never resolves via a timer**; `test_ev_exception_ageing` |
| **`ExceptionEscalated`** EC-5 | proves escalation threshold reached | — | Oversight | `test_ev_exception_escalated` |
| **`ExceptionResolved`** EC-3/6 | ### **proves an authenticated human (or ACTIVE rule) resolved it** · ¬proves closure by inactivity | ### `decision_ref`(R, resolves per K-1) | Oversight; unblocks the frozen entity | ### **`decision_ref` MUST resolve to a human-decision audit event OR an ACTIVE rule_id (GR-14); an `AutoClose`/inactivity resolution is ILLEGAL**; `test_ev_exceptionresolved_valid_decision_ref` |

## Cross-cutting
**Dedup:** optional `(tenant,source_ref,type) WHERE state!='RESOLVED'` — a re-raise of the same cause is a no-op. **Ordering:** order-tolerant. **Replay:** reconstructs the queue; an open Exception keeps its entity blocked. **Projection:** none. **Security:** ### **Sev-0 exceptions (orphan adapter, cross-tenant breach, rebuild divergence) are produced BY F14 detectors and auto-engage the brake**; a model resolving an Exception is impossible (ER-9, GR-7). **Audit:** mean-time-to-human-resolution is the metric that matters. **Open validation:** V10 (thresholds) — fail-closed (ages, escalates, never expires).

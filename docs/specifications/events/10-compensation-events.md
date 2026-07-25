# Event Family F10 — Compensation Events

*Registry: `events/registry.md`. Producer: machine M10. Defaults: registry §1–§2.*

**Family defaults:** `aggregate_type=compensation`; ordering = **STRICT per-aggregate**; security=`high` (money-reversal); projection = **none directly** (its executing pipeline drives `ProjectionUpdated`); `accountable_owner_id` required (a human, from `REQUIRED`); consequential where it executes.

| Event · v1 · producer | Proves / ¬Proves | Payload | Consumers → guard | Notes / tests |
|---|---|---|---|---|
| **`CompensationRequired`** CM-1 | proves a VERIFIED effect is now known wrong and must be undone · ¬proves it can be undone | `original_effect_id`(R), `exposure`(R), `reason`, `decision_ref`(R, the invalidating correction) | Oversight; M4 (approval) | ### **only from a `VERIFIED` original (M-33)**; `test_ev_comp_required_from_verified` |
| **`CompensationRefused`** CM-1r | ### **proves compensation was REFUSED because the original outcome is UNKNOWN** · ¬proves anything about the effect | `original_effect_id`, `cause=unknown_outcome` | Oversight (waits for the human) | ### **you cannot undo what you cannot prove you did (M-33)**; `test_ev_comp_refused_on_unknown` |
| **`CompensationApproved`** CM-2 | proves a human approved the reversal | `approval_id`(R) | M10 (execute) | ### **money-affecting compensation is ALWAYS `HUMAN_APPROVAL_REQUIRED`**; `test_ev_comp_human_approved` |
| **`CompensationImpossible`** CM-2n | proves the world offers no undo (a sent email, a wire) | `exposure` | M9/Oversight | ### **honest — does not pretend it compensated**; `test_ev_comp_impossible` |
| **`CompensationStarted`** CM-3 | proves a NEW gated pipeline began the reversal | `pipeline_instance_id`(R) | Oversight | ### **a full pipeline — no privileged path**; `test_ev_comp_started_full_pipeline` |
| **`CompensationCompleted`** CM-4 | proves the reversal was verified by readback | — | Oversight; analytics | consequential; `test_ev_comp_completed_verified` |
| **`CompensationFailed`** CM-4f | proves the reversal failed/went unknown — ### **reality and projection are KNOWN to diverge** | `exposure` | M9 (human-owned) | ### **non-terminal; never auto-resolves; the loudest state**; `test_ev_comp_failed_non_terminal` |

## Cross-cutting
**Dedup:** `(tenant,original_effect_id) WHERE state!='NOT_POSSIBLE'`. **Ordering:** STRICT. **Replay:** the compensating effect, like any effect, is never produced by replay (ER-2). **Projection:** via its executing pipeline's verified `ProjectionUpdated`. **Security:** ### **a compensation is an effect — full checkpoint; BLOCKED under an active brake (an urgent one needs a human brake-narrow)**; no bulk undo (N individually-gated events, aggregate exposure shown first). **Audit:** `high` — `original_effect_id` + invalidating `decision_ref`. **Open validation:** V1 interaction — fail-closed (each human-approved).

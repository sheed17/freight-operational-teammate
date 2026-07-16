# Event Family F4 — Approval Events

*Registry: `events/registry.md`. Producer: machine M4. Defaults: registry §1–§2.*

**Family defaults:** `aggregate_type=approval`; ordering = **STRICT per-aggregate**; security=`high`; projection = **none** (approvals are native authority state, never projected truth); consequential ⇒ pin `material_facts_fingerprint`, `policy_version`, `entity_versions`; `commit_key` on all.

| Event · v1 · producer | Proves / ¬Proves | Payload | Consumers → guard | Notes / tests |
|---|---|---|---|---|
| **`ApprovalRequested`** AP-1 | proves a human decision was solicited with a pinned fingerprint · ¬proves consent | `fingerprint`(R), `gate_decision`(R), `rendered_facts`, `expires_at`(R) | Oversight (renders the card) | fingerprint from **runtime reads** (ER-9/M-13); `test_ev_approvalrequested_runtime_fingerprint` |
| **`ApprovalGranted`** AP-2 | ### **proves an authenticated, authorized human consented to the action AND its exact facts** · ¬proves the effect happened, ¬authorizes a second attempt | `granted_by`(R), `signatures[]?` (dual control) | M2 (bind) | ### **`actor_type=human` ONLY (ER-10); a model/counterparty producing this is illegal ⇒ `CounterpartySelfAuthorizationDetected`**; `test_ev_approvalgranted_human_only` |
| **`ApprovalDenied`** AP-2d | proves the human declined | — | M2 (void) | `test_ev_approvaldenied` |
| **`ApprovalExpired`** AP-3 | proves the TTL elapsed — ### **an expired approval is not a weak approval; it is not an approval** | — | M2 (void) | ER-5 (a timeout here proves the *approval* lapsed, not that an effect failed); `test_ev_approvalexpired` |
| **`ApprovalVoided`** AP-4/4p/5 | proves the approval was voided because reality/policy/brake changed · ¬proves any effect | `cause∈{drift,policy,brake}`(R), `drift_diff?` | M2 (void) | ### **carries the field-level `drift_diff` so the refusal is explainable (I3)**; `test_ev_approvalvoided_carries_diff` |
| **`ApprovalRevoked`** AP-6 | proves a human revoked before consumption | — | M2 (void) | `actor_type=human`; `test_ev_approvalrevoked` |
| **`ApprovalConsumed`** AP-7 | proves the approval authorized exactly ONE committed effect | — | Oversight | ### **co-commit with the M3 claim CAS; single-use**; `test_ev_approvalconsumed_once` |

## Cross-cutting
**Dedup:** transition-natural; ### **a double-tap of the Slack button is idempotent — the second finds `CONSUMED` and re-emits nothing (replies "already done")**. **Ordering:** STRICT per-approval; `ApprovalConsumed` after `ApprovalVoided` is impossible (a voided approval cannot be consumed — the claim CAS fails). **Replay:** never re-grants, never consumes into an effect (ER-2). **Projection:** none. **Security:** ### **`ApprovalGranted` by a non-human ⇒ `CounterpartySelfAuthorizationDetected` (F14) + fraud signal**; the transport token is single-use + actor-bound. **Audit:** `high` — the retained `canonical_payload` (on the M4 aggregate) plus these events reconstruct exactly what the human saw. **Open validation:** V2 (TTLs), V3 (dual-control) — fail-closed.

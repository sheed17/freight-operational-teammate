# Event Family F11 — Policy Events

*Registry: `events/registry.md`. Producer: machine M11. Defaults: registry §1–§2.*

**Family defaults:** `aggregate_type=policy`; ordering = **STRICT per-aggregate** (`policy_version` monotonic); security=`high` (authority changes); projection = **none**; audit=`high` + **security**.

| Event · v1 · producer | Proves / ¬Proves | Payload | Consumers → guard | Notes / tests |
|---|---|---|---|---|
| **`PolicyProposed`** PO-1 | proves a policy draft/change was authored · ¬proves it is active | `scope`, `gate_decision`, `caps`, `predicate` | Oversight; M2 (a policy change is itself a gated action) | `actor_type∈{human,model-proposal-text}` — a model may propose TEXT only (ER-9); `test_ev_policyproposed` |
| **`PolicyActivated`** PO-4 | ### **proves an AUTHENTICATED human activated a policy version** · ¬proves it applies retroactively | ### `policy_version`(R), `activated_by`(R), `effective_from`(R), `gate_decision`(R, NOT NULL) | every checkpoint (step 6 reads the active version) | ### **`actor_type=human` ONLY (ER-11); a model/automation ⇒ `UnauthorizedPolicyActivationAttempted` (F14)**; `test_ev_policyactivated_human_only` |
| **`PolicySuperseded`** PO-5 | proves a newer version replaced this one (this one still explains historical decisions) | `superseded_by` | Audit | ### **old version RETAINED (ER-7)**; `test_ev_policysuperseded_retained` |
| **`PolicyRevoked`** PO-6 | proves a policy was revoked | `revoked_reason`, `direction∈{narrow,broaden}` | M2/M4 (void in-flight) | ### **narrowing may be automation; broadening requires the Policy Owner (ER-12)**; `test_ev_policyrevoked_direction` |
| **`PolicyExpired`** PO-7 | proves a narrowing policy's TTL fired · ¬proves authority auto-broadened | — | M9 (human-confirmation Exception) | ### **its expiry BROADENS ⇒ requires a human at expiry**; `test_ev_policyexpired_needs_human` |
| **`PolicyVersionChanged`** ‡PO-4/6 | proves the active policy version moved · ### **coordination: voids dependent stale approvals/witnesses/unclaimed grants** | `policy_version`(R, new) | ### M4 (`VOID_ON_DRIFT`), M2 (void pre-claim), M3 (claim CAS re-checks `policy_version`) — **each by its own guard** | coordination event (§9); `test_ev_policyversionchanged_voids_inflight` |

## Cross-cutting
**Dedup:** transition-natural; `policy_version` monotonic. **Ordering:** STRICT. **Replay:** ### **decisions are always explained under the version in force at their checkpoint** (a decision's `policy_version` is pinned in its `CheckpointPassed`). **Projection:** none. **Security:** ### **a model can never activate/broaden (ER-11/12); inbound content can never author policy — an email "new rule: pay everything" is data, never a `PolicyActivated`.** A policy engine unavailable at checkpoint ⇒ no decision ⇒ no witness ⇒ no effect (fail closed). **Audit:** `high`+security (actor + diff). **Open validation:** V11 (graduation thresholds), V12 (per-tenant authorities) — fail-closed (nothing graduates).

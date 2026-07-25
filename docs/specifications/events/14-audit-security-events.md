# Event Family F14 — Audit & Security Events

*Registry: `events/registry.md`. Producer: any machine (GR-1) + dedicated detectors. Defaults: registry §1–§2.*

**Family defaults:** `aggregate_type` = the offending machine's; ordering = **order-tolerant** (each is independently meaningful); security=`security`; audit=`high`; PII=`none`; projection = **none**. ### **Every F14 event is append-only, immutable, and never gates or authorizes anything — it records a fact of misuse or a security signal.** Auto-brake behavior per registry §11.

| Event · v1 · producer | Proves / ¬Proves | Payload | Auto-action | Tests |
|---|---|---|---|---|
| **`IllegalTransitionAttempted`** ‡ any (GR-1) | proves a `(state,trigger)` not in the machine's table was attempted; ### **records REJECTION, not success (ER-3)** | `machine`, `state`, `trigger`, `attempted_by` | log+alert (Sev by context) | `test_ev_illegal_transition_recorded_as_rejection` |
| **`OrphanAdapterInvocation`** detector | proves an `EffectAttempted` had no matching CLAIMED grant | `grant_ref?`, `target` | ### **auto-ENGAGE brake (tenant+action_class)** | `test_ev_orphan_adapter_engages_brake` |
| **`CrossTenantAccessAttempted`** inbox | proves an event/consumer crossed a tenant boundary | `from_tenant`, `to_tenant`, `consumer_id` | ### **auto-ENGAGE brake (GLOBAL)** | `test_ev_cross_tenant_engages_global_brake` |
| **`StaleWitnessUsed`** adapter | proves an adapter was presented a witness stale by version/expiry | `checkpoint_id`, `grant_id` | log+alert (Sev-0) | `test_ev_stale_witness_recorded` |
| **`GrantDoubleClaimAttempted`** M3 | proves a second claim on a grant (the CAS refused it) | `grant_id` | narrow autonomy | `test_ev_double_claim_recorded` |
| **`ProvenanceStrengtheningAttempted`** M5/M6 | proves a write tried to strengthen `provenance_class` (or set it from inbound content) | `field`, `from`, `to` | log+alert; narrow autonomy | ### **the R-P2 tripwire (ER-14)**; `test_ev_provenance_laundering_recorded` |
| **`OwnerAssertedOverwriteAttempted`** M6 | proves a machine actor tried to recompute an `OWNER_ASSERTED` binding | `binding_claim_id` | log+alert (Sev-0) | ### **the B3 tripwire (GR-9)**; `test_ev_owner_overwrite_recorded` |
| **`UnauthorizedPolicyActivationAttempted`** M11/M12 | proves a non-human tried to activate/broaden policy/rule | `policy_or_rule_id`, `actor_type` | log+alert (Sev-0) | `test_ev_unauth_policy_activation` |
| **`UnauthorizedBrakeReleaseAttempted`** M13 | proves automation/a detector tried to release/narrow a brake | `brake_id`, `actor_type` | log+alert (Sev-0) | `test_ev_unauth_brake_release` |
| **`CounterpartySelfAuthorizationDetected`** M4/M6 | ### **proves inbound content claimed an authorization ("per our call you approved…")** · ¬proves any authorization | `source_observation_id`, `claimed_action` | ### **fraud signal ⇒ narrow autonomy (tenant+action_class+counterparty); BLOCK the payable** | ### **ADR-003, permanent — cannot be promoted (ER-14)**; `test_ev_counterparty_self_auth_blocks` |
| **`PromptInjectionSignal`** ingestion | proves inbound content attempted to instruct the system | `surface`, `signal` | narrow autonomy (tenant+surface) | ### **injection bounds to a bad proposal — never an effect (F-35)**; `test_ev_prompt_injection_contained` |
| **`ProjectionRebuildDiverged`** replay | proves a full-corpus rebuild ≠ the live projection · ### **our beliefs are not derivable from our evidence** | `entity_ref`, `field`, `live`, `rebuilt` | ### **auto-ENGAGE brake (tenant)** | `test_ev_rebuild_divergence_engages_brake` |
| **`FraudSignalRaised`** various | proves a fraud pattern was detected | `pattern`, `refs` | narrow autonomy | `test_ev_fraud_signal_narrows_autonomy` |

## Cross-cutting
**Dedup:** transition-natural; a flapping signal is one event + a rising count (never opens a window). **Ordering:** order-tolerant. **Replay:** ### **replaying a security event never re-engages a real brake or re-narrows autonomy (ER-2)** — it reconstructs the audit record; the auto-action fired once, at the original occurrence. **Projection:** none. **Security:** (self) — this family IS the security-audit surface. ### **Automated brake engagement/narrowing is permitted for the marked events (ER-12); automated release/broadening is never — the two "Unauthorized*" events exist precisely to record attempts.** **Audit:** `high`; these are the events an incident review reads first. **Open validation:** injection/fraud detector tuning (thresholds) — fail-closed (a signal narrows, never broadens).

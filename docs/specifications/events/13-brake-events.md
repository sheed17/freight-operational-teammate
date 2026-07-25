# Event Family F13 — Brake Events

*Registry: `events/registry.md`. Producer: machine M13. Defaults: registry §1–§2.*

**Family defaults:** `aggregate_type=brake`; ordering = **STRICT per-aggregate** (`brake_version` monotonic); security=`high`; projection = **none**; audit=`high`+security; ### the `GLOBAL` brake is one platform-row (SD-12), its `brake_version` = `global_brake_version`.

| Event · v1 · producer | Proves / ¬Proves | Payload | Consumers → guard | Notes / tests |
|---|---|---|---|---|
| **`BrakeEngaged`** BR-1 | ### **proves new admission is withdrawn in scope** · ¬proves in-flight work was killed (it is not — GR-16) | `scope`(R), `actor`(R, human or detector id), `reason`(R), `brake_version`(R) | ### M2 (`PipelineVoided` iff pre-claim), M4 (`VOID_ON_BRAKE`), M3 (claim CAS re-checks `brake_version`) — **each by its own guard (§9)** | ### **any authenticated human OR a Sev-0 detector; works with the system unhealthy (M-61)**; coordination event; `test_ev_brakeengaged_admission_only` |
| **`BrakeWidened`** BR-2 | proves the brake's scope grew (authority narrowed) | `scope`, `brake_version`(R) | as BR-1 | ### **automation MAY widen (narrows authority — ER-12)**; `test_ev_brakewidened_automation_ok` |
| **`BrakeNarrowed`** BR-3 | proves the brake's scope shrank (authority broadened) | `scope`, `brake_version`(R) | as BR-1 | ### **AUTHENTICATED HUMAN ONLY (broadens authority — ER-12)**; `test_ev_brakenarrowed_human_only` |
| **`BrakeReleased`** BR-4 | proves a human released the brake with the required evidence · ¬proves queued work may reuse old witnesses | ### `released_by`(R, human), `release_decision_ref`(R), `brake_version`(R) | ### every checkpoint (re-checkpoint queued work; the bumped `brake_version` invalidates all stale witnesses/grants) | ### **`actor_type=human` ONLY; a detector/automation ⇒ `UnauthorizedBrakeReleaseAttempted` (F14); requires in-flight-accounted + no unresolved Sev-0 + positive integration health + decision_ref**; `test_ev_brakereleased_human_and_evidence` |

## Cross-cutting
**Dedup:** transition-natural; engagement idempotent on scope (a flapping detector ⇒ one `ACTIVE` brake + a rising signal count, no window). **Ordering:** STRICT (`brake_version` monotonic); ### **the claim CAS re-validating `brake_version` is how a `BrakeEngaged` delivered "after" a checkpoint but before a claim still wins — the CAS matches zero rows (T2/T9, never both never neither).** **Replay:** brake history replays; never re-engages a real brake (ER-2). **Projection:** none. **Security:** ### **automation may engage/widen; NEVER release/narrow (ER-12); a detector may never clear its own alarm.** The brake store unreachable at checkpoint ⇒ no effect ("cannot read the brake" ≠ "off"). **Audit:** `high`+security — the brake report (assembled from these events) is the incident timeline; a hidden brake violates R17 (every surface reports it unprompted). **Open validation:** V13/V14/V15 — fail-closed defaults.

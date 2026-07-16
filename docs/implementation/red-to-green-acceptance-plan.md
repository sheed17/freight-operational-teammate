# Red-to-Green Acceptance Plan

*Ordered: acceptance case → current status → blocking unit → expected green phase → gate.*

## The intentionally-red baseline
| Case | Status @ `6057dfe` | Why red | Blocking unit | Green at | Gate |
|---|---|---|---|---|---|
| ### **AC-SAFE-012** | ### **RED (by design)** | ### **`_commit_identity` includes `approved_amount`** | **U1.2** | ### **Phase 1** | **G0** |
| ### **AC-SAFE-013** | ### **RED (by design)** | ### **`if not amount: return None`** | **U1.3** | ### **Phase 1** | **G0** |
| `AC-SEC-001` | ### **RED** *(new — recon §5)* | ### **6/8 tables not tenant-first** | U2.1 | Phase 2 | G0/G4 |
| `AC-SEC-013` | RED | 13 direct import sites | U4.\* | Phase 4 | G4 |
| `AC-SAFE-002/004/005` | RED | no checkpoint/witness | U3.1 | Phase 3 | G4 |
| the 105 `AC-CKPT-*` | RED | as above | U3.1–3.4 | Phase 3 | G4 |
| `AC-EVT-007/008` | RED | no outbox/replay/corpus | U5.\* | Phase 5 | G2 |
| `AC-SAFE-028` | RED | ### **no Work Item entity ⇒ no ownership** | U6.1 | Phase 6 | G4 |
| `AC-SAFE-015/016` | RED | no `provenance_class` | U7.1 | Phase 7 | G4 |
| `AC-DOM-*` (40) | RED | domain entities partial | U9.\* | Phase 9 | G1 |
| `AC-WF6-*`, `AC-WF8-*`, `AC-FC-*` | RED | no loops | U10+ | Phase 10+ | G5+ |

## Already GREEN at baseline *(do not regress)*
`test_no_mock_effect_in_production` (7 cases — R-01 severed) · `test_consequential_read_boundary` (V-3, **proven by negative control**) · `test_the_gated_write_driver_survives` (R-03).

## Ordered milestones
| Milestone | Cases that MUST be green | Gate |
|---|---|---|
| ### **Before ANY broader write-path migration** | ### **AC-SAFE-012, AC-SAFE-013** | **G0** |
| Before the first external write **of any kind** | ### **AC-SAFE-001..014, AC-SEC-001/013, the 105 AC-CKPT, AC-RACE-001..017** | **G4** |
| **G4 qualification** | all of the above + `AC-REC-*` + `AC-EVT-007` | G4 |
| **W6 shadow** | `AC-WF6-001..005`, `AC-EVT-*`, `AC-AUD-*`, zero-effect assertions | G6 |
| **W6 human-executed** | + `AC-DEG-W6-readonly`, `AC-DEG` assertion 5 (### **never claim Neyma executed**) | G7 |
| **W8 supervised release** | + `AC-WF8-001..010`, `AC-FC-005..009`, ### **AC-SAFE-001..028 RE-RUN LIVE** | G8 |
| Before multi-loop | + `AC-WF-H*` (atomic handoffs), `AC-FC-016` | G9 |
| Before bounded autonomy | + the full suite + the graduation dossier (**zero wrong actions**) | G10 |

## When a case may stay red
> ### **ONLY when: (a) the capability is UNREACHABLE in production, (b) the gate does not require it, AND (c) the plan records why — all three.**
> ### **No reachable unsafe behavior may be excused by a future test phase.** The 6 production-reachable live-write paths (EP-1,3,6,7,9,10) are reachable **today** ⇒ ### **their risk is NOT excused; it is contained by the runbook discipline (operator discipline, not a mechanism) until P4 deletes or converts them.** This is recorded as the plan's single largest standing risk (R-07).

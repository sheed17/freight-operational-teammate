# Event & Replay Acceptance *(AC-EVT-*)*

*Registry defaults apply. Levels: `EVENT_CONTRACT` / `REPLAY`. Gate: **G2**.*

## Coverage requirement
> ### **All 98 canonical emitted event names × all event versions. A `STRUCTURAL` case (`AC-EVT-000`) asserts a BIJECTION between the implementation's emitted-event registry and the frozen 98 — an undefined event or an unemitted contract fails the build.**
> ### **The oracle is EXACT SET EQUALITY of event names, not a count. A count match with different members MUST fail.**
> *(Errata 2026-07-16: corrected from 92. The canonical event list (`events/registry.md` §3) enumerates **98** across F1–F13. F14's 13 audit/security events are counted separately and were correct; F15 is a lens and declares no contracts; `TimerFired` is a TRIGGER, not an emitted event, and is excluded. See `docs/implementation/canonical-corpus-errata-review.md`.)*

## Per-event mandatory assertions
| # | Assertion | Oracle |
|---|---|---|
| **AC-EVT-001** | every event uses the **canonical envelope** | schema assertion over all 98 |
| **AC-EVT-002** | ### **`tenant_id` mandatory AND first in partition identity** | reject any event without it; partition-key probe |
| **AC-EVT-003** | ### **every producer transition emits its required event** (134→98 map) | the outbox row exists in the transition's commit |
| **AC-EVT-004** | duplicate delivery is harmless | inbox `(consumer,tenant,event_id)` ⇒ no-op; state digest unchanged |
| **AC-EVT-005** | out-of-order delivery handled per contract | STRICT families reject/park; order-tolerant families converge |
| **AC-EVT-006** | ### **dangling references PARKED, never dropped** | `pending_references` row; drained in arrival order; TTL ⇒ Exception |
| **AC-EVT-007** | ### **replay is SIDE-EFFECT FREE** | replay `GC-1` ⇒ **0 witnesses, 0 grants, 0 adapter calls, 0 real-consumer emissions** |
| **AC-EVT-008** | ### **full-history rebuild reproduces canonical projections** | ### **`GC-1` ⇒ the SAME projection DIGEST, byte-for-byte** |
| **AC-EVT-009** | mixed versions upcast deterministically | v1+v2+v3 in one corpus ⇒ one digest; run twice ⇒ identical |
| **AC-EVT-010** | ### **correction preserves original history** | the original event is byte-identical after a `ClaimCorrected` |
| **AC-EVT-011** | ### **provenance is never strengthened** | push a `MODEL_INFERRED` value through copy/cache/re-observe/reconcile/serialize/process-boundary ⇒ **emerges `MODEL_INFERRED` every time** |
| **AC-EVT-012** | ### **an event payload cannot authorize an action** | a crafted payload asserting approval/authority ⇒ zero effect; it is data |
| **AC-EVT-013** | ### **malicious payload fields cannot assign provenance or authority** | a payload with `provenance_class: OWNER_ASSERTED` ⇒ **ignored** + `ProvenanceStrengtheningAttempted` |
| **AC-EVT-014** | historical events remain readable | ### **every historical version readable via upcasters — forever; a deleted schema field is still readable** |
| **AC-EVT-015** | projection divergence detected + handled | `GC-1` + an injected divergence ⇒ `ProjectionRebuildDiverged` ⇒ **auto-brake** |

## The golden corpus `GC-1` *(immutable fixture)*
Spans **≥1 schema version change · ≥2 tenants · ≥1 correction (+ its propagation) · ≥1 `UNKNOWN_OUTCOME` · ≥1 compensation · ≥1 brake episode · ≥1 parked dangling reference · ≥1 duplicate delivery.**
> ### **THE CORPUS ORACLE: `rebuild(GC-1) → digest D`. D is pinned in the repo. Every build, every version, forever: the SAME D. A changed digest is a FAILING build until a human explains why — a rebuild that "looks right" is not a pass.**
> ### **`GC-1` is NEVER reset between replay tests** (a suite that resets state between replays is testing nothing — see the hostile review's loophole L-19).

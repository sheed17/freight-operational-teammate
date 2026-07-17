# Current-to-Target Gap Matrix

*Source: `current-state-inventory.md` (mechanical recon @ `6057dfe`) → the frozen specs. ### **No component is classified compatible merely because it has a similar name.***

**Classes:** `ABSENT` · `PARTIAL` · `PRESENT_BUT_NONCANONICAL` · `PRESENT_AND_COMPATIBLE` · `PRESENT_BUT_UNSAFE` · `DEPRECATED` · `UNKNOWN_NEEDS_INSPECTION`

> ### **DEFINITION OF THE GATE COLUMN** *(added after this plan's own mechanical check found the column had NO defined meaning — see review finding M-4)*: ### **"the EARLIEST gate that cannot pass without this component."** It is computed mechanically as the **strictest gate among the row's cited acceptance cases**, not chosen by feel. ### **An undefined column in a plan that gates live writes is not a cosmetic problem: 14 of 34 rows were internally inconsistent under ANY reading, and nobody could have adjudicated them, because there was no rule to adjudicate against.**

| # | Component | Current | Class | Target | Acceptance | Task | Depends on | Gate |
|---|---|---|---|---|---|---|---|---|
| 1 | **Tenancy** | ### **7/8 tables not tenant-first** *(errata: was 6/8)* | ### **PRESENT_BUT_UNSAFE** | `tenant_id` NOT NULL, first in all 9 surfaces | `AC-SEC-001..003` | U2.1 | — | **G4** |
| 2 | **Commit Key** | amount-in-key; absent for non-money; not tenant-first | ### **PRESENT_BUT_UNSAFE** | logical-effect key, amount-free, mandatory | ### **`AC-SAFE-012/013`** | ### **U1.\*** | — | **G4** |
| 3 | **Effect Ledger** | `operation_commit_claims` (claim-once, single-col PK) | **PRESENT_BUT_NONCANONICAL** | one row, 8 states, tenant-scoped, 2 partial indexes | `AC-SAFE-014`, the `AC-MACH-3*` series (`AC-MACH-301`…) | U2.2/U2.3 | U1, U2.1 | **G1** *(+G4 safety)* |
| 4 | **Checkpoint Witness** | ### **none** | ### **ABSENT** | immutable, unconstructable `CheckpointPassed` | `AC-SAFE-002/004/005` + 105 `AC-CKPT` | U3.1 | U2 | **G4** |
| 5 | **Effect Grant** | reservation only | **PARTIAL** | mint-from-witness + claim CAS | `AC-SAFE-001/006/014` | U3.3 | U3.1 | **G4** |
| 6 | **Adapter isolation** | ### **13 direct import sites** | ### **PRESENT_BUT_UNSAFE** | module-private + CI import gate | `AC-ADPT-002`, `AC-SEC-013` | U4.\* | U3 | **G3** *(+G4 safety)* |
| 7 | **Approvals** | Slack HMAC token + resume | **PARTIAL** | + fingerprint, drift, consume-CAS | `AC-SAFE-008/011`, `AC-CKPT-2` | U3.2 | U3.1 | **G4** |
| 8 | **Material-Facts Fingerprint** | none | **ABSENT** | `fp_v1` + retained canonical payload | `AC-SAFE-008` | U3.2 | — | **G4** |
| 9 | **Entity-version sets** | none | **ABSENT** | the SD-3 set pinned | `AC-CKPT-5-*` | U3.1 | U2.1 | **G4** |
| 10 | **Policy** | lane caps + graduation config | **PRESENT_BUT_NONCANONICAL** | typed/versioned/never-null gate | `AC-CKPT-6-*` | U8.1 | U3 | **G4** |
| 11 | **Rule** | `knowledge.PROCEDURE` → prompt | ### **PRESENT_BUT_UNSAFE** *(L-C: claims enforcement)* | compile-or-refuse | `AC-WF10-005` | U8.2 | U8.1 | **G5** |
| 12 | **Brake** | ### **a convention-checked flag** | ### **PRESENT_BUT_UNSAFE** | admission control at mint+claim | `AC-SAFE-006/007` | U3.4 | U3.3 | **G4** |
| 13 | **Verification** | readback + amount reconcile | **PARTIAL** | 8 outcomes + positive health | `AC-SAFE-021/023`, `AC-ADPT-012` | U4.11 | U3 | **G3** *(+G4 safety)* |
| 14 | **UNKNOWN_OUTCOME** | a `NEEDS_VERIFICATION` payload | **PARTIAL** | non-terminal, owned, reason, frozen | `AC-SAFE-022` | ### **U3.3** *(corrected: it is one of the grant's 8 states, so it lands with the grant in P3 — an earlier draft said P6, which would have made G4 depend on a LATER phase)* | U3.1 | **G4** |
| 15 | **Outbox/Inbox** | ### **none** | ### **ABSENT** | transactional outbox + dedup inbox | `AC-RACE-006..009`, `AC-EVT-003` | U5.1/U5.2 | U2.1 | **G2** *(+G4 safety)* |
| 16 | **Event contracts** | ad-hoc audit rows | **PARTIAL** | ### **98 events** + envelope + versions | `AC-EVT-*` | U5.3 | U5.1/U5.2 | **G2** |
| 17 | **Replay** | ### **none** | ### **ABSENT** | sandboxed, zero-effect, `GC-1` digest | `AC-EVT-007/008`, `AC-SEC-014` | U5.4/U5.5 | U5.3 | **G2** *(+G4 safety)* |
| 18 | **Work Item** | implicit in runs | **ABSENT** *(as an entity)* | M1, owned, closure≠pipeline | `AC-SAFE-028`, `AC-FC-015` | U6.1 | U5 | **G4** |
| 19 | **Pipeline Instance** | `workflow_runs`+router | **PRESENT_BUT_NONCANONICAL** | M2 (16 states) | the `AC-MACH-2*` series (`AC-MACH-201`…`AC-MACH-215x`) | U6.2 | U5 | **G1** |
| 20 | **Machines (13)** | 1 doc-shaped machine | **PARTIAL** | ### **134 transitions** declarative | `AC-MACH-*` ### **(134)** | U6.3 | U5 | **G1** |
| 21 | **Provenance** | ### **none** | ### **ABSENT** | 6 classes, R-P1/2/3 | `AC-SAFE-015/016`, `AC-EVT-011` | U7.1 | U6 | **G2** *(+G4 safety)* |
| 22 | **Evidence** | files on disk | **PARTIAL** | content-addressed, immutable | `AC-DOM-009` | U7.2 | U7.1 | **G1** |
| 23 | **Observation** | ad-hoc reads | **PARTIAL** | natural-key idempotent | the `AC-MACH-5*` series (`AC-MACH-501`…), `AC-ADPT-010` | U7.3 | U7.1 | **G1** |
| 24 | **Identity Binding** | `email_triage` linker | ### **PRESENT_AND_COMPATIBLE** *(in spirit)* | M6 + provenance + Conflict | `AC-SAFE-016`, `AC-DOM-013` | U7.4 | U7.1 | **G1** *(+G4 safety)* |
| 25 | **Field-level authority** | none | **ABSENT** | the authority matrix | `AC-DOM-005` | U9.13 | U7 | **G1** |
| 26 | **Conflict / Expectation / Exception / Compensation** | ad-hoc exceptions | **ABSENT** | M7/M8/M9/M10 | the `AC-MACH-7*`/`8*`/`9*`/`10*` series (`AC-MACH-701`, `801`, `901`, `1001`…) | U8.4 | U6 | **G1** |
| 27 | **Domain entities (40)** | ~load/invoice/payable partial | **PARTIAL** | 40 distinct, no `Load` collapse | `AC-DOM-*` | U9.1–U9.11 | U7 | **G1** |
| 28 | **Workflow projections** | script loops | **PARTIAL** | 11 loops, atomic handoffs | `AC-WF*`, `AC-FC-016` | P10+ | U9 | **G5** |
| 29 | **Ownership** | none | ### **ABSENT** | one accountable human, always | ### **`AC-SAFE-028`** | U6.1 | U6 | **G4** |
| 30 | **Audit reconstruction** | audit rows | **PARTIAL** | 18-field explainability, beliefs-of-that-day | `AC-AUD-*` | U5.6 | U5.3 | **G9** |
| 31 | **Release gates** | none | **ABSENT** | G0–G10 | `release-gates.md` | U0.1 | — | **G0** |
| 32 | `CommandIntent` (92 hits) | named for a deleted entity | ### **DEPRECATED** | Proposal / Effect Request | ### **none — a rename has no acceptance case** *(corrected: an earlier draft cited `AC-TRACE-000`, which asserts a bijection over the FROZEN SPEC CORPUS and says NOTHING about implementation symbols — a mis-citation)*. Oracle: ### **diff-shape review, behavior-free** | U8.6 | U8.1 | **G0** |
| 33 | `lane` (310 hits) | ### **overloads action class, workflow AND policy scope** | ### **DEPRECATED** *(as Action Class)* | `action_class` ∪ `workflow_id` ∪ policy scope | ### **none — a rename has no acceptance case** (as row 32). Oracle: ### **diff-shape review, behavior-free** | U8.5 | U8.1 | ### **n/a — lands in P8** |
| 34 | `orient_tms` imports the actuator | read-only by convention | ### **PRESENT_BUT_UNSAFE** | structurally read-only | `AC-ADPT-002` | U4.7 | U3 | **G3** |

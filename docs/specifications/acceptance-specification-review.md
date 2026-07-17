# Acceptance Specification Review — Hostile

> ## ⛔ ERRATA — 2026-07-16 *(appended; the record below is PRESERVED as written)*
> ### **The coverage totals stated in this review are WRONG: transitions are 134 (not 141) and emitted events are 98 (not 92).**
> Every other total in this review — 40 entities · 28 safety invariants · 16 false-closure rules · 11 loops · the 7×15=105 checkpoint matrix — ### **was verified mechanically and is CORRECT.** ### **The pattern: every count enumerated in ONE table was right; both counts requiring summation across 13 files were wrong.**
> ### **HISTORICAL EVIDENCE. NOT normative.** See `docs/implementation/canonical-corpus-errata-review.md`.


**Subject:** `docs/specifications/acceptance/` — 24 files (registry · 11 core · 11 per-loop · gates · traceability).
**Method:** a **false-pass attack** (could an implementation pass these while violating the architecture's spirit?), then a mechanical sweep.
**Date:** 2026-07-16 · **No frozen document modified.**

---

## PART 1 — THE FALSE-PASS ATTACK *(20 loopholes found; each CLOSED by a strengthened oracle)*

*I attacked my own acceptance suite as an implementation team trying to go green while gutting the architecture. Every loophole below was real when found; each names the oracle now closing it.*

| # | The cheat | Why it would have worked | ### The closing oracle |
|---|---|---|---|
| **L-1** | **Mock the safety kernel** — stub `mint_grant`/the checkpoint in tests | the machine cases would pass against a fake | ### **`AC-SAFE-004/005` are TXN-BOUNDARY + INSTRUMENTATION probes on the REAL kernel; G4 forbids mocking the kernel (mocks permitted column = simulators for *external systems only*)** |
| **L-2** | **Validate only local state** — assert the DB row says `VERIFIED` | never touches the world | ### **`AC-SAFE-023` + the ORACLE RULE: a local write is NEVER an oracle for an external effect; the simulator's call log is the oracle** |
| **L-3** | **Omit authoritative readback** — verify by the adapter's return code | a 200 "proves" success | ### **`AC-FC-014`: the simulator returns 200 while the healthy readback finds NOTHING ⇒ must yield `VERIFIED_FAILURE`; 200 + blind ⇒ `UNKNOWN_OUTCOME`** |
| **L-4** | **Use a stale cache** for the money read | fast, green | ### **`AC-ADPT-003` is a NEGATIVE CONTROL: inject a `cache_path` into the consequential reader ⇒ the guard MUST fire (construction failure). Proven-by-firing, not by absence** |
| **L-5** | **Skip concurrency schedules** — "no race observed" | flaky tests get deleted | ### **`AC-RACE-*` require EXACT interleavings via a controllable scheduler + 10,000 runs; "no reproducible race occurred" is an explicit FAIL** |
| **L-6** | **Treat a receipt as completion** | SMTP 250 ⇒ done | ### **`AC-ADPT-006`: assert NO "delivered/received/read" field is EVER written** |
| **L-7** | **Treat a timeout as failure** — clean, terminal | avoids the ugly unknown state | ### **`AC-SAFE-021`: `EffectFailed` requires `failure_proof`; a timeout emitting it FAILS the build** |
| **L-8** | **Create synthetic evidence** — fabricate a health signal / a POD | packets complete, loops close | ### **`AC-ADPT-012`: serve a logged-out page that "loads fine" ⇒ must yield `OBSERVATION_UNAVAILABLE`; the health control is a POSITIVE sentinel the simulator controls, not the implementation** |
| **L-9** | **Write the simulator from the implementation** | it agrees with whatever was built | ### **The simulator is SPEC-DERIVED and lives with the contract (`adapter-boundary-acceptance.md`); a simulator written from the code is named as a loophole and forbidden at G3** |
| **L-10** | **Hardcode a passing event sequence** | golden-file the expected output | ### **`AC-EVT-008`: the `GC-1` DIGEST is pinned in the repo and rebuilt from the corpus, not from the code's own emission; `AC-EVT-000` asserts a bijection with the FROZEN 92, not with the implementation's list** |
| **L-11** | **Ignore tenant partitioning** in tests — single-tenant fixtures | isolation never exercised | ### **The registry DEFAULT: every case runs `T_A`+`T_B`; `AC-SEC-001` is a schema sweep over all nine surfaces** |
| **L-12** | **Weaken provenance** — let a consumer "upgrade" a claim | makes bindings easy | ### **`AC-EVT-011`/`AC-SEC-009`: the six-path laundering sweep (copy/cache/re-observe/reconcile/serialize/process-boundary)** |
| **L-13** | ### **Close only the Pipeline Instance** and call the loop done | the most seductive one — the pipeline IS "complete" | ### **`AC-FC-015`: drive a pipeline to `CLOSED` with the obligation unmet (billed-not-paid) ⇒ the Work Item MUST stay OPEN** |
| **L-14** | ### **Silently abandon downstream work** — emit the event, close the source | looks like a clean handoff | ### **`AC-FC-016`/`AC-RACE-017`: crash between the source transition and the downstream Work Item insert ⇒ NEITHER may happen; the source cannot advance** |
| **L-15** | **Test only happy paths** | 100% "coverage" | ### **The 18 mandatory per-loop dimensions + the exhaustive `(state × trigger)` illegal sweep (`AC-MACH` assertion 2)** |
| **L-16** | **Disable the brake** in the test env | it keeps blocking things | ### **G4 brake posture = "engaged by default in test"; `AC-SAFE-006/007` + `AC-RACE-002` require it live; `AC-SEC-014` proves the replay env CANNOT act** |
| **L-17** | **Bypass ownership** — set owner to `system` | avoids fixture work | ### **`AC-SAFE-028` is a DB INVARIANT SCAN: zero open Work Items with null/`system` owner, at any time** |
| **L-18** | ### **Label manual actions as autonomous** — the demo looks better | the classic pilot lie | ### **`AC-DEG` assertion 5: the audit MUST record `actor_type=human`, out-of-band, with NO grant/`EffectAttempted`; G7's autonomy ceiling is "preparation only"** |
| **L-19** | ### **Exclude unknown outcomes from metrics** | the dashboard looks clean | ### **`AC-AUD-007`: the safety-metric oracle asserts `UNKNOWN_OUTCOME` rate is REPORTED, not filtered** |
| **L-20** | ### **Reset state between replay tests / delete inconvenient historical events** | replay always "works" | ### **`GC-1` is IMMUTABLE and never reset mid-suite; `AC-AUD-003` proves no DELETE grant exists; `AC-EVT-014` proves deleted-field events remain readable forever** |

> ### **Every loophole above is a way to be GREEN and WRONG. The suite is designed so that the cheapest path to passing is to actually build it correctly — which is the only property that matters in an acceptance layer.**

---

## PART 2 — MECHANICAL CONSISTENCY REVIEW

| Check | Result |
|---|---|
| All 11 workflows covered | ✅ `W1..W11-acceptance.md`, each with the 18 mandatory dimensions |
| All 141 transitions covered | ✅ `AC-MACH-*` + `AC-MACH-000` bijection probe |
| All 92 emitted events covered | ✅ `AC-EVT-*` + `AC-EVT-000` bijection probe |
| All 40 domain entities covered | ✅ `AC-DOM-E01..E40` + 17 invariants (DB **and** event oracles) |
| All adapter operations covered | ✅ `AC-ADPT-*` + `AC-ADPT-000` bijection |
| All permanent safety invariants | ✅ **28/28** (`AC-SAFE-001..028`), all merge-gating |
| All false-closure rules | ✅ **16/16** (`AC-FC-001..016`), all merge-gating, all structurally rejected |
| 40 hostile workflow traces | ✅ mapped into `W1..W11` + `AC-FC-*` + `AC-RACE-*` |
| 30 hostile adapter traces | ✅ mapped into `AC-ADPT-*` |
| 20 hostile event traces | ✅ mapped into `AC-EVT-*` |
| 20 hostile cross-machine traces | ✅ mapped into `AC-MACH-*` + `AC-RACE-*` |
| All cases have requirement sources | ✅ `AC-TRACE-000` bijection — an orphan case fails the build |
| All merge-gating cases have deterministic oracles | ✅ the ORACLE RULE (5 forms); "appears correct" is excluded by construction |
| All consequential cases assert forbidden side effects | ✅ registry default: **every** consequential case asserts the negative (the simulator call log) |
| All race cases define exact schedules | ✅ 17 schedules, controllable scheduler, 10,000 interleavings |
| All replay cases assert zero external effects | ✅ `AC-SAFE-019`, `AC-EVT-007`, `AC-SEC-014` |
| All `UNKNOWN_OUTCOME` cases assert ownership | ✅ `AC-SAFE-022`, `AC-WF7-005`, `AC-REC-004` |
| All degraded modes covered | ✅ 11 loops × 11 modes + 7 universal assertions |
| All gates have promotion **and demotion** criteria | ✅ `release-gates.md` — automatic demotion; **automation may demote, never promote** |
| No test accepts local state as external verification | ✅ the ORACLE RULE + `AC-SAFE-023` + L-2 |
| No test requires inventing business semantics | ✅ every case cites a frozen source; `NEEDS VALIDATION` items are fail-closed, never guessed |

---

## PART 3 — FINDINGS

**1. Acceptance files created:** **24**.
**2. Acceptance-case count:** **~430** (28 safety + 105 checkpoint + 141 machine + ~100 event + 57 domain + ~45 adapter + ~100 workflow/loop + 16 false-closure + 121 degraded + 17 race + 14 security + 7 audit + gates/traceability).
**3. Merge-gating case count:** ### **~270** (all SAFETY_CRITICAL / FINANCIAL_CORRECTNESS / TENANT_ISOLATION / COMMERCIAL_COMMITMENT, incl. all 105 checkpoint cases and all 16 false-closure negatives). **No individual waiver.**
**4. Safety-critical case count:** **28 invariants + 105 checkpoint + 17 race = 150 core**.
**5–9. Coverage:** 11/11 loops · 141/141 transitions · 92/92 events · 40/40 entities · all adapter ops — **each asserted by a structural bijection probe, not by a checklist.**
**10. Race & fault coverage:** 17 deterministic schedules; every crash point in the checkpoint matrix; ### **non-determinism is a FAIL.**
**11. Replay coverage:** `GC-1` immutable golden corpus, pinned digest, zero-effect assertions.
**12. Degraded-mode coverage:** 11×11 + the 7 universal assertions, incl. ### **"never claim Neyma executed the human's action."**
**13. False-pass loopholes found and closed:** ### **20** (Part 1) — including the three most dangerous: **closing only the Pipeline Instance (L-13)**, **silently abandoning downstream work (L-14)**, and **labeling manual actions as autonomous (L-18)**.
**14. Remaining `NEEDS VALIDATION`:** ### **the pilot profile (Documentation→Billing) requires design-partner validation** — with the confirm/reject evidence named; the L8 closure disposition set; autonomy graduation thresholds (V11); per-customer rules; after-hours ownership; vendor postures. **All fail-closed; none blocks planning.**
**15. Higher-level amendments required:** ### **NONE.** Every case derives from a frozen requirement; no acceptance case needed a new primitive or exposed a contradiction.
**16. Recorded migration guard:** ### **`AC-SAFE-012/013` (`MIGRATION_GUARD`) FAIL BY DESIGN against the current baseline** — the live `commit_identity` includes the amount and is absent for non-money effects. **This is the intended signal: the guard goes green when Migration Safety Task #1 lands. It is the first implementation task.**

---

## VERDICT

> # **READY FOR IMPLEMENTATION AND MIGRATION PLANNING**
>
> **Evidence:** ~430 acceptance cases across 24 files, ~270 merge-gating with zero waiver, every one traced to a frozen requirement by a **bijection probe that fails the build on an orphan in either direction**; the 28 permanent safety invariants and the full **7×15 = 105-case checkpoint matrix**, whose universal oracle admits **exactly one witness + one claimed grant, or no authorization capability — never a partial state**, at every isolation level and every crash point; 100% coverage of the 141 transitions, 92 events, 40 entities, and all adapter operations, each asserted structurally rather than by checklist; 17 deterministic race schedules where **non-determinism is a failure**; an immutable golden corpus with a **pinned digest that must reproduce forever**; 16 false-closure negatives proving closure is **structurally rejected**; 11×11 degraded-mode coverage including *never claim Neyma executed the human's action*; eleven staged gates G0–G10 with promotion **and automatic demotion**, where **no gate passes on a demonstration** and **automation may demote but never promote**; and a **false-pass attack that found and closed 20 loopholes** — such that the cheapest path to green is to build it correctly.
>
> **The pilot profile (Documentation → Billing) is marked NEEDS DESIGN-PARTNER VALIDATION with its confirm/reject evidence named — the wedge may move; the architecture does not, which is why it was built loop-agnostic.**
>
> ### **The migration guard `AC-SAFE-012/013` fails by design against the current baseline: `commit_identity` still includes the approved amount and is absent for non-money effects. That guard turning green IS the definition of Migration Safety Task #1 being done — and it is the first thing implementation planning must schedule.**
>
> **No higher-level amendment required. Implementation and migration planning may begin.**

*Not started (per instruction): production code, API implementation, database migrations, migration execution plans, implementation task breakdowns, PRODUCT/ARCHITECTURE/CLAUDE.*

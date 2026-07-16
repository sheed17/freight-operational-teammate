# Hostile Planning Review

> ### **THE REVIEW QUESTION:** ### **"Can a competent, well-intentioned engineer follow this plan EXACTLY, to the letter, and still produce an unsafe system?"**
> Not "is the plan good." Not "did we cover the topics." ### **A plan is not a set of intentions — it is a set of constraints on a future engineer who will be tired, under pressure, and reading only the row in front of them. Every place this plan relies on that person's judgment rather than a mechanism is a defect in the PLAN, not in them.**

## PART 1 — THE EIGHTEEN PLANNING LOOPHOLES

| # | The loophole *(followed literally, produces an unsafe system)* | Closed? | ### By what |
|---|---|---|---|
| **PL-1** | ### **"Phase 1 is a big refactor — do it after the pilot."** | ### **YES** | ### **U1.2/U1.3 are the FIRST implementation units; the dependency spine puts every other unit behind them. There is no unit that can start "instead of" Phase 1.** |
| **PL-2** | Fix the key derivation but leave the 14 consumer sites reading the old shape | **YES** | U1.2 names all 14 sites + `workflow.py:543,582`; ### **`AC-SAFE-012`'s oracle includes a grep proving NO amount reaches ANY key derivation** |
| **PL-3** | ### **Add the new key alongside the old one "for safety during transition"** | ### **YES** | ### **principle 2 + R-02: ONE key namespace. Two namespaces = two exclusion domains = the double-commit the plan exists to prevent. Coexistence is permitted ONLY through the shared unique index.** |
| **PL-4** | ### **Ship the checkpoint with a `skip_checkpoint=True` test flag** | ### **YES** | ### **`CheckpointPassed` has NO public constructor — the bypass FAILS TO COMPILE. No flag can undo a type. `AC-SAFE-002` is a negative control that must fail to build.** |
| **PL-5** | Do the checkpoint's 7 steps, but fetch freshness asynchronously first | **YES** | ### **U3.2: one transaction, no async work before the CAS; the 105 `AC-CKPT-*` + 10k interleavings** |
| **PL-6** | ### **Enable the CI import gate at P2 and wrap the adapters to satisfy it** | ### **YES** | ### **the roadmap's stated deviation: P4 MUST follow P3, because "a wrapper that logs the bypass is not containment."** |
| **PL-7** | ### **Convert EP-6/7/9/10 to pipeline clients instead of deleting them** | ### **YES** | ### **cutover C-4 is PHYSICAL DELETION. "Convert" leaves a terminal-invocable write path whose only exclusion is that nobody should run it — which is not a mechanism.** |
| **PL-8** | Leave `orient_tms`'s actuator import — "it's read-only, it never calls it" | ### **YES** | ### **U4.7 removes the import. Read-only BY CONVENTION, actuator-capable BY IMPORT. The recon found this; reputation did not.** |
| **PL-9** | Backfill historical ops as `VERIFIED` because "they probably worked" | ### **YES** | ### **the data plan's rule: the backfill HAS NO CODE PATH that writes VERIFIED. Ambiguous ⇒ `UNKNOWN_OUTCOME` + a named owner + the key held.** |
| **PL-10** | ### **Sweep the resulting `UNKNOWN_OUTCOME` backlog because it's noisy** | ### **YES** | ### **the operating discipline: never auto-resolved, never aged out, never swept. Each holds its key and its owner until an authoritative observation reconciles it.** |
| **PL-11** | ### **Rename `lane`→`action_class` early "to make the code read canonically"** | ### **YES** | ### **U8.5 is LAST. Renaming 310 sites into a concept that does not exist is one guess made 310 times, and produces code that READS canonical and BEHAVES legacy — the artifact that defeats every reviewer.** |
| **PL-12** | Split `workflow_runs`, then "simplify" it back to one row | **YES** | ### **MERGE_FORBIDDEN + `AC-FC-015`: a completed pipeline with an unmet obligation must leave the Work Item OPEN** |
| **PL-13** | Write the contract simulators from the implementation | **YES** | ### **L-9 / R-11: the simulator lives with the SPEC. A simulator built from the code is a test that agrees with the bug.** |
| **PL-14** | ### **Qualify G4 against simulators, then go live** | ### **YES** | ### **G8 requires `AC-SAFE-001..028` RE-RUN LIVE. Passing against a simulator is evidence about the simulator.** |
| **PL-15** | ### **Ship the first live write at P10/P11 because "the slice works"** | ### **YES** | ### **G4 is the wall and it qualifies at P8; G6=zero effects, G7=the HUMAN executes. P12 is the first write, and it sits behind the whole spine.** |
| **PL-16** | Roll back a bad live write by turning the flag off | ### **YES** | ### **R-20 + the rollback table: a flag NEVER un-writes the world. Reversal is a NEW, separately-gated compensating effect with its OWN commit key — and `AC-REC-001` FORBIDS compensating an `UNKNOWN_OUTCOME`.** |
| **PL-17** | Let automation widen autonomy once metrics look good | **YES** | ### **the one-way ratchet / ER-12: automation may narrow and may demote; ONLY the Policy Owner may broaden, in writing, per class, time-boxed.** |
| **PL-18** | ### **Treat "the plan is written" as "the risk is handled"** | ### **NO — AND IT CANNOT BE** | ### **R-07 is OPEN: the 6 production-reachable live-write paths are reachable RIGHT NOW and stay reachable until P4 DELETES them. The honest mitigation is operator discipline, which is not a mechanism. Planning does not close R-07. Only reaching P4 closes it. This review refuses to mark it green.** |

### Verdict on Part 1: ### **17 of 18 closed structurally. PL-18 is OPEN and un-closable by planning — it is discharged only by executing Phases 0–4.**

---

## PART 2 — MECHANICAL CONSISTENCY REVIEW
> ### **This section reports what the machine found in MY OWN planning output — including two errors I would not have caught by reading, and one case where my checker itself lied to me.**

| # | Finding | Severity | Status |
|---|---|---|---|
| ### **M-1** | ### **`AC-SEC-000` DID NOT EXIST.** U0.3's completion oracle pointed at an invented acceptance case. ### **An oracle naming a test that does not exist is not an oracle — it is a unit that can never be proven done, and would have been marked done anyway.** | ### **HIGH** | ### **FIXED → `AC-CKPT-6-missing`** (the real frozen case) |
| **M-2** | `AC-MACH-2xx/3xx/5xx/7xx` were glob shorthand, not real IDs (the frozen scheme is `AC-MACH-201`, `301`, …). Under `AC-TRACE-000`'s bijection they are **orphans that fail the build**. | MEDIUM | FIXED → real series anchors |
| ### **M-3** | ### **G4 WAS SCOPED TO "P2+P3+P4". THE FROZEN GATE REQUIRES `AC-SAFE-001..028` — which reaches to P5 (outbox), P6 (ownership), P7 (provenance), P8 (Exception/Compensation). G4 ACTUALLY QUALIFIES AT P8.** | ### **CRITICAL** | ### **FIXED — rescoped P2→P8** |
| ### **M-4** | ### **The gap matrix's Gate column had NO DEFINED MEANING.** 14 of 34 rows were inconsistent under any reading — and were unadjudicable, because there was no rule to adjudicate against. | ### **HIGH** | ### **FIXED — defined as "the earliest gate that cannot pass without this component" and RECOMPUTED mechanically (20 rows rewritten, 0 contradictions remain)** |
| **M-5** | ### **Two unit-ID namespaces** — the gap matrix said `T2.1`, the PR sequence said `U2.1`, for the same work. A cross-reference between two of my own documents did not resolve. | HIGH | FIXED — unified on `U*` |
| **M-6** | Rows 14 (`UNKNOWN_OUTCOME`→P6) and 21 (Provenance→P7) named a G4 gate with a task in a LATER phase — ### **a direct violation of principle 13 (no phase may depend on future work for a CURRENT safety guarantee)** | HIGH | FIXED (row 14 → U3.3; row 21 clarified: P7 is *inside* the G4 scope) |
| **M-7** | Rows 32/33 cited `AC-TRACE-000` as a code rename's oracle. It asserts a bijection over the **spec corpus** and says nothing about implementation symbols. | MEDIUM | FIXED → renames have **no** acceptance case; the oracle is a diff-shape review |
| **M-8** | The EP summary read "6 … (EP-1,2,3,6,7,9,10)" — a count and a list that disagreed on their face. | LOW | FIXED — EP-2 is the supervisor, counted with them |
| ### **M-9** | ### **MY OWN CONTRADICTION-CHECKER RETURNED "0 CONTRADICTIONS" WHILE PARSING ZERO ROWS.** A wrong column index produced a clean bill of health from a check that examined nothing. | ### **HIGH (methodological)** | ### **FIXED — the checker now prints its row count; it found 14. ### A green check that cannot show its work is not evidence — which is exactly the P17 SCAR the frozen gates already warn about, reproduced by me, in the act of checking for it.** |

**Mechanical assertions now passing:** ### **all 46 acceptance IDs cited across the plan resolve to the frozen registry (0 orphans)** · 0 gate-column contradictions across 34 rows · 0 residual `T*` references · every phase in the roadmap appears in the registry and the PR sequence · every EP is classified · every risk has an owner.

**What remains UNVERIFIABLE by any mechanical check:** ### **whether W6→W8 is the right wedge (R-16 — only the design partner can answer)** and ### **whether the operator honors the one-writer discipline before P4 (R-07 — nothing automated can observe this; that IS the risk).**

---

## PART 3 — THE REPORT

1. **Recon method:** mechanical — file/LOC counts, AST-level import inspection, schema reading, and grep over the real tree at `6057dfe`; ### **prior inventories were used only to be contradicted.** They were, three times (M-1/M-3 aside): the 6-of-8 non-tenant-first tables, `orient_tms`'s actuator import, and the 13 import sites.
2. **Current state:** 208 py files · 73 src · 50 scripts · 78 tests · ~20.7k LOC · 8 tables · ### **6 production-reachable live-write paths.**
3. **The live defect:** confirmed at `operation_router.py:335` — ### **(A) the amount IS in the identity, (B) non-money effects get NO identity, (C) the claims table is not tenant-first.** `eval/tests/test_lane_graduation.py:206` ### **encodes the defect as expected behavior.**
4. **Gap:** 34 components — ### **6 `PRESENT_BUT_UNSAFE`**, 9 `ABSENT`, 12 `PARTIAL`, 4 `PRESENT_BUT_NONCANONICAL`, 1 compatible, 2 `DEPRECATED`.
5. **Safety Task #1:** Phase 1, units U1.1–U1.6, ### **forward-only (no rollback — rolling it back would restore the double-pay defect)**; collisions in the backfill are ### **evidence of a historical double-commit: never merged, never picked.**
6. **Ledger:** one table, 8 states, tenant-first, ### **two partial unique indexes — U2.3 is the load-bearing unit of the entire plan, because it is the only mechanism that makes coexistence safe.**
7. **Checkpoint:** 7 steps, one transaction, CAS last, ### **`CheckpointPassed` unconstructable — capability by construction.**
8. **Containment:** 13 import sites; ### **4 scripts DELETED (C-4), 1 import removed, the rest converted; the CI gate lands only after the pipeline exists.**
9. **Order:** ### **no deviation from the frozen safety order is required.** Two clarifications: P2 is schema-wide (6/8 tables), and P4 must follow P3.
10. **The wedge:** W6→W8, ### **NEEDS DESIGN-PARTNER VALIDATION.** ### **If rejected, ONLY P10 changes — Phases 0–9 are loop-agnostic by construction. The wedge decision may be deferred to P9 and MUST NOT delay the kernel.**
11. **Units:** U0.\*–U9.\* + P10–P14, ### **no calendar estimates**; each names its files, its acceptance cases, its flag, its rollback, and a completion oracle.
12. **Red-to-green:** `AC-SAFE-012/013` are ### **RED BY DESIGN today and are the plan's first green.** ### **No reachable unsafe behavior is excused by a future phase — R-07 is recorded as open rather than explained away.**
13. **Gates:** ### **G4 is the wall and qualifies at P8, not P4 (finding M-3).** ### **P12 — the first live external write — sits behind the entire spine and a LIVE re-run of G4.**
14. **Risks:** R-01…R-20. ### **The standing one is R-07** (the 6 live paths, reachable now, mitigated only by operator discipline until P4). ### **The unanswerable one is R-16** (the wedge).

### What I would tell you if you asked me the uncomfortable question
> ### **The most dangerous thing in this session was not the defect in the code — it was finding M-3 in my own plan. I scoped the safety wall three phases too early. P12 is gated on G4; had that error survived, an engineer could have qualified "G4" at P4, honestly believed the wall was cleared, and shipped a live money write with no provenance rules, no accountable owner, and no compensation semantics — while following this plan exactly.** ### **That is the precise failure mode this review exists to catch, and the plan produced it. It was caught by a machine check, not by re-reading — and my first version of that check reported "0 contradictions" while examining nothing (M-9).**

---

# VERDICT

## ### **READY FOR IMPLEMENTATION — BEGIN AT PHASE 0.**

**Conditions carried into implementation, not resolved by it:**
- ### **R-07 is OPEN.** The 6 live-write paths are reachable **today**. Until P4 deletes them, the only thing standing between this repo and an ungated live write is ### **the owner's personal discipline. This is stated as a fact, not a mitigation.**
- ### **P10+ is BLOCKED on design-partner validation of the W6→W8 wedge.** ### **Phases 0–9 are not blocked, and must not wait for it.**
- ### **Phase 1 is forward-only.** Once the amount leaves the commit key, there is no supported path back.

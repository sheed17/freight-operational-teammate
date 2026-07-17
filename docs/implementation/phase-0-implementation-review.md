# Phase-0 Implementation Review — Baseline & Migration Guards

> ### **Phase 0 does not make the current write paths safe. It makes their unsafe state explicit, measurable, and unable to regress silently.**
> ### **Nothing in this phase touched production code, database schemas, migrations, or symbol names. Every tracked file in `src/` and `scripts/` is byte-identical to `9f20b25`.**

---

## ⛔ SCOPE CONFLICT — REPORTED, NOT SILENTLY ABSORBED

The frozen PR sequence defines Phase 0 as **four** units (U0.1–U0.4). The Phase-0 brief requires **ten** protection areas. That is an **expansion**, not a contradiction — every added area is baseline-and-guard work, consistent with the phase's stated purpose, and adds no production behaviour. I implemented them as **U0.5–U0.13** and report the delta rather than quietly rewriting the frozen plan.

| Unit | Area | In frozen `pr-sequence.md`? |
|---|---|---|
| U0.1 | acceptance harness + registry loader | ### **yes** |
| U0.2 | ### **the two MIGRATION_GUARD cases** | ### **yes** |
| ### **U0.3** | ### **the null-gate startup check** | ### **yes — but NOT ACHIEVABLE (finding P0-F1)** |
| U0.4 | `AC-SEC-001` tenant-first probe | ### **yes** |
| **U0.5** | the evaluation contract (anti-false-green) | no — added |
| **U0.6** | canonical identifier resolution | no — added |
| **U0.7** | planning-graph consistency | no — added |
| **U0.8** | acceptance bijection probes | no — added |
| **U0.9** | direct adapter import guard | no — added |
| **U0.10** | live-effect entry-point guard | no — added |
| **U0.11** | deprecated-semantics baseline | no — added |
| **U0.12** | the baseline manifest + its integrity | no — added |
| **U0.13** | ### **guard integrity (the guards guard themselves)** | no — added |

> ### **`pr-sequence.md` now under-describes Phase 0. It is frozen; I did not edit it. Amending it is an owner decision.**

### ⛔ P0-F1 — U0.3 IS NOT ACHIEVABLE AT PHASE 0
`AC-CKPT-6-missing` asserts that an action class with a **null policy gate** causes the system to **fail to start**. That needs typed policy and action classes — which land at **P8 (U8.1)**. Today the repo has `lane_graduation`, whose `is_autonomous()` returns a **fail-safe default**.

> ### **A default and a NOT-NULL gate are not the same thing, and the difference is the entire point.** A default says *"nobody decided, so we picked the safe answer."* The canonical rule says *"nobody decided, so REFUSE TO START."* The first is safe today and silently wrong tomorrow.

Implementing it now would enumerate **zero gates and report green** — the exact M-9 false-green, and the same error as **PL-6**: a gate enabled before the thing it gates exists. ### **The roadmap already names the rule: a gate with nothing behind it is theatre.**
**Resolution:** `AC-CKPT-6-missing` = `NOT_YET_EXECUTABLE`, adjudicated in the manifest, green at P8. [`test_phase0_null_gate.py`](../../eval/tests/test_phase0_null_gate.py) **proves the population is empty** rather than asserting it. ### **U0.3 should move to P8. That is an owner decision.**

---

## 1. Implementation units completed
**U0.1, U0.2, U0.4** (frozen) + **U0.5–U0.13** (added). ### **U0.3 deferred to P8 — see P0-F1.**

## 2–3. Files added / modified
**Added (24):** `eval/phase0/` (11 modules, 1,003 lines) · `eval/tests/test_phase0_*.py` (12 files, 1,147 lines) · `docs/implementation/phase-0-baseline-manifest.yaml` (386 lines).
### **Modified: NONE.** No production file, schema, migration, or symbol was touched.

## 4. Baseline manifest contents
`docs/implementation/phase-0-baseline-manifest.yaml` — 5 `REQUIRED_INVARIANT` · 6 `EXPECTED_CURRENT_DEFECT` · 7 `EXPECTED_NONCANONICAL_SCHEMA` tables · 10 `EXPECTED_LEGACY_PATH` + 2 adjudicated references · 6 `EXPECTED_DEPRECATED_TERM` · 4 `EXPECTED_ACCEPTANCE_FAILURE` · 8 `PROHIBITED_NEW_REGRESSION` · a 31-edge shrinking-only adapter allowlist.
### **Every allowance carries a reason, a risk id, a removal phase, a deletion condition, and an accountable unit — enforced mechanically, not by review etiquette.** No indefinite, wildcard, or "legacy"-justified allowance survives ([`test_phase0_baseline_manifest.py`](../../eval/tests/test_phase0_baseline_manifest.py)).

## 5. Repository facts recomputed — ### **THREE CONTRADICT THE FROZEN PLAN**
| Fact | Frozen plan / brief | ### Recomputed | Verdict |
|---|---|---|---|
| tables | 8 | **8** | ✔ |
| ### **tables NOT tenant-first** | ### **6 of 8** | ### **7 of 8** | ### **⛔ DEF-6** |
| tests passing | 677 | **677** | ✔ |
| ### **direct adapter import sites** | ### **13** | ### **31 edges / 18 modules** | ### **⛔ P0-F3 (no stated rule)** |
| effect-capable entry points | 13 EPs listed | ### **10 by import + 1 by spawn; 1 unlisted** | ### **⛔ P0-F4** |
| `lane` / `CommandIntent` / `MockTmsWriteLedger` | 310 / 92 / 27 | **310 / 92 / 27** | ✔ |
| `workflow_runs` / `commit_identity` | 22 / 16 | **20 / 14** | minor delta, recorded |
| ### **machine transitions** | ### **141** | ### **134** | ### **⛔ DEF-4** |
| ### **emitted events** | ### **92** | ### **98** | ### **⛔ DEF-5** |
| domain entities / adapters / loops / invariants / FC rules | 40 / 18 / 11 / 28 / 16 | **40 / 18 / 11 / 28 / 16** | ✔ |

### ⛔ DEF-4 / DEF-5 — THE FROZEN CORPUS'S HEADLINE COVERAGE NUMBERS ARE WRONG
The 13 machine files enumerate **134** transitions. ### **The acceptance spec's OWN per-machine table lists all 13 counts correctly — and they sum to 134. Its `Total` row says 141.** That 141 is repeated in **six** places, including **G1's exit criterion ("141/141")** and **`AC-MACH-000` ("a bijection with the 141 spec rows")**.
Likewise the canonical event list enumerates **98** emitted events (F1–F13) against a declared **92**. F14's 13 security events are correct; F15 is a lens and declares nothing.

> ### **This is not cosmetic. A correct implementation of all 134 spec transitions would FAIL AC-MACH-000 forever, and G1 would be unmeetable. The two fixes a tired engineer reaches for are both corrupting: invent 7 transitions to reach 141, or weaken the bijection to an inequality — which destroys the only mechanism that proves the machines match the spec.**
> ### **The pattern is clean and worth naming: every count enumerated in ONE table is exactly right. BOTH counts that required summing across 13 files are wrong. That is a human error a machine catches instantly — which is the entire thesis of Phase 0.**
**Blocks G1 (P6) and G2 (P5). Needs an owner decision: amend the corpus, or specify the missing rows.**

### ⛔ DEF-6 — "6 of 8" IS WRONG; IT IS 7 OF 8
Exactly one table (`autonomous_run_counters`) is tenant-first. ### **The frozen plan says "6 of 8" in seven places, and the Phase-0 brief repeats it as a verified fact.**
> ### **U2.1 is scoped to "tenant-first keys across the 6 offending tables." Executed literally, Phase 2 migrates six, leaves one non-tenant-first, and AC-SEC-001 stays red with the phase marked done.** A miscount that hides a table from its own migration is not a typo.

## 6. Live effect entry points
**10 effect-capable by import**, **1 by spawn** (`run_teammate.py` → EP-1/EP-3 — ### **invisible to an import-only guard**), **1 adjudicated DOCUMENTS** (`run_sunday_readiness.py` prints the command in a runbook string; it launches nothing).
### **P0-F4:** `scripts/read_tms_browser_use.py` is effect-capable by import and **absent from the frozen EP-1…EP-13 inventory**. Recorded as `UNLISTED` / `CLASSIFY`.
### **R-07 status is unchanged: OPEN, NOT CONTAINED.** `containment_mechanism: NONE`.

## 7. Direct adapter imports
### **P0-F3:** the frozen "13" is **not reproducible** — several defensible rules give 13, 16, 18 or 31. ### **An unstated counting rule is the M-4 pattern: a number nobody can adjudicate.** I stated the rule (an AST import EDGE where the importer is not the adapter itself), recomputed **31 edges / 18 modules**, and allowlisted all 31 — shrinking-only.
The guard is **detection only**. ### **It is NOT the U4.9 containment gate, which lands at P4 after the pipeline client exists; enabling it now would force wrappers, and a wrapper that logs the bypass is not containment (PL-6).** Allowlisting every current site means it cannot induce that behaviour.
`orient_tms.py → cdp_actuator` (EP-8) is recorded: ### **read-only by convention, actuator-capable by import.**

## 8–9. Tenant posture / deprecated semantics
7 of 8 tables non-tenant-first, each named. ### **`operation_commit_claims` HAS a tenant column and is still unsafe — its PK is `commit_key` alone, so the uniqueness domain is global. A tenant column is not tenant isolation**, and the probe has a negative control proving it is not fooled.
Six deprecated terms recorded at exact counts, ratcheted downward-only. Nothing renamed.

## 10–12. Identifier resolution / planning graph / bijections
All cited acceptance ids resolve. ### **`AC-SEC-000` may now appear ONLY inside the review, as the finding it was.** Series-globs and the **scheme-derived** checkpoint ids resolve correctly — see P0-F5 below. Legacy `T*` unit namespace is gone. G4 mechanically resolves **through P8**; the Gate column's definition is enforced; **0 contradictions across 34 rows, with the population asserted (≥25) so the check cannot pass by parsing nothing.**

### P0-F5 — MY OWN M-2 FIX WAS ITSELF NOT LITERALLY RESOLVABLE
`AC-CKPT-6-missing` — the id I substituted for the invented `AC-SEC-000` — **never appears literally in the corpus.** It is *derived* from a declared scheme (`AC-CKPT-<step>-<condition>`, 7 steps × 15 conditions = 105). ### **A resolver that only string-matched would have called a CORRECT citation invented — and the "fix" would have been to replace a right answer with a wrong one.** The resolver now parses the scheme and expands it.

## 13. False-green regression coverage
[`test_phase0_evaluation_contract.py`](../../eval/tests/test_phase0_evaluation_contract.py) **reproduces M-9 exactly**: a wrong column index skips every row, the contradiction count is legitimately `0`, and the assertion `contradictions == []` **passes** — then `require_population()` raises. Every probe reports **sources inspected · candidates · parsed · accepted · rejected · unmatched · duplicates · FINAL EVALUATED COUNT**. ### **A zero-row result is a hard failure unless an empty set is explicitly declared legitimate, with a stated reason, at the call site.**

## 14. Existing defects still open
DEF-1, DEF-2, DEF-3 (P1) · **DEF-4, DEF-5 (owner adjudication, before G1/G2)** · DEF-6 (P2) · **R-07 (P4)**.

## 15. New regressions found
### **NONE in production code.** Eight defects found in the **frozen corpus and in Phase 0's own guards** — DEF-4, DEF-5, DEF-6, P0-F1, P0-F3, P0-F4, P0-F5, and the mutation findings below.

### ⛔ WHAT THE MUTATION HARNESS FOUND IN MY OWN GUARDS
**18 mutations applied to the real tree, every one restored and digest-verified. The first run detected only 9 of 12.**
| Guard hole | Consequence |
|---|---|
| ### **`from freight_recon import cdp_actuator` was INVISIBLE** | ### **The adapter guard read only an `ImportFrom`'s module, so the adapter name landed in the imported SYMBOLS and was never seen. The guard could be bypassed by changing import style — precisely the "effect path hidden behind an alias" case it exists to catch. Three of my most safety-relevant guards were decorative.** |
| ### **A migration guard could be neutered into `@pytest.mark.skip`** | ### **The suite stays green and CI says nothing. A skip is silence — and silence is what let the commit-key defect live this long.** |
| Two manifest sections could drift | DEF-2 could move to P9 while AC-SAFE-013 still claimed P1 |
| The harness's own early `sys.exit` hid 6 mutations | ### **The validation tool lied by omission — the same M-9 shape, in the tool built to catch M-9** |

**All fixed. Final: 18/18 detected**, including a zero-row parser, an alias import, a dynamic `importlib` import, a skipped guard, a falsely-contained R-07, and G4 reduced to P2–P4.
> ### **Three of these guards passed their own tests while being unable to detect the thing they existed to detect. Only mutation proved it. A guard that has never been seen to fail is a decoration.**

## 16. R-07 status — ### **OPEN. NOT CONTAINED.**
> ### **The six production-reachable live-write paths remain physically capable of ungated external effects. Phase 0 added visibility, CI detection, an inventory and a shrinking allowlist — and NONE of that is containment.** The manifest states it in the artifact itself: ### **"discipline, not a mechanism… may never be read as containment."** ### **PL-18 is not closed. Only reaching P4 closes it.** [`test_phase0_baseline_manifest.py`](../../eval/tests/test_phase0_baseline_manifest.py) fails the build if anyone ever writes `CONTAINED` there.

## 17–18. AC-SAFE-012 / AC-SAFE-013 — ### **RED BY DESIGN. RUNNING. NAMED IN CI.**
Both execute against the real `_commit_identity` at `operation_router.py:335` and fail:
- **AC-SAFE-012** — £2,850 and £3,100 produce **different** identities. ### **Two proposals for one logical invoice ⇒ two keys ⇒ two reservations ⇒ TWO INVOICES.**
- **AC-SAFE-013** — a POD filing returns `None`. ### **No key, so single-commitment cannot be enforced or proven.**

They are **`strict` xfails, not skips**: they run, they are named in CI, and ### **they FAIL THE BUILD the day they start passing** — so P1 cannot land quietly. ### **Neither was weakened, marked passed, or fixed.**

## 19. Test-suite result
**Phase-0 guard suite: 76 passed, 4 xfailed** (AC-SAFE-012, AC-SAFE-013, DEF-4, DEF-5 — all named). ### **Full suite: 677 pre-existing tests unchanged and green; 80 added. No pre-existing test was modified, skipped, or weakened.**

## 20. May Phase 1 begin?
| Condition | Status |
|---|---|
| all Phase-0 units complete | ### **U0.1/U0.2/U0.4 + U0.5–U0.13 ✔ — U0.3 deferred (P0-F1)** |
| all Phase-0 guards pass | ✔ 76 passed / 4 named xfails |
| baseline manifest complete | ✔ every allowance justified + owned |
| no unclassified live-effect entry point | ✔ (incl. the unlisted `read_tms_browser_use`) |
| no unclassified direct adapter import | ✔ 31/31 allowlisted, rule stated |
| all planning identifiers resolve | ✔ |
| G4 resolves through Phase 8 | ✔ mechanically enforced |
| no checker can report green on zero records | ✔ + M-9 regression test |
| ordinary suite green | ✔ 677 unchanged |
| **AC-SAFE-012 / AC-SAFE-013 still red** | ### **✔ red, running, named** |
| **R-07 explicitly open** | ### **✔ NOT CONTAINED** |

### Forward-only Phase-1 boundary
> ### **Once the mutable approved amount leaves the Commit Key and non-money Commit Keys become mandatory, rollback may disable capability but may NEVER restore the defective behaviour. Restoring it would re-introduce the double-pay defect. Phase 1 is forward-only. There is no supported path back.**

---

# VERDICT

## ### **READY TO BEGIN IMPLEMENTATION PHASE 1**

**Carried forward, unresolved by Phase 0:**
- ### **R-07 remains OPEN.** Six live-write paths are reachable today. Until P4 deletes them, the only thing between this repo and an ungated live write is ### **your personal discipline — a fact, not a mitigation.**
- ### **THREE OWNER DECISIONS ARE NOW PENDING, and two of them block gates:**
  1. ### **DEF-4 / DEF-5 — the corpus says 141 transitions and 92 events; it enumerates 134 and 98. Blocks G1 and G2. Do NOT let anyone reconcile this by inventing transitions or weakening AC-MACH-000's bijection.**
  2. ### **DEF-6 — "6 of 8 tables" is really 7 of 8. U2.1's scope must be corrected BEFORE Phase 2, or Phase 2 completes with a table left behind.**
  3. **P0-F1 — U0.3 belongs at P8, not Phase 0; `pr-sequence.md` under-describes Phase 0 (U0.5–U0.13).**
- ### **None of these block Phase 1.** DEF-6 blocks P2; DEF-4/DEF-5 block G1/G2. ### **Phase 1 — the commit-key fix — is unblocked and remains the correct next act.**

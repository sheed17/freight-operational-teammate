# P8 Phase-Acceptance Review — candidate `319debc` — VERDICT: **BLOCKED**

> **This is a phase review, not an implementation record.** It scores the frozen P8
> acceptance-criteria contract (`IMPLEMENTATION-REGISTRY.yaml` unit P8) and records the G4
> qualification evidence. It changes no product runtime. P8 stays `READY / NOT_STARTED /
> NO_CHECKPOINT`; P9 stays `BLOCKED`.

## 1. Exact candidate reviewed
- **Product commit / tree:** `319debccfdcb2344edf34fc28cabd0f2e9312861` / `8aad5359e56c64d4a5322d5188ed4fd2514aec11` — the commit CI run #53 judged.
- **Review tree:** `HEAD` at review time carries only two *added* acceptance-gate guard files on top of the candidate (`eval/tests/test_p8_g4_acceptance_gate_r13.py`, `test_p8_g4_acceptance_gate_r13w2.py`) plus this document and the frozen criteria table. **`src/` is byte-identical to `319debc`** (`git diff --quiet 319debc HEAD -- src`), so the product runtime CI #53 validated is unchanged.

## 2. Reviewer identity / lineage (Tier-1 independent phase review)
This review was produced by a session **outside the P8 build/remediation lineage**: it wrote **no P8 product code** (the P8 product artifacts under `src/` were authored by the `P8/U8.1…U8.6` commit series; `src/` is byte-identical to the candidate). The only artifacts this session authored are **verification machinery** — the R13/R13-w2 acceptance-gate guards, this review document, and the frozen criteria table (acceptance-contract/status metadata authorized by the founder). It re-derived all evidence itself by operating the repository's approved probes, mutation batteries, guards, and the CI provider API; builder reports and prior U8 reviews were treated as supporting lineage only. **Verdict: DOES NOT SUPPORT acceptance — BLOCK.**

## 3. Frozen criteria + scoring (re-derived evidence)
The complete criterion population was frozen in the registry (17 criteria, `required: true`, weights = 100, `result: PENDING`) **before** scoring, as a deterministic decomposition of already-binding P8/G4 authority. Scoring:

| Criterion | Scored | Evidence (re-derived on the candidate) |
|---|---|---|
| P8-AC-1 U8.1 gate registration | PASS | `product_policy.verify_registration_complete()` fails startup over a non-zero 8-class population discovered from `OCCURRENCE_RULES`; `GateRegistry.gate_for` refuses unregistered (no `_DEFAULT`); `test_p8_policy_admission.py` 42 passed; `mutate_p8_policy_admission.py` 15/15. *(Note: `AC-CKPT-6-missing` still formally DEFERRED in the manifest against the empty kernel `GateRegistry`; the U8.1 obligation is enforced by `product_policy`.)* |
| P8-AC-2 U8.2 compile-or-refuse rules | PASS | `test_p8_rule_admission.py`, `test_phase6_rule.py` green; `mutate_p8_rule_admission.py` 6/6 (locally). |
| P8-AC-3 U8.3 real brake | PASS | `test_phase3_brake.py`, `test_p8_brake_scope.py`, `test_phase6_brake.py` green; `probe_phase6_brake.py` 0 wrong; CAS revalidates both brake versions. |
| P8-AC-4 U8.4 M7–M10 layer | PASS | `test_p8_u84_seams.py` green; `test_phase6_compensation.py` 64 passed; AC-REC 5/5. |
| P8-AC-5 U8.5 lane migration | PASS | `test_phase8_action_class_migration.py`, `test_phase8_action_class_equivalence.py` green. |
| P8-AC-6 U8.6 proposal boundary | PASS | `probe_phase8_proposal.py` 23/0 wrong; `mutate_phase8_proposal.py` 18/18; 150 P8 unit tests green. |
| P8-AC-7 CI #52 regressions closed | PASS | P1 structural guards green; mutation battery interpreter-hermetic (tree clean after run). |
| P8-AC-8 no second authority | PASS | AST evidence: only `checkpoint.py` mints a `GateDecision`; witness/grant/claim boundary intact. |
| P8-AC-9 tenant isolation | PASS | `test_ac_sec_001_registry.py` 30 passed (cross-tenant reads as absent); cross-tenant refusal tests green; T_A/T_B fixtures. |
| P8-AC-10 replay inert | PASS | `test_phase3_witness.py` (reconstructed pass mints nothing); `test_p5_replay_and_audit.py`; replay-of-corpus zero effects. |
| **P8-AC-11 mutation anti-vacuity (standing)** | **FAIL** | `mutate_p8_rule_admission.py` and `mutate_phase6_compensation.py` are **never executed by standing evidence** (no CI step, no collected test runs them — only manifest/doc mentions); their mutants are not seen RED in re-derivable evidence. Measured by `test_p8_g4_acceptance_gate_r13w2.py`. |
| P8-AC-12 ships dark | PASS | production `GateRegistry` empty (`test_phase0_null_gate.py`); `operation_router` None; `ROUTE_NOT_CONFIGURED`; no autonomy. |
| **P8-AC-13 G4 qualification** | **FAIL** | See §4. AC-RACE-017 has no oracle; AC-RACE 10,000-interleaving depth not standing; AC-SEC-002..014 unmapped; no enumerated crash-point matrix denominator. |
| P8-AC-14 exact-tree CI | PASS (candidate) | CI #53 on `319debc` = success (see §5). *(The review tree with the added guards has not itself been through CI; moot under BLOCK.)* |
| P8-AC-15 independent phase review supports | **FAIL** | This review does not support — it blocks on P8-AC-13/AC-11. |
| P8-AC-16 status honesty | PARTIAL/PENDING | Machine surfaces reconcile (P8 NOT_STARTED everywhere; `test_current_status_reconciliation.py` green). CURRENT.md narrative prose ("U8.2–U8.6 are NOT STARTED") is stale relative to the branch — nonblocking debt. |
| P8-AC-17 outside build lineage | satisfied for the review; acceptance not reached | This session is outside the P8 product lineage; but acceptance is BLOCKED. |

**Not all `required` criteria PASS → P8 does not reach `PHASE_ACCEPTANCE_COMPLETE`.**

## 4. G4 population and qualification — **DOES NOT QUALIFY**
Re-derived directly from `release-gates.md` G4 (100%, zero-tolerance) and mapped to present executable oracles:

- **AC-SAFE-001..028** — 28/28 defined; 28/28 have oracles. **Satisfied.**
- **105 AC-CKPT** — `test_phase3_checkpoint_matrix.py` parametrizes exactly 7×15=105 + a `7×15==105` count assertion + per-cell anti-vacuity; 106 collected, pass. **Satisfied.**
- **AC-REC-*** — 5/5 with oracles; `test_phase6_compensation.py` 64 passed. **Satisfied.**
- **AC-SEC-*** — 14 defined; **only AC-SEC-001 is id-mapped to an oracle**; AC-SEC-002..014 carry no id-mapped executable oracle (some behaviours tested unlabeled). **Family population not proven complete.**
- **AC-RACE-001..017 + crash matrices** —
  - **AC-RACE-002 "10,000 interleavings per race":** no standing oracle exercises 10,000 (pytest runs `range(40)`; the probe runs 250+1000; the 10,000 cap is reachable only by a hand-typed `--repeat 10000`, and even then the oracle is a single-threaded deterministic alternation whose "never both, never neither" headline is tautological by construction). **Not established as standing evidence.**
  - **AC-RACE-017** (downstream Work-Item-creation crash / atomic handoff): **no oracle anywhere** in `eval/`/`scripts/`.
  - **AC-RACE-011** (browser crash after click): covered only at the state-machine abstraction.
  - **crash matrices / "every crash point":** two crash kits inject crash points, but **neither is an enumerated matrix asserting a coverage denominator** — completeness cannot be established.

Per `release-gates.md` G4 and the task rule "if any G4 family lacks a present executable oracle/evidence sufficient for its canonical requirement, G4 does NOT qualify," **G4 does not qualify** (AC-RACE and AC-SEC families incomplete; crash-point coverage unproven). A green full suite is not a substitute (`release-gates.md` header; the ORACLE RULE).

These gaps are now **mechanically enforced**: the R13/R13-w2 acceptance-gate guards fail closed if P8 is ever set COMPLETE while these oracles are missing — they are the durable proof that this contract cannot be flipped to PASS while G4 is under-evidenced.

## 5. Exact-tree CI #53 verification (independent, GitHub REST API)
Exactly **one** workflow run on the candidate SHA: **run #53**, `run_attempt=1`, event **push**, status **completed**, conclusion **success**, `head_sha=319debc…`. Jobs: **31 success + 1 skipped** — the skipped job is `risk-radar`, which `.github/workflows/ci.yml` gates `if: github.event_name == 'pull_request'` (advisory, not in the `CI verdict` needs). Every blocking job succeeded: `partition`; both `suite-completeness` proofs (py3.11/3.12); all `safety` shards; all 20 `suite` shards; `effect-grant`; `brake`; `proposal` (the P8 certification); `CI verdict`. **CI #53 = SUCCESS on the candidate — used only as the CI-provider oracle, never as the phase review.**

## 6. Findings
**BLOCKING:**
- **B1 — G4 does not qualify** (P8-AC-13): AC-RACE-017 no oracle; AC-RACE 10,000-interleaving depth not standing; no enumerated crash-point-matrix denominator; AC-SEC-002..014 unmapped.
- **B2 — Mutation anti-vacuity not standing** (P8-AC-11): `mutate_p8_rule_admission` and `mutate_phase6_compensation` mutants are never seen RED in CI/collected evidence.

**NONBLOCKING debt (record, don't action here):**
- N1 — CURRENT.md narrative prose still says "U8.2–U8.6 are NOT STARTED"; stale relative to the branch (machine surfaces are correct and reconciled).
- N2 — `AC-CKPT-6-missing` remains formally DEFERRED in the manifest while `product_policy` enforces the U8.1 registration obligation.
- N3 — `GateDecision` docstring (`checkpoint.py`) still references the removed `_DEFAULT`.
- N4 — `test_phase8_action_class_registered.py` is misnamed (holds U8.6 proposal tests).

## 7. Can P8 truthfully become COMPLETE?
**No.** G4 does not qualify and the standing mutation anti-vacuity is incomplete; materializing COMPLETE would make the truthful R13/R13-w2 guards go RED, and a truthful guard may not be weakened to write COMPLETE. Remediation belongs to a separate builder run (wire the AC-RACE 10,000-interleaving oracle and a crash-point matrix into standing evidence; add an AC-RACE-017 oracle; id-map AC-SEC-002..014; wire `mutate_p8_rule_admission` and `mutate_phase6_compensation` into CI/pytest), followed by a fresh independent phase review.

## 8. Status outcome
P8 stays `READY / NOT_STARTED / NO_CHECKPOINT`. P9 stays `BLOCKED` (its P8 dependency is not COMPLETE). No status materialization performed. The frozen criteria contract is now recorded so a future acceptance is evaluable against an explicit, guarded bar.

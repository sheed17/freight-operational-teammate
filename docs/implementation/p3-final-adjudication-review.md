# P3 — FINAL ADJUDICATION

> ### **HISTORICAL EVIDENCE — NOT CURRENT AUTHORITY.**
> The status authority is [`CURRENT.md`](CURRENT.md) and the registry. This document RECORDS the
> final adjudication of Neyma Phase 3; it is preserved evidence of what one adjudicating session
> verified and decided. Once written, it does not itself move a gate — the registry criteria it set
> and the finalizer-derived status are the authority. Read it for the reasoning; act on the registry.

| | |
|---|---|
| **Unit adjudicated** | `P3` — Checkpoint Witness, seven-step atomic checkpoint, and claim CAS |
| **Adjudicated content lineage** | `0bf72b7` (kernel tree `cc53ff4f…`), byte-identical through the recorded content commit |
| **Genuine independent review** | [`p3-genuine-independent-review.md`](p3-genuine-independent-review.md) — PASS, zero new defects, 13/13 hostile probes |
| **Result** | ### **ALL 14 WEIGHTED CRITERIA PASS → 100/100 → P3 COMPLETE** |
| **Consequences** | P4 becomes the sole READY unit (NOT begun). R-07 stays **OPEN — NOT CONTAINED**. The kernel still **ships dark**. Nothing pushed. |

---

## 1. Adjudicating-session independence

This session is the adjudicator of record for P3. It did **not**: implement the P3 kernel; perform
either earlier independent review; remediate findings F-A … F-I; normalize the git history; correct
N-1; or author the genuine independent review. Its only role was to weigh the authoritative evidence
and set the registry criteria. `independent_review` (weight 5) and `final_adjudication` (weight 4)
are, by construction, the two criteria a phase's own author cannot supply; the reviewer supplied the
first, this session the second, and **no session adjudicated its own work.**

## 2. Adjudication inputs verified before any change

- **Working tree clean; branch `p3/checkpoint-witness`; HEAD a metadata-only finalizer commit;**
  `HEAD^` the current content commit whose tree the finalizer/clean-clone receipts bind to.
- **Legal FINALIZED topology.** The content lineage `0bf72b7 → …` is byte-identical in every kernel
  file (`checkpoint.py`, `workflow.py`, `brake.py`, `migrations/phase3_checkpoint.py`, all
  `test_phase3_*`, `test_rebaseline_invariants`) through the recorded content commit — verified by
  `git diff --name-only` returning empty over `src/` and the P3 tests. The finalizer's status-metadata
  commits touched only the declared status files.
- **Receipts bind correctly.** `SUITE-RESULT.json` (exit 0, 1535 passed / 0 failed / 1 skip) and
  `GATE-RESULT.json` (`passed: true`, clean-clone reproduced the suite) both bind to the recorded
  content commit and tree.
- **The reviewer-authored N-1 correction was independently re-verified by this session** rather than
  trusted: the `BUILD-STATUS.yaml` `finalizer_result` / `clean_clone_result` narratives lead with
  `PASS` and match the receipts, and the N-1 guard `test_build_status_receipt_consistency.py` enforces
  that consistency in both directions with frozen mutation fixtures. N-1 touches no kernel file, no P3
  test, and no P3 safety guard.
- **Kernel re-verified from source, not from prose.** An independent inspection confirmed, with
  file+line evidence and a green P3 battery (nine `test_phase3_*` files, 0 failed, 0 skipped): the
  single atomic seven-step checkpoint in canonical order (short-circuit → earliest failing step
  reported) inside one transaction with the witness insert and grant mint; `CheckpointPassed`
  unconstructable (private-token `__init__`, `__init_subclass__`/`__reduce__`/`__copy__` raise,
  `WeakSet` genuine-instance registry); the append-only witness enforced by **database triggers**; the
  claim CAS revalidating **six** predicates (tenant, grant_id, state=GRANTED, expiry, brake_version,
  policy_version) inside the UPDATE's own WHERE clause, exactly-one-winner under a thread race;
  fail-closed brake admission read inside the transaction, one-way ratchet, no TTL, platform-then-tenant
  composite version token; tenant-first scoping with cross-tenant refusal; replay non-authority; and the
  105-case matrix mechanically derived (7 × 15) with a universal no-partial-authorization oracle.
- **P3 sole READY unit; P4+ blocked; R-07 OPEN — NOT CONTAINED** — all confirmed from the registry
  and `phase-0-baseline-manifest.yaml` before the adjudication.

## 3. The 14 weighted criteria — verdicts and evidence

Weights are the registry's (Σ = 100). Every criterion is **PASS**.

| # | Criterion | Wt | Verdict | Evidence consulted |
|---|---|--:|:--:|---|
| 1 | `accepted_scope_and_design` | 6 | PASS | Kernel-only scope honored; ships dark; two-key rule realised per ADR-004/005/009/010/011; no P4 containment work; P3 prohibited-scope intact |
| 2 | `required_tests` | 8 | PASS | The 105-case matrix + witness, claim-CAS, brake, fingerprint, schema, step-order, ledger-compat and observability suites; nine `test_phase3_*` files green |
| 3 | `core_implementation` | 20 | PASS | Seven-step atomic checkpoint, unconstructable witness, grant mint, claim CAS — all present and correct (source-verified) |
| 4 | `failure_handling` | 8 | PASS | Earliest-failing-step reported; rollback on refusal; fail-closed source/brake reads; universal oracle proves no partial-authorization state |
| 5 | `concurrency_handling` | 8 | PASS | `BEGIN IMMEDIATE`; claim CAS single-use; independent thread-race probe → exactly one winner, one CLAIMED row |
| 6 | `authorization_and_security` | 10 | PASS | Witness unforgeable; confusion check; Sev-0 events; tenant isolation; six-predicate two-key CAS |
| 7 | `migrations_and_persistence` | 6 | PASS | Live-hold index replaces the strict form; append-only witness trigger; tenant-consistent FK; readiness oracle; F-C ledger compatibility |
| 8 | `observability_and_operational_behavior` | 6 | PASS | Per-step emission; refusal names the step; observer exceptions swallowed; exploding-observer isolation leaves outcome/rows byte-identical |
| 9 | `mutation_or_hostile_cases` | 8 | PASS | Guard battery (8/8) + kernel battery (K1–K11) as evidence, corroborated by the review's **13/13 independent hostile probes** (see §5 caveat) |
| 10 | `full_test_suite` | 5 | PASS | Finalizer-executed canonical suite green on the final tree; `SUITE-RESULT.json` exit 0, 1535 passed / 0 failed / 1 skip |
| 11 | `canonical_finalizer` | 3 | PASS | `scripts/finalize_status.py` executed on the final tree, exit 0, PRODUCED the status record |
| 12 | `clean_clone_execution` | 3 | PASS | Clean-clone gate reproduced the full green suite in a fresh clone+venv; `GATE-RESULT.json` `passed: true` bound to the reviewed commit/tree |
| 13 | `independent_review` | 5 | PASS | The genuine independent review — independent of implementation, both prior reviews, remediation and normalization; zero new defects; F-A…F-I confirmed remediated; 13/13 probes |
| 14 | `final_adjudication` | 4 | PASS | **This adjudication** — a session independent of implementation, review, remediation, normalization and N-1, acting on the evidence above |

**Weighted total: 100 / 100. P3 phase completion = 100%. P3 is COMPLETE.**

## 4. Findings F-A … F-I — independently confirmed remediated

Each of the nine findings from the first independent review (1 CRITICAL, 3 HIGH, 3 MEDIUM, 2 LOW,
60/100, `NOT READY`) was independently confirmed remediated by the genuine review and re-checked here:
the mis-anchored rebaseline-invariant guard (F-A) re-anchored to an immutable window with exact
63-path membership and a proven non-vacuous population; the false `socket.bind` attribution (F-B)
corrected and superseded by an actual green finalizer/clean-clone; the `effect_grants` ledger
compatibility (F-C) rescoped so no live P3 grant reaches the legacy consumers that could break the P2
ledger; canonical seven-step order (F-D) proved by short-circuit + multi-fault composition; the
`platform_brake`/SD-12 representation (F-E) amended and guarded; observability (F-F) with
exploding-observer isolation; the typed-policy P8 deferral (F-G) reconciled with AC-CKPT-6-missing
staying deferred on a mechanically-proven zero production gate-registration population; mutation-battery
honesty (F-H); and CAS defense-in-depth predicates (F-I).

## 5. Residual observations (non-blocking — recorded, not defects)

1. **Mutation-battery independence (F-H caveat).** No *independent* mutation battery was run; the
   implementer guard battery (8/8) and kernel battery (K1–K11) are evidence, and the genuine review
   corroborated the kernel with 13/13 *independent* hostile probes. Criterion 9 is an OR
   (`mutation_or_hostile_cases`); the independent hostile-probe evidence carries it. Non-blocking.
2. **CAS exact-set guard is misnamed.** `test_phase3_claim_cas.py::test_the_cas_where_clause_still_carries_all_five_predicates` correctly enforces the exact **six**-predicate membership set and forbids a
   seventh; only the function *name* says "five." Cosmetic; the guard is load-bearing and correct. Not
   touched, to keep the reviewed kernel tree byte-identical.
3. **F-C summary phrasing.** The genuine review's F-C *summary* sentence over-generalizes ("all four
   legacy consumers carry both predicates"); the actual per-method code is deliberate and documented —
   the two *mutating* methods carry both `checkpoint_id IS NULL` and the live-hold state filter, while
   `operation_commit_claim` scopes by live-hold state and relies on the live-hold **unique index**
   (at most one live row per `(tenant, commit_key)`, raising on >1) and `legacy_commit_rows` scopes by
   `checkpoint_id IS NULL`. Returning the single live reservation is correct, and P3 ships dark so no
   live P3 grant exists in production. Not a defect.
4. **PROGRAM-WEIGHTS advisory tier.** P3's per-phase `readiness_tier` in `PROGRAM-WEIGHTS.yaml` is
   advisory display metadata (frozen-weights file); the authoritative readiness is the registry's
   `readiness_target: LOCALLY_IMPLEMENTED`. Left untouched.

## 6. What this adjudication does and does not do

- **Does:** set the 14 P3 criteria to PASS, record P3 COMPLETE, advance P4 (whose sole dependency is
  now satisfied) to READY, and re-point the control guards and live guidance surfaces to the
  post-adjudication truth (CLAUDE.md rule 20 — guards replaced, not deleted).
- **Does NOT:** begin P4; enable the kernel on any live path; close or narrow R-07; delete legacy
  production code; touch the kernel or its tests; invent product scope; or push.

## Verdict

### **P3 FINAL ADJUDICATION — PASS. All 14 weighted criteria PASS (100/100). P3 is COMPLETE.**

P4 is the sole READY unit and has not begun. R-07 stays **OPEN — NOT CONTAINED** — completing P3 did
not close it; only completing P4 does. The checkpoint kernel ships dark until P4 routes effects
through it. The repository is ready for the product driver to begin P4 under P4's own acceptance
contract.

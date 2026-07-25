# P3 — GENUINE INDEPENDENT REVIEW OF THE REMEDIATED, FINALIZED TREE

> ### **NOT CURRENT AUTHORITY — this is preserved evidence, not status.**
> The status authority is [`CURRENT.md`](CURRENT.md). Nothing here approves work, moves a gate, sets
> a registry criterion or authorises a phase transition. ### **This document is an INDEPENDENT
> REVIEW; it is NOT the final adjudication.** It records what one independent session verified and
> recommends. The registry's 14 P3 acceptance criteria remain `PENDING` until the ADJUDICATING
> session sets them from this evidence. P3 is **NOT COMPLETE**; P4 is **BLOCKED**; R-07 is
> **OPEN — NOT CONTAINED**; the kernel **ships dark**.

| | |
|---|---|
| **Reviewed content commit** | `2fad4252f8a37d12057e95f0e42f6b7060fcd79a` |
| **Reviewed content tree** | `fa369f226cc2ca0452ab533c01fea39a95ddf46d` |
| **P3 kernel content lineage** | `0bf72b7…` (kernel tree `cc53ff4f…`) — the consolidated P3 content this review's kernel verdicts are about |
| **Reviewer independence** | did NOT implement P3, did NOT perform either prior review, did NOT remediate the findings, did NOT normalize the git history, did NOT author `0bf72b7` or `9a48cf8` (§1) |
| **Findings verified** | F-A … F-I — all nine independently confirmed remediated |
| **New defects found** | **0** |
| **Independent hostile probes** | **13 / 13 passed** (§4) |
| **Verdict** | ### **PASS — READY FOR FINAL ADJUDICATION** |

---

## 1. Independence — stated plainly, including what this session DID author

This session is the genuinely independent reviewer of record for P3. It did **not**:

- implement the P3 checkpoint kernel (that work is commit `0bf72b7`'s kernel content);
- perform either prior review (the independent findings review of `38f2714`, nor the prior
  re-review that N-2 disqualified);
- remediate the nine findings;
- normalize the git history or author the consolidation/finalization commits `0bf72b7` or `9a48cf8`.

**What this session DID author, disclosed so the adjudicator can weigh it:** the N-1 correction
(content commit `2fad4252`). N-1 corrected the stale `BUILD-STATUS.yaml` `snapshot:` narrative to
match the executed receipts, added `eval/tests/test_build_status_receipt_consistency.py`
(a BUILD-STATUS-narrative-vs-receipts guard), regenerated the node manifest and updated the
reproducible guard-count figure. **N-1 touches no kernel file, no P3 test, and no P3 safety guard**
(`checkpoint.py`, `workflow.py`, `brake.py`, the migration, and every `test_phase3_*` /
`test_rebaseline_invariants` file are byte-identical to their state before N-1). The review of the
P3 kernel and its nine findings below is therefore independent in substance: this session neither
wrote, remediated, nor normalized any of what it reviews.

The one review item this session authored is the N-1 narrative correction itself (§6). That item is
mechanically self-verifying — the guard added in N-1 enforces its consistency against the receipts —
and it is flagged here so the **separate** final-adjudication session independently confirms it. That
separation is the two-key discipline this repository runs on: this review is evidence; the
adjudicator certifies.

## 2. Legal topology, receipt bindings, and the metadata-only finalizer commit

Verified directly from `git` and the committed artifacts:

- **Topology at review time** (four commits): `0bf72b7` (P3 kernel content) → `9a48cf8` (its
  status-metadata commit) → `2fad4252` (the N-1 content correction) → `5caf8f8…` (the N-1
  status-metadata commit, `HEAD` when this review was performed). At that point the repository was in
  the legal **FINALIZED** state: `CURRENT.md` recorded `2fad4252` and `HEAD^` was `2fad4252`. This
  review artifact is itself preserved in a subsequent content commit (which re-finalizes onto its own
  tree); the reviewed subject remains `2fad4252` / `fa369f22`.
- **The metadata commit changed only status files.** `git diff --name-only 2fad4252 5caf8f8`
  yields exactly `BUILD-STATUS.yaml`, `CURRENT.md`, `GATE-RESULT.json`,
  `IMPLEMENTATION-REGISTRY.yaml`, `SUITE-RESULT.json` — all members of the finalizer's declared
  status-metadata set. `test_status_reality.py` confirms the FINALIZED relationship and the
  metadata-only constraint.
- **Receipt bindings.** `SUITE-RESULT.json` and `GATE-RESULT.json` both bind to commit `2fad4252`
  and tree `fa369f22`. The suite receipt records exit 0, 1535 passed, 0 failed, 1 skipped; the gate
  receipt records `passed: true`. The recorded figures match `CURRENT.md`'s finalizer-written
  status block.
- **Finalizer.** `scripts/finalize_status.py` was executed on the reviewed content commit and exited
  0 after running the complete canonical suite, the clean-clone gate, the control guards and the
  AC gates in-process — it PRODUCED the status record rather than validating a supplied one.
- **Clean clone.** The finalizer's clean-clone gate cloned the committed state into a fresh temp
  directory, built a fresh venv, installed only declared dependencies, and reproduced the full
  suite green (1535 passed / 0 failed / 1 skipped, 1536 collected) plus the control and AC gates —
  `GATE-RESULT.json` records the PASS bound to the reviewed commit/tree.

## 3. Finding-by-finding independent verification (F-A … F-I)

Each finding was verified by reading the actual remediation in the source and confirming its
mechanism, not by trusting the remediation record.

- **F-A (CRITICAL) — mis-anchored rebaseline invariant guard. CONFIRMED REMEDIATED.**
  `test_no_src_runtime_file_was_touched_by_the_rebaseline` is re-anchored to the unit's **immutable**
  window in `U-REBASELINE-1-ACCEPTANCE.yaml` (`base 43a0c4a…` → `head b330614…`, a file the finalizer
  never writes), computes `git diff --name-only base head`, requires a non-empty population, asserts
  **exact 63-path membership** (membership, not count — the assertion spells out unexpected/missing),
  and only then asserts nothing under `src/`. Non-vacuity is proven by a *separate* pure-predicate
  test (`forbidden_runtime_changes`) fed synthetic clean/dirty inputs. The loud NOT-RUN skip on a
  shallow clone is preserved and deliberately excluded from the approved canonical-run skips. The
  invariant is preserved, the population is now correct, and the guard cannot drift with the
  finalizer.

- **F-B (HIGH) — false `socket.bind` attribution. CONFIRMED REMEDIATED, and now superseded by
  fact.** The false attribution was corrected in place. This review supersedes the point entirely:
  the finalizer and clean-clone gate have now **actually executed and passed** on the finalized tree
  (§2), so there is no blocker left to mis-attribute. The N-1 correction (§6) removed the last stale
  traces of the failure narrative.

- **F-C (HIGH) — `effect_grants` persistence broke the P2 ledger. CONFIRMED REMEDIATED.** All four
  legacy consumers in `workflow.py` are rescoped with two **structural** predicates:
  `checkpoint_id IS NULL` (a P3 grant always writes a non-null `checkpoint_id`; the legacy writer
  never does — so no P3 row can satisfy the legacy scope) and `state IN LIVE_HOLD_STATES` (imported
  from the migration that defines the live-hold index, so the two cannot drift). `operation_commit_claim`
  now returns the live reservation and raises on >1 live row; `release_operation_commit` is
  idempotent and no longer reaches checkpoint-bound grants (so the reviewer's `FOREIGN KEY` error is
  gone); `update_operation_commit_payload` targets the one legacy-owned live row; `legacy_commit_rows`
  excludes checkpoint-bound grants. `test_phase3_ledger_compatibility.py` reproduces both reviewer
  failures plus FK-actually-enforced and live-hold uniqueness (248-test P3 battery green).

- **F-D (HIGH) — canonical seven-step order. CONFIRMED REMEDIATED.** The order is enforced by
  short-circuit in `_seven_steps_locked`: each step returns its refusal immediately, so the earliest
  canonical failing step is always the one reported. The 105-case matrix cannot observe order
  (one fault at a time), so `test_phase3_step_order.py` adds multi-fault composition including the
  named dual-fault case (policy vs active brake). This review additionally proved ordering with an
  **independent** multi-fault probe (§4, probe 3): FORBIDDEN (step 6) + active brake (step 7) reports
  step 6; missing approval (step 1) + active brake (step 7) reports step 1.

- **F-E (MEDIUM) — `platform_brake` representation / SD-12. CONFIRMED APPLIED.** `16-brake.md`
  point 7 is formally amended (A1): the single global brake lives in its own tenant-exempt
  `platform_brake` table (`id = 1` CHECK, seeded RELEASED v0 so absent ≠ released). `brake.py`
  admission consults platform **then** tenant, fails closed on an absent/unreadable row, and
  `version_token` binds the composite `global:<v>|tenant:<max>`. The witness and grant store the
  composite `brake_version`; the claim CAS revalidates it. Independently probed (§4, probes 7–8):
  deleting the platform row makes step 7 refuse `BRAKE_UNREADABLE`, and a brake engaged between mint
  and claim makes the CAS refuse `BRAKE_CHANGED`.

- **F-F (MEDIUM) — observability. CONFIRMED REMEDIATED.** `_step_passed` emits a `CheckpointStep`
  PASS for every step; `_record_refusal` emits the refusal naming the failing step; step 7's PASS
  carries both brake owners' state and version. `kernel.observe` swallows observer exceptions, so
  observability can describe control flow but never alter it. `test_phase3_observability.py` proves
  all five properties with a real observer, including that an `Exploding` observer leaves the
  outcome, witness row and grant row byte-identical to a silent run.

- **F-G (MEDIUM) — typed policy vs the P8 deferral. CONFIRMED APPLIED.** P3 holds the minimal
  structural `GateDecision`/`GateRegistry` contract that checkpoint step 5/6 requires; the stale
  manifest rationale ("typed policy … do not exist until P8") is corrected. AC-CKPT-6-missing stays
  DEFERRED and UNGREEN on the ground that actually holds — the **production** gate-registration
  population is still zero, proven mechanically by
  `test_the_production_gate_registration_population_is_still_empty`, which fails the moment any
  production module constructs a `GateRegistry`. Confirmed independently: no production module
  imports the kernel (§5).

- **F-H (LOW) — mutation-battery honesty. CONFIRMED REMEDIATED.** `BUILD-STATUS.yaml` distinguishes
  the implementer guard battery (8/8), the kernel battery added at remediation (K1–K11), and the
  fact that no **independent** mutation battery has been run — no claim of final mutation success is
  made. The N-1 correction (§6) preserves this distinction.

- **F-I (LOW) — CAS defense-in-depth predicates. CONFIRMED REMEDIATED.** `claim_grant_cas`'s
  WHERE clause carries six predicates; `expires_at > ?` and `tenant = ?` are documented as defense
  in depth, each naming what masks it. `test_phase3_claim_cas.py` isolates each and a structural
  membership check fails if the WHERE clause loses **or gains** a predicate. The masking invariant
  behind `expires_at` (`witness_window ≤ grant_ttl`, enforced in `CheckpointKernel.__init__`) is
  separately guarded.

## 4. Independent hostile probes — 13 / 13 passed

Fresh adversarial attacks written by this reviewing session (not reruns of the P3 battery), each
reusing only the boring builders in `phase3_kit`:

| # | Property attacked | Result |
|---|---|---|
| 1 | a forged `CheckpointPassed` (public ctor, `object.__new__`, subclass, pickle, copy) mints/constructs nothing | PASS |
| 2 | a genuine witness is single-use — a second mint from the same pass is refused | PASS |
| 3 | multi-fault ordering — the earliest canonical step is reported (6 over 7; 1 over 7) | PASS |
| 4 | claim CAS single-use — a double claim yields `ALREADY_CLAIMED`, one `CLAIMED` row | PASS |
| 5 | claim CAS thread race — exactly one of two racing kernels wins, one `CLAIMED` row | PASS |
| 6 | tenant isolation — a cross-tenant effect is refused `TENANT_MISMATCH` | PASS |
| 7 | brake fail-closed — an absent `platform_brake` row refuses at step 7 `BRAKE_UNREADABLE` | PASS |
| 8 | a brake engaged between mint and claim — the CAS refuses `BRAKE_CHANGED` | PASS |
| 9 | a stale witness (past its freshness window) refuses `STALE_WITNESS` | PASS |
| 10 | material-facts drift voids the approval at step 2 with a named diff | PASS |
| 11 | a `MODEL_INFERRED` material fact cannot gate (step 4), and the `.value` accessor raises | PASS |
| 12 | `checkpoint_witnesses` is append-only — UPDATE and DELETE are refused by the database | PASS |
| 13 | replay non-authority — the durable witness record cannot mint a grant | PASS |

Two probes initially reported the kernel refusing **earlier/harder** than the probe expected — a
human-gated witness with no approval is rejected by the witness CHECK constraint, and a provenance
change after approval is caught at step 2 as drift rather than at step 4. Both were probe-construction
artifacts, not kernel defects; corrected, both pass. The kernel enforcing safety sooner than an
attacker anticipates is the desired direction.

## 5. Cross-cutting properties

- **Ships dark.** No production module (`src/`, `scripts/`) imports the checkpoint kernel except
  `scripts/mutate_phase3_guards.py`, a mutation-testing tool. No live-write path routes through it.
- **P4 containment untouched.** The six R-07 live-write paths and the 31 adapter-import edges are
  intact (phase-0 guards); R-07 stays OPEN — NOT CONTAINED. P3 honored its prohibited scope.
- **Replay non-authority.** `CheckpointPassed` has no public constructor, is final, cannot be
  pickled/copied, and is tracked in a process-local `WeakSet`; a witness reconstructed from history
  is a plain dataclass with no capability. Replay can mint neither witnesses nor grants.
- **Negative assertions use proven populations.** The guards this review exercised
  (`require_population`, the non-vacuity predicate for F-A, exact-membership for the rebaseline
  window and the CAS WHERE clause) all assert against a proven, non-empty population.

## 6. The N-1 narrative correction (authored this session; flagged for adjudicator confirmation)

N-1 reconciled every stale `BUILD-STATUS.yaml` `snapshot:` field to the executed receipts: the
resolved illegal-history deadlock, the green finalizer, the passing clean-clone, and the deferral of
volatile counts to `CURRENT.md`. It is verified here to match the receipts (`finalizer_result` and
`clean_clone_result` lead with `PASS`; no field asserts a failure the receipts contradict), and the
new guard `test_build_status_receipt_consistency.py` now enforces that consistency mechanically in
both directions (a failure narrative under passing receipts, and a PASS narrative under failing
receipts, are both rejected — proven with frozen fixtures of the exact stale text). Because this item
was authored this session, the adjudicator should confirm it independently; the check is a mechanical
comparison against `SUITE-RESULT.json` / `GATE-RESULT.json`.

## 7. The 14 weighted acceptance criteria — evidence and reviewer verdict

Weights are the registry's. **These verdicts are the reviewer's assessment of the evidence; they do
NOT set the registry results, which remain `PENDING` until the adjudicating session records them.**

| # | Criterion | Wt | Evidence | Reviewer verdict |
|---|---|--:|---|---|
| 1 | `accepted_scope_and_design` | 6 | kernel-only scope honored; ships dark; no P4 containment; two-key rule realised per ADR-004 | **PASS** |
| 2 | `required_tests` | 8 | the 105-case matrix, witness, claim-CAS, brake, fingerprint, schema, plus F-C/F-D/F-F suites — 248-test P3 battery green | **PASS** |
| 3 | `core_implementation` | 20 | seven-step atomic checkpoint, unconstructable witness, grant mint, claim CAS all present and correct (§3, §4) | **PASS** |
| 4 | `failure_handling` | 8 | first-failing-step reported; rollback on refusal; fail-closed source/brake reads; `COMMIT_KEY_HELD` on integrity | **PASS** |
| 5 | `concurrency_handling` | 8 | `BEGIN IMMEDIATE`; claim CAS single-use; thread-race probe → exactly one winner (§4 p4–p5) | **PASS** |
| 6 | `authorization_and_security` | 10 | witness unforgeable; confusion check; Sev-0 events; tenant isolation; two-key CAS (§3, §4) | **PASS** |
| 7 | `migrations_and_persistence` | 6 | live-hold index replaces the strict form; append-only witness trigger; tenant-consistent FK; readiness oracle; F-C ledger compat | **PASS** |
| 8 | `observability_and_operational_behavior` | 6 | per-step emission; refusal names the step; observer exceptions swallowed; exploding-observer isolation (F-F) | **PASS** |
| 9 | `mutation_or_hostile_cases` | 8 | guard+kernel mutation battery 19/19 (audited session — evidence) corroborated by this session's 13/13 independent hostile probes | **PASS** |
| 10 | `full_test_suite` | 5 | finalizer-executed canonical suite green on the final tree: 1535 passed / 0 failed / 1 skipped | **PASS** |
| 11 | `canonical_finalizer` | 3 | `scripts/finalize_status.py` executed on the final tree, exit 0, PRODUCED the status record | **PASS** |
| 12 | `clean_clone_execution` | 3 | clean-clone gate reproduced the full green suite in a fresh clone+venv; `GATE-RESULT.json` `passed:true` bound to the reviewed commit/tree | **PASS** |
| 13 | `independent_review` | 5 | this session — independent of implementation, prior reviews, remediation and normalization (§1); zero new defects; F-A…F-I confirmed; 13/13 probes | **PASS (satisfied by this review)** |
| 14 | `final_adjudication` | 4 | not performed here — separation of reviewer and adjudicator is required; this artifact is the evidence the adjudicator will act on | **PENDING (adjudicator's to set)** |

Criteria 1–12 are fully supported (91 of 100 weight). Criterion 13 (`independent_review`) is
satisfied by this session. Criterion 14 (`final_adjudication`) is deliberately not performed.

## 8. What this review does NOT do

- It does **not** edit the registry's acceptance-criterion results — they stay `PENDING` until the
  adjudicator sets them.
- It does **not** perform final adjudication, mark P3 COMPLETE, advance P4, close R-07, or push.
- It does **not** enable the kernel on any live path — the kernel still ships dark.

## Verdict

Nine findings independently confirmed remediated; zero new defects; the seven-step ordering,
witness/grant atomicity, claim-CAS single-use and concurrency, tenant isolation, brake fail-closed
behaviour and version binding, replay non-authority, observability, and the migration/persistence
model all independently verified; the full suite, the finalizer and the clean-clone gate executed
green on the finalized tree; criteria 1–12 supported and `independent_review` satisfied.

### **P3 GENUINE INDEPENDENT REVIEW PASS — READY FOR FINAL ADJUDICATION.**

The next step is a **separate** final-adjudication session, which sets the registry's 14 criteria
from this evidence and only then may record P3 COMPLETE. Until it does: P3 is NOT COMPLETE, P4 is
BLOCKED, R-07 is OPEN — NOT CONTAINED, and the kernel ships dark.

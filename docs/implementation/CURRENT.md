# CURRENT — The Repository Status Authority

> ### **This is the ONLY short-form current-status authority in this repository.**
> Every phase review, blocker review and planning document is **historical evidence**. Do not
> reconstruct status by reading them — that is the failure this file exists to prevent.
>
> **Last updated:** P5 — Canonical events, outbox/inbox, replay isolation and production
> persistence **ADJUDICATED COMPLETE.** ### **All 14 weighted P5 criteria PASS → 100/100 → P5
> COMPLETE.** A **FRESH INDEPENDENT REVIEW** of the P5 surface at content commit `1216254` returned
> **ACCEPT FOR SEPARATE FINAL ADJUDICATION** with **NO material blocking defect**
> ([report](p5-independent-review-report-1216254.md)); a **SEPARATE FINAL ADJUDICATION** — by a
> session that neither implemented, remediated, reviewed nor finalized P5 — then set the fourteen
> results from evidence it reproduced itself
> ([report](p5-final-adjudication-report-91ba4e6.md)). **`P6` (foundational entities and state
> machines) is now the sole READY unit.**
> ### **THIS COMMIT IS NOT YET FINALIZED, AND P6 MAY NOT BEGIN UNTIL IT IS.** A closure content
> commit must first receive a **fresh targeted independent review**, a **separate targeted
> adjudication**, and then **exactly one finalizer** — the sequence the P4 acceptance closure and the
> R-07 closure both executed. **No finalizer receipt exists for this commit and none may be
> fabricated.**
> ### **P5 SHIPS DARK.** The outbox, inbox, relay, timers and PostgreSQL connector have **zero
> production callers**; their only consumers are explicitly-invoked evidence tooling. Completing P5
> enables no external effect.
> ### **R-07 is now CONTAINED.** Completing P4's weighted acceptance did **not** close it — the
> CONTAINED record belongs in [`phase-0-baseline-manifest.yaml`](phase-0-baseline-manifest.yaml),
> which is not a status-metadata file, so it required its own separate content commit **after** both
> finalization passes. That commit has been made, and **it** is the act that closed R-07.
> ### **CONTAINED MEANS: external-effect paths are structurally forced through the governed boundary
> or they fail closed. It does NOT mean production writes are enabled**, it registers no production
> policy gate (the production `GateRegistry` population stays EMPTY until U8.1 / P8), and it grants
> no autonomy of any kind. The capability still ships **dark**.

---

## Position

**The block below is machine-maintained and machine-verified.** It is written by
`scripts/update_current_status.py` from `git rev-parse` and a real suite run — never by hand — and
[`eval/tests/test_status_reality.py`](../../eval/tests/test_status_reality.py) fails the build when
it disagrees with the checked-out commit. The zero-context rehearsal proved a hand-maintained
version of this block goes stale within one commit and nothing notices.

```yaml
# status-block: maintained by scripts/finalize_status.py - do not edit by hand
recorded_authoring_branch: p5/u5-1-g2-spec-correction   # advisory; not verified across bundles/clones
content_commit: 761fcd78cf3196368bb27ec824a5e4c966b8d6eb
content_tree: 04932bbd4f746e9545038ed1500dbda0b31bc0dc
suite_passed: 2860
suite_failed: 0
suite_skipped: 1
```

> ### **The two-commit convention (why this block can be truthful):** a commit cannot contain its
> own hash, so a self-referential "current commit" field is impossible and claiming one would be a
> lie. Instead: every substantive change lands in a **content commit**; the finalization script
> then records that commit here and the record lands in **exactly one status-metadata commit
> directly on top**, touching only the status files. `HEAD` is therefore either the content
> baseline itself or that one metadata commit — and the guard verifies exactly this relationship,
> including that the metadata commit changed nothing else.

| | |
|---|---|
| **The one skip** | Conditional and self-describing: *"no red-by-design cases remain: AC-SAFE-012/013 went green at Phase 1"* |
| **Working tree** | clean |
| **Suite counts elsewhere** | ### **Volatile commit/tree/suite figures live ONLY in the block above.** Other files link here instead of copying numbers — the rehearsal found the old figure duplicated into five files, all stale. |

## Completed phases

| Phase | Status | Evidence |
|---|---|---|
| **P0** — baseline & anti-false-green infrastructure | ### **COMPLETE** | [`phase-0-implementation-review.md`](phase-0-implementation-review.md) · `d33f251` |
| **P1** — correct effect identity (Commit Key) | ### **COMPLETE** | [`phase-1-implementation-review.md`](phase-1-implementation-review.md) · `149c02a`, `da07936` |
| **P2** — tenant-safe persistence | ### **COMPLETE** | [`u2-6bc-blocker-6-final-phase-2-review.md`](u2-6bc-blocker-6-final-phase-2-review.md) · `7d72498` |
| **P3** — checkpoint, witness, claim CAS | ### **COMPLETE** | [`phase-3-implementation-review.md`](phase-3-implementation-review.md) — the implementer's record · [`p3-independent-review-findings.md`](p3-independent-review-findings.md) — the first INDEPENDENT review, which P3 **did not pass** (9 findings, 60/100) · [`p3-findings-remediation-review.md`](p3-findings-remediation-review.md) — the remediation · [`p3-genuine-independent-review.md`](p3-genuine-independent-review.md) — the FRESH independent review of the remediated, finalized tree, **PASS** (zero new defects, 13/13 hostile probes) · [`p3-final-adjudication-review.md`](p3-final-adjudication-review.md) — ### **the FINAL ADJUDICATION: all 14 weighted criteria PASS, P3 recorded COMPLETE.** The kernel still ships dark. ### **Completing P3 did not close R-07 — and neither did completing P4:** R-07 closed only when a separate content commit, made after both P4 finalization passes, wrote the CONTAINED record into `phase-0-baseline-manifest.yaml` |
| **P4** — adapter containment | ### **COMPLETE** | [`p4-independent-review-report.md`](p4-independent-review-report.md) — the first INDEPENDENT review, which candidate `95cf5af7` **did not pass** (REJECT — remediation required) · [`p4-independent-rereview-report-0891d1a.md`](p4-independent-rereview-report-0891d1a.md) — the FRESH INDEPENDENT re-review of the remediated candidate `0891d1a`, **ACCEPT FOR SEPARATE FINAL ADJUDICATION** · [`p4-final-adjudication-report-0891d1a.md`](p4-final-adjudication-report-0891d1a.md) — ### **the FINAL ADJUDICATION: all 14 weighted criteria PASS, P4 recorded COMPLETE** · [`p4-first-finalization-pass-report-86306d5.md`](p4-first-finalization-pass-report-86306d5.md) — the one canonical finalizer run. ### **This did NOT close R-07** — see the open-risks table |
| **P5** — events, outbox/inbox, replay isolation, PostgreSQL | ### **COMPLETE** | [`p5-independent-review-report-1216254.md`](p5-independent-review-report-1216254.md) — the FRESH INDEPENDENT review of the whole P5 surface, **ACCEPT FOR SEPARATE FINAL ADJUDICATION**, **zero material blocking defects**, 45/45 hostile probes (eight of which it reported as its *own* defective probes rather than only the corrected results) · [`p5-final-adjudication-report-91ba4e6.md`](p5-final-adjudication-report-91ba4e6.md) — ### **the FINAL ADJUDICATION: all 14 weighted criteria PASS, 100/100, P5 recorded COMPLETE.** What it certifies: the **118 canonical event contracts** (105 machine-emitted F1–F13 + 13 audit/security F14) with the upcaster; the **transactional outbox** and **dedup inbox**; the **GC-1 golden corpus**, deterministic **replay** and **audit reconstruction**; **durable timers** (M-36); and the runtime on **production PostgreSQL** (ADR-016). The adjudicator re-executed the canonical suite, the clean-clone gate, the PostgreSQL gate against a database it created, both mutation batteries (24/24 · 37/37) and its own import-closure probe. ### **P5 ships dark — zero production callers.** |
| **P6–P14** | **NOT STARTED** — `P6` is the sole `READY` unit | [`PHASE-OUTPUTS.md`](PHASE-OUTPUTS.md) |

## Completed acceptance gates

| Case | Status |
|---|---|
| **AC-SAFE-012** | ### **GREEN** |
| **AC-SAFE-013** | ### **GREEN** |
| **AC-SEC-001** | ### **GREEN at the Phase-2 AND Phase-3 surfaces** (records, grants, api + witnesses, leases). Five surfaces deferred by phase: events (P5), mappings (P9), credentials (P4), cache keys (P4), adapter calls (P4). |
| **AC-CKPT matrix** | ### **GREEN — all 105 merge-gating cases** (7 steps × 15 conditions on the universal oracle), [`test_phase3_checkpoint_matrix.py`](../../eval/tests/test_phase3_checkpoint_matrix.py) |
| **G0** | passed |
| **G1–G10** | not reached |

## Exact counts *(recomputed mechanically, not transcribed)*

| Quantity | Count |
|---|---|
| **Canonical table partition** *(exact, disjoint, guarded — 7 + 1 + 3 + 2 + 1 + 4 + 2 = 20)* | |
| — Phase-2 **migrated** tenant-owned tables | **7** — `workflow_runs`, `audit_events`, `security_events`, `operation_action_claims`, `delivery_action_claims`, `effect_grants`, `operation_token_amounts` |
| — **Already tenant-first before P2** (the eighth tenant-first table, migrated by nobody) | **1** — `autonomous_run_counters` |
| — Tenant-**exempt** bookkeeping tables | **3** — `schema_migrations`, `migration_quarantine`, `owner_assertions` |
| — **Phase-3** tenant-owned tables | **2** — `checkpoint_witnesses` (append-only by trigger), `brakes` |
| — **Phase-3** tenant-exempt table | **1** — `platform_brake` (the ONE global admission brake, SD-12 — by definition nobody's tenant data) |
| — **Phase-5** tenant-owned tables *(the durable event transport, U5.7+U5.8)* | **4** — `event_outbox` (envelope columns immutable by trigger), `event_inbox` (fully append-only), `inbox_aggregate_cursor`, `pending_references`. ### **P5 adds NO tenant-exempt table** — tenant is the FIRST partition dimension of every store, stream and inbox [C-1], so "whose event is this" has no honest answer other than a tenant |
| — **Phase-6** tenant-owned tables *(the entity layer, P6-U1)* | **2** — `tenant_humans` (the recorded, attributed human authority; identity and recording act immutable by trigger, never deleted — a human is OFFBOARDED), `work_items` (owner is a FOREIGN KEY into it, required ACTIVE at assignment; terminal states final by trigger; version advances by exactly one). ### **P6 adds NO tenant-exempt table** — a tenant-exempt roster would be an authority nobody scoped, and a tenant-exempt Work Item an obligation nobody owes |
| — Canonical tables **total** | **20** — exactly the union of the seven sets above |
| `WorkflowStore` methods, tenant-scoped + readiness-gated | **22 / 22** |
| `WorkflowStore` construction sites *(the AC-SEC-001 sweep)* | **168** — 166 with an explicit tenant, 2 registered refusal probes |
| Guard files / guard tests *(discovered by `guard_files()`, never enumerated — the transcribed "25 / 367" figure is retired: no executable source ever computed it. **Method, stated so the figure is reproducible:** files = `len(test_phase2_guard_registry.guard_files())`; tests = the AST count of `def test_*` functions across those files — test FUNCTIONS, not collected nodes, so parametrization does not inflate it)* | **42 / 631** *(was 38 / 578, then 41 / 624 after the P3 findings remediation added three guard files — ledger compatibility, step order, observability — and 46 test functions; the N-1 receipt-consistency correction then added one guard file — the BUILD-STATUS receipt-consistency guard — and 7 test functions)* |
| Canonical transitions | **134** |
| Canonical emitted events | **105** |
| Canonical loops | **11** |
| Domain entities | **40** · adapters **18** · safety invariants **28** |
| **AC-CKPT checkpoint matrix** | **105 / 105 GREEN** (7 steps × 15 conditions) |

## ⛔ Open risks and findings — R-07 is CLOSED; every other residual below is CARRIED, not discharged

**Nothing on this page was discharged by the R-07 closure.** R-07 is the only line that changed
state, and it changed because a record was written, not because a residual was waived.

| ID | Finding | Status | Closes at |
|---|---|---|---|
| **R-07** | Ungated live-write paths | ### **CONTAINED** — recorded in [`phase-0-baseline-manifest.yaml`](phase-0-baseline-manifest.yaml) (`expected_legacy_paths.status: CONTAINED`) with the mechanism named | ### **CLOSED** by the separate R-07 content commit |
| — | ### **HOW R-07 CLOSED, AND WHAT CLOSING IT DOES NOT MEAN.** The **mechanical** close condition was met and independently verified — the effect-capable violation surface is EMPTY with the CI import gate asserting empty, 0 live / 0 recorded violation edges agreeing both-sided, positively anchored by 152 inspected sources and 13 live detection edges. That was never sufficient on its own: the **recording** lives in `phase-0-baseline-manifest.yaml`, which is **not** in `STATUS_METADATA_FILES`, so it could ride in neither finalizer's commit. It required its own content commit **after** the acceptance-closure candidate was independently reviewed, separately adjudicated and finalized — and that commit is what wrote `status: CONTAINED`. ### **CONTAINMENT MECHANISM:** an external effect can be produced only by an effect-capable adapter; the only application-layer importer of one is `effect_boundary`; the import gate fails the build if a second appears; and inside the boundary the sole external-write path is `execute_invoice_write`, behind checkpoint → witness → grant → atomic claim. **Anything that cannot present that chain REFUSES — it does not fall back.** ### **CONTAINED ≠ ENABLED:** no production write is enabled, the deployed route answers a recorded `ROUTE_NOT_CONFIGURED` refusal, the production `GateRegistry` population is EMPTY until U8.1 / P8, and **no autonomy — bounded or otherwise — was granted.** | ### **CONTAINED** | ### **CLOSED** |
| — | **6 production-reachable live-write paths** — EP-1, EP-3, EP-6, EP-7, EP-9, EP-10 (the P0 baseline finding) | ### **CUT AND RECORDED** — EP-6/7/9/10 physically deleted (on-disk absence proved), EP-3/EP-8/EP-14 structurally read-only, EP-1's write half routed through the governed boundary | ### **CLOSED at P4 / R-07** |
| — | **31 direct adapter-import edges** across 18 importer modules (the P0 baseline finding) | ### **RESOLVED AND RECORDED** — 0 effect-capable violation edges remain; 13 authorized detection edges | ### **CLOSED at P4 / R-07** |
| — | P4 CHECKPOINT (P4-CP-1): EP-6/7/9/10 **DELETED** → 2 live-write paths remained (EP-1, EP-3); edges cut 31 → 20; effect-capable gate violations 12 → 5 | superseded by later P4 work | — |
| — | P4 CONTAINMENT CUTOVER CHECKPOINT (P4-CP-2): findings **F1 + F4 fixed** (F1 = EP-12's live `--browser` path removed + AST structural quarantine proof; F4 = a generic post-attempt adapter exception becomes UNKNOWN_OUTCOME, never CLAIMED, never FAILED); **brain_runtime → tms_write edge cut** by injection; the **orphan-effect detective sweep mechanism implemented and mutation-proven** (`run_detective_sweep` is its per-cycle invocation surface; **no production/runtime caller exists yet** — production scheduling is deferred to P11 and the boundary still ships dark); gate violations **5 → 4**, edges **20 → 18**, importer modules **14 → 13**. The four violations then outstanding (EP-1, EP-3, EP-8, EP-14) and finding **F2** were deferred at that checkpoint and have since been closed — see the milestone section | superseded by later P4 work | — |
| — | **RR-01 — a BINDING P12 PRECONDITION, NOT DISCHARGED.** `base_url` is outside `payload_hash()`'s canonical set and outside `approval_operation_mismatch`, so a tampered stored proposal row can carry a foreign target URL past the integrity anchor; two docstrings overclaim that every consequential value is hash-bound. Compounded by **F-09** (an empty `base_url` skips the loopback refusal) and **F-08** (approved-field *values* unconstrained and interpolated into an LLM task). Contained today only because the capability is dark and the deployed route is fail-closed | ### **OPEN — must be discharged before any live writer is injected** | **P12** |
| — | **AD-01** — `EFFECT-PATH-INVENTORY.yaml` and `LEGACY-DISPOSITION.md` said the deployed callback server leaves `governed_write_provider`/`governed_write_kernel` as `None`. Mechanically false for the **provider**: it is **WIRED** (a bounded lookup, `writer=None`); the **kernel** is `None`, deliberately, pending Phase 8. The operative conclusion — the route is unreachable and fails closed — was and is true. ### **The prose in both files is CORRECTED by the R-07 closure commit; the stale "provider is `None`" wording must not reappear.** The finding is **carried, not discharged**: it stays recorded so a reintroduction is recognisable | ### **CARRIED — prose corrected, finding NOT discharged** | remains recorded; re-verify at P12 wiring |
| — | **AD-02** — `finalizer_lock.py` is a 188-line safety-critical module with **zero committed test coverage**: no references under `eval/`, no nodes in [`TEST-NODE-MANIFEST.json`](TEST-NODE-MANIFEST.json), no mutant. Verified sound 16/16 twice, but only ad hoc — and it is directly load-bearing for the next finalizer run | OPEN, recorded, non-blocking | a committed hostile battery + manifest regeneration |
| — | **RR-02 · RR-03 · RR-04 · RR-05 · RR-06 · F-03 · F-06 · F-07 · F-10** — the remaining residuals the independent re-review and the final adjudication retained; each is recorded in full, with its severity and disposition, in the P4 unit's `residual_risks_carried_forward` block in [`IMPLEMENTATION-REGISTRY.yaml`](IMPLEMENTATION-REGISTRY.yaml) | OPEN, recorded, non-blocking | as recorded per finding |
| — | ### **P5 RESIDUALS — `IR-R5`…`IR-R12`, carried out of the independent review and NOT discharged by the adjudication.** The load-bearing ones: **`IR-R7`** — GC-1 does not span a schema version change, because every canonical contract is at v1, so `AC-EVT-009` is proven through the **real** replay path against a **test-only** versioned contract set. Minting a production v2 to satisfy a fixture would amend a protected specification under authority P5 does not hold; a guard goes red the day a contract leaves v1. ### **That is the honest disposition, not a gap.** **`IR-R8`** — `AC-EVT-003` (every producer transition emits its required event in its own commit) **cannot be proven at P5**; the 134 transitions are P6's. **`IR-R9`** — `AC-EVT-011` and the `ProvenanceStrengtheningAttempted` (F14) **emission** half of `AC-EVT-013` are unimplemented; ### **the dangerous half is CLOSED** (laundering is refused across four evasion shapes) and what is missing is the audit *record* of an attempt — provenance is P5's `prohibited_scope`. `IR-R10`/`IR-R11`/`IR-R12` are prose-overstates-in-the-safe-direction, a discarded advisory timer payload, and unenforced `relay_id` uniqueness whose only consequence is duplicate delivery the dedup inbox makes free | OPEN, recorded, non-blocking | `IR-R8` → **P6** · `IR-R9` → **P7** · `IR-R7` → the day a contract leaves v1 · rest as recorded |
| — | **ADJ-P5-01 · ADJ-P5-02** — record-accuracy defects the **final adjudication** found, of the same `IR-R1` class the independent review recorded: `BUILD-STATUS.yaml`'s authored `snapshot:` block asserted *"The event contracts, GC-1 corpus, replay sandbox, audit reconstruction and PostgreSQL do not exist"*, *"the transport is SQLite only"* and *"U5.1 … IS STILL UNREVIEWED"*; and two further stale instances survived in this file and in the registry comment above P5's status fields. ### **The finalizer-maintained `derived:` block and every machine-read field were correct throughout** | ### **CORRECTED by the P5 closure commit** — a snapshot asserting P5's infrastructure does not exist cannot ride in the commit that records P5 COMPLETE | ### **CLOSED** |
| — | ### **ADJ-P5-03 — a scope boundary, stated rather than waived.** P5's `rebaseline_contract` sets `readiness_target: STAGING_READY` for the persistence infrastructure. ### **THAT TARGET IS NOT MET AND IS NOT CLAIMED MET.** The PostgreSQL surface is proven against a real server on a developer machine; it has **not** been deployed to a production-like staging environment with secrets, monitoring and operational controls, and the observability surfaces are query primitives rather than dashboards or alerting. `readiness_target` is a maturity target, **not** one of the 14 weighted acceptance criteria, and ADR-016 assigns deployment and environments to P11 — the gate receipt says so itself | OPEN, recorded, non-blocking | **P11** |
| — | **Transition/event completeness — G2 ADJUDICATED; ITS SEVEN EVENT OBLIGATIONS DISCHARGED.** The predicate is settled and mechanised (interpretation C, HYBRID): a *producer transition* is one declared in `events/registry.md` §3 — **117 of the 134 rows; the other 17 are non-producer transitions** — and completeness is `GR-2` over durable writes. All 134 rows carry structured classification (117 PRODUCER · 9 CONSUMES · 6 NON_PRODUCING · 2 DELEGATES_TO · 0 EVENT_REQUIRED); prose is never a classifier and an undecidable row fails the build. `EF-3` is re-attributed to the **existing** `EffectExecuted`. ### **`CONSUMES` IS PROVEN, NOT ASSERTED.** A durable-writing consumer must satisfy `CONSUMES-VALID`: a **bidirectionally declared co-commit** in both rows' `Writes` cells, a **different machine**, **not mutually exclusive** with the owner, and every persisted field carried by a consumed event's `state-machines/registry.md` §5 payload — undecidable **fails the build**. The first U5.1 candidate's version of this class was self-certifying and was **rejected**: it let `AP-9` be relabelled `CONSUMES:BrakeReleased` and stay green. `PL-15x` and `IB-5x` are `NON_PRODUCING` (their event's producer is the *rule* `GR-1`, not a transition). ### **`DELEGATES_TO` IS BOUNDED BY TRIGGER TYPE TOO** — a delegating row's `Trig` set must intersect each target's, which is what refuses `PL-7a → PL-7b` (`S` against `H`: the autonomous path may not be recorded by an event asserting a bound human approval). ### **THE RECORDED FINDING — *"7 transitions perform durable writes and name no event outright"* (`PL-7a`, `AP-9`, `CF-7`, `EC-7`, `PO-2`, `PO-3`, `RU-8`) — IS DISCHARGED, AND IS KEPT HERE IN ITS ORIGINAL WORDS SO THE FINDING SURVIVES ITS OWN REPAIR. THE SEVEN NOW HAVE SEVEN MINTED CANONICAL EVENTS** (`AutonomousAdmissionRecorded`, `ApprovalFrozen`, `ConflictPartyAttached`, `ExceptionSeverityChanged`, `PolicySubmitted`, `PolicyApproved`, `RuleExpired`), minted 2026-08-12 under founder/architect authority; the registry moved **98 → 105**, `PolicyProposed` stayed PO-1's, and every discharge is re-proven mechanically on each run. The obligations are **retained**, marked discharged, in [`TRANSITION-EVENT-AUDIT.yaml`](TRANSITION-EVENT-AUDIT.yaml). The retired "24-name-no-event" figure and the retired "121/13" split were never correct | ### **EVENT OBLIGATIONS DISCHARGED — residuals `G2-D4`/`D6`/`D8`/`D9`/`D10` OPEN** | **G2 residuals `G2-D4`/`D6`/`D8`/`D9`/`D10` — each at the unit authorized for its surface; none blocks P6.** ### **THIS CELL USED TO READ *"G2 residuals; P5 event infrastructure still unbuilt"*, WHICH WAS TRUE WHEN WRITTEN AND IS FALSE NOW** — that infrastructure is built, independently reviewed and separately adjudicated at 14/14, as this row's own `Status` cell and this file's P5 record both state. Preserved in its own words because a finding must survive its own repair |
| — | **PD-02 — the Product Driver's commit-topology warning is a TOOLING defect, not a repository conflict.** The driver reports `topology: BLOCKED_AUTHORITY` and a `max_content_commits` of **7**. The G2 adjudication proved this mechanically: `neyma_product_driver/protocol_sources.py`'s `_CONTENT_COUNT_RE` uses a `\d{1,2}` alternative behind a `\b`, which matches between a hyphen and a digit, so *"CLOSED by the separate **R-07** content commit"* is read as the cardinal **7**. The bad value is **consumed**, not merely displayed. ### **Repository authority is NOT contradictory: the rule is exactly ONE content commit, then exactly ONE finalizer-generated metadata commit** ([`PROGRESS-PROTOCOL.md`](PROGRESS-PROTOCOL.md) §10, `integration-topology-procedure.md`). A session must take commit topology from those two documents only and treat the driver's `BLOCKED_AUTHORITY` output as non-authoritative on this point. The fix is a one-line regex hardening **outside this repository** | OPEN — inherited governance/tooling residual, non-blocking; **rank-1 for the Product Driver** | Product Driver, not a product unit |
| — | **P6-D8 — the "42 / 631" guard-file figure in the Exact-counts table is STALE, and it is not reproducible from outside pytest.** The stated method (`len(test_phase2_guard_registry.guard_files())` and the AST count of `def test_*` across those files) returns a DIFFERENT answer depending on how the module is imported, because `guard_files()` mutates `sys.path` and the central inventory reads `git ls-files` relative to the invocation. Measured 26/708 and 52/1105 from two invocation styles on the same tree. P6-U1 adds one guard file and 186 test functions, so it is now stale in a fourth way. ### **RECORDED, NOT ACTIONED (§13.3): no number is guessed here, because the honest fix is to make the method invocation-independent and have the figure derived rather than transcribed** — which is guard-tooling work, not a product unit | OPEN, recorded, non-blocking — **no executable source asserts this figure**, so nothing depends on it | the guard-tooling unit that makes the derivation invocation-independent |
| — | Hardcoded knowledge-base `tenant="default"` — `ops_control.py` ×5, `action_callback.py::_learn_correction` (the `KnowledgeBase(...).learn` call) | OPEN | the phase that makes the KB tenant-safe |
| — | ~~Checkpoint Witness + seven-step checkpoint + claim CAS unimplemented~~ | ### **RESOLVED at P3** — the kernel exists and ships dark | **P3 ✅** |
| — | ~~Adapter containment unimplemented~~ | ### **RESOLVED at P4** — the containment mechanism exists and is adjudicated 14/14, and the separate act of recording R-07 CONTAINED has now been made | **P4 ✅ · R-07 ✅** |
| — | **F-TR-01 · F-TR-02 · F-TR-03 · F-TR-04** — the four documentation-consistency defects the targeted adjudication of `42ea24c` classified as real, non-blocking for the second finalizer and **binding on the next content commit** (`ARCHITECTURE.md` and `AGENTS.md` describing P4 incomplete, `AGENTS.md` implying P4 alone closes R-07, `FREIGHT-CAPABILITY-MAP.md` stale, `EFFECT-PATH-INVENTORY.yaml`'s free-text "P4 REMAINS NOT COMPLETE") | ### **REMEDIATED by the R-07 closure commit** | ### **CLOSED** |
| — | **ADJ-01** — the switch-consistency guard states the one-READY-unit invariant but its regex did not reach the `READY *(selected)*` / `the sole READY unit` constructions it claims to guard, so the very defect it exists to catch passed it | ### **REMEDIATED by the R-07 closure commit** — the completed-unit patterns are broadened and a new positive check requires the selected-READY construction to exist, to be singular, and to agree with the registry | ### **CLOSED** |
| — | **ADJ-02** — the P3 precedent's correction scope was not fully carried into P4 (`f579d92` corrected `AGENTS.md`, `ARCHITECTURE.md`, `CLAUDE.md`, `README.md`; `42ea24c` corrected only the latter two) | ### **PARITY RESTORED by the R-07 closure commit** | ### **CLOSED** |
| — | **Product Driver `BLOCKED_AUTHORITY` observation, reported during the second finalization.** Classified as a **pre-existing prose-extraction ambiguity in the external driver's protocol resolver**, not a failed repository guard: no repository guard reported it, `progress_status.build_status_errors()` was `[]`, `repo_state()` was legal, and the canonical suite was green | OPEN, recorded, non-blocking — **not discharged** | the driver's own resolver work; re-observe each finalization |
| — | **Production Action Class gate registration** — the production `GateRegistry` population is **EMPTY** and must stay empty; `AC-CKPT-6-missing` remains `DEFERRED_BY_DEPENDENCY - REQUIRED AT PHASE 8` | ### **DEFERRED BY FOUNDER DECISION — unchanged** | **U8.1 / P8** |
| — | **No firsthand design-partner observation recorded by any agent** | OPEN | [`design-partner-observations.md`](../product/design-partner-observations.md) |
| — | Repository legacy reduction unfinished | OPEN | [`LEGACY-DISPOSITION.md`](LEGACY-DISPOSITION.md) |

> ### **HISTORICAL — SUPERSEDED BY THE R-07 CONTAINMENT RECORD.** From P0 until P4 this page read:
> *"The only mitigation for R-07 is the operator's one-writer-at-a-time discipline. That is
> discipline, not a mechanism, and it may NEVER be recorded as containment."* It was correct for
> every day of that life. R-07's mitigation is now a **mechanism**, recorded in
> [`phase-0-baseline-manifest.yaml`](phase-0-baseline-manifest.yaml).
> ### **THE RULE BEHIND THE OLD SENTENCE DOES NOT EXPIRE: discipline is still never containment,
> and no allowance may ever be read as one.** What changed is that there is now a mechanism to read.
>
> ### **Phase 2 made tenant ownership real at persistence boundaries.**
> ### **Phase 2 did NOT make external effects safe.**
>
> ### **Neither does P4's completion, by itself, make them safe in the record.** The mechanism is
> built and independently verified; the containment *record* is one further content commit away,
> and no production write is enabled by any of it. Nothing was pushed, merged, deployed or enabled.

## Current implementation milestone

**P5 — CANONICAL EVENTS, OUTBOX/INBOX, REPLAY ISOLATION AND PRODUCTION PERSISTENCE** —
### **ADJUDICATED COMPLETE. 14/14 WEIGHTED CRITERIA PASS. 100/100.**
Accepted independent review:
[`p5-independent-review-report-1216254.md`](p5-independent-review-report-1216254.md);
final adjudication:
[`p5-final-adjudication-report-91ba4e6.md`](p5-final-adjudication-report-91ba4e6.md).

> ### **How P5 reached COMPLETE.** The adjudicated **content commit is `91ba4e6`** (tree
> `05baa45`). Its weighted acceptance contract was instantiated from the **frozen**
> `acceptance_template` in [`PROGRAM-WEIGHTS.yaml`](PROGRAM-WEIGHTS.yaml): exactly 14 criteria,
> weights summing to exactly 100. A **FRESH INDEPENDENT REVIEW** of the P5 surface at content commit
> `1216254` returned **ACCEPT FOR SEPARATE FINAL ADJUDICATION** with **zero material blocking
> defects**; a **SEPARATE FINAL ADJUDICATION** — by a session that neither implemented, remediated,
> reviewed nor finalized P5 — then set all fourteen results. ### **The runtime delta between the
> reviewed tree and the adjudicated tree is ZERO:** the two commits in between touched only
> `docs/implementation/`, so the review binds in full.
>
> ### **THE ADJUDICATOR REPRODUCED THE EVIDENCE RATHER THAN READING IT.** It ran the canonical suite
> (**2674 · 0 · 1**); re-executed the **clean-clone gate** (9/9 steps exit 0, reproducing the same
> counts in a fresh clone with declared dependencies only); re-executed the **PostgreSQL P5 gate**
> against a database it created itself (26 migration steps, **0 on replay**, 8 invariants REFUSED,
> 2 positive controls ACCEPTED, 17 runtime probes PASS); re-ran both **mutation batteries**
> (replay/audit **24/24**, contracts **37/37**, byte-exact tree restoration); re-derived
> `event_contracts_data.json` from the specification; and wrote its **own import-closure probe** —
> reporting that its first version was defective and could not have failed, before correcting it and
> proving it with a positive control that fires.
>
> ### **`canonical_finalizer` (weight 3) was `PENDING` at adjudication by construction** — a
> finalizer cannot have run on the candidate being adjudicated — and is `PASS` on the one finalizer
> run that had already executed on `91ba4e6` (metadata commit `4150149`, single parent, exactly the
> five authorized status files). This is the identical pattern by which P4's became `PASS`.
>
> ### **WHAT P5's COMPLETION IS NOT.** It is **not** permission to begin P6 yet — this closure commit
> owes its own targeted review, targeted adjudication and one finalizer first. It is **not** a
> production enablement: **P5 ships dark with zero production callers**, R-07 stays **CONTAINED**,
> the production `GateRegistry` population stays **EMPTY** until U8.1 / P8, and the deployed governed
> route still answers `ROUTE_NOT_CONFIGURED`.

**What P5 bought, concretely:** Neyma can now hold durable operational state that survives crashes
and can be rebuilt from history without ever re-executing an effect. A state change and the events
it emits commit atomically or not at all — a crash between them leaves **neither**. Consumption is
idempotent, so a redelivery is a no-op rather than a second effect, and a raising handler records
nothing at all. Out-of-order events **park** and drain in version order; an event referencing
something that does not exist yet parks **with its accountable human** and is drained or expired,
never dropped. State rebuilt from history is a pure function of the event **set** — stable across 40
shuffles — and an audit can explain a past decision using **the beliefs of that day**, naming the
fields it cannot reconstruct instead of inventing them. Timers survive a full restart and fire
exactly once. All of it runs on **production PostgreSQL** with the durable invariants enforced by
database trigger, and **replay cannot call an adapter because the capability is not reachable** —
`event_replay`'s entire transitive import closure is five inert modules.

---

**P4 — ADAPTER CONTAINMENT** — ### **ADJUDICATED COMPLETE. 14/14 WEIGHTED CRITERIA PASS.**
Accepted independent re-review:
[`p4-independent-rereview-report-0891d1a.md`](p4-independent-rereview-report-0891d1a.md);
final adjudication:
[`p4-final-adjudication-report-0891d1a.md`](p4-final-adjudication-report-0891d1a.md);
the one canonical finalizer run:
[`p4-first-finalization-pass-report-86306d5.md`](p4-first-finalization-pass-report-86306d5.md);
legal-topology determination:
[`p4-closure-content-topology-determination.md`](p4-closure-content-topology-determination.md).

> ### **How P4 reached COMPLETE — and what each session was allowed to do.**
> The adjudicated **implementation candidate is `0891d1a`** (tree `a3e70464`). Its weighted
> acceptance contract was instantiated from the **frozen** `acceptance_template` in
> [`PROGRAM-WEIGHTS.yaml`](PROGRAM-WEIGHTS.yaml): exactly 14 criteria, weights summing to exactly
> 100. Thirteen results were set by a **separate final adjudication** from independent evidence.
> The fourteenth, `canonical_finalizer` (weight 3), was `PENDING` there by construction — a
> finalizer cannot have run on a candidate that is being adjudicated — and is `PASS` on the one
> finalizer run that has since executed. 14/14 PASS → **100/100** → P4 **COMPLETE**.
>
> ### **THE FULL REVIEW HISTORY, PRESERVED — P4 FAILED ITS FIRST INDEPENDENT REVIEW.** Candidate
> `95cf5af7` was **REJECTED** ([`p4-independent-review-report.md`](p4-independent-review-report.md),
> preserved byte-exactly at `refs/preserve/p4-independent-review-95cf5af` and carried in-tree with a
> disarming banner as its only modification) on two blocking findings: **F-01**, the decision half
> and the execution half of the governed write shared no authority; and **F-02**, an empty or absent
> URL filter permitted cross-origin navigation. A **remediating session that was neither reviewer
> nor adjudicator** produced `0891d1a`. A **FRESH INDEPENDENT re-review** then re-derived the whole
> 46-file unit diff from source — inheriting nothing from the handoff, and contradicting it where it
> was wrong — and returned **ACCEPT FOR SEPARATE FINAL ADJUDICATION**. A **separate adjudicating
> session**, which did not implement, remediate or review P4, discharged both findings on evidence
> it reproduced itself and set the fourteen criteria.
> ### **No session adjudicated its own work, and the session recording this transition implemented,
> reviewed and adjudicated nothing — it transcribes.**
>
> ### **The finalizer and clean-clone gate EXECUTED and PASSED on candidate `0891d1a`.**
> `scripts/finalize_status.py` exited **0** under a single exclusively-held `finalizer_lock`,
> executing the canonical suite in-process, the clean-clone gate (nine steps, all exit 0, bound to
> `0891d1a` / `a3e70464`), the control guards and the AC gates. It wrote metadata commit `86306d5`,
> touching exactly the five authorized status files and nothing else. **No finalizer receipt was
> forged, and none was written for this closure commit** — this commit is a *content* commit and
> owes its own finalization after its own independent review and adjudication.
>
> ### **WHAT P4's COMPLETION WAS NOT.** It was **not** R-07 closed — that took a **separate content
> commit**, made after both finalization passes, which is what actually wrote the CONTAINED record
> (see the open-risks table). It is **not** permission to begin P5. It is **not** a production
> enablement: the capability still ships dark, the deployed governed route still answers
> `ROUTE_NOT_CONFIGURED`, and the production `GateRegistry` population is still **EMPTY** by founder
> decision until U8.1 / P8. ### **The same is true of the R-07 closure itself: recording CONTAINED
> enabled nothing.**

**What P4 bought, concretely:** an external effect without a grant is now structurally impossible
rather than merely discouraged. The governed write route is production code with exactly one
production caller for the checkpoint join, reachable from the authenticated Slack callback; one
continuous approval identity travels from the signed envelope through the queued intent, the
checkpoint witness row, the `effect_grants` row and the typed operation the adapter itself receives;
nineteen hostile classes refuse with **zero** external attempts; repeated and concurrent delivery
produce exactly one attempt and one grant; `UNKNOWN_OUTCOME` escalates to a named human and can
never auto-retry a possibly-completed write; the navigation origin is a parsed, operator-established,
immutable origin that fails **closed** when absent or malformed; and the CI import gate asserts the
effect-capable violation surface is **EMPTY**, positively anchored rather than vacuously so.

### **P4's containment ships dark too.** The deployed callback server wires the lookup boundary and
leaves the execution kernel `None`, so the governed route reaches the seam and stops at a **recorded**
`ROUTE_NOT_CONFIGURED` refusal with zero grants minted. That is deliberate: registering production
Action Class gates is U8.1 / P8 work, and a refusal that is recorded with a named cause is strictly
more contained than an execution.

---

**P3 — CHECKPOINT WITNESS, SEVEN-STEP ATOMIC CHECKPOINT, AND CLAIM CAS** —
### **ADJUDICATED COMPLETE** (the phase P4 was built on).
Implementer's record: [`phase-3-implementation-review.md`](phase-3-implementation-review.md);
final adjudication: [`p3-final-adjudication-review.md`](p3-final-adjudication-review.md).

> ### **How P3 reached COMPLETE.** Its weighted acceptance contract has 14 criteria. Twelve were
> supplied by the implementing lineage; **`independent_review` (weight 5) and `final_adjudication`
> (weight 4) could not be** — by construction they require a session other than the implementing
> one, which is why P3 stood at **91/100 at best** until a different session closed them. All 14 are
> now `PASS`, so under [`PROGRESS-PROTOCOL.md`](PROGRESS-PROTOCOL.md) §3 the phase computes to
> **100/100** and P3 is recorded **COMPLETE**.
>
> ### **THE FULL REVIEW HISTORY, PRESERVED.** The first INDEPENDENT review (commit `38f2714`)
> returned **9 findings — 1 CRITICAL, 3 HIGH, 3 MEDIUM, 2 LOW — 60/100, `NOT READY`**
> ([findings](p3-independent-review-findings.md)); **P3 did not pass it.** All nine were
> **remediated** ([dispositions](p3-findings-remediation-review.md)) by a session that was neither
> the reviewer nor the adjudicator. A **FRESH INDEPENDENT** review of the remediated, finalized tree
> then **PASSED** with zero new defects and 13/13 hostile probes
> ([`p3-genuine-independent-review.md`](p3-genuine-independent-review.md)). Finally, a **separate
> ADJUDICATING session** — which did not implement P3, perform either review, remediate the
> findings, normalize the git history, correct N-1, or author the genuine review — set the 14
> criteria from that evidence ([`p3-final-adjudication-review.md`](p3-final-adjudication-review.md)).
> ### **Remediation is not adjudication, and no session adjudicated its own work** — the two-key
> discipline held end to end.
>
> ### **The finalizer and clean-clone gate EXECUTED and PASSED on the finalized P3 tree.** The
> CRITICAL finding (F-A) — a mis-anchored rebaseline-invariant guard that failed the canonical suite
> — is fixed; the earlier illegal-history deadlock (two unfinalized content commits) is resolved by
> consolidating the content and finalizing it. `SUITE-RESULT.json` (green) and `GATE-RESULT.json`
> (`passed: true`) bind to the recorded content commit and tree. The finalizer PRODUCED the status
> record by executing the suite, the clean-clone gate and the acceptance gates itself.

**What P3 bought, concretely:** the two-key rule is real. The seven checks run in canonical order
inside ONE transaction with the witness insert and the grant mint (`run_checkpoint` /
`seven_step_checkpoint`); `CheckpointPassed` has no public constructor and cannot be pickled,
copied, subclassed or reconstructed from history; the durable witness is append-only by database
trigger, tenant-first, 1:1 with its grant; `claim_grant_cas` performs the atomic
`GRANTED → CLAIMED` revalidating state, expiry, brake token and policy version inside the
UPDATE's own WHERE clause; the brake store enforces the one-way ratchet (automation may
engage/widen, never release/narrow, no TTL exists); and the fp_v1 fingerprint makes drift
byte-decidable with a field-level diff (the F-01 case names the amount, old → new). The ledger's
strict one-row-per-effect index was replaced by the **live-hold** form so a provably-dead grant
(EXPIRED_UNCLAIMED / REVOKED / FAILED) frees its commit key for the safe re-checkpoint the crash
semantics require — VERIFIED and UNKNOWN_OUTCOME hold their keys forever.

### **P3 SHIPPED DARK.** No production path routed through the kernel at P3; the capability became
load-bearing only when **P4** contained the adapters behind it. **Completing P3 did NOT close
R-07** — the six live-write paths were physically untouched by P3, exactly as its prohibited scope
required. P4 has since deleted EP-6/7/9/10, cut EP-1/EP-3/EP-8/EP-14 and routed the governed write
through the checkpoint kernel; ### **and R-07 STILL did not close there** — the CONTAINED record in
[`phase-0-baseline-manifest.yaml`](phase-0-baseline-manifest.yaml) cannot be written by a
status-metadata commit, so it took a further, separate content commit after both finalization
passes. ### **That commit has now been made, and R-07 is CONTAINED.**

### Gate history — ### **BOTH GATES ARE CLOSED**, all on independent evidence

> These two gates are closed. ### **Neither is a P3 review.** They predate P3 and say nothing
> about the checkpoint kernel; P3's own `independent_review` was performed **separately** (the
> genuine independent review of the remediated tree) and is now adjudicated `PASS`.
- **U-HANDOFF-1** — closed by U-HANDOFF-1D from the independent U-HANDOFF-2B hostile review
  ([`u-handoff-1d-final-adjudication-review.md`](u-handoff-1d-final-adjudication-review.md)).
- **U-REBASELINE-1** — RB-01..RB-24 ALL PASS, adjudicated by U-REBASELINE-1A from the INDEPENDENT
  U-REBASELINE-REVIEW-1 ([preserved report](u-rebaseline-review-1-independent-report.md) ·
  [adjudication](u-rebaseline-1a-founder-adjudication-review.md)).

The second hostile review — **U-HANDOFF-2B**, independent and repository-only — defended its
attack battery against the U-HANDOFF-1C-corrected controls, and U-HANDOFF-1D adjudicated all 13
checklist criteria **PASS** from that independent evidence (preserved verbatim, with its
transport truncation disclosed, in
[`u-handoff-2b-hostile-review-report.md`](u-handoff-2b-hostile-review-report.md)).

### The full rehearsal record — how the handoff gate closed
1. A **non-independent** rehearsal (the control-document author) returned **NOT READY** — the
   status authority was stale by one commit, unguarded. Corrected by **U-HANDOFF-1A**.
2. The **first INDEPENDENT rehearsal** (fresh session, repository-only) returned **NOT READY** —
   **11 of 13 criteria PASS; HANDOFF-03 and HANDOFF-12 FAIL.** Its decisive finding: the recorded
   green was **not clean-clone reproducible** (46 tests read a gitignored developer-local
   database; an undeclared dependency; an unenforced Python floor; a status guard that verified
   test COUNTS, not test RESULTS) — plus a contradictory `registry.md`, an unclassified root
   roadmap, eight graph inconsistencies, and figures (the since-retired "24 of 134", the since-drifted `:1639`, the unadjudicated "six") that no
   executable source computed. All corrected and guarded by **U-HANDOFF-1B**; the suite is now
   hermetic, the status record is artifact-backed, and the clean-clone gate
   (`scripts/clean_clone_gate.py`) is the reproducibility oracle.
3. The **second independent rehearsal** PASSED **13/13** — comprehension is proven. The
   subsequent **hostile formal handoff-readiness review** then attacked the CONTROLS and returned
   **NOT READY**: fabricated artifacts were accepted, pytest configuration could silently remove
   tests, skip detection covered a quarter of the suite, a live "24" contradiction survived in
   the registry, P6+ could bypass the safety wall, and guard populations were hand-enumerated.
   All corrected and mutation-proven (44/44) by **U-HANDOFF-1C**: status is now finalized only by
   [`scripts/finalize_status.py`](../../scripts/finalize_status.py), which EXECUTES the suite,
   the clean-clone gate and the acceptance gates itself.
4. **U-HANDOFF-2B — the SECOND HOSTILE review** (independent, repository-only, branch
   `hostile-review-fe7843d`) attacked the corrected controls: bootstrap, finalizer execution,
   clean-clone reproduction, node-manifest identity, skip enforcement, dynamic discovery,
   authority resolution, the safety graph, product identity and the tool-authority boundary,
   plus a false-confidence mutation battery — **all received attack rows DEFENDED, zero
   critical or high findings in the received sections**. Its verdict — READY FOR FINAL ZIP
   INSPECTION — is founder-attested; the received evidence body plus the adjudicating session's
   own re-execution of the finalizer, suite and clean-clone gate closed the gate. Adjudication:
   [`u-handoff-1d-final-adjudication-review.md`](u-handoff-1d-final-adjudication-review.md).

## The P4 execution record — how containment was actually built

> ### **This is the implementer's narrative, preserved and brought up to date.** It records what
> landed, in order. It is **evidence, not acceptance**: acceptance is the fourteen weighted criteria
> in [`IMPLEMENTATION-REGISTRY.yaml`](IMPLEMENTATION-REGISTRY.yaml), set by sessions that did not
> write any of this. Item 8's design note is explicitly marked where it has been **superseded** by
> what was built afterwards.

1. The **implementation checkpoint** (P4-CP-1): the containment boundary, the boundary-aware
   import gate, and the DELETE cutover of EP-6/7/9/10 — acceptance-proven (33 boundary cases) and
   mutation-proven (14/14 mutants caught).
2. The **containment cutover checkpoint** (P4-CP-2): the mandated review findings **F1** and
   **F4** are fixed, the **brain_runtime → tms_write** edge is cut by injection, and the
   **orphan-effect detective sweep** mechanism is implemented and mutation-proven
   (`run_detective_sweep` is its per-cycle invocation surface; **no production/runtime caller exists
   yet** — production scheduling is deferred to P11 and the boundary still ships dark). The boundary
   mutation battery is now **21/21** (added F4 B15/B16, F1
   B17/B18, brain_runtime B19, detective B20/B21). Gate violations fell **5 → 4**; edges **20 → 18**.
3. The remaining four violations (**EP-1, EP-3, EP-8, EP-14**) and finding **F2** (cdp_session.evaluate
   is an ungated actuation primitive) were DEFERRED at that checkpoint: each hinges on
   correctness-critical browser code with no live-browser/live-TMS runtime available to verify
   against, so per CLAUDE.md §9 they were NOT done blind. EP-1 in particular routes the
   OperationRouter→OperatorAgent autonomous browser write (the live R-07 write), whose containment
   is the P12-scale supervised-write integration.

4. **F2 built and verified, EP-8 cut.** **F2 is no longer deferred**:
   `cdp_readonly.ReadOnlyCdpObserver` is a genuinely read-only CDP surface with three independent
   barriers — no mutation API exists on it; caller data travels as `Runtime.callFunctionOn`
   `arguments`, never as source; the channel allowlists CDP methods and vetted scripts by exact
   value. The deferral's premise ("no live browser here") did not hold: Chrome for Testing launches
   in this environment and `scripts/verify_readonly_cdp.py` proves the surface against a real
   browser. **EP-8 is now CUT** on it (U4.7): `scripts/orient_tms.py` imports **no adapter module at
   all**, so it is structurally read-only rather than read-only by convention — the gap-matrix
   row-34 target state, reached by an absent API rather than a promise. Gate violations **4 → 3**;
   edges **18 → 16**; boundary mutation battery **24/24** (added EP-8 B22/B23/B24: re-import the
   actuator, re-import the mutation-capable session, smuggle the actuator in dynamically — all
   caught). The click-driven deep walk is **RETAINED, not deleted**, in
   `system_orientation.orient_system`/`orient_record_actions` for the authorized actuator-capable
   caller behind the effect boundary; what EP-8 loses is reach to it, not the capability itself.

5. **EP-3 cut.** `propose_ar_from_tms.py` holds a `ReadOnlyCdpNavigator` and imports
   no adapter module. Its browser surface was the worst remaining instance of F2's defect: it
   navigated via `cdp_session.evaluate("location.href=…")` — caller data interpolated into
   JavaScript source — with a `cdp_actuator.click(load_ref)` fallback to open a load's detail page
   for the POD check. Both are gone. The navigator adds exactly **one** capability over the
   observer, a document fetch, and that is a **reduction** in reachable behaviour: a click
   dispatches the SPA's `onclick` handler, which can POST an invoice while being no kind of form
   submit target, whereas `Page.navigate` never runs it. Schemes
   `javascript:/data:/file:/vbscript:/blob:` are refused; the transport carries exactly
   `{Page.enable, Page.navigate}` and has no script path. The click fallback was **deleted, not
   guarded** — no structural test on an element can classify a SPA click as safe — so a load whose
   detail document cannot be bound stays POD-unknown, which blocks the money button.
   `ReadOnlyCdpObserver` is **untouched**: the navigator composes it. Gate violations **3 → 2**;
   edges **16 → 14**.

6. **EP-3 provenance hardening, against the recorded hostile-review obligation.**
   The cut above accepted any URL the observed page published as an `<a href>`. The obligation says
   that is not enough, and it is right:

   > A same-origin, page-published href is not inherently read-only. Legacy systems may expose
   > state-changing GET routes.

   `/loads/101/delete`, `/invoices/9/approve`, `/logout` and Rails-style
   `<a href="/loads/101" data-method="delete">` are all same-origin anchors a real TMS renders, and
   the caller selected among them by **substring matching** a load ref against the document-wide
   `nav` list — so `<a href="/loads/9/purge_all">Delete L-101</a>` would have been followed. That
   was a live defect, not a theoretical one.

   `follow()` no longer takes a URL. It takes a **provenance record**
   (`cdp_readonly.ObservedLoadLink`) binding the observed ROW, the observed LOAD IDENTITY, the exact
   href and the observation CONTEXT, and it **re-derives that record from the live page** and
   demands an exact match before fetching anything. Four independent barriers decide membership:
   row containment (the anchor must be inside the one row whose own cells carry the identifier);
   identity binding (exact link text or exact whole path segment — never a substring); route family
   (no consequential action token in the path, no destructive token or method-override key in the
   query, applied to both the raw attribute and the browser-resolved URL, so a `<base>` tag cannot
   redirect it); and anchor shape (no `data-method`/`data-turbo-method` other than GET, no
   `data-confirm`, no `onclick`, no `download`, no `role=button`/`menuitem`, no `aria-haspopup`, not
   inside an action menu). Ambiguity is a refusal, never a pick. After the fetch the landed URL is
   re-checked, so a redirect out of the observational route family fails closed. A forged, composed,
   lookalike or stale record is refused even when well-formed, and every successful fetch advances
   the observation context so a record cannot be replayed.

   No part of F2 is reopened: there is still no evaluate, no command, no click, no caller-authored
   JavaScript and no generic traversal method on the surface. The provenance observation
   (`LOAD_ROW_LINKS_FN`) is a **vetted read script** like every other, taking the load identifier as
   protocol DATA. Violation and detection edges are **unchanged at 2 and 14** — this is a
   correctness hardening of an already-cut entry point, not a new cut. Boundary mutation battery
   **37/37** (added B28/B28a–B28f/B30a; the earlier B28 anchor and B30's now-ambiguous anchor were
   re-aimed). One case, B30a, was first reported as a MISS and the report was correct: it disabled
   only one of two deliberately redundant scheme rules, so it reintroduced no defect. The two rules
   now live in one function (`scheme_refusal_reason`) and the mutant removes the whole decision.

7. **EP-14 cut.** `scripts/read_tms_browser_use.py` imports only
   `browser_use_adapter`, and `browser_use_adapter` is no longer effect-capable — so the edge is
   ordinary detection residue rather than an unauthorized violation. Gate violations **2 → 1**;
   detection edges **14 → 14**.

   The write half moved into `browser_use_write`, the effect-capable slot the frozen phase-0
   inventory had **already reserved** (present in `import_probe.ADAPTER_MODULES`,
   `EFFECT_CAPABLE_ADAPTERS`, `entrypoint_probe` and the manifest, with no file behind it). So this
   occupies a pre-registered destination rather than inventing a module, and it is a **swap**:
   `browser_use_adapter → tms_write` becomes `browser_use_write → tms_write`, one authorized
   intra-adapter composition edge for another, with no application or script reachability gained.

   **`NativeBrowserUseRunner` moved too, and that was the load-bearing correction.** The earlier
   deferral had scoped this as "move the write ledger". But the runner executes an **arbitrary**
   natural-language task, which makes it an actuation primitive in the same sense
   `cdp_session.evaluate()` is: whoever hands it a task decides what happens to the page. Leaving it
   in the read module would have produced read-only *by naming* — the precise failure the EP-14
   requirement rejects. The repository's own guard already said so: `_LIVE_WRITE_DRIVERS` listed
   `BrowserUseTmsAdapter` next to `CdpActuator`. It no longer does, because the class no longer
   reaches either.

   What remains is structurally read-only on the F2 pattern: no write API exists on it; the agent's
   task is **never caller-authored** (`run_vetted` takes a task id from the frozen
   `VETTED_READ_TASKS` registry plus validated data and renders the task itself — no method accepts
   a task string); and it imports no effect-capable adapter. `BrowserUseWriteLedger` is **intact**
   for its documented P12 future — deleting a real future capability to make a gate green would be a
   false green. Evidence: `test_browser_use_readonly_surface.py` (structural, call-closure,
   behavioural, relocation) and a relocation guard asserting the nine swap conditions mechanically
   rather than trusting the manifest edit. Boundary mutation battery **42/42** (added B31–B35,
   including "the probe is weakened instead of the architecture" and "a script gains a direct import
   of the write half" — the two false-greens a count-only check would miss).

   *Honest scope, deliberately narrower than F2:* CDP containment is protocol-level — the channel
   allowlists CDP **methods**, so the browser never sees an actuation. A browser-use agent has no
   such chokepoint; it is an LLM driving a real browser and could in principle click inside a read
   task. What is mechanically true is that a read-side caller cannot express a write, cannot author
   the task, and cannot reach the write ledger or the generic runner. The residual belongs to the
   browser-agent execution class and is contained by the effect boundary where a write is
   *attempted*, not by this module claiming more than it has.

8. **EP-1 READ half cut (U4.11).** The callback server
   built five read closures over a mutation-capable session, and three held a `CdpActuator` purely
   to call `.observe()`. Two of them **spliced caller data into JavaScript source** —
   `_JS + "(" + repr(str(load_ref)) + ")"` — which is F2's exact defect, in closures that only ever
   wanted to look at a page. One **composed a target the page never published**
   (`href.rstrip("/") + "/attachments"`) and navigated to it with `location.href=` — the generic
   traversal shape EP-3 had just removed, still live here.

   All five now run on `cdp_readonly`. The header-driven column mapping and the document-name
   scrape moved into Python over a vetted observation
   (`operation_proposal.load_row_from_loads_table` / `document_labels_from_observation`), so the
   JavaScript is **gone rather than escaped more carefully**; load matching is exact on a delimited
   token rather than a comparison inside a caller-composed script; and the load's documents page is
   reached through an **EP-3 provenance record** instead of a composed URL. A latent bug surfaced
   and was fixed on the way: the brief reader's retry re-observed through a session the `with` block
   had already closed, so that retry could only ever fail.

   At the moment this item was written the `cdp_actuator` import survived, because
   `_build_live_operation_router._build_agent` still constructed it for the autonomous browser
   WRITE, and a guard asserted that factory was the **only** construction site so the residual was
   named and could not quietly spread. Mutation battery **45/45** at that point (added B36–B39,
   including "a second live write driver appears beside the residual").

<details>
<summary><b>⛔ HISTORICAL — SUPERSEDED DESIGN NOTE (NOT current instruction)</b></summary>

> ### **NOT CURRENT AUTHORITY — this design note was written before the EP-1 write half was built,
> and it has since been SUPERSEDED by what was actually done.** It is preserved because it records
> the reasoning that produced the design, and because deleting a superseded prediction hides how a
> decision was reached. The live account of what exists today is item 9 below.
>
> ### EP-1's write path: the design, and why it was not done blind.
> `effect_boundary.execute_effect` still has **no production caller** — it ships dark. Closing EP-1
> means registering the first real `AdapterOperation` and routing the Slack-approved invoice write
> through Work Item → policy → approval → checkpoint → fresh witness → grant → atomic claim →
> adapter execution → readback verification → evidence, which is the P12-scale supervised-write
> integration this repository already records it as.
>
> The import-graph shape is forced and worth recording now: the agent factory cannot simply move to
> another adapter module, because any `ADAPTER_MODULES` import from a script is an edge and an
> effect-capable one is a violation. The **only** destination that removes the edge is
> `effect_boundary` itself — it is not an adapter module, so `run_action_callback_server →
> effect_boundary` is no edge at all, while `effect_boundary → cdp_actuator` is the one import the
> gate already exempts (`CONTAINMENT_BOUNDARY`). That would take detection **14 → 15** and the
> shrinking-only guard would flag it, so it needs the same narrow, condition-checked treatment the
> EP-14 relocation got — not a broadened allowlist.
>
> **Moving the factory without routing the write through the grant chain would be a wrapper, and a
> wrapper that logs the bypass is not containment (PL-6).** It would take the violation count to
> zero while leaving an ungated live write — the exact false green P4 exists to prevent. So the
> factory stays where it is, visibly, until the boundary integration is real.

</details>

9. **EP-1 WRITE half cut, and the gate flipped to EMPTY — the work the adjudicated candidate
   `0891d1a` carries.** The legacy `_build_live_operation_router` factory is **deleted**, not
   disabled; `operation_router` in the deployed entry point is a single unconditional literal
   `None`, and an AST import-closure from that entry point shows `cdp_actuator` and `cdp_session`
   are **unreachable**. In its place the governed write route exists as real production code: a
   signed Slack approval envelope → a bounded, `writer=None` pending-write **lookup** → an
   actor/channel allowlist and a fail-closed stored-channel-receipt check → HMAC verification of
   every binding → a single-use queued intent → an atomic tenant-scoped claim → the checkpoint join
   → a fresh witness and Effect Grant in one transaction → the effect boundary with readback
   verification. The CI import gate now **asserts the effect-capable violation surface is EMPTY**,
   and the boundary mutation battery stands at **61/61 caught** with byte-exact tree restoration.
   ### **This is the mechanical close condition for R-07 — met and independently verified — and the
   CONTAINED record has now been written, in a separate content commit after both finalization
   passes. R-07 is CONTAINED. Containment forces external effects through the governed boundary or
   fails them closed; it enables no production write.**

## ✅ The exact next approved work program

### **P6 — FOUNDATIONAL ENTITIES AND STATE MACHINES. IT IS THE SOLE `READY` UNIT.**

### **`P6` is `READY`, which means SELECTED. Its recorded `execution_state` is `NOT_STARTED` and
its `checkpoint_state` is `NO_CHECKPOINT` — and this tree carries a P6 CONTENT CANDIDATE.**

### **READ THOSE TWO SENTENCES TOGETHER; EITHER ALONE IS A LIE IN ONE DIRECTION.** The code exists,
it is green, and it is **not accepted work**. The registry does not record it as landed because
`test_status_reality.py` requires every landed checkpoint to cite an on-disk **independent review
report** — *"P4-CP-1's null review report is a recorded gap, not a precedent to copy"* — and no such
report exists for this candidate. The session that built it may not write one (§11). ### **THIS IS
THE PRECEDENT THE REPOSITORY ALREADY SET:** P5's outbox and inbox were working code at candidate
`d807261` while this file and the registry both read `NOT_STARTED` / `NO_CHECKPOINT`; the fields
moved only at the replacement commit `de526c1`, which carried its independent review on disk.
Candidate first; landed when reviewed.

### **THE CANDIDATE — the Work Item, and accountable human ownership as a mechanism.**
Machine **M1**: the **14 transitions** of `state-machines/01-work-item.machine.md` §14 as declarative
data, with `AC-MACH-000`'s bijection asserted by **EXACT SET EQUALITY of transition identifiers**;
the exhaustive **64-pair** illegal sweep recorded to the audit backbone **and** `security_events`;
closure only through a `decision_ref` that **RESOLVES** (K-1); reopening that leaves the prior closure
event **byte-identical**; and `work_items.owner_id` as a **FOREIGN KEY** into `tenant_humans`, the
durable record of who was admitted to this brokerage, by whom, and when.
### **186 acceptance/hostile nodes, 32/32 mutants caught, and it ships DARK — zero production
callers, asserted by an AST scan and by an import-closure walk, not announced.**
Implementer's record:
[`p6-u1-work-item-ownership-implementation-record.md`](p6-u1-work-item-ownership-implementation-record.md).

### **THE FIRST CANDIDATE (`2ed750e`) WAS REJECTED BY A FRESH INDEPENDENT REVIEW, AND THIS TREE IS
ITS REPLACEMENT.** The review upheld the ownership model, the transition table, closure semantics,
timer semantics, the OCC write, tenant isolation and the P5 reuse as **sound**, and rejected the
candidate on one material defect class: ### **evidence of a REFUSAL was keyed on the identity of a
transition that did not happen.** `IllegalTransitionAttempted` carried §4's *transition-natural*
identity, which contains the aggregate version — and an illegal transition does not advance that
version. So a **second distinct hostile attempt** against one Work Item at one version collided on
`idempotency_identity` (**F-01**): only the first was ever recorded, later ones raised
`event_outbox.DuplicateEmission` instead of a refusal, and inside `DedupInbox.consume` that exception
rolled the inbox receipt back and made the event **redeliver forever, recording nothing on any
pass**. Separately (**F-02**), `consume()` could park a missing-aggregate obligation with
`accountable_owner_id` **NULL** — rule 13's one exception, created by the method whose own contract
promises the park surfaces *with* the human accountable for it.
### **BOTH WERE REPRODUCED MECHANICALLY AGAINST `2ed750e` BEFORE ANY LINE WAS CHANGED**, and the
remediation is narrow: one runtime module (`work_item.py`), **+8 regressions** and **+5 mutants**
(`W27`/`W27a`/`W28`/`W28a`/`W28b`) that restore the rejected behaviour and prove the new regressions
go red on it. The old suite was green on the rejected tree, which is exactly why the mutants exist.

### **WHAT THE CANDIDATE OWES, AND WHAT IT MAY NOT DO.** A **fresh targeted independent review by a
session that neither implemented nor remediated it**, then a **separate adjudication**. Only then may
`execution_state` become `IN_PROGRESS`, `checkpoint_state` leave `NO_CHECKPOINT`, and the record
become a `landed_checkpoints` entry citing the report. ### **THE REMEDIATING SESSION DID NOT REVIEW
OR ADJUDICATE ITS OWN REMEDIATION**, and the re-review must be fresh with respect to it too.
### **NO P6 ACCEPTANCE CRITERION IS SCORED, AND NONE MAY BE SCORED BY THE IMPLEMENTING LINEAGE**
(CLAUDE.md §11). The Product Driver returned **ACCEPT** on observed product behaviour — 35 behaviours
as specified, 0 wrong, including the three scenes added for the rejected defects, and proven able to
fail — and that is an independent judgement of the PRODUCT, **not** the targeted independent
engineering review this candidate owes.

### **P6 IS NOT COMPLETE, AND THE GAP IS LARGE AND NAMED.** `foundational-machine-acceptance.md`
requires **100% of the 134 legal transitions** across **13 machines**. One machine and 14 transitions
have landed. Still owed: the **Pipeline Instance** (M2, 25 transitions), **M3–M13** (95 transitions),
and with them `AC-EVT-003` (P5's `IR-R8`), which discharges only when all 134 land.

### **The next approved unit is `P6`.** P5 is COMPLETE — all 14 weighted criteria PASS at 100/100 on
independent evidence — so P6's sole dependency is satisfied and its `validation_blockers` are empty.
The three status fields are defined in `meta.status_model` of
[`IMPLEMENTATION-REGISTRY.yaml`](IMPLEMENTATION-REGISTRY.yaml).

Unit `P6` in [`IMPLEMENTATION-REGISTRY.yaml`](IMPLEMENTATION-REGISTRY.yaml) — **the one and only
READY unit.** To build: the **Work Item** with a structurally accountable human owner, the
**Pipeline Instance** as a durable reservation, the **13 machines** and the **134 transitions**.
Acceptance: `foundational-machine-acceptance.md`, gate **G1**, **AC-SAFE-028**. Ships dark;
`readiness_target: LOCALLY_IMPLEMENTED`. ### **The capability, in one line: every unit of work has
an accountable owner — structurally, not by documentation.** That turns CLAUDE.md rule 13 from a
written rule into a mechanism, and its Sev-0 hostile case is a Work Item with no owner.
### **`AC-EVT-003` DISCHARGES HERE** — P5 recorded as `IR-R8` that *"every producer transition emits
its required event in the transition's own commit"* cannot be proven at P5, because the 134
transitions are P6's. They are now built on a transport that has been certified.

> ### **BUT P6 MAY NOT BEGIN YET.** The commit recording P5 COMPLETE is a **closure content commit**
> and is **NOT FINALIZED**. Repository protocol — executed twice, at the P4 acceptance closure and at
> the R-07 closure — requires a closure commit to receive a **fresh targeted independent review**,
> then a **separate targeted adjudication**, then **exactly one finalizer**, in that order. P6 opens
> when that finalizer has run and the machine-readable authority records P5 COMPLETE. **No finalizer
> receipt exists for this commit and none may be fabricated.**

> ### **P5's OWN BLOCKER: G2's SEVEN EVENT OBLIGATIONS ARE DISCHARGED.** The G2 contract is settled
> and mechanised, `EF-3` is re-attributed to the existing `EffectExecuted`, all 134 transitions are
> structurally classified, and the seven durable writes that had no canonical event (`PL-7a`, `AP-9`,
> `CF-7`, `EC-7`, `PO-2`, `PO-3`, `RU-8`) were given **seven minted canonical events under
> founder/architect authority** on 2026-08-12, taking the registry 98 → **105**. Each departure from
> `EVENT_REQUIRED` is re-proven mechanically from `events/registry.md` §3 on every run; the seven
> obligations are **retained** in the audit, marked discharged with their authority, never deleted.
> ### **WHAT THIS DID NOT MEAN — `ADJ-P5-02`, corrected by the final adjudication.** This paragraph
> used to continue: *"The discharge built nothing. What exists is the U5.7+U5.8 transport — the
> outbox and the inbox — and no event-contract implementation, no replay sandbox, no audit
> reconstruction and no PostgreSQL work. P5 is `READY / IN_PROGRESS /
> CHECKPOINT_ACCEPTED_FOR_CONTINUATION` with all 14 criteria `PENDING`."* It is kept in its own
> words because a finding must survive its own repair. **It was true when written and is false now:**
> the discharge itself still built nothing, but everything it said was missing has since been built,
> independently reviewed and separately adjudicated. P5 is
> `COMPLETE / COMPLETE / PHASE_ACCEPTANCE_COMPLETE` at 14/14. The G2 residuals `G2-D4`, `G2-D6`, `G2-D8`, `G2-D9`
> and `G2-D10` remain OPEN and are recorded, not closed, in
> [`TRANSITION-EVENT-AUDIT.yaml`](TRANSITION-EVENT-AUDIT.yaml) — as do `G2-D15` (AP-9's **unfreeze**
> direction is unmodelled; the sentence asserting it is deleted, not restated) and `G2-D16` (the
> delegation predicate is a conjunction of **necessary conditions**, not a semantic proof), both
> opened and recorded by this sub-unit's replacement candidate rather than improvised shut.

> ### **AND THE CONTROL BOUNDARY STOPS HERE.** Recording this transition authorizes the *status
> change*, not the start of P6 work. Under [`PROGRESS-PROTOCOL.md`](PROGRESS-PROTOCOL.md) §9 a
> session must never roll into the next unit merely because the current one finished.
> ### **The next legal acts on this branch are, in order: (1) a fresh targeted independent review of
> THIS P5 closure content commit, by a session that did not write or adjudicate it; (2) a separate
> targeted adjudication of it, by a further session; (3) exactly ONE finalizer run
> (`.venv/bin/python scripts/finalize_status.py`) under an exclusively-held `finalizer_lock`,
> producing exactly one status-metadata commit; and only then (4) may P6 begin.** That is the
> sequence the P4 acceptance closure (`42ea24c → c30a43b → d3cf1de → 06ebfdb`) and the R-07 closure
> (`a31a94a → c26aeae → 035cb55 → 6e8127d`) each executed, in that order and in that commit time.
> Integration to `main` is fast-forward-only under R-21 and is a separate founder-authorized act.

How P3 got here, in order (all done): mutation proofs (guard battery 8/8; kernel battery K1–K11);
green final-tree validation via [`scripts/finalize_status.py`](../../scripts/finalize_status.py),
which EXECUTES the suite, the clean-clone gate and the acceptance gates itself; the first
INDEPENDENT review — which **P3 failed** (9 findings, 60/100) — then remediation of all nine; a
**FRESH INDEPENDENT** review of the remediated, finalized tree
([`p3-genuine-independent-review.md`](p3-genuine-independent-review.md), **PASS**, zero new
defects, 13/13 hostile probes); and a **separate FINAL ADJUDICATION**
([`p3-final-adjudication-review.md`](p3-final-adjudication-review.md)) that set the 14 criteria PASS
— by a session that neither implemented P3, reviewed it, remediated it, normalized the history, nor
corrected N-1.

> ### **R-07 is CONTAINED — and completing P4's weighted acceptance is NOT what did it.** The P0
> finding was 31 direct adapter-import edges and all six production-reachable live-write paths. P4
> deleted EP-6/7/9/10, cut EP-1/EP-3/EP-8/EP-14, routed the governed write through the checkpoint
> kernel and flipped the gate to assert the effect-capable violation surface is EMPTY — the
> **mechanical** close condition, independently verified twice. What remained after all of that was
> the **record**, and `phase-0-baseline-manifest.yaml` is not a status-metadata file, so it needed
> its own content commit after both finalization passes. **That commit is what closed R-07** — not
> P3, not P4's acceptance block, not a finalizer, not a plan, and not operator discipline.

## ⛔ What must NOT begin yet

| Not yet | Why |
|---|---|
| ### **Implementation Phase 7** (provenance, evidence, observation, claims, identity binding) | Requires `P6` **COMPLETE**, and P6 is not: one of its thirteen machines has landed. P5's `IR-R9` (`AC-EVT-011` and the `ProvenanceStrengtheningAttempted` F14 emission half) lands here, not earlier: provenance was P5's `prohibited_scope` and is P6's too |
| ### **Self-certifying the candidate in this tree** | `P6-CP-1-CANDIDATE` owes a **fresh targeted independent review** by a session that neither implemented nor remediated it, then a **separate adjudication**, before it may be recorded as landed or score anything. CLAUDE.md §11: certifying your own fixes is self-adjudication, a defect with a passing status. The Product Driver's ACCEPT is a product judgement and is **not** that review |
| ### **Treating the Work Item machine as a freight workflow** | M1 is a platform primitive that ships **dark**. It performs no external effect, holds no commit key, mints no witness and no grant, and has **zero** production callers. Freight workflow implementation still requires the remaining foundations |
| **Rebuilding any P5 surface** — event contracts, GC-1 corpus, replay sandbox, audit reconstruction, outbox/inbox, durable timers, PostgreSQL | ### **BUILT, REVIEWED, ADJUDICATED — do not rebuild, and do not re-open.** All 14 P5 criteria are `PASS`. Reopening a closed phase to polish it is forbidden by CLAUDE.md §13.8. The recorded nonblocking residuals (`IR-R5`–`IR-R12`, `ADJ-P5-01`–`ADJ-P5-03`) are **debt rows, and the debt row is the complete deliverable** (§13.3) |
| Treating R-07 CONTAINED as production enablement | ### **Containment is not enablement.** External-effect paths are structurally forced through the governed boundary or fail closed. No production write is enabled, the deployed route answers `ROUTE_NOT_CONFIGURED`, the production `GateRegistry` population stays **EMPTY** until U8.1 / P8, and **no autonomy — bounded or otherwise — was granted.** Live supervised writes are P12, behind the undischarged **RR-01** |
| Running a finalizer on the R-07 closure content commit | It must first receive a **fresh targeted independent review** and a **separate targeted adjudication**. No finalizer receipt exists for it and none may be fabricated |
| Freight workflow implementation | Requires P6–P9 foundations |
| Deleting legacy production code | Requires the deletion conditions in [`LEGACY-DISPOSITION.md`](LEGACY-DISPOSITION.md); P4 executed only the S1/S2 deletions its own acceptance covered |
| Registering production Action Class gates | ### **DEFERRED BY FOUNDER DECISION to U8.1 / P8.** The production `GateRegistry` population is EMPTY and must stay empty; `AC-CKPT-6-missing` stays `DEFERRED_BY_DEPENDENCY - REQUIRED AT PHASE 8` |
| Injecting any live writer | Requires **RR-01** discharged (with F-08 and F-09) — a binding **P12** precondition |
| Promoting Delivered Load Closure to validated | It is a **`HYPOTHESIS`** — requires recorded design-partner evidence ([`DESIGN-PARTNER-EVIDENCE-PROGRAM.md`](../product/DESIGN-PARTNER-EVIDENCE-PROGRAM.md)) |
| Enabling any external effect on live traffic | The capability ships dark. The deployed governed route answers a recorded `ROUTE_NOT_CONFIGURED` refusal with zero grants minted, and enabling it is a separate, later, founder-authorized decision — not a consequence of P4's acceptance |

## Blocked future units

**`P6` is now `READY`; every implementation phase from `P7` onward is BLOCKED behind `P6`.** See the
registry for the full dependency graph; the transitive safety wall (P3 an ancestor of every P≥4, P4
of every P≥5, P5 of every P≥6) is guarded.

<details>
<summary><b>⛔ HISTORICAL — SUPERSEDED PROGRAMS (NOT current instruction)</b></summary>

**Everything in this block is superseded and must not be followed.**

- *Before the U-REBASELINE-1A adjudication (2026-07-20)*, this file named **U-REBASELINE-1** as
  the next approved work program, described its contract as RB-01..RB-23 PASS with RB-24 PENDING,
  and listed P3 as BLOCKED behind it. The independent review was then run, delivered, preserved
  and adjudicated: U-REBASELINE-1 is COMPLETE and P3 became the sole READY unit.
Retained only so the transitions are auditable.

> ### **A false transition was recorded here and has been removed.** A prior working tree added a
> bullet stating that P3 had been "implemented, tested, mutation-proven, reviewed and adjudicated"
> and that "P3 is COMPLETE and P4 is the sole READY unit." ### **No such transition occurred.**
> P3's kernel was written, but its independent review and final adjudication never happened, its
> 14 criteria never left `PENDING`, and the review it cited as evidence did not exist. It sat
> inside this `<details>` block, where every control guard deliberately stops reading — which is
> exactly why a false claim placed here is more dangerous than one in live text, not less.
> **P3 remains the sole READY unit. No transition away from it has been recorded.**
>
> ### **SUBSEQUENT NOTE — the transition later happened, properly.** The paragraph above is
> preserved verbatim as the record of a false claim and of the reasoning that caught it; it is
> **historical, and its closing sentence is no longer current.** P3 was afterwards genuinely
> reviewed by a fresh independent session and adjudicated COMPLETE by a separate adjudicating
> session, and P4 became the selected unit — that evidence lives in the live tables above, never
> here. The lesson is unchanged: **a false claim inside a quarantined block is more dangerous than
> one in live text**, which is why the roadmap-completeness drift guard reads live text only and
> requires historical blocks to be self-labelling rather than silently trusted.

</details>

## Documents required before proceeding

A session picking up `P6` must have read, in order:
[`CLAUDE.md`](../../CLAUDE.md) → [`PRODUCT.md`](../../PRODUCT.md) →
[`ARCHITECTURE.md`](../../ARCHITECTURE.md) → [`CANONICAL-DOCUMENTS.md`](../CANONICAL-DOCUMENTS.md) →
this file → [`IMPLEMENTATION-REGISTRY.yaml`](IMPLEMENTATION-REGISTRY.yaml) →
[`TOOL-ACCESS-POLICY.md`](TOOL-ACCESS-POLICY.md) → the **P6** unit block (scope, prohibited scope,
acceptance contract) in [`IMPLEMENTATION-REGISTRY.yaml`](IMPLEMENTATION-REGISTRY.yaml) →
[`foundational-machine-acceptance.md`](../specifications/acceptance/foundational-machine-acceptance.md) →
`docs/specifications/entities/` and `docs/specifications/state-machines/` →
[`LEGACY-DISPOSITION.md`](LEGACY-DISPOSITION.md) → [`PROGRESS-PROTOCOL.md`](PROGRESS-PROTOCOL.md).
### **It must ALSO confirm that this P5 closure commit has been finalized before writing any P6
code** — the two-commit convention makes that a `git log` check, not a judgement call.

**A session performing the fresh targeted independent review or the targeted adjudication of the
P5 closure content commit** must additionally read, in order:
[`p5-independent-review-report-1216254.md`](p5-independent-review-report-1216254.md) →
[`p5-final-adjudication-report-91ba4e6.md`](p5-final-adjudication-report-91ba4e6.md) →
the P5 unit block's `acceptance_criteria` and sub-unit records in
[`IMPLEMENTATION-REGISTRY.yaml`](IMPLEMENTATION-REGISTRY.yaml).
### **Neither of those two reports reviewed the closure commit itself** — the independent review is
bound to `1216254` and the adjudication to `91ba4e6`, and both say so in their own headers.

**A session performing the fresh targeted independent review or the targeted adjudication of the
P4 closure content commit** must additionally read, in order:
[`p4-independent-rereview-report-0891d1a.md`](p4-independent-rereview-report-0891d1a.md) →
[`p4-final-adjudication-report-0891d1a.md`](p4-final-adjudication-report-0891d1a.md) →
[`p4-first-finalization-pass-report-86306d5.md`](p4-first-finalization-pass-report-86306d5.md) →
[`p4-closure-content-topology-determination.md`](p4-closure-content-topology-determination.md) →
the P4 unit block's `acceptance_criteria` and `residual_risks_carried_forward` in
[`IMPLEMENTATION-REGISTRY.yaml`](IMPLEMENTATION-REGISTRY.yaml) →
[`phase-0-baseline-manifest.yaml`](phase-0-baseline-manifest.yaml) (the R-07 containment record).
### **None of those four reports reviewed the closure commit itself** — the re-review and the
adjudication are bound to implementation candidate `0891d1a`, and they say so in their own headers.

**A session performing the fresh targeted independent review or the targeted adjudication of the
R-07 CLOSURE content commit** must additionally read, in order:
[`p4-closure-candidate-targeted-review-report-42ea24c.md`](p4-closure-candidate-targeted-review-report-42ea24c.md) →
[`p4-closure-candidate-targeted-adjudication-report-42ea24c.md`](p4-closure-candidate-targeted-adjudication-report-42ea24c.md) →
[`p4-second-finalization-pass-report-06ebfdb3.md`](p4-second-finalization-pass-report-06ebfdb3.md) →
[`p4-r07-closure-handoff.md`](p4-r07-closure-handoff.md) →
[`phase-0-baseline-manifest.yaml`](phase-0-baseline-manifest.yaml)'s `expected_legacy_paths` block.
### **The second-finalization report is a RECONSTRUCTION authored after the run by an independent
attestation session that did not execute the finalizer.** It may be cited for facts independently
established by Git objects, canonical receipts, lock/run artifacts and preserved scratchpad
evidence — never as contemporaneous finalizer testimony — and the items it marks `[UNAVAILABLE]`
(the process PID and the Product Driver run/session IDs) are documented limitations, not blanks to
be filled in. ### **None of the reports above reviewed the R-07 closure commit itself.**

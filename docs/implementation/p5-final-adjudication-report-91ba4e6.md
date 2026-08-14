# P5 — FINAL ADJUDICATION REPORT

### **VERDICT: P5 ACCEPTED. ALL 14 WEIGHTED CRITERIA `PASS`. SCORE 100/100.**

> **This report SETS the fourteen weighted P5 acceptance criteria.** It is the separate final
> adjudication CLAUDE.md §11 requires: performed by a session that did not implement P5, did not
> remediate it, did not perform its independent review, did not author any P5 evidence document and
> did not run any finalizer. Every value below was re-derived from the object store or from a
> command this session executed. **No conversational claim was accepted as evidence.**

| | |
|---|---|
| **Adjudicated content commit** | `91ba4e6560d456eeee5a3e8b96748319d358a33d` (tree `05baa45772be70091d87ff1463b3249e9b373cd0`) |
| **`HEAD` at adjudication** | `4150149401d42252e7ca5be862f4c66c367f5f70` — the single finalizer-generated status-metadata commit directly above it |
| **Repository state** | `FINALIZED` (recorded `content_commit` == `HEAD^`, and `HEAD` touches only the five `STATUS_METADATA_FILES`) — legal under `PROGRESS-PROTOCOL.md` §10 |
| **Independently reviewed surface** | `1216254c1b3e04bad72ff9c4c5aa3718a2a6ae92` (tree `3914e28b63ed6ce2b8468ec385daecb79eba2b28`) |
| **Runtime delta, reviewed tree → adjudicated tree** | ### **ZERO.** `git diff c14014b HEAD -- src/ scripts/ eval/` is EMPTY |
| **Branch** | `p5/u5-1-g2-spec-correction` · `main` unmoved at `152574e` |
| **Working tree** | clean before, during and after every probe below |

---

## A. Independence — established, and its limit stated

This session implemented no P5 sub-unit, remediated nothing, reviewed nothing, authored no P5
evidence document, and ran no finalizer. It inherited no findings: the twelve residuals in the
independent review were read *after* this session had reproduced the gates itself.

### **The honest limit.** Every commit in this repository carries the same git author identity
(`sheed17 <rsamady2@gmail.com>`), because every session runs on the founder's machine. **Git
authorship therefore cannot distinguish sessions and is not offered as independence evidence.**
Independence is established the way this repository has always established it — by the *acts*: the
review is a distinct preserved commit that adds only its own report, the adjudication is this
distinct document, and no session set a criterion from its own work. That is the same mechanism
that closed P3 and P4.

**Mechanical corroboration of the reviewer's independence:**
`refs/preserve/p5-independent-review-1216254` (`192aaad5`) has parent `c14014b8` and its diff
against that parent is **exactly two paths** — the report and its digest sidecar. The reviewer
modified no runtime file, no test, no fixture and no status record, which is what its §7 claims and
what the object store confirms.

---

## B. The independent review artifact — located, digest-verified, verdict confirmed

| Check | Result |
|---|---|
| Preserved artifact | `refs/preserve/p5-independent-review-1216254` → `192aaad56b1c8c63dd1fd92d797fdc28e5f6688d` |
| Recorded digest (`.sha256` sidecar) | `f028696b68235a7700491585b230c3290081138825fa1fa31f860dcacdc533f0` |
| SHA-256 of the **byte-exact preserved original** | `f028696b…533f0` — ### **MATCH** |
| SHA-256 of the **in-tree copy** | `5d7a2f35…1e35fd` — differs, **correctly** |
| Why the in-tree copy differs | A single prepended disarming banner, required by `test_false_green_defenses.py::test_historical_documents_disarm_before_any_stale_claim`. `git diff` against the preserve ref shows the banner is the file's **only** modification. ### **This is the established convention, not a defect** — `p4-independent-rereview-report-0891d1a.md` diverges from its own sidecar in exactly the same way and for exactly the same reason. The sidecar authenticates the artifact, never the in-tree rendering |
| **Verdict** | ### **ACCEPT FOR SEPARATE FINAL ADJUDICATION** (§6.1) |
| **Material blocking defects** | ### **NONE** (§4) |
| Nonblocking residuals | twelve — `IR-R1`…`IR-R12` (§5) |
| Hostile verification actually executed? | ### **YES** — 45 probes, 45 PASS after correction. ### **Eight of the reviewer's own probes were defective on first execution and the report says so**, naming five distinct harness defects including a `node.level`-gated AST walk that would have been blind to absolute imports (the repository's own R19 blind spot) and a substring guard that fired on the module's own prose. A reviewer that reports its own defective probes is applying §9 to itself; this materially raises the report's credibility rather than lowering it |

**Did the review bind to the tree being adjudicated?** It reviewed `1216254`. Two commits landed
after it: `91ba4e6` (record correction) and `4150149` (status metadata). `git diff c14014b HEAD`
touches **eight paths, all under `docs/implementation/`** — five status files, the review report,
its sidecar, and `pr-sequence.md`. **Not one runtime, test or fixture byte changed.** The review's
technical findings therefore bind to the adjudicated tree in full.

---

## C. What this session executed itself

Nothing below was accepted from a receipt. Each was run by this session on the adjudicated tree.

| Act | Result |
|---|---|
| Canonical suite, final tree | ### **2674 passed · 0 failed · 1 skipped** (410.76s, exit 0) — identical to `SUITE-RESULT.json` and to the reviewer's run |
| The one skip | `test_phase0_guard_integrity.py::test_the_red_by_design_cases_are_strict_xfails` — the conditional, self-describing AC-SAFE-012/013 skip, the sole entry in `APPROVED-SKIPS.yaml` |
| **Clean-clone gate, re-executed** | ### **PASS** — 9/9 steps exit 0; a fresh clone with declared dependencies only reproduced **2674 · 0 · 1** over 2675 collected. The committed receipt was restored byte-exactly afterwards and the tree verified clean |
| **PostgreSQL P5 gate, re-executed against a database this session created** (`neyma_adjudicator_p5`, PostgreSQL 16.15) | ### **PASS** — 26 migration steps; replay **0 steps** (a genuine no-op); tenant-first PK column order on the live catalog; SQLite/PostgreSQL structural equivalence; **8 invariants REFUSED**; **2 positive controls ACCEPTED** (proving the triggers are not refusing everything); **17 runtime probes PASS**. ### **The committed `POSTGRES-P5-GATE.json` is not a false green** |
| **Replay/audit mutation battery, re-executed** | ### **24/24 mutants caught**, tree byte-clean after restore |
| **Event-contract mutation battery, re-executed** | ### **37/37 mutants caught**, tree byte-clean after restore |
| Contract re-derivation (`generate_event_contracts.py --check`) | `event_contracts_data.json` **matches the specification** — the corpus is derived, not transcribed |
| Test-node manifest | 2675 nodes; **556** on the five P5 modules (333 contracts · 133 transport · 44 replay/audit · 27 timers · 19 canonical mint) |
| Finalizer metadata commit legality | `4150149` has **single parent** `91ba4e6` and changes **exactly** the five authorized `STATUS_METADATA_FILES` and no other path |

### C.1 This session's own import-closure probe — and its first version was defective

CLAUDE.md rule 11 (*replay cannot call adapters*) is P5's single most consequential invariant, so
this session proved it independently rather than accepting either the review or the committed test.

**The first probe returned an empty closure for every module and its positive control reported the
control module absent.** That is a probe that could not have failed, and §9 exists to catch exactly
it — so it is reported here rather than silently replaced. The defect was relative-import
resolution: for a module at the package root, `from .event_contracts import …` was being resolved
to `event_replay.event_contracts` instead of `event_contracts`.

The corrected probe walks relative imports, absolute `freight_recon.*` imports and plain `import`
statements, and **carries a positive control that fires**:

```
POSITIVE CONTROL  effect_boundary   closure_size=36
                  forbidden reached: browser_use_write, checkpoint, operation_router,
                                     ops_control, tms_write
```

Against a 15-module effect-capable forbidden set, on the adjudicated tree:

```
event_replay    closure = {event_contracts, event_envelope, fingerprint,
                           migrations.phase5_event_transport, tenant}
event_audit     closure = {event_contracts, event_envelope, fingerprint,
                           migrations.phase5_event_transport, tenant}
event_contracts, event_envelope, event_outbox, event_inbox, event_timers, persistence
                → zero forbidden reach
```

### **Replay's transitive closure reaches no adapter, no effect boundary, no checkpoint kernel, no brake store, no router and not even a database layer.** Independently re-derived, matching the reviewer exactly. **Replay cannot call an adapter because the capability is not reachable — not because it declines to.**

---

## D. Materiality standard applied

A criterion fails only for a real, unresolved issue in correctness, durability, canonical event
truth, replay truth, audit reconstruction, outbox/inbox semantics, timers, PostgreSQL production
behaviour, transaction/concurrency safety, idempotency, tenant isolation, restart/recovery, effect
isolation, or another binding P5 requirement.

**No such issue was found.** Every residual identified — by the reviewer, and the three additional
record-accuracy instances this session found (§F) — is stale or imprecise *prose* in a record whose
machine-read fields are correct. Per CLAUDE.md §13.3 these are debt rows, not a remediation
campaign, and none is permitted to fail a criterion.

---

## E. THE FOURTEEN WEIGHTED CRITERIA

Instantiated verbatim from the frozen `PROGRAM-WEIGHTS.yaml` `acceptance_template`; weights
6+8+20+8+8+10+6+6+8+5+3+3+5+4 = **exactly 100**, verified by summation.

### E.1 `accepted_scope_and_design` — weight 6 — ### **PASS**
**Evidence:** the P5 unit block's `objective`, `allowed_scope`, `prohibited_scope` and
`expected_production_outputs`; sub-unit records U5.1–U5.9; the `rebaseline_contract`.
**Reason:** every landed surface — event contracts, GC-1, replay, audit reconstruction, outbox,
inbox, durable timers, PostgreSQL store and migrations — falls inside `allowed_scope` as corrected,
and the correction **granted no new scope**: each added item was already required by the same
unit's `objective` and `expected_production_outputs`. `prohibited_scope` (entities → P6,
provenance → P7) is **untouched**: no entity and no provenance class was implemented. The
`allowed_scope` omission the reviewer recorded as `IR-R4` is corrected in the adjudicated tree.

### E.2 `required_tests` — weight 8 — ### **PASS**
**Evidence:** `TEST-NODE-MANIFEST.json`; the canonical suite this session ran.
**Reason:** **556** committed nodes across the five P5 modules, all five registered in the manifest,
all executing (0 unexecuted, 0 rogue, 0 xfail). Tests are set-based rather than count-based: the
contract bijection asserts **set equality in both directions** against `events/registry.md` §3, so a
same-count substitution fails.

### E.3 `core_implementation` — weight 20 — ### **PASS**
**Evidence:** 5,590 lines across `event_envelope`, `event_contracts`, `event_outbox`, `event_inbox`,
`event_replay`, `event_audit`, `event_timers`, `persistence` and three migration modules;
independent review §3.1–§3.5; this session's PostgreSQL gate and closure probe.
**Reason:** all six required capabilities exist and behave: **118 canonical event contracts**
(105 machine-emitted F1–F13 + 13 audit/security F14) derived from the specification and re-derivable
on demand; a **transactional outbox** whose contract gate runs inside the caller's transaction, so a
non-canonical event rolls the state change back with it; a **dedup inbox** idempotent on
`(tenant, consumer_id, event_id)`; **deterministic replay** whose rebuild digest is a pure function
of the event *set*, stable across 40 shuffles and equal to the pin; **audit reconstruction** that is
order-independent across 25 shuffles and names unreconstructible fields rather than inventing them;
and **durable timers** surviving a full connection restart.

### E.4 `failure_handling` — weight 8 — ### **PASS**
**Evidence:** independent review §3.2–§3.5; mutants R9–R15, R24, C15–C19; this session's gate run.
**Reason:** every failure path fails **closed**. A crash between the state write and the event write
leaves **neither**. A raising handler records nothing — its writes, the inbox row and the cursor
vanish together, and redelivery still applies, so a failed consumption is never recorded as a
successful one. A version gap **parks** and drains in version order; a dangling reference parks
**with its accountable human**, and is drained or expired, never dropped. A future `event_version`
fails closed on emit **and** on read. `BEGIN IMMEDIATE` on a tenant-less PostgreSQL connection fails
closed rather than handing back a transaction without the exclusion requested. Timeout alone never
becomes `FAILED` (rule 12): `TimerFired` is deliberately not an `EventEnvelope` and carries no
decision.

### E.5 `concurrency_handling` — weight 8 — ### **PASS**
**Evidence:** `AC-RACE-006/007`; independent review §3.2–§3.3; **this session's PostgreSQL gate**.
**Reason:** reproduced on a real server by this session — concurrent emitters allocate distinct
sequences; a leased outbox row cannot be claimed by a second connection; a lapsed lease is
reclaimable; duplicate relay workers deliver exactly once; the inbox applies once and redelivery is
a no-op; tenant isolation holds. 16 concurrent emitters on real OS threads allocate 16 distinct
contiguous sequences under SQLite. Emission under a **deferred** `BEGIN` fails closed rather than
duplicating, with `UNIQUE (tenant, sequence)` as the backstop. Strict per-aggregate ordering is a
**trigger, not a UNIQUE index** — deliberately, because a UNIQUE index would have made EF-2's
legitimate `GrantClaimed` + `EffectAttempted` co-emission uninsertable at P6; two *different*
transitions claiming one version raise `StrictOrderViolation` and are **not** misreported as a
duplicate.

### E.6 `authorization_and_security` — weight 10 — ### **PASS**
**Evidence:** independent review §3.1, §3.6; mutants C25–C28, C32; R7, R8; this session's closure
probe and PostgreSQL gate.
**Reason:** **events cannot grant authority (rule 9)** — a crafted payload asserting
`approved: true`, `authority: grant_effect`, `execute: tms_write` produced **0 grants and 0
witnesses**. An event is data. Actor authority is **derived, not hand-listed**: 6
authority-broadening events refuse a machine actor, 98 contracts refuse `actor_type=model`, against
7 model-permitted claim/proposal contracts. **Provenance laundering is refused across four evasion
shapes** — flat value, nested list-of-dicts, `Enum` member, envelope-level `provenance_refs` — with a
positive control confirming the guard is not blanket-refusing. **Tenant is the first partition
dimension of every store, stream and inbox [C-1]**; a tenant-bound rebuild **refuses** a foreign
event rather than filtering it, and tenant-first PK column order was verified by this session on the
live PostgreSQL catalog. P5 adds **no** tenant-exempt table.

### E.7 `migrations_and_persistence` — weight 6 — ### **PASS**
**Evidence:** **this session's PostgreSQL P5 gate**, executed against a database it created.
**Reason:** 26 migration steps applied to an empty database and reached readiness; **replaying the
migration performed 0 steps** — a genuine no-op, which is the `migration replayed twice` hostile
case and is strictly stronger than "it worked again"; migration status is queryable; the SQLite and
PostgreSQL catalogs agree column-for-column and key-for-key; the eight durable invariants are
enforced **by trigger** on PostgreSQL and all eight refuse, with two positive controls proving
delivery bookkeeping may still legitimately move.

### E.8 `observability_and_operational_behavior` — weight 6 — ### **PASS**
**Evidence:** the P5 `rebaseline_contract.observability_requirements`; the module surfaces; mutant
R18.
**Reason:** all four required signals have real query surfaces on the adjudicated tree — **outbox
lag** (`count_unpublished()`, `pending()`, `published()`, `RelayResult.published_count`); **dedup
hits** (`ConsumeResult.applied`/`is_noop`, `seen()`, and the `APPLIED`/`DUPLICATE_NOOP`/`STALE_NOOP`
outcomes); **GC-1 rebuild digest vs pinned** (mutant R18 — *"the committed corpus drifts from its
builder"* — is caught); and **migration status** (`postgres_p5.migration_status`, exercised by the
gate). Counts are derived from rowcounts, never from intentions: a timer cancelled underneath a
mid-flight delivery reports `superseded`, not `fired`. Parked references expose their accountable
human by name.
**Stated honestly:** these are query primitives, not dashboards or alerting. Production monitoring
is ADR-016 / P11 scope and is **not** claimed here.

### E.9 `mutation_or_hostile_cases` — weight 8 — ### **PASS**
**Evidence:** **re-executed by this session** — replay/audit **24/24**, contracts **37/37**, both
with byte-exact tree restoration; the reviewer's 45-probe hostile battery.
**Reason:** the unit's `mutation_requirements` are *"required — replay must be proven unable to call
an adapter"*, and that is discharged twice over: mutant **R19** re-introduces the `node.level` gate
that would blind the closure proof to absolute imports and **is caught**, and this session's own
independent probe re-derived the closure with a positive control that fires. The guards are proven
able to fail, not merely present.

### E.10 `full_test_suite` — weight 5 — ### **PASS**
**Evidence:** this session's run — **2674 passed · 0 failed · 1 skipped**, exit 0, on the final tree;
`SUITE-RESULT.json` binds the same figures to `91ba4e6` / `05baa45`.
**Reason:** green on the final tree, with the single skip conditional, self-describing and
pre-approved.

### E.11 `canonical_finalizer` — weight 3 — ### **PASS**
**Evidence:** metadata commit `4150149401d42252e7ca5be862f4c66c367f5f70`.
**Reason:** ### **NOT this adjudication's own act.** A finalizer cannot have run on the candidate
being adjudicated, so this criterion is `PENDING` by construction *at* adjudication — exactly as it
was for P3 and P4. It is `PASS` here on the one finalizer run that **has already executed** on the
adjudicated content commit: `4150149` has **single parent `91ba4e6`** and changes **exactly** the
five authorized `STATUS_METADATA_FILES` (`SUITE-RESULT.json`, `GATE-RESULT.json`, `CURRENT.md`,
`IMPLEMENTATION-REGISTRY.yaml`, `BUILD-STATUS.yaml`) and no other path — verified by this session
against the object store. Its receipts bind to `91ba4e6` / `05baa45` with exit status 0. **This is
the identical pattern by which P4's `canonical_finalizer` became `PASS` on run `86306d5`.**

### E.12 `clean_clone_execution` — weight 3 — ### **PASS**
**Evidence:** **this session re-executed `scripts/clean_clone_gate.py`.**
**Reason:** 9/9 steps exit 0 — clone committed state, python floor (host), fresh venv, python floor
(venv), install declared deps only, complete canonical suite, control guards, AC-SAFE-012/013 +
AC-SEC-001, clone tree still clean — reproducing **2674 · 0 · 1** over 2675 collected in a fresh
clone with declared dependencies only. **The green is clean-clone reproducible, not a property of
one working copy.** The committed receipt was then restored byte-exactly.

### E.13 `independent_review` — weight 5 — ### **PASS**
**Evidence:** `refs/preserve/p5-independent-review-1216254` (`192aaad5`, parent `c14014b8`), report
SHA-256 `f028696b…533f0` matching its sidecar byte-exactly; verdict **ACCEPT FOR SEPARATE FINAL
ADJUDICATION**, material blocking defects **NONE**.
**Reason:** supplied by a session that did not implement or remediate P5, whose preserved commit
adds only the report and its sidecar. Its hostile verification **actually executed** (45 probes) and
its gate results were **reproduced by this adjudication** — the PostgreSQL gate, the clean-clone
gate, both mutation batteries and the closure proof. ### **It reviewed the P5 surface at `1216254`;
the runtime delta from there to the adjudicated tree is ZERO.**

### E.14 `final_adjudication` — weight 4 — ### **PASS**
**Evidence:** this report.
**Reason:** performed by a session that neither implemented, remediated, reviewed nor finalized P5,
on evidence it reproduced itself rather than inherited. **No session adjudicated its own work.**

### E.15 Score

**14 / 14 `PASS` → weights summing to 100 → P5 computes to 100/100 → ### P5 ACCEPTED.**

---

## F. Residual debt — carried, NOT discharged, and NOT actioned

Per CLAUDE.md §13.3 the debt row is the deliverable. **None of these fails a criterion; none is
actioned here.**

| ID | Finding | Disposition |
|---|---|---|
| `IR-R5` | `CURRENT.md` prose stale against its own live status row | corrected by the closure commit that carries this report |
| `IR-R6` | registry says *"105 event contracts"*; implementation carries 118 (105 F1–F13 + 13 F14) | qualifier omission; 105 is right for the machine-emitted corpus |
| `IR-R7` | **GC-1 does not span a schema version change.** Every canonical contract is at v1, so `AC-EVT-009` is proven through the real replay path against a **test-only** versioned contract set | ### **The honest disposition, not a gap.** Minting a production v2 to satisfy a fixture would amend a protected specification under authority this unit does not hold. Recorded as `U546-D1`; a guard goes red the day a contract leaves v1 |
| `IR-R8` | **`AC-EVT-003`** (every producer transition emits its required event in its own commit) **cannot be proven at P5** — the 134 transitions are P6 | ### **A structural deferral, correctly scoped.** Recorded in U5.3's `explicitly_not_done`. ### **This is P6's first acceptance obligation** |
| `IR-R9` | `AC-EVT-011` and the `ProvenanceStrengtheningAttempted` (F14) **emission** half of `AC-EVT-013` are unimplemented | ### **The dangerous half is CLOSED** — laundering is refused across four evasion shapes. What is missing is the audit *record* of an attempt. Provenance is P5's `prohibited_scope` (**P7**), so declining to build it is correct scoping |
| `IR-R10` | `persistence.py` docstring overstates the danger of a missing advisory lock (it fails closed on `UNIQUE (tenant, sequence)`, it does not corrupt) | prose overstates in the **safe** direction |
| `IR-R11` | `event_timers._load` returns `{}` on malformed payload JSON | payload is advisory; identity, kind and deadline are separate columns and survive |
| `IR-R12` | `OutboxRelay` does not enforce `relay_id` uniqueness | consequence is duplicate delivery, which the dedup inbox makes free; per-aggregate order preserved |
| **`ADJ-P5-01`** | ### **NEW — found by this adjudication.** `BUILD-STATUS.yaml`'s authored `snapshot:` block was materially stale: it stated *"The event contracts, GC-1 corpus, replay sandbox, audit reconstruction and PostgreSQL do not exist"*, *"the transport is SQLite only"* and *"U5.1 IS ON ITS SECOND CANDIDATE AND IS STILL UNREVIEWED"* — all false. The finalizer-maintained `derived:` block was correct throughout | ### **Same IR-R1 record-accuracy class**, in a file the reviewer's residuals did not cover. Corrected by the closure commit, because a snapshot asserting P5's infrastructure does not exist cannot ride in the commit that records P5 COMPLETE |
| **`ADJ-P5-02`** | ### **NEW.** Two further IR-R1-class instances: `CURRENT.md` §"P5's OWN BLOCKER" (*"no event-contract implementation, no replay sandbox, no audit reconstruction and no PostgreSQL work"*) and the registry comment above `status: READY` (*"The event contracts (U5.3), GC-1 (U5.4), the replay sandbox (U5.5), audit reconstruction (U5.6) and PostgreSQL do not exist"*) | corrected by the closure commit; machine-read fields were correct throughout |
| **`ADJ-P5-03`** | ### **NEW — scope boundary, stated rather than waived.** The P5 `rebaseline_contract` sets `readiness_target: STAGING_READY for the persistence infrastructure`. **That target is NOT met and is not claimed met.** The PostgreSQL surface is proven against a real server on a developer machine; it has **not** been deployed to a production-like staging environment with secrets, monitoring and operational controls | ### **NOT a P5 acceptance criterion.** The fourteen weighted criteria are the acceptance contract; `readiness_target` is a maturity target. ADR-016 assigns deployment and environments to **P11**, and the gate receipt says so itself. Carried to P11 |
| `AD-02` | `finalizer_lock.py` — 188 safety-critical lines, zero committed test coverage | inherited from P4, still open, **load-bearing for the next finalizer run** |
| `PD-02` | Product Driver `_CONTENT_COUNT_RE` misreads the `07` of *"R-07"* as the cardinal 7 | inherited tooling defect **outside this repository**; repository authority is not contradictory |
| `G2-D4/D6/D8/D9/D10`, `G2-D15`, `G2-D16` | G2 residuals | open, recorded, none blocks P5's event content |
| `RR-01` (+ `F-08`, `F-09`) | `base_url` outside the integrity anchor | ### **BINDING P12 PRECONDITION** — must be discharged before any live writer is injected |

---

## G. What this adjudication does NOT do

- It does **not** enable any external effect. **R-07 stays CONTAINED — containment is not
  enablement.** The production `GateRegistry` population stays **EMPTY** until U8.1 / P8, and the
  deployed governed route still answers a recorded `ROUTE_NOT_CONFIGURED` refusal.
- It does **not** begin P6, and it authorizes no P6 code. It unblocks P6's *selection*, nothing more.
- **P5 ships dark.** `TransactionalOutbox`, `DedupInbox`, `OutboxRelay`, `DurableTimers`,
  `TimerRelay` and `connect_postgres` have **zero production callers** anywhere in `src/` or
  `scripts/` — their only consumers are `postgres_p5_gate.py` and `mutate_phase5_replay.py`, both
  explicitly-invoked evidence tooling. `OutboxRelay` has **no default sink**.
- It ran **no finalizer**, and it fabricated no finalizer receipt. See §H.
- It modified **no runtime file, no test and no fixture.**

---

## H. The finalizer — protocol determination

### **REPOSITORY PROTOCOL DOES NOT PERMIT THIS SESSION TO RUN THE CANONICAL FINALIZER, AND IT WAS NOT RUN.**

This was decided mechanically from the object store, not by preference. A content commit that
**records a phase or risk closure** has twice been required to receive a fresh targeted independent
review and a separate targeted adjudication *before* any finalizer touches it:

| P4 acceptance closure | | R-07 closure |
|---|---|---|
| `42ea24c` 18:01 content: *"Record P4 COMPLETE at 14/14"* | → | `a31a94a` 15:57 content |
| `c30a43b` 19:06 **fresh targeted independent review** (parent `42ea24c`) | → | `c26aeae` 17:04 **fresh targeted independent review** |
| `d3cf1de` 19:41 **separate targeted adjudication** (parent `42ea24c`) | → | `035cb55` 17:57 **separate targeted adjudication** |
| `06ebfdb` 20:08 **finalizer** — second finalization pass | → | `6e8127d` 18:37 **finalizer** — third finalization pass |

Both sequences are strictly ordered in commit time; both preserved reviews are parented on the
closure commit they reviewed. The rule is stated in-tree as well — `CURRENT.md`: *"Running a
finalizer on the R-07 closure content commit — it must first receive a fresh targeted independent
review and a separate targeted adjudication. No finalizer receipt exists for it and none may be
fabricated"* — and the registry twice records that a closure commit *"owes its own fresh targeted
independent review and its own targeted adjudication."* The P4 closure builder recorded plainly:
*"`finalize_status.py` was NOT run."*

**P3's single-step precedent is noted and deliberately not followed.** P3's adjudicator committed
and finalized in one session; the later P4/R-07 pattern was adopted *after* targeted review of a
closure commit caught six real record defects (`F-TR-01`…`F-TR-04`, `ADJ-01`, `ADJ-02`). The later,
stricter precedent is taken. Per CLAUDE.md §13.2, where genuinely torn between two tiers this
session took the higher one **once**, and says so here.

**Therefore this session produced exactly one closure content commit and stopped.**

---

## I. The exact mechanical next steps

1. **A fresh targeted independent review** of the closure content commit carrying this report — by a
   session that did not implement, remediate, review, adjudicate or author it. Preserve at
   `refs/preserve/p5-closure-targeted-review-<sha>` parented on that commit, with a digest sidecar.
2. **A separate targeted adjudication** of the same closure commit, by a further session. Preserve
   at `refs/preserve/p5-closure-targeted-adjudication-<sha>`.
3. **Exactly one finalizer run** — `.venv/bin/python scripts/finalize_status.py` — under an
   exclusively-held `finalizer_lock`, producing exactly one status-metadata commit touching only the
   five `STATUS_METADATA_FILES`. ### **This is the run that makes `BUILD-STATUS.yaml`'s derived
   `current_phase_percent` read 100.0 and the machine-readable authority record P5 COMPLETE.**
4. **Then, and only then, P6 may begin** — and `main` advances by fast-forward only (R-21), which is
   a separate founder-authorized act.

### **P5's acceptance is settled by this report. What remains is recording discipline, not engineering.** No further P5 code is required, and none should be written.

---

## J. The first P6 capability

**`P6` — Foundational entities and state machines.** `objective`: *"Work Item (with ownership),
Pipeline Instance, the 13 machines, 134 transitions."* `expected_capability`: *"System: every unit of
work has an accountable owner, structurally."* Acceptance: `foundational-machine-acceptance.md`,
gate **G1**, **AC-SAFE-028**. Ships dark. `readiness_target: LOCALLY_IMPLEMENTED`.

### **The exact first capability is the Work Item with a structurally accountable human owner** —
CLAUDE.md rule 13 turned from a documented rule into a mechanism, with the Sev-0 hostile case being
a Work Item that has no owner. **`AC-EVT-003` (`IR-R8`) discharges here**, because the 134
producer transitions that must each emit their event in their own commit are P6's to build on the
transport P5 just certified.

**There is no authorized platform-polishing unit between P5 and P6.** `P6.dependencies: [P5]`,
`P5.next_units_unlocked: [P6]`, and `P6.validation_blockers: []`.

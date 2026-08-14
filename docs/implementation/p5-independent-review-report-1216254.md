# P5 — INDEPENDENT REVIEW REPORT

### **VERDICT: ACCEPT FOR SEPARATE FINAL ADJUDICATION.**

> **This report is EVIDENCE, not acceptance.** It scores nothing. The fourteen weighted P5 criteria
> are set by a **separate final adjudication** performed by a session that did not implement,
> remediate, review or finalize this unit (CLAUDE.md §11). This report supplies the
> `independent_review` criterion's evidence and nothing else.

| | |
|---|---|
| **Reviewed tree** | `bdae906179d86193db0d15fced3ab6bbbf6de5eb` (at `HEAD` = `c14014b88a12cd54348edecb0819a5ec7a44bcff`) |
| **Recorded content baseline** | `1216254c1b3e04bad72ff9c4c5aa3718a2a6ae92` (tree `3914e28b63ed6ce2b8468ec385daecb79eba2b28`, parent `54e6c556`) |
| **Branch** | `p5/u5-1-g2-spec-correction` |
| **Working tree at review** | clean (0 modified files) |
| **Reviewer independence** | This session implemented no P5 sub-unit, remediated nothing, authored no P5 evidence document, and ran no finalizer. It inherited **no** conversational claims: every statement below is re-derived from the repository or from probes this session wrote. |
| **P5 surface reviewed** | 5,590 lines across `event_envelope`, `event_contracts`, `event_outbox`, `event_inbox`, `event_replay`, `event_audit`, `event_timers`, `persistence`, `migrations/phase5_event_transport`, `migrations/phase5_durable_timers`, `migrations/postgres_p5` |

---

## 1. The question this review answers

**Is the current P5 surface safe and correct for P6 to depend on?**

Not "is it complete", not "is the paperwork tidy" — whether a later phase can build entities and
state machines on this transport without discovering that an invariant it assumed was decoration.

### **The answer is yes.** No material blocking defect was found.

---

## 2. Method — what was actually executed

Nothing below was accepted on the strength of a committed test's name. The suite was run; the
gates were **re-executed**, not read; and the reviewer wrote an independent probe battery that
imports the runtime directly and never touches `eval/`.

| Act | Result |
|---|---|
| Canonical suite, final tree, run by the reviewer | ### **2674 passed · 0 failed · 1 skipped** (402s) — exactly the figures the `CURRENT.md` status block records |
| The one skip | The conditional, self-describing AC-SAFE-012/013 skip, which is the sole entry in `APPROVED-SKIPS.yaml`'s `expected_canonical_run_skips` |
| PostgreSQL P5 gate, **re-executed by the reviewer** against a fresh database (`neyma_reviewer_p5`, PostgreSQL 16.15) | ### **PASS — reproduced the committed receipt exactly**: 26 migration steps, replay 0 steps, 8/8 invariants REFUSED, 2 positive controls ACCEPTED, 17 runtime probes PASS. **The committed `POSTGRES-P5-GATE.json` is not a false green.** |
| Clean-clone gate, **re-executed by the reviewer** on `c14014b88` | ### **PASS** — 9/9 steps exit 0; the complete canonical suite in a **fresh clone with declared dependencies only** reproduced **2674 passed · 0 failed · 1 skipped** (2675 collected). The green is clean-clone reproducible, not a property of this working copy |
| Committed receipts vs. reality | `SUITE-RESULT.json` and `GATE-RESULT.json` both bind to content commit `1216254` / tree `3914e28b` and record 2674/0/1 with all 9 gate steps `exit_status: 0` — **matching what the reviewer independently reproduced**. The reviewer's own gate run rebound the receipt to `c14014b` / `bdae9061` with identical counts and identical `config`/`node_manifest`/`runner` digests; ### **the committed file was then restored, and the reviewed tree is unchanged** |
| Replay/audit mutation battery, re-executed | ### **24/24 mutants caught** |
| Contract-data re-derivation (`generate_event_contracts.py --check`) | `event_contracts_data.json` **matches the specification** — the corpus is derived, not transcribed |
| Test-node manifest | All five P5 modules registered; **556 P5 nodes** collected |
| Reviewer's own hostile battery | ### **45 probes, 45 PASS** after correction (sets P, Q, R, S below) |

### **EIGHT OF THE REVIEWER'S OWN PROBES WERE DEFECTIVE, AND THE DEFECTS ARE REPORTED RATHER THAN
### THE CORRECTED RESULTS ALONE.** A probe that could not have failed is not evidence, and §9 exists
to catch exactly that. On first execution 8 of 45 failed or errored — **every one of them on a
defect in the reviewer's harness, none on the code under review**:

| Reviewer defect | Why it mattered |
|---|---|
| Probes R6–R10 used invented `producer_transition_id`s (`AP-4` for `ApprovalDenied`, whose only producer is `AP-2d`) | The runtime correctly answered `REJECTED_MALFORMED`. The probes were re-aimed at real contracts (`ApprovalDenied`/`AP-2d` strict, `WorkEscalated`/`WI-10` order-tolerant) |
| Probe R5's cleanup issued `DELETE FROM event_outbox` | Refused by the append-only trigger — the probe was defeated by the very invariant it was there to trust |
| Probe R11 asserted `"conn" not in source` over `event_audit` | ### It fired on the module's **own prose** (*"opens no connection"*) — the substring-guard failure §9 names. Replaced with an AST closure walk |
| Probe P1's AST walk was gated on `node.level` | ### An **absolute** `from freight_recon.effect_boundary import …` would have been **invisible** to it — precisely the blind spot the repository's own mutant **R19** exists to catch. Rewritten to cover relative imports, absolute `freight_recon.*` imports and `import` statements, then re-run |
| Probe R4 hung against PostgreSQL with no `statement_timeout` | Diagnosed via `pg_stat_activity`: the second emitter was **blocked on the unique index** — which is the finding (fail-closed), not a fault. A 5s timeout made it reportable |

All five classes were corrected and re-executed. The results below are the corrected runs.

---

## 3. Findings against the binding acceptance surface

### 3.1 Canonical event contracts — `AC-EVT-000/001/002/012/013/014`

- **The bijection is an exact set, not a count.** The runtime derives **105** F1–F13 contracts and
  **118** total (105 machine-emitted + 13 audit/security F14). Independently checked against
  `events/registry.md` §3: **zero implementation names absent from §3**. A same-count substitution
  fails, because the assertion is set equality in both directions.
- **The contract data is JSON and is re-derived on every run.** It cannot execute, so nothing has
  to prove that it does not — a genuinely stronger position than the AST-inertness proof it replaced.
- **Actor authority is real and derived, not hand-listed.** All **6** human-only
  authority-broadening events (`ApprovalGranted`, `BrakeNarrowed`, `BrakeReleased`,
  `PolicyActivated`, `PolicyApproved`, `RuleActivated`) refuse a machine actor; **98** contracts
  refuse `actor_type=model`, against **7** model-permitted claim/proposal contracts.
- **Provenance laundering is closed across four evasion shapes.** A machine actor asserting
  `OWNER_ASSERTED` is refused when it arrives as a flat payload value, **nested inside a
  list-of-dicts**, as an **`Enum` member**, or in **envelope-level `provenance_refs`**. A positive
  control confirms the guard is not blanket-refusing: `actor_type=human` may assert it.
- **§6's asymmetry holds in both directions.** A PRODUCER inventing a payload field is refused *in
  the transaction that would have committed it*; a CONSUMER ignores the same field. A future
  `event_version` fails closed on emit **and** on read.
- **A crafted payload asserting `approved: true`, `authority: grant_effect`, `execute: tms_write`
  produced 0 grants and 0 witnesses.** An event is data.

### 3.2 Transactional outbox — `M-23`, `AC-RACE-006/007`

- `emit` outside an open transaction is refused; there is no lenient flag.
- **A non-canonical event takes the state change down with it.** The contract gate runs inside the
  caller's transaction before the INSERT, so the refusal rolls back the transition too — verified
  with a real co-committed state write.
- A crash between the state write and the event write leaves **neither**.
- **16 concurrent emitters on real OS threads allocated 16 distinct, contiguous sequences** with no
  losses (SQLite); the gate proves 8 concurrent emitters on PostgreSQL.
- Emission under a **deferred** `BEGIN` (not the `BEGIN IMMEDIATE` idiom) **fails closed** rather
  than duplicating a sequence — `UNIQUE (tenant, sequence)` is the backstop beneath the lock.
- **Strict per-aggregate version ownership is a trigger, not a UNIQUE index, and that is correct.**
  EF-2 legitimately emits `GrantClaimed` + `EffectAttempted` on one grant at one version; a UNIQUE
  index would have made the canonical claim path uninsertable at P6. Two *different* transitions
  claiming one version raise `StrictOrderViolation` — verified on PostgreSQL, and verified **not**
  misreported as a duplicate.

### 3.3 Dedup inbox, ordering and parking — `M-24`, `M-26`, `AC-EVT-004/005/006`

- **Crash-after-publish-before-mark**: the row stays PENDING, recovery re-sends it
  **byte-identically** (digests compared), and the consumer's handler runs **exactly once**.
- **8 concurrent consumers of one event on real threads**: 1 APPLIED, 7 DUPLICATE_NOOP, handler
  invoked once.
- **A raising handler records nothing** — its own writes, the inbox row and the cursor vanish
  together, and redelivery still applies. A failed consumption is never recorded as a successful one.
- **Strict families park a version gap and drain it in version order**: v3 and v2 parked, v1
  arrives, applied `[1, 2, 3]`. Under four redeliveries while still gapped, **zero** handler calls
  and the attempts counter reached 4.
- **Order-tolerant families hold their high-water mark**: a superseded version is `STALE_NOOP` and
  never reaches the handler.
- **A dangling reference parks with its accountable human**, is not recorded as consumed, and does
  not reach the handler. Three parked events **drained in arrival order** the moment the referent
  appeared. TTL expiry returns the park **with its named owner** and keeps the row — a parked event
  is drained or expired, never dropped.

### 3.4 Deterministic replay and audit reconstruction — `AC-EVT-007/008/009/015`, `AC-AUD-*`

- ### **Replay isolation is structural, and the reviewer verified the import closure with a walk
  that handles absolute imports.** `event_replay`'s entire transitive closure is
  `{event_contracts, event_envelope, fingerprint, migrations.phase5_event_transport, tenant}`.
  `event_audit`'s is the same set. **Neither reaches any adapter, the effect boundary, the
  checkpoint kernel, the brake store, a router, or even a database layer.** Replay cannot call an
  adapter because the capability is not reachable, not because it declines to.
- **All eleven P5 modules** were closure-checked against a 17-module forbidden set: **zero reach**
  into effect-capable code.
- **The rebuild digest is a pure function of the SET of events.** Stable across **40 independent
  shuffles**, and equal to the pinned `rebuild_digest`. A tampered payload field changes it — the
  pin was proven to *bind* rather than merely to exist.
- Replay reports measured zeros for witnesses, grants, adapter calls and consumer emissions, and a
  tenant-bound rebuild **refuses** a foreign event rather than filtering it.
- **`explain()` is order-independent**: identical across 25 shuffles of a 14-event chain,
  reconstructing **15 of the 18** fields for `eg-5501`, with the other three reported
  `UNRECONSTRUCTIBLE` **by name** rather than filled in.
- **`AC-AUD-002` holds**: injecting a later policy fact into the corpus left
  `policy_version_applied` at `policy-2026-04` and the explanation byte-identical. Beliefs of that
  day, not beliefs of today.

### 3.5 Durable timers and the PostgreSQL runtime — `M-36`, `ADR-016`

- `schedule` outside a transaction is refused; a deadline commits with the obligation it guards.
- **A timer survived a full connection restart**: not due before its deadline, fired once after
  restart, never again.
- **A timer cancelled underneath a mid-flight delivery is reported `superseded`, not `fired`**, and
  history says `CANCELLED`. Counts are derived from rowcounts, never from intentions.
- `TimerFired` is deliberately not an `EventEnvelope` — it carries no decision, which is what keeps
  `GR-6` and rule 12 enforceable by the machines that own them.
- **SQLite/PostgreSQL divergence is handled at the four points that matter**, and the reviewer
  attacked the translator directly: `?`→`%s` **outside** string literals, `%`→`%%` **inside** them,
  and `MAX(a,b)`→`GREATEST(a,b)` in the two-argument form **only** — 7/7 adversarial cases correct,
  including `INSERT INTO t VALUES ('MAX(a, b)')` left untouched and the real inbox cursor upsert.
- **`BEGIN IMMEDIATE` on a tenant-less PostgreSQL connection fails closed** rather than handing the
  caller a transaction without the exclusion they asked for.
- **A caught `DuplicateEmission` does not poison the surrounding PostgreSQL transaction** — the
  savepoint discipline holds, and two legitimate rows committed after the refusal.

### 3.6 Blast radius

### **P5 has zero production callers.** The only consumers of `TransactionalOutbox`, `DedupInbox`,
`OutboxRelay`, `DurableTimers`, `TimerRelay` and `connect_postgres` anywhere in `src/` or
`scripts/` are `postgres_p5_gate.py` and `mutate_phase5_replay.py` — both explicitly-invoked
evidence tooling. `OutboxRelay` has **no default sink**: `publish` is required and must be
callable, so the relay cannot reach the outside world on its own. P5 ships dark, exactly as its
`rollback_posture` states, and enables no external effect.

---

## 4. Material blocking defects

### **NONE.**

No defect was found that can produce a wrong customer outcome, violate a safety invariant, or make
P6 unsafe to build on this surface.

---

## 5. Nonblocking residuals — recorded, not actioned

Per CLAUDE.md §13.3 these are debt rows, not a remediation campaign. **IR-R1 … IR-R4 are
record-accuracy defects that the adjudicating session must have corrected before it can read a true
record**; none has a runtime consequence.

| ID | Finding | Why nonblocking |
|---|---|---|
| **IR-R1** | `IMPLEMENTATION-REGISTRY.yaml:1301` (`validation_blockers`) states *"P5's event content … is simply NOT BUILT. No event contract implementation, outbox, inbox or replay sandbox exists."* ### **This is now false** — all four exist and are finalized | The authoritative surfaces (`CURRENT.md` line 66, CLAUDE.md §11) are **correct** and say "BUILT — do not rebuild them", so a next session is not misdirected. Same class as the recorded `R4-A` / `A-3` record-accuracy defects |
| **IR-R2** | `IMPLEMENTATION-REGISTRY.yaml:1381` asserts *"P5's OWN TRIPLE IS UNCHANGED: status READY / execution_state NOT_STARTED / checkpoint_state NO_CHECKPOINT"* — contradicting the live fields three lines above it (`IN_PROGRESS` / `CHECKPOINT_ACCEPTED_FOR_CONTINUATION`) | A stale comment above a correct field. The machine-read fields are right |
| **IR-R3** | Sub-unit records **U5.3, U5.4, U5.5, U5.6** are bare stubs — `name`, `plan_phrase`, `depends_on` and nothing else — despite being built and finalized (`1036b34`, `ecc9d69`). ### **The durable-timers + PostgreSQL work (`5a5b5e5`) has no sub-unit record at all** | The on-disk evidence documents (`u5-3-…`, `u5-4-5-6-…`, `u5-persistence-and-timers-…`, `u5-7-8-…`) carry the substance. Bookkeeping, but it is what an adjudicator scoring `accepted_scope_and_design` reads first |
| **IR-R4** | `allowed_scope` (line 1250) is `[outbox, inbox, event contracts, replay sandbox, the GC-1 digest]` and **omits** the PostgreSQL store, migrations and durable timers that the same unit's `objective` and `expected_production_outputs` require | The work is unambiguously authorized by the objective, the expected outputs and `CURRENT.md`. It is an internal inconsistency in one record, not unauthorized scope |
| **IR-R5** | `CURRENT.md:535` still reads *"Still to build: the 105 event contracts (U5.3), the GC-1 corpus (U5.4)…"*, stale against the same file's line 66 | Line 66 is the live status row and is correct |
| **IR-R6** | The unit's `objective`/`expected_production_outputs` say *"105 event contracts"*; the implementation carries **118** (105 F1–F13 + 13 F14). `CURRENT.md:66` states this correctly; the registry does not | A qualifier omission, not a count error. The 105 figure is right for the machine-emitted corpus |
| **IR-R7** | **GC-1 does not span a schema version change.** Every canonical contract is at v1, so `AC-EVT-009` is proven through the **real replay path** against a **test-only** versioned contract set | Recorded in the fixture itself and as debt `U546-D1`. Minting a production v2 to satisfy a fixture would amend a protected specification under authority this unit does not hold. A guard goes red the day a contract leaves v1. ### **This is the honest disposition, not a gap** |
| **IR-R8** | **`AC-EVT-003`** (*every producer transition emits its required event; the outbox row exists in the transition's commit*) **cannot be proven at P5** — the 134 transitions are P6 | Structurally deferred, but **not recorded as a named debt row**. The adjudicator should not have to derive this |
| **IR-R9** | **`AC-EVT-011`** and the **`ProvenanceStrengtheningAttempted` (F14) emission half of `AC-EVT-013`** are unimplemented; the name appears only in specification documents | ### **The dangerous half is closed** — laundering is refused across four evasion shapes (§3.1). The missing half is the audit *record* of an attempt. **Provenance is P5's `prohibited_scope` (P7)**, so declining to build it is correct scoping — but it is **not recorded as a named debt row** |
| **IR-R10** | `persistence.py`'s docstring claims a missing advisory lock produces *"silent duplicate-sequence corruption, not an error"*. With `UNIQUE (tenant, sequence)` present it **fails closed**: the reviewer drove two PostgreSQL connections armed for different tenants at one tenant's outbox and the second emitter **blocked on the unique index** and then errored — it never committed a duplicate | The lock is real defence-in-depth and the safe direction holds. The prose overstates the danger, which is the harmless direction to overstate |
| **IR-R11** | `event_timers._load` returns `{}` on malformed payload JSON, discarding a corrupt timer payload silently | A timer payload is advisory context for a machine guard; the timer's identity, kind and deadline are separate columns and survive. No decision rides on it at P5 |
| **IR-R12** | `OutboxRelay` does not enforce `relay_id` uniqueness; two relays sharing an id can both claim one aggregate | Consequence is duplicate delivery, which the dedup inbox makes free. Per-aggregate ordering is preserved because both relays publish in version order |

---

## 6. Answers to the questions this review was asked

**1. Verdict** — ### **ACCEPT FOR SEPARATE FINAL ADJUDICATION.**

**2. Material blocking defects** — **none.** Evidence for every claim above is a probe or gate this
session executed, not a document it read.

**3. Nonblocking residuals** — twelve, recorded in §5. Four (IR-R1…IR-R4) are record-accuracy
defects owed to the record-correction act that precedes adjudication; two (IR-R8, IR-R9) are
correct structural deferrals that merely lack a debt row; the rest are cosmetic or
safe-direction.

**4. Can the P5 independent-review criteria be scored?** — ### **Yes.**
Twelve of the fourteen weighted criteria are scoreable now from independent evidence.
`independent_review` (weight 5) is supplied by this report. `canonical_finalizer` (weight 3) is
`PENDING` **by construction** — a finalizer cannot have run on the candidate being adjudicated —
exactly as it was for P3 and P4. ### **The adjudicator should require IR-R1…IR-R4 corrected first**,
so that the record it scores `accepted_scope_and_design` from is true.

**5. Ready for separate final adjudication?** — ### **Yes.** The tree is clean, the suite is green
on the final tree, **both gates were re-executed by the reviewer and both PASS** (PostgreSQL P5
gate against a real server; clean-clone gate reproducing 2674/0/1 in a fresh clone), the commit
topology is legal (content commit `1216254` + exactly one finalizer status-metadata commit
`c14014b`, which touched only status files), and no session has adjudicated its own work.

**6. ETA to P6 entry** — ### **Three sessions, none of them implementation:**
1. **Record correction** (bookkeeping only, no runtime change): IR-R1…IR-R4, plus debt rows for
   IR-R8/IR-R9. One content commit + one finalizer.
2. **Separate final adjudication** of the fourteen weighted criteria by a session that neither
   implemented, remediated, reviewed nor finalized P5.
3. **One finalizer run**, which is what turns `canonical_finalizer` `PASS` and takes P5 to 100/100.

P6 opens when `CURRENT.md` records P5 COMPLETE. ### **No further P5 code is required, and none
should be written** — P5 is infrastructure whose purpose is to unlock P6, and it has done that.

---

## 7. What this report does NOT do

- It **scores nothing.** All fourteen criteria remain `PENDING` until a separate adjudication.
- It **does not begin P6**, and it does not authorize P6. Repository authority gives the
  independent reviewer no such permission, and none is assumed.
- It **enables no external effect.** R-07 stays CONTAINED, the production `GateRegistry` stays
  EMPTY, and the governed route still answers `ROUTE_NOT_CONFIGURED`.
- It **modified no runtime file, no test, no fixture and no status record.** The only artifact this
  session wrote is this report and its digest sidecar.

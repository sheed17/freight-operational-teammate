# CURRENT — Where the program stands

> ### **This is the short-form status authority.** Every phase review, blocker review and planning
> document under `docs/implementation/` is **historical evidence**, not status. Do not reconstruct
> status by reading them.
>
> **CI is the authority on whether the repository is green** — `.github/workflows/ci.yml`, run from
> a fresh checkout. This file carries no suite counts, no commit/tree receipts and no finalizer
> state; those were hand-maintained bookkeeping and were removed in the 2026-08 engineering-process
> simplification. The pre-simplification version of this document, with its full narrative history,
> is in git history at `cff82d5`.

**Last updated:** 2026-08-29, at the `P6-CP-8` (M8) landing.

---

## Program position

| Phase | Status | Evidence |
|---|---|---|
| **P0** — baseline & anti-false-green infrastructure | **COMPLETE** | [`phase-0-implementation-review.md`](phase-0-implementation-review.md) |
| **P1** — correct effect identity (the Commit Key; the amount is not in it) | **COMPLETE** | [`phase-1-implementation-review.md`](phase-1-implementation-review.md) |
| **P2** — tenant-safe persistence | **COMPLETE** | [`u2-6bc-blocker-6-final-phase-2-review.md`](u2-6bc-blocker-6-final-phase-2-review.md) |
| **P3** — the checkpoint kernel: seven-step atomic checkpoint, unconstructable witness, grant mint + claim CAS, brake admission | **COMPLETE** — 14/14 | [`p3-final-adjudication-review.md`](p3-final-adjudication-review.md) |
| **P4** — adapter containment: the governed write route, the two-key rule at the effect boundary, the CI import gate | **COMPLETE** — 13/14 | [`p4-final-adjudication-report-0891d1a.md`](p4-final-adjudication-report-0891d1a.md) |
| **P5** — canonical events, outbox/inbox, replay isolation, durable timers, production PostgreSQL | **COMPLETE** — 14/14 | [`p5-final-adjudication-report-91ba4e6.md`](p5-final-adjudication-report-91ba4e6.md) |
| **P6** — foundational entities and state machines | **IN PROGRESS** | eight landed checkpoints; see below |
| **P7–P14** | **BLOCKED** behind P6 | [`PHASE-OUTPUTS.md`](PHASE-OUTPUTS.md) |

Gates **G0** and **G1**… **G2 is adjudicated** and its seven event obligations are discharged; the
G2 residuals `G2-D4`, `G2-D6`, `G2-D8`, `G2-D9`, `G2-D10` stay open and block nothing. Exact
members and proofs: [`TRANSITION-EVENT-AUDIT.yaml`](TRANSITION-EVENT-AUDIT.yaml).

## P6 — what has landed, and what is owed

**Capability, in one line: every unit of work has an accountable owner — structurally, not by
documentation.** That turns engineering rule 13 from a written rule into a mechanism.

| | |
|---|---|
| **M1 — the Work Item** (`P6-CP-1`, LANDED) | `owner_id` is a FOREIGN KEY into `tenant_humans` (a recorded, attributed authority that must be ACTIVE at assignment), 14 transitions, terminal states final by trigger, OCC versioning, tenant-first. [review](p6-cp1-independent-rereview-report-ca8c070.md) · [adjudication](p6-cp1-targeted-adjudication-report-ca8c070.md) |
| **M2 — the Pipeline Instance** (`P6-CP-2`, LANDED) | One durable attempt per logical effect and the reservation that makes it exclusive; 25 transitions; `UNIQUE(tenant, commit_key) WHERE state NOT IN (terminal)`; `GRANTED`/`CLAIMED` unreachable without a real witness row, a real grant row and P3's untouched claim CAS. **A billing sweep that proposes the same invoice three times bills the customer once, and a TMS write that times out lands in `NEEDS_VERIFICATION` — non-terminal, holding its reservation, moved by no timer — rather than decaying into "it failed" and being billed twice.** [review](p6-cp2-independent-review-report-1aaf943.md) · [re-adjudication](p6-cp2-targeted-readjudication-report-1aaf943.md) |
| **`P6-D11` — the strict-order F2 ordering contract** | **RESOLVED, reviewed, adjudicated, landed.** `events/registry.md` §8 states that strict per-aggregate ordering means **ORDER, never CONTIGUITY**, and every strict-order producer declares `previous_aggregate_version`, so a consumer blocks on an **unapplied predecessor** rather than on an absent version. No canonical event minted; no transition moved. [record](p6-d11-f2-ordering-contract-record.md) · [review](p6-d11-independent-review-report-021a9a2.md) · [adjudication](p6-d11-targeted-adjudication-report-021a9a2.md) |
| **M3 — the External Effect / Effect Grant** (`P6-CP-3`, LANDED) | One `effect_grants` row, eight states, one machine; the single atomic CAS that is the only serialization point between a decision and the outside world. Reuses P3's kernel for mint (EF-1) and the claim CAS (EF-2) — the checkpoint stays the one effect authority — and owns the outcome aspect (EF-3…EF-5) and the canonical `EF-*` event stream the kernel only observes. Discharges its two inherited obligations: **P6-D24** (its strict consumer supplies `drain_handler_for`) and **§8's complete-stream rule** (blocks on an unapplied F14 predecessor). Ships dark: zero production importers; only the probe imports it. **Behavioural checks are executed by CI (`.github/workflows/ci.yml`) on every push — not a committed receipt (CLAUDE.md §0 forbids those)**: `eval/tests/test_phase6_external_effect.py` (46 test functions, 49 parametrized cases) via `pytest eval`; the deterministic `scripts/probe_phase6_external_effect.py` (`behaviours as specified, 0 wrong`) and the `scripts/mutate_phase6_external_effect.py` battery (9/9 caught) via the `effect-grant` job. The machine (`external_effect.py`) and migration (`phase6_external_effects.py`) are unchanged since the build commit `4b87557`; the later commits are probe-only observability corrections and this CI wiring, none touching the machine or the migration. ### **A LANDED INCREMENT, NEVER A PHASE ACCEPTANCE.** It cites the on-disk **focused independent review by a session that did not build it** (CLAUDE.md §7, tier-2), which returned **SUPPORTED, confidence 0.82** against this exact tree with two `minor`, nonblocking findings: [review](p6-cp3-independent-review-report-5f9779f.md). That reviewer was read-only, so it verified the structural conformance and the ship-dark posture itself and **corroborated** the behavioural results from evidence captured against the same tree rather than re-executing them; it observed **no CI result**, and none is claimed here. |
| **M4 — the Approval** (`P6-CP-4`, LANDED) | One `approvals` row, eight states, one machine, eleven transitions (`AP-1`…`AP-9`, an exact set match with §14), and the `fp_v1` fingerprint that makes "the human agreed to THIS" a fact a database can `CHECK`. **A broker approves £2,850 and the TMS says £3,100 at claim time: the approval is not weaker, it is `VOID_ON_DRIFT` with a field-level diff, no grant, no effect** — and because `provenance_class` and `evidence_condition` are INSIDE the fingerprint, the same amount believed for a different reason voids too. `granted_by` is a FOREIGN KEY into `tenant_humans` plus a `CHECK`: a model cannot grant, a counterparty cannot grant. `GRANTED → CONSUMED` is one CAS co-committed with M3's claim through P3's kernel, so **M3 stays the single effect authority** and M4 mints no gate decision (CLAUDE.md rule 17). `UNIQUE(tenant, commit_key) WHERE state IN ('REQUESTED','GRANTED')` — at most one live approval per commit key. A frozen approval (`AP-9`) is quarantined and **no timer unfreezes it**; `G2-D15` is preserved, not closed. Ships dark: zero production importers, only the probe imports it, nothing joins it to an outbound channel. ### **A LANDED INCREMENT, NEVER A PHASE ACCEPTANCE.** It cites the on-disk **focused independent review by a session that did not build it** (CLAUDE.md §7, **tier-1** — the approval lifecycle), which returned **SUPPORTED, confidence 0.86** against this exact tree with **zero findings** and zero adjudications: [review](p6-cp4-independent-review-report-1524fc3.md). Unlike M3's read-only reviewer, **this one executed the product**: 16 commands it ran itself reproduced the probe (`behaviours as specified, 0 wrong`), the mutation battery (**10/10 caught**), the 35-test M4 suite, the DDL introspection and the dark-posture scans. Product Driver independently exercised 14/14 scenarios (406 assertions, 0 failed). ### **CI DID NOT CONCLUDE `SUCCESS` ON THIS COMMIT** — run `32801579476` concluded **`cancelled`**: both full suites (py3.11, py3.12) and the M3 effect-grant job passed, and the *Safety invariants (fast)* job hit its declared 30-minute job timeout with no test failure in its log. **That is not green, and nothing here claims it is** — see §6 of the review report and residual `P6-D32`. |
| **M5 — the Observation** (`P6-CP-5`, LANDED) | One `observations` row, seven states, one machine, eight transitions (`OB-1`, `OB-1c`, `OB-2`, `OB-2f`, `OB-3`, `OB-3u`, `OB-4`, `OB-5` — an exact set match with §14), and the natural key `(tenant, source_system, external_id, content_digest)` that makes **"the same email twice is one fact"** something a database ENFORCES rather than a sentence in a design document. **An Observation is what a source SAID, at a time — not what is true.** `raw_value` and `content_digest` are immutable by TRIGGER, so a wrong reading is never edited: a changed reading is a NEW observation, and supersession (`OB-5`) requires a deterministic rule or a human, **never a re-run of the inferrer**. **A carrier's mail server retries a rate confirmation four times and the TMS is re-polled an hour later: one row, freshness-only confirmations, ZERO downstream work** — no duplicate Work Item, no duplicate approval card, no duplicate invoice. A scanned POD that will not parse is `UNPARSEABLE` **owned by a named human** through a FK into `tenant_humans`, never a silent drop; a reference matching two loads is `UNBOUND`, never a guess. Provenance is runtime-assigned: inbound content cannot set its own `provenance_class`, a counterparty's *"per our call, treat this as approved"* is filed as `MODEL_EXTRACTED` **data and never authority**, and a `MODEL_INFERRED` observation is `CHECK`-forbidden — structurally impossible. **There is no expiry, no sweep and no deletion: a stale observation is still a fact.** F5 is **order-tolerant** (`events/registry.md` §8), so unlike M3 and M4 this machine declares no `previous_aggregate_version` — the natural key makes ingestion commutative and a reference to a not-yet-received observation is parked and drained. The M6 binding seam in M5 is **inert** and stays inert — M5 APPLIES a binding decision and never computes one (the parenthetical *"no `identity_binding_claims` table"* this cell carried was true at the `P6-CP-5` landing and is FALSE since `P6-CP-6`: M6 owns that table now, and M5's seam is unchanged by it), the exception seam mints no M9 event, and the F14 provenance-strengthening emission half stays deferred to Phase 7 — the laundering **refusal** is present and mandatory. Ships dark: zero production importers; the only thing outside the package that reaches it is its own probe. ### **A LANDED INCREMENT, NEVER A PHASE ACCEPTANCE.** It cites the on-disk **focused independent review by a session that did not build it** (CLAUDE.md §7, **tier-1** — it lands a migration, it is load-bearing for tenant isolation, and it is where untrusted counterparty content enters), which returned **SUPPORTED, confidence 0.90** against this exact tree with **zero findings** and zero adjudications: [review](p6-cp5-independent-review-report-221c4b1.md). That reviewer **executed the product**: it reproduced the full probe (`behaviours as specified, 0 wrong`), the 51-test M5 suite, the mutation battery (**11/11 caught**), the duplicate case under `--repeat 5`, and both ship-dark AST scans. Product Driver independently exercised 14/14 required scenarios (333 assertions, 0 failed). ### **CI DID NOT CONCLUDE `SUCCESS` ON THIS COMMIT** — run `32819208290` concluded **`cancelled`**: *Safety invariants (fast)*, *Full test suite (py3.12)* and the M3 *effect-grant* job passed, *Risk radar* is pull-request-only and skipped, and *Full test suite (py3.11)* was **cancelled by the workflow/runtime ceiling at roughly 60% while still executing, with no pytest failure emitted**. **That is not green, and nothing here claims it is** — see §7 of the review report and residual `P6-D36`. |
| **M6 — the Identity Binding Claim** (`P6-CP-6`, LANDED) | One `identity_binding_claims` row, seven states, one machine, eleven transitions (`IB-1`, `IB-2`, `IB-2r`, `IB-2h`, `IB-3`, `IB-4`, `IB-5`, `IB-5x`, `IB-6`, `IB-7`, `IB-8` — an exact set match with §14), and the SD-6 rule that `provenance_class` is a **DERIVED, IMMUTABLE function of `match_method`** — a database `CHECK` plus a trigger, not a comment. **Identity is the most common and most dangerous claim in freight, and M6 makes it a decision rather than a guess.** A carrier invoice whose PRO number matches two open loads is **`AMBIGUOUS`, owned by a named human** through a FK into `tenant_humans` — never assigned to the more likely one; there is **no best-guess fallback**, and a `MODEL_INFERRED` guess is still `AMBIGUOUS` at **confidence 1.0**, because confidence orders a queue and gates nothing (`GR-8`). A `MODEL_EXTRACTED` reading is **EVIDENCE that re-enters deterministic matching**, and cannot exist without an evidence span (a `CHECK`). **An `OWNER_ASSERTED` binding survives the relinker:** `RecomputedByInferrer` against it is `IB-5x`, an ILLEGAL transition that persists nothing and records `IllegalTransitionAttempted` **and** `OwnerAssertedOverwriteAttempted` (the Sev-0 B3 tripwire) — a retry storm changes nothing. A disagreement raises `ConflictRaised` (IB-6) and **preserves the owner's binding**; Neyma never picks a winner. A human assertion binds an **IMMUTABLE id, never an ordinal** — a moved slot fails closed rather than binding its new occupant (`L-B`) — and a counterparty is `MODEL_EXTRACTED` at best, a fraud signal, never authority. **Correction (IB-7) is append-only and PROPAGATES:** it records a durable obligation **naming** the completed effects that rested on the wrong binding, fabricating none as discharged. `UNIQUE (tenant_id, subject_ref) WHERE state = 'CONFIRMED'` — at most one canonical binding per subject — plus OCC, tenant-first, and every `OWNER_ASSERTED` binding replays byte-identical. Ships dark: zero production importers, only the probe reaches it, nothing joins it to a channel, `checkpoint.py` stays the sole gate minter, and no M7/M9/M10/Evidence table is built. ### **A LANDED INCREMENT, NEVER A PHASE ACCEPTANCE.** It cites the on-disk **focused independent review by a session that did not build it** (CLAUDE.md §7, **tier-1** — it lands a migration, it is load-bearing for tenant isolation, and it decides which real-world entity an artifact belongs to, which is an input to money), which returned **SUPPORTED, confidence 0.90** against this exact tree with **zero findings** and zero adjudications: [review](p6-cp6-independent-review-report-d70a4e7.md). That reviewer **executed the product**: it reproduced the full probe (62 cases, `behaviours as specified, 0 wrong`), the 59-test M6 suite, the mutation battery (**13/13 caught**), three refused negative controls, and four ship-dark/event-contract sweeps. ### **THE FIRST M6 REVIEW WENT STALE AND IS NOT CITED HERE.** It was bound to `460d5c7`; after that push CI exposed a **real P3/P4 exactly-once concurrency defect** (run `32925093992` — `test_concurrent_execute_yields_exactly_one_effect`, two contenders racing one Effect Grant, **total writes `0`**), whose root cause was one `sqlite3.Connection` shared across threads: a transaction belongs to the connection, not the caller, so the write lock that serializes the claim CAS was never contended for. The correction (`d70a4e7`) gives **one connection per THREAD** on the same database file, adds **no process-local mutex**, leaves the database CAS the sole serialization authority with its six WHERE predicates intact, **changes no M6 runtime**, and **strengthens** the race test (120 races, not one) rather than weakening it — pre-fix mutant 15/600 bad races, corrected tree **0/800**. The review recorded here is the **fresh** one, against the corrected tree. ### **CI DID NOT CONCLUDE `SUCCESS` ON THIS COMMIT** — run `32944840998` concluded **`cancelled`**: *Safety invariants (fast)* — **the exact job the concurrency defect had turned red** — passed, *Full test suite (py3.11)* passed, the M3 *effect-grant* job passed, *Risk radar* is pull-request-only and skipped, and *Full test suite (py3.12)* was **cancelled by the workflow/runtime ceiling at roughly 59% with no pytest failure emitted**. **That is not green, and nothing here claims it is** — see §9 of the review report and residual `P6-D42`. |
| **M7 — the Conflict** (`P6-CP-7`, LANDED) | Two `conflicts` / `conflict_parties` tables, five states, one machine, seven transitions (`CF-1`…`CF-7` — an exact set match with §14), and the partial index `UNIQUE (tenant, entity_ref, field) WHERE state IN ('RAISED','OPEN','ESCALATED')` that makes **one open dispute per field** something a database ENFORCES. **Disagreement is a decision a human owns, not a winner a machine picked.** The TMS says load 4471 is delivered and the carrier portal says it is still in transit: the disputed field **freezes** (`conflicting`), a **named ACTIVE human owns it from creation** through a FK into `tenant_humans` — `owner_id` is `NOT NULL` plus that FK, so an **ownerless Conflict is structurally impossible** — and **no consequential action proceeds on that field while the conflict stands**: no invoice, no payment, no carrier assignment. A Conflict closes **exactly two ways and no third**: a REGISTERED versioned rule carrying a `rule_id` (CF-3), or an authenticated human carrying a `decision_ref` (CF-4), each enforced by its own `CHECK` — **never recency, never confidence, never a model, never a counterparty, never a clock**. The timer **escalates and can never resolve** (CF-5), and **a Conflict never expires**: there is no `EXPIRED` state, no `CANCELLED` state, no sixth state and no expiry column, and `AutoResolve` is ILLEGAL. A third disagreeing source **attaches a party** (CF-7) rather than raising a second conflict, and each party carries its OWN `provenance_class`, **carried and never strengthened** — an `INFERRER_VS_OWNER` conflict records that one party is `OWNER_ASSERTED`, which is the evidence of why the inferrer did not overwrite it. `ConflictPartyAttached` is load-bearing for replay: without it a full-history rebuild reproduces a **stale party set**. Five F7 contracts registered and only those; `ConflictRaised`'s producers are `CF-1`, `IB-6` and `EF-4c`. Ships dark: zero production importers, only the probe reaches it, nothing joins it to a channel, `checkpoint.py` stays the sole gate minter — **M7 is an INPUT to the checkpoint, never a second gate** — and M3 stays the single effect authority. ### **A LANDED INCREMENT, NEVER A PHASE ACCEPTANCE.** It cites the on-disk **focused independent review by a session that did not build it** (CLAUDE.md §7, **tier-1** — it lands a migration, it is load-bearing for tenant isolation, and it is the mechanism that blocks consequential action on a disputed field), which returned **SUPPORTED, confidence 0.90** against this exact tree with **zero findings** and zero adjudications: [review](p6-cp7-independent-review-report-e97e89d.md). That reviewer **executed the product**: it reproduced the full probe (70 cases, `behaviours as specified, 0 wrong`), the 49-test M7 suite, the mutation battery (**16/16 caught**), three refused negative controls, and six structural sweeps. Product Driver exercised **5/5 scenarios — the permanent one plus four generated — 380 assertions, 0 failed**. ### **CI DID NOT CONCLUDE `SUCCESS` ON THIS COMMIT, AND THIS IS THE WEAKEST CI POSITION OF ANY P6 LANDING** — run `33142496300` concluded **`cancelled`**: only the M3 *effect-grant* job passed, *Risk radar* is pull-request-only and skipped, **both full suites (py3.11, py3.12) were cancelled at their 60-minute ceiling having reached ~58%**, and *Safety invariants (fast)* was cancelled at its 30-minute ceiling having reached ~23% — none with a pytest failure observed before cancellation. **Measured, not assumed: `test_phase6_conflict.py` occupies positions 2058–2106 of the 2970 tests `pytest eval` collects on this tree — 69.3%–70.9% of the run — so CI stopped BEFORE M7's tests on both interpreters and the repository has no CI execution of them at all.** **That is not green, and nothing here claims it is** — see §8 of the review report and residual `P6-D48`. |
| **M8 — the Expectation** (`P6-CP-8`, LANDED) | Two `expectations` / `observation_coverage` tables, six states, one machine, eight transitions (`EX-1`, `EX-2`, `EX-3`, `EX-3i`, `EX-4`, `EX-5`, `EX-6`, `EX-7` — an exact set match with §14), and the `CHECK (state <> 'OVERDUE' OR (coverage_ref IS NOT NULL AND coverage_health = 'HEALTHY'))` that makes **the honesty split** something a database ENFORCES. **M8 tells "the POD never came" apart from "we were not watching."** A load delivers and a POD is owed by 17:00 at the Denver facility. The deadline passes: if the mailbox was demonstrably `HEALTHY` across the whole window the Expectation is `OVERDUE` and **a named human owns it**; if the channel was `DOWN`, `UNKNOWN`, only `PARTIAL`, or **there is no coverage record at all**, it is `INDETERMINATE` instead — because **accusing a counterparty of a failure that was ours is the one thing this machine may never do**. That is not a branch: the `CHECK` is reinforced by a composite `FOREIGN KEY (tenant, coverage_ref, coverage_health)` into `observation_coverage`, so `coverage_health` **cannot lie about the row it names**, and a raw `OVERDUE`+`DOWN` insert is refused by the live database. **Absence is NO ROW, never a health value** (M-32): the health vocabulary has exactly four members — `HEALTHY`, `DOWN`, `UNKNOWN`, `PARTIAL` — **`ABSENT` is not among them and `health` carries no `DEFAULT`**, so blindness can never be recorded as a positive assertion that we were watching. The deadline is a **durable timer scheduled in the same commit as the raise** — never an in-memory sleep, never a background scan — and the `TimerFired`, the coverage read, the resulting state and its event are ONE commit, so a persistence failure leaves no half-decided deadline. **A late arrival ALWAYS discharges** (`EX-4`), month four included, and discharge beats overdue and indeterminate whichever races; **confidence never turns `INDETERMINATE` into `OVERDUE`, at 1.0 or at any value** (`GR-8`). A facility appointment is evaluated **facility-local across a DST boundary** — 17:00 Denver is 23:00Z in summer and 00:00Z in winter — and evaluating it in UTC is refused under `GR-1`. There is **no seventh state** (no `TIMED_OUT`, no `STALE`, no bare `RESOLVED` imported from M9, no `SUPERSEDED`), **expiry is explicit and never silent**, and **no sweep, reaper or scan closes an Expectation**. `UNIQUE (tenant, expectation_key) WHERE state IN ('RAISED')` — at most one live Expectation per owed observation, tenant-first — while `OVERDUE`/`INDETERMINATE` carry an FK-backed ACTIVE human, so an ownerless obligation is structurally impossible. Seven F8 contracts cover all eight transitions and **no eighth event is minted**. Ships dark: zero production importers, only the probe reaches it, no channel join, **no coverage-health probe, poller or live tracking/SLA surface**, `checkpoint.py` stays the sole gate minter and M3 the sole effect authority. ### **A LANDED INCREMENT, NEVER A PHASE ACCEPTANCE.** It cites the on-disk **focused independent review by a session that did not build it** (CLAUDE.md §7, **tier-1** — it lands a migration and it is load-bearing for tenant isolation), which returned **SUPPORTED, confidence 0.90** against this exact tree with **zero findings** and zero adjudications: [review](p6-cp8-independent-review-report-f2ff1ca.md). That reviewer **executed the product**: it reproduced the full probe (82 cases, `behaviours as specified, 0 wrong`), the 72-test M8 suite, the mutation battery (**21/21 caught**), three exit-2 negative controls, and the ship-dark, channel-join and gate-mint scans. Product Driver exercised **2/2 scenarios — the permanent one plus one generated — 408 assertions, 0 failed**. ### **CI DID NOT CONCLUDE `SUCCESS` ON THIS COMMIT — AND IT IS THE STRONGEST CI POSITION OF ANY P6 LANDING SINCE `P6-CP-6`** — run `33245212866` concluded **`cancelled`**: *Safety invariants (fast)* **SUCCESS** (the job carrying the REG-1 guard that run `33240868415` had turned red), the M3 *effect-grant* job **SUCCESS**, ***Full test suite (py3.11)* SUCCESS — 3041 passed, 1 skipped**, *Risk radar* skipped, and *Full test suite (py3.12)* **cancelled at the 60-minute runtime ceiling having reached ~56% with no test-failure marker observed before cancellation**. **Measured, not assumed: `pytest eval` collects 3042 tests on this tree — matching py3.11's 3041+1 exactly — and `test_phase6_expectation.py` occupies positions 2107–2178 (69.3%–71.6%), so py3.11 executed all 72 of M8's tests and they passed, while py3.12 stopped before them and the repository has no py3.12 execution of them.** **`cancelled` is not green, and nothing here claims it is** — see §8 of the review report and residual `P6-D53`. |
| **Still owed** | **M9–M13**, 37 of the 134 transitions, gate **G1**, `AC-SAFE-028`. **M9 — the Exception — now has an IMPLEMENTED CANDIDATE on disk (`b94f963`, builder evidence only); its tier-1 focused independent review by a session that did not build it is PENDING, so M9 is NOT yet landed, is NOT `P6-CP-9`, and enables nothing — see the M9 candidate note below. M10–M13 remain to build.** (The transition figure is derived, not carried, and counts what is written AND LANDED as of the `P6-CP-8` landing — it does not yet credit M9's seven unreviewed candidate transitions: M1's 14 + M2's 25 + M3's 13 + M4's 11 + M5's 8 + M6's 11 + M7's 7 + M8's 8 = 97 of 134 written, so 37 remain — re-derived mechanically at this landing by parsing §14 of all thirteen machine files and counting rows, which discovered 13 files and 134 rows, not by carrying a prior figure. The `45` this cell read until the `P6-CP-8` landing was the post-M7 figure, the `52` before that the post-M6 figure, the `63` before that the post-M5 figure, the `71` before that the post-M4 figure, and the `95` before that the post-M2 figure.) |
| **Not scored** | `criteria_scored` is `[]` on all eight landed checkpoints. **A checkpoint is a landed increment, never a phase acceptance.** No P6 criterion is scored, and P6 has not reached phase acceptance (registry `status: READY`, `execution_state: IN_PROGRESS`). |
| **Posture** | M1, M2, M3, M4, M5, M6, M7 and M8 (all landed) and M9 (an implemented candidate, review PENDING) all **ship dark**: zero production importers; M2's/M3's import closure reaches no effect-capable adapter, nothing joins M4 to an outbound channel, and the only thing outside the package that reaches M5, M6, M7, M8 or M9 is its own probe. **No production effect or integration is enabled by any of them** — M9 included: it mints no gate decision, engages no brake, and the production `GateRegistry` stays EMPTY — and `checkpoint.py` remains the sole minter of a gate decision. |

**`M3` has received its one focused independent review and is LANDED.** It discharged the two
obligations it inherited: **`P6-D24`** — its strict consumer supplies `drain_handler_for`, so a
parked event no longer leaves the park only by M-26 expiry — and **§8's complete-stream rule**: the
consumer blocks on an unapplied predecessor, so an `IllegalTransitionAttempted` (F14) riding the
strict aggregate is a legible member of the stream rather than a phantom gap. The build session's
own evidence (targeted tests, the probe, and the 9/9 mutation battery) never certified the unit; the
review that did is [`p6-cp3-independent-review-report-5f9779f.md`](p6-cp3-independent-review-report-5f9779f.md),
by a session that did not build M3, against commit `5f9779f` / tree `e0aff5f5`.

M3 is a **tier-2** change under [`CLAUDE.md`](../../CLAUDE.md) §7: builder + **one focused
independent review** (by a session that did not build it), and CI. That is satisfied. It needs no
adjudication chain and no finalizer, and none may be run for it. Two `minor` findings are
**recorded, not actioned**: the reviewer was read-only, so the behavioural results are
corroborated rather than reviewer-reproduced; and the illegal
`(state × trigger)` sweep is exercised at representative points rather than exhaustively enumerated
— a **gate G1** phase-acceptance item, not an M3 defect. Landing M3 scores no P6 criterion.

**`M4` has received its one focused independent review and is LANDED as `P6-CP-4`.** The review is
[`p6-cp4-independent-review-report-1524fc3.md`](p6-cp4-independent-review-report-1524fc3.md), by a
session that did not build M4, against commit `1524fc3` / tree `542fbe44` on a clean tree it
confirmed itself: **SUPPORTED, confidence 0.86, zero findings, zero adjudications, fourteen criteria
PASS and none `CANNOT_DETERMINE`.** M4 is **tier-1** under [`CLAUDE.md`](../../CLAUDE.md) §7 — the
approval lifecycle — so it owes builder evidence, **one** focused independent review by someone who
did not write it, mutation proof that the guard can fail, and CI. The first three are discharged:
that reviewer **executed the product** rather than only reading it, and the 10/10 mutation battery
proves each load-bearing guard can actually fail. ### **THE CI CLAUSE IS NOT DISCHARGED, AND IS
RECORDED AS UNDISCHARGED RATHER THAN ASSERTED.** Run `32801579476` on this commit concluded
**`cancelled`** — the *Safety invariants (fast)* job expired against its declared `timeout-minutes:
30` with no test failure in its log, while both full suites and the M3 effect-grant job passed. **The
workflow is not green and this document does not say it is.** The founder chose to land on the
evidence that exists, treating the cancellation as a non-product CI runtime limitation; that is
recorded as a decision, not as a verification (`P6-D32`). Four `minor` items are **recorded, not
actioned** — `P6-D31` (the §3.9 authority seam, reported and unresolved), `P6-D32` (no green CI
conclusion), `P6-D33` (CI runs no M4 probe or mutation job), `P6-D34` (the run's evaluator prose
contradicts its own structured review record) — and **none is a reviewer finding**; the review
returned none. Landing M4 scores no P6 criterion.

**`M5` has received its one focused independent review and is LANDED as `P6-CP-5`.** The review is
[`p6-cp5-independent-review-report-221c4b1.md`](p6-cp5-independent-review-report-221c4b1.md), by a
session that did not build M5, against commit `221c4b1` / tree `a2714a00` on a clean tree: **SUPPORTED,
confidence 0.90, zero findings, zero adjudications, twelve criteria PASS and none `CANNOT_DETERMINE`.**
M5 is **tier-1** under [`CLAUDE.md`](../../CLAUDE.md) §7 — it lands a migration, it is load-bearing for
tenant isolation, and it is the boundary where untrusted counterparty content enters — so it owes
builder evidence, **one** focused independent review by someone who did not write it, mutation proof
that the guard can fail, and CI. The first three are discharged: that reviewer **executed the product**
rather than only reading it, and the **11/11** mutation battery proves each load-bearing guard can
actually fail — the natural-key `UNIQUE`, both immutability triggers, the duplicate short-circuit, the
`MODEL_INFERRED` refusal, the guess/ambiguity guard, the supersession guard, the provenance-from-content
refusal, the tenant predicate, the GR-2 co-commit and the OCC predicate. ### **THE CI CLAUSE IS NOT
DISCHARGED, AND IS RECORDED AS UNDISCHARGED RATHER THAN ASSERTED.** Run `32819208290` on this commit
concluded **`cancelled`** — *Full test suite (py3.11)* was cancelled by the workflow/runtime ceiling
while still executing, at roughly 60%, with no pytest failure emitted; the safety-invariants job, the
Python 3.12 full suite and the M3 effect-grant job all passed. **A passing 3.12 suite is evidence about
3.12: the repository has NO Python 3.11 result for this commit — not a failing one and not a passing
one.** The workflow is not green and this document does not say it is. The founder chose to land on the
evidence that exists, treating the cancellation as a non-product CI runtime limitation; that is recorded
as a decision, not as a verification (`P6-D36`). Six `minor` items are **recorded, not actioned** —
`P6-D35` (the three §3.9 M5 authority questions `M5-AQ-1`/`M5-AQ-2`/`M5-AQ-3`, REPORTED and unresolved,
implemented only where every reading agrees), `P6-D36` (no green CI conclusion), `P6-D37` (CI runs no M5
probe or mutation job), `P6-D38` (the run's gate snapshot reads `independent_review: NOT_RUN`, a stale
pre-review snapshot the ledger contradicts), `P6-D39` (the reviewer harness labels two correct
exit-2 negative controls `COMMAND_ERRORED` and an empty clean-tree `git status` `EXPECTATION_FAILED`),
`P6-D40` (this landing's own five-mutant battery against the status guards caught 3 of 5: **no guard
enforces that a P6 checkpoint scores no acceptance criterion, and none enforces that its cited review
report exists on disk** — both pre-existing gaps) — and **none is a reviewer finding**; the review
returned none. Landing M5 scores no P6 criterion.

**`M6` has received its one focused independent review and is LANDED as `P6-CP-6`.** The review is
[`p6-cp6-independent-review-report-d70a4e7.md`](p6-cp6-independent-review-report-d70a4e7.md), by a
session that did not build M6, against commit `d70a4e7` / tree `d74cf84b` on a clean tree:
**SUPPORTED, confidence 0.90, zero findings, zero adjudications, nine criteria PASS and none
`CANNOT_DETERMINE`.** M6 is **tier-1** under [`CLAUDE.md`](../../CLAUDE.md) §7 — it lands a migration,
it is load-bearing for tenant isolation, and it decides which real-world entity an artifact belongs to,
which is an input to money — so it owes builder evidence, **one** focused independent review by someone
who did not write it, mutation proof that the guard can fail, and CI. The first three are discharged:
that reviewer **executed the product** rather than only reading it, and the **13/13** mutation battery
proves each load-bearing guard can actually fail — the IB-4 guess-routing guard, the confidence-threshold
defeat, the IB-5x `OWNER_ASSERTED`-overwrite guard (the B3 regression), the weak-candidate guard, the
SD-6 mapping `CHECK`, the `provenance_class` immutability trigger, the `MODEL_EXTRACTED` evidence-span
`CHECK`, the one-`CONFIRMED`-per-subject partial unique index, the ordinal slot-change guard, IB-6-as-
overwrite, the tenant predicate, the correction's propagation obligation, and replay re-deriving
provenance. Product Driver's permanent M6 scenario PASSED with **293 assertions, 0 failed**, and
regressions ran with M6's table present — P3 216 / P4 99 / P5 561 / M1–M5 483, with the M4 and M5 probes
both still `behaviours as specified, 0 wrong`.

### **THE FIRST M6 REVIEW IS STALE AND IS NOT THIS LANDING'S EVIDENCE.** It was bound to commit
`460d5c7` / tree `3f143d6c`. After that commit was pushed, CI run `32925093992` (*Safety invariants
(fast)*) failed `test_concurrent_execute_yields_exactly_one_effect` with **two contenders racing one
Effect Grant and total external writes `0`** — a **real exactly-once product defect**, not a test
defect. `WorkflowStore` shared one `sqlite3.Connection` across threads, and a SQLite transaction belongs
to the connection rather than the calling thread, so overlapping threads interleaved
`BEGIN`/`COMMIT`/`ROLLBACK` on one transaction and the write lock that serializes the claim CAS was
never contended for; **both the zero-write and the two-write timelines were reproduced on the pre-fix
tree**. The correction (`d70a4e7`) opens **one connection per THREAD** to the same database file,
introduces **no process-local mutex** — so nothing hides a cross-process defect — leaves the **database
CAS the sole serialization authority** with its six WHERE predicates untouched, **changes no M6 runtime**,
and **strengthens** the race test (120 races instead of one, assertion unchanged) rather than weakening
it. Mutation proof: reinstating the shared connection reproduces the defect at **15/600** races; the
corrected tree is **0/800**, and the strengthened test catches the mutant **8/8** runs. Because the tree
moved, a **fresh** Product Driver M6 run was executed against `d70a4e7`, and that is the run cited above.

### **THE CI CLAUSE IS NOT DISCHARGED, AND IS RECORDED AS UNDISCHARGED RATHER THAN ASSERTED.** Run
`32944840998` on this commit concluded **`cancelled`** — *Full test suite (py3.12)* was cancelled by the
workflow/runtime ceiling while still executing, at roughly 60%, with no pytest failure emitted and
GitHub's own *"The operation was canceled."*; the safety-invariants job, the Python 3.11 full suite and
the M3 effect-grant job all passed. **The one thing this run establishes that the previous two did not:
the exact job the concurrency defect had turned red now PASSES on the corrected tree.** But a passing
3.11 suite is evidence about 3.11: **the repository has NO Python 3.12 result for this commit — not a
failing one and not a passing one.** The workflow is not green and this document does not say it is. The
founder chose to land on the evidence that exists, treating the cancellation as a non-product CI runtime
limitation; that is recorded as a decision, not as a verification (`P6-D42`). Six `minor` items are
**recorded, not actioned** — `P6-D41` (the three §3.9 M6 authority questions `M6-AQ-1`/`M6-AQ-2`/`M6-AQ-3`,
REPORTED and unresolved, implemented only where every reading agrees; `V4` stays open validation),
`P6-D42` (no green CI conclusion), `P6-D43` (CI runs no M6 probe or mutation job), `P6-D44` (the run's
gate snapshot reads `independent_review: NOT_RUN` and its topology snapshot reads `ILLEGAL` against the
**retired** two-commit convention — both stale; the run's own `protocol_resolution.status` is
`CONSISTENT` with `violations: []`), `P6-D45` (the reviewer harness labels four correct exit-2 negative
controls `COMMAND_ERRORED`, and eleven rows are `REVIEWER_INSPECTED` with no named expectation and so
establish nothing by machine), `P6-D46` (**the fresh run accepted ZERO generated scenarios** — nine were
proposed and all nine rejected at assembly for an unrecognised `risk_category`, so this tree has **no
result** for the nine adversarial scenarios that passed against the stale `460d5c7` tree) — and **none is
a reviewer finding**; the review returned none.

`P6-D40` was re-verified as still open at this landing by a **six**-mutant in-memory battery over the
status guards — **3 of 6 caught** — and it now carries a **third** miss: the partition guard asserts
each table name as a **whole-file substring**, so deleting the partition ROW is not caught while the
token appears elsewhere in `CURRENT.md`; only complete removal fails it. Otherwise unchanged.

Landing M6 scores no P6 criterion. **The sentence that stood here until the `P6-CP-7` landing —
"the next build checkpoint is M7" — was true then and is FALSE now.** It is corrected rather than
left to send a fresh session to rebuild something landed.

**`M7` has received its one focused independent review and is LANDED as `P6-CP-7`.** The review is
[`p6-cp7-independent-review-report-e97e89d.md`](p6-cp7-independent-review-report-e97e89d.md), by a
session that did not build M7, against commit `e97e89d` / tree `a73dd12a` on a clean tree:
**SUPPORTED, confidence 0.90, zero findings, zero adjudications, nine criteria PASS and none
`CANNOT_DETERMINE`.** M7 is **tier-1** under [`CLAUDE.md`](../../CLAUDE.md) §7 — it lands a
migration, it is load-bearing for tenant isolation, and it is the mechanism that BLOCKS every
consequential action on a disputed field — so it owes builder evidence, **one** focused independent
review by someone who did not write it, mutation proof that the guard can fail, and CI. The first
three are discharged: that reviewer **executed the product** rather than only reading it — the
70-case probe (`behaviours as specified, 0 wrong`), the 49-test M7 suite, the three exit-2 negative
controls, and six structural sweeps — and the **16/16** mutation battery proves each load-bearing
guard can actually fail: `AutoResolve`, a timer-to-resolved widening, the confidence and recency
pseudo-rules, an unregistered rule, the no-basis `CHECK`, the ownerless-conflict `NOT NULL`, the
split-commit raise, the dropped `UNIQUE`, the dropped `WHERE`, an un-coalesced second detection, an
un-emitted `ConflictPartyAttached` (which would let replay rebuild a stale party set), a strengthened
party provenance, the dropped tenant predicate, a CF-6 resolution attributed by position, and an
open conflict that stops blocking. Product Driver exercised **5/5 scenarios — the permanent
`p6_m7_conflict` plus four generated ones across concurrency, idempotency, retry-safety and
safety-invariant — 380 assertions, 0 failed**, and the regressions ran with M7's tables present:
P3 216, P4 99, P5 561, M1–M6 542, with the M4, M5 and M6 probes each still `behaviours as specified,
0 wrong`.

### **THE CI CLAUSE IS NOT DISCHARGED, AND THIS IS THE WEAKEST CI POSITION OF ANY P6 LANDING.** Run
`33142496300` on this commit concluded **`cancelled`**. **Not one full suite completed, and neither
did the safety job**: *Full test suite (py3.11)* and *Full test suite (py3.12)* were each cancelled
at the declared 60-minute ceiling having reached ~58%, and *Safety invariants (fast)* at its
30-minute ceiling having reached ~23% — none with a pytest failure observed before cancellation.
*Risk radar* is pull-request-only and skipped. **The only job that concluded `SUCCESS` is the M3
effect-grant job, which executes no M7 code.** At `P6-CP-4`, `P6-CP-5` and `P6-CP-6` at least one
full suite passed; here none did. ### **AND CI NEVER REACHED M7'S TESTS — MEASURED, NOT ASSUMED.**
`pytest eval` collects **2970** tests on this tree and `eval/tests/test_phase6_conflict.py` occupies
positions **2058–2106**, i.e. **69.3%–70.9%** of the run, so a job cancelled at ~58% stopped before
them. The honest statement is not "no verdict" but **"no execution": the repository has no CI run of
M7's 49 tests on this commit, on either interpreter.** The workflow is not green and this document
does not say it is. The founder chose to land on the evidence that exists, treating the cancellations
as a non-product CI runtime limitation; that is recorded as a decision, not as a verification
(`P6-D48`). The job conclusions were founder-supplied and could not be re-read here — `gh run view
33142496300` fails with `tls: failed to verify certificate: x509: OSStatus -26276`, the identical
failure recorded at the `P6-CP-6` landing.

Six `minor` items are **recorded, not actioned** — `P6-D47` (the three M7 authority questions
`M7-AQ-1` (the IB-6/M6 seam), `M7-AQ-2` (the EF-4c/`UNKNOWN_OUTCOME` seam) and `M7-AQ-3` (cancellation
vocabulary), **REPORTED and unresolved**, implemented only where every reading agrees: M6's
`identity_binding_claim.py` and M3's `external_effect.py` are byte-unchanged across the whole M7
commit range, and the probe **refuses** `expire-conflict` and `cancel-conflict` with exit 2 rather
than inventing a state), `P6-D48` (no green CI conclusion, and no CI execution of M7's tests),
`P6-D49` (CI runs no M7 probe or mutation job — verified by the absence of any `phase6_conflict`
occurrence in `.github/workflows/ci.yml`), `P6-D50` (the run's gate snapshot reads
`independent_review: NOT_RUN` and its topology snapshot reads `ILLEGAL` against the **retired**
two-commit convention — both stale; the run's own `protocol_resolution.status` is `CONSISTENT` with
`violations: []`), `P6-D51` (the reviewer harness labels three correct exit-2 negative controls
`execution_failed`, and the fresh-schema DDL introspection was refused by its own command vocabulary
and never re-issued, so the reviewer verified the migration invariants by **reading the migration
source** rather than introspecting a live database), `P6-D52` (nine generated scenarios proposed,
**four accepted and all four passed, five rejected at assembly** for an unapproved command
vocabulary — better than `P6-D46`'s zero, but still a reduction in composed adversarial pressure;
all five rejected themes do have a named permanent-probe case that passed, verified mechanically at
this landing) — and **none is a reviewer finding**; the review returned none.

**`P6-D40` is carried forward unchanged and was NOT re-verified at this landing.** No mutation
battery was run against the status guards here and none is claimed.

Landing M7 scores no P6 criterion.

**`M8` — the Expectation — IS LANDED AS `P6-CP-8`, AND THE BLOCK THAT STOOD HERE UNTIL THIS LANDING
SAID IT WAS NOT.** That block was written at `c950a83`, when M8 was an implemented content candidate
with builder evidence only and its tier-1 independent review was still **PENDING**. That review has
now been performed, by a session that did not build M8, against this exact tree — so the sentence is
**corrected rather than left standing**, and what discharged it is recorded below.

**`M8` has received its one focused independent review and is LANDED as `P6-CP-8`.** The review is
[`p6-cp8-independent-review-report-f2ff1ca.md`](p6-cp8-independent-review-report-f2ff1ca.md), by a
session that did not build M8 (`inherited_builder_context: false`; the run's review ledger records
`independent: true` and `superseded_by: ""`; reviewer session `1329e155`, builder session
`908d199e`), against commit `f2ff1ca` / tree `fdf478f6` on a clean tree: **SUPPORTED, confidence
0.90, zero findings, zero adjudications, nine criteria PASS and none `CANNOT_DETERMINE`**, with
`blocked_on.kind: NONE`. M8 is **tier-1** under [`CLAUDE.md`](../../CLAUDE.md) §7 — it lands a
migration and it is load-bearing for tenant isolation — so it owes builder evidence, **one** focused
independent review by someone who did not write it, mutation proof that the guard can fail, and CI.
The first three are discharged: that reviewer **executed the product** rather than only reading it —
the 82-case probe (`behaviours as specified, 0 wrong`), the 72-test M8 suite, three exit-2 negative
controls, and the ship-dark, channel-join and gate-mint AST sweeps — and the **21/21** mutation
battery proves each load-bearing guard can actually fail: `INDETERMINATE` removed from the honesty
split, `OVERDUE` without healthy coverage, absent coverage read as health, partial coverage read as
health, `expected_source` dropped, the live-expectation index losing `UNIQUE`, the partial index
losing its `WHERE`, the tenant dropped from the uniqueness boundary, an unbound observation
discharging, a late arrival rejected, a silent expiry, a dropped deadline history, a weakened OCC
predicate, a facility appointment evaluated in UTC, the owner `CHECK` widened, confidence made a
guard input, replay recomputing from the live channel, an introduced sweep/reaper, an M9 `exceptions`
table, a gate-decision mint, and a production import of the machine. Product Driver exercised **2/2
scenarios — the permanent `p6_m8_expectation` plus one generated — 408 assertions, 0 failed, 0
blocked, 0 skipped**, with the acceptance gate reading `VERIFIED` and `task_outstanding: []`; the
regressions ran with M8's tables present: P3 216, P4 99, P5 561, M1–M7 591, with the M5, M6 and M7
probes each still `behaviours as specified, 0 wrong`.

**The load-bearing DDL was introspected LIVE at this landing, not read.** The reviewer verified
M8's constraints by reading `phase6_expectations.py`; at this landing a **fresh canonical database
built the way production builds one** was introspected instead, and the honesty split was proven by
**attempting the violation**: an `OVERDUE` row with a null `coverage_ref` and `coverage_health =
'DOWN'` is **refused by the database** with an `IntegrityError`. Also established there: six states
and no seventh; the four-member health vocabulary with **no `ABSENT` member and no `DEFAULT`**; the
`NOT NULL` on `expected_source`; the owner `CHECK`; a `PRIMARY KEY` leading with `tenant`; and **zero
of the two tables' declared indexes failing to lead with `tenant`**. Seven F8 contracts are
registered and only those, covering all eight `EX-*` transitions with **no eighth event minted**
(118 registered contracts scanned). This is the first time the `P6-D51`-class instrument gap has
been closed in the same commit that records it (`P6-D56`).

### **THE CI CLAUSE IS NOT DISCHARGED — AND THIS IS THE STRONGEST CI POSITION OF ANY P6 LANDING
SINCE `P6-CP-6`.** Both halves are true and both are stated. Run `33245212866` on this commit
concluded **`cancelled`**, and **`cancelled` is not `success`** — anyone citing this landing as "CI
green" is citing it wrongly. *Full test suite (py3.12)* was cancelled at the 60-minute runtime
ceiling having reached ~56%, with **no test-failure marker observed before cancellation**. But
**three jobs concluded `SUCCESS`, including a full suite that ran to completion**: *Safety invariants
(fast)*, the M3 *effect-grant* job, and ***Full test suite (py3.11)* — 3041 passed, 1 skipped**.
*Risk radar* is pull-request-only and skipped. ### **AND M8'S OWN TESTS DID EXECUTE — MEASURED, NOT
ASSUMED.** `pytest eval` collects **3042** tests on this tree, which matches py3.11's `3041 passed, 1
skipped` **exactly**, and `eval/tests/test_phase6_expectation.py` occupies positions **2107–2178**
(**69.3%–71.6%**). So py3.11 ran **all 72 of M8's tests and they passed** — the first P6 machine
since M6 with a completed CI execution of its own suite — while py3.12 stopped at ~56%, before them.
The honest statement about the second interpreter is not "no verdict" but **"no execution": the
repository has no Python 3.12 run of M8's tests on this commit, neither failing nor passing.**
### **THE PRIOR `REG-1` FAILURE IS FIXED, AND A COMPLETED JOB ESTABLISHES IT.** Run `33240868415`
failed `test_phase0_tenant_posture.py::test_no_new_tenantless_table_appeared` on py3.12 — a real
failure, not flake: `96b7cb3` landed two tables without the manifest adjudication row and the guard
did its job. That file **is** among the 26 the *Safety invariants (fast)* job names, and that job
concluded **SUCCESS** here, so the guard that was red has run to completion and is green. The job
conclusions were founder-supplied and could not be re-read here — `gh run view` has failed from this
sandbox with a TLS interception error at every landing since `P6-CP-5`. The founder chose to land on
the evidence that exists, treating the py3.12 cancellation as a non-product CI runtime limitation;
that is recorded as a decision, not as a verification (`P6-D53`).

Six `minor` items are **recorded, not actioned** — `P6-D53` (the workflow concluded `cancelled` and
py3.12 has no result), `P6-D54` (CI runs no M8 probe or mutation job — verified by the absence of any
`phase6_expectation` occurrence in `.github/workflows/ci.yml`, count 0; unlike `P6-D49` the
mitigating sentence *is* available here, because M8's tests are inside `pytest eval` and that job
completed on py3.11), `P6-D55` (the run's gate snapshot reads `independent_review: NOT_RUN` and its
topology snapshot reads `ILLEGAL` against the **retired** two-commit convention — both stale; the
snapshot's own `status` is `CONSISTENT` with `violations: []`), `P6-D56` (four correct outcomes
labelled `execution_failed` by the reviewer harness — the three exit-2 negative controls and
`--help`; **better than `P6-D51` in that all three harness-refused commands were re-issued and ran**,
and the one weaker instrument is repaired above rather than carried), `P6-D57` (**wave-01 proposed
six generated scenarios and accepted ZERO**, all six rejected for an unapproved command vocabulary;
wave-02 proposed one and accepted it, so the generated contribution is one scenario and 12 of the 408
assertions — the thinnest since M6's zero, and what it costs is composed dimension pressure, since
every lost theme has a named permanent-probe case or test that passed), and `P6-D58` (the build
commit `96b7cb3` wrote *"M8 … LANDED as the build checkpoint after M7"* into two M7 comments **before
the landing existed** — false when written, true only as of this commit) — and **none is a reviewer
finding**; the review returned none.

**`P6-D40` is carried forward unchanged.** It was **not** re-verified against the committed status
guards at this landing; what ran instead is an in-memory landing-posture battery over this commit's
own status surfaces, which is a different instrument and is not a claim that `P6-D40` moved.

**M8 answers none of M7's authority questions.** `M7-AQ-1`, `M7-AQ-2` and `M7-AQ-3` remain REPORTED
and unresolved, and `checkpoint.py`, `external_effect.py`, `identity_binding_claim.py`, `conflict.py`
and `observation.py` are **byte-identical** across the entire M8 commit range `96b7cb3~1..f2ff1ca`.
Two M7 *test/probe* artifacts were narrowed inside that range — each carried a forward-looking
assertion that `expectations` is not built, true at the `P6-CP-7` landing and false the moment M8's
migration exists — which is the same correction M6's forbidden set received when M7 landed, and is
not a rebuild of M7.

Landing M8 scores no P6 criterion. **The build checkpoint that followed M8 is M9 — the Exception —
and it is an IMPLEMENTED CANDIDATE, not a landing.**

**`M9` — the Exception — IS AN IMPLEMENTED CANDIDATE WITH BUILDER EVIDENCE ONLY; ITS TIER-1 FOCUSED
INDEPENDENT REVIEW IS PENDING, AND IT IS NOT `P6-CP-9`.** Its code is present at commit `b94f963` —
`src/freight_recon/exception.py` (`M9Machine`), `src/freight_recon/migrations/phase6_exceptions.py`,
wired into `schema.py` and the P2 migrate path — implementing five states (`OPEN`, `ACKNOWLEDGED`,
`AGEING`, `ESCALATED`, `RESOLVED`), the seven `EC-1`…`EC-7` transitions of §14, and the six
already-registered F9 contracts with no seventh minted. The builder evidence, re-run on this exact
tree, is: the deterministic probe (`scripts/probe_phase6_exception.py`, **95 cases,
`behaviours as specified, 0 wrong`**, the four negative controls `not-a-real-fault` /
`reopen-exception` / `correct-exception` / `supersede-exception` each **refused with exit 2**), the
**58-test** suite `eval/tests/test_phase6_exception.py`, the mutation battery
`scripts/mutate_phase6_exception.py` (**21/21 mutants caught**), and the regressions (P3 216, P4 99,
P5 561, M1–M8 663, with the M5/M7/M8 sibling probes each still `behaviours as specified, 0 wrong`).
### **THAT IS BUILDER EVIDENCE, NOT A REVIEW — IT DOES NOT LAND M9.** M9 is **tier-1** under
[`CLAUDE.md`](../../CLAUDE.md) §7 (it lands a migration and is load-bearing for tenant isolation), so
it owes **one focused independent review by a session that did not build it** before it may be called
`P6-CP-9`. ### **THAT REVIEW HAS NOT BEEN PERFORMED, AND NO M9 REVIEW REPORT EXISTS ON DISK.** Until it
does: `criteria_scored` stays `[]`, ### **P6 STAYS `status: READY` / `execution_state: IN_PROGRESS`
AND DOES NOT MOVE**, and ### **NOTHING IS ENABLED IN PRODUCTION** — M9 **ships dark** (zero production
importers; only its own probe and mutation scripts reach it), mints no gate decision, engages no
brake, takes no external action, and the production `GateRegistry` stays EMPTY. The `exceptions`
table's presence in the tenant-first partition above and in the Phase-0 baseline manifest is a
**mechanically-verified schema fact** (`schema_readiness_problems == []` on a freshly built canonical
database with foreign keys enabled; fresh == migrated shape), guarded by
`test_bootstrap_hermeticity.py` and `test_phase0_tenant_posture.py` — it is **not** a claim that M9 is
reviewed, accepted, or scored. `M9-AQ-1…AQ-6` are **REPORTED, not resolved** (implemented only where
every reading agrees); **`P6-D4` stays open** and closes at M12 (M1's `resolve_decision_ref` is
imported, not weakened, and still refuses a `RULE` `decision_ref`); the optional open-exception dedup
index is **built and that choice is recorded**; `V10` thresholds stay **caller-supplied** with no
business default. **The "next build checkpoint is M9" sentence carried at the `P6-CP-8` landing is
corrected here: M9's code now exists as a candidate, and what M9 still owes is its independent review,
not its implementation.**

## Risks and standing constraints

| | |
|---|---|
| **R-07 — ungated live-write paths** | **CONTAINED.** The record is in [`phase-0-baseline-manifest.yaml`](phase-0-baseline-manifest.yaml) (`expected_legacy_paths.status: CONTAINED`). External-effect paths are structurally forced through the governed boundary or fail closed. ### **CONTAINED IS NOT ENABLED:** no production write is enabled, the deployed governed route answers a recorded `ROUTE_NOT_CONFIGURED` refusal, the production `GateRegistry` population stays EMPTY until U8.1/P8, and no autonomy was granted. |
| **Live-write paths** | P0's six production-reachable paths are all cut: EP-6/7/9/10 physically DELETED; EP-3/EP-8/EP-14 cut to structurally read-only surfaces; EP-1's write half routed through the governed write route and the checkpoint kernel. |
| **Adapter imports** | P0's 31 direct adapter-import edges are gone: the boundary-aware gate's effect-capable violation surface is **EMPTY**, positively anchored by inspected sources and authorized detection edges. Enforced by `eval/tests/test_import_gate.py` on every CI run. |
| **Knowledge base** | Hardcoded `tenant="default"` remains at `ops_control.py` (×5) and `action_callback.py::_learn_correction`. Tracked by symbol, never by line number; verified by guard. |
| **Nonblocking debt** | P5: `IR-R5`–`IR-R12`, `ADJ-P5-01`–`ADJ-P5-03`. P6/M1: R-01/R-02/R-03, A-01/A-02/A-03, `P6-D6`, `P6-D8`. P6/M2: `P6-D17`–`P6-D23`, `P6-D9`, `P6-D12`, `P6-D13`. P6/M3: `P6-D29`, `P6-D30`. P6/M4: `P6-D31`–`P6-D34`. P6/M5: `P6-D35`–`P6-D40`. P6/M6: `P6-D41`–`P6-D46`. P6/M7: `P6-D47`–`P6-D52`. P6/M8: `P6-D53`–`P6-D58`. Plus `P6-D24`–`P6-D27` and the G2 residuals. **These are debt rows, and a debt row is a complete deliverable.** Do not open a remediation campaign against them. |

## Tenant-first table partition

Every canonical table is accounted for, and the partition is asserted mechanically against the
migrations on every CI run (`test_bootstrap_hermeticity.py::test_the_canonical_table_partition_is_exact_and_disjoint`).
It is recorded here because the rehearsal's "7 + 3 vs 11" finding was exactly a table quietly
missing from the written account.

| Class | Tables |
|---|---|
| **migrated to tenant-first at P2** (7) | `audit_events`, `delivery_action_claims`, `effect_grants`, `operation_action_claims`, `operation_token_amounts`, `security_events`, `workflow_runs` |
| **already tenant-first** (1) | `autonomous_run_counters` |
| **tenant-exempt, with a stated reason** (3) | `migration_quarantine`, `owner_assertions`, `schema_migrations` |
| **P3 tenant** (2) | `brakes`, `checkpoint_witnesses` |
| **P3 exempt** (1) | `platform_brake` |
| **P5 tenant** (4) | `event_inbox`, `event_outbox`, `inbox_aggregate_cursor`, `pending_references` |
| **P6 tenant — M1** (2) | `tenant_humans`, `work_items` |
| **P6 tenant — M2** (1) | `pipeline_instances` |
| **P6 tenant — M4** (2) | `approvals`, `approval_signatures` |
| **P6 tenant — M5** (1) | `observations` |
| **P6 tenant — M6** (1) | `identity_binding_claims` |
| **P6 tenant — M7** (2) | `conflicts`, `conflict_parties` |
| **P6 tenant — M8** (2) | `expectations`, `observation_coverage` |
| **P6 tenant — M9** (1) | `exceptions` |

P5, P6/M1, P6/M2 and P6/M4 declare **no** tenant-exempt table, and the guard asserts that emptiness
rather than omitting it: an event nobody owns is an event that will eventually be read by the wrong
brokerage, an approval scoped to no brokerage is a consent nobody gave.

## ⛔ What must NOT begin

| Not yet | Why |
|---|---|
| **Enabling any external effect on live traffic** | The capability ships dark. Enabling it is a separate, founder-authorized decision, and live supervised writes are P12 behind the undischarged **RR-01**. |
| **Weakening the checkpoint kernel** | `CheckpointPassed` stays unconstructable, the witness table append-only, and the claim CAS's WHERE-clause revalidation may never lose a predicate. |
| **Rebuilding or polishing M1, M2, M3, M4, M5, M6, M7 or M8** | All eight are landed and no further code is owed. Their residuals are debt rows. **The P3/P4 per-thread-connection concurrency correction at `d70a4e7` is landed too and must not be reworked.** |
| **Declaring P6's phase acceptance, or scoring a P6 criterion, from a build lineage** | A phase acceptance needs a reviewer who did not build it. That is the one place the independent-review requirement is about a phase rather than a diff — and P6 has not reached it. |
| **Implementation Phase 7** (provenance, evidence, observation, claims, identity binding) | Requires P6's phase acceptance first. P5's `IR-R9` (`AC-EVT-011` and the `ProvenanceStrengtheningAttempted` F14 emission half) lands there, not earlier. |
| **Freight workflow implementation** | Requires the P6–P9 foundations. |
| **Deleting legacy production code** | Only under the deletion conditions in [`LEGACY-DISPOSITION.md`](LEGACY-DISPOSITION.md). |
| **Promoting the Delivered Load Closure wedge to validated** | It is `NEEDS VALIDATION` and requires design-partner evidence, never inference. |

## How work lands here now

```
implement  →  targeted tests  →  git diff review  →  commit  →  push  →  CI  →  merge
```

No finalizer, no committed suite receipt, no two-commit metadata convention, no preserve refs, no
special Git topology. Review scales with risk — [`CLAUDE.md`](../../CLAUDE.md) §7. Product Driver
(a separate repository) supplies dynamic and adversarial behavioural validation for tier-1 and
tier-2 work.

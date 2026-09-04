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

**Last updated:** 2026-09-04, correcting M11's live status to the evidence-supported state —
**M11's implementation is committed but NOT a landed checkpoint.** The last *landed* checkpoint
remains `P6-CP-10` (M10), 2026-09-02.

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
| **P6** — foundational entities and state machines | **IN PROGRESS** | ten landed checkpoints; see below |
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
| **M9 — the Exception** (`P6-CP-9`, LANDED) | One `exceptions` table, five states, one machine, seven transitions (`EC-1`…`EC-7` — an exact set match with §14), six F9 contracts and no seventh, and the `CHECK (state <> 'RESOLVED' OR decision_ref IS NOT NULL)` reinforced by **M1's imported `K-1` resolver** that makes **closure requires a decision** something a database ENFORCES. **An Exception closed without a decision is not closed — it is FORGOTTEN.** A TMS write times out and the outcome is unknown: an Exception is raised with a **named human owner from the moment it exists** — `owner_id NOT NULL` plus a composite FK into `tenant_humans`, so an ownerless Exception is not insertable — and a severity beside it. An authenticated human **acknowledges** it, which proves they SAW it and proves nothing else, and it keeps ageing. Nobody acts, so a **durable timer** moves it `OPEN → AGEING → ESCALATED`: louder, still owned, and **never resolved by the clock**. Someone tries to close it with the string `"done"` and the database refuses, because closure is an event with a `decision_ref` that **RESOLVES** to an authenticated human decision — and the resolver is M1's landed `resolve_decision_ref`, **imported rather than rewritten**, which is the difference between *"the column is not null"* and *"a real human really decided"*. A model is refused at any confidence — on acknowledge, on resolve, on severity change and on ownership alike. **No mechanism of forgetting exists:** a `BEFORE DELETE` trigger refuses the delete outright, ageing and escalation ride P5's durable timers and never resolve, and there is no expiry, no TTL, no sweep, no reaper and no scan. **There is no sixth state** — no `CANCELLED`, no `EXPIRED`, no `TIMED_OUT`, no `STALE`, no `CLOSED` — and the finer operational terms (`triage`, `assigned`, `investigating`, `awaiting_external`, `awaiting_human`, `resolution_proposed`) are a `sub_status` **field** with a vocabulary disjoint from the state set. Severity is the closed three-member `CHECK` {`SEV0`,`SEV1`,`SEV2`} with **no `DEFAULT`**, and a severity change is a **field** mutation carrying the value it moved FROM and its reason, so a rebuild folds `ExceptionSeverityChanged` at the highest aggregate version and reproduces the **live** severity rather than the one the row was born with. Ageing and escalation thresholds are **caller-supplied**, with no business default invented (`V10`). The failure classification is **supplied, never inferred** from a message or a status code: a `PERMANENT` auth or config failure raises **immediately with zero retries**, because a permanent credential failure retried forever is a system hiding a fixable problem from the only person who can fix it. `UNIQUE (tenant, source_ref, type) WHERE state != 'RESOLVED'` — at most one open Exception per cause, tenant-first — recorded as a **choice**, since three canonical files call that index OPTIONAL. **M9 is an input to the gate and never a gate:** a freezing Exception is projected into the checkpoint's existing `NativeClaim(conflicting)` **without importing the checkpoint**; `checkpoint.py` stays the sole gate minter and M3 the sole effect authority; M9 engages no brake. Ships dark: zero production importers, only its own probe reaches it, no channel join, **and no oversight queue, dashboard, notifier or MTTR surface** — M9 owes the row and the tenant-first index and builds none of those. ### **A LANDED INCREMENT, NEVER A PHASE ACCEPTANCE.** It cites the on-disk **focused independent review by a session that did not build it** (CLAUDE.md §7, **tier-1** — it lands a migration and it is load-bearing for tenant isolation), which returned **SUPPORTED, confidence 0.88** against this exact tree with **zero findings** and zero adjudications: [review](p6-cp9-independent-review-report-a6e9d3b.md). That reviewer **executed the product**: it reproduced the full probe (95 cases, `behaviours as specified, 0 wrong`), the 58-test M9 suite, the mutation battery (**21/21 caught**), the M1+M3 neighbour regressions (239 passed), the ship-dark and script-reach AST scans, and the `K-1` resolver oracle. Product Driver exercised **11/11 scenarios — the permanent one plus TEN generated — 615 assertions, 0 failed**, the strongest generated contribution of any P6 landing. **Three instruments the reviewer lacked are supplied at this landing rather than carried as debt** — a fresh canonical database introspected with **nine illegal inserts refused and two positive controls accepted**, the channel-join scan its harness hard-blocked, and the seam-isolation oracle its harness refused by token. ### **CI DID NOT CONCLUDE `SUCCESS` ON THIS COMMIT** — run `33460644572` concluded **`cancelled`**: *Safety invariants (fast)* **SUCCESS**, the M3 *effect-grant* job **SUCCESS**, ***Full test suite (py3.11)* SUCCESS — 3099 passed, 1 skipped**, *Risk radar* skipped, and *Full test suite (py3.12)* **cancelled at the runtime ceiling having reached ~55% with no test-failure marker observed before cancellation**. **Measured, not assumed: `pytest eval --collect-only` collects 3100 tests on this tree — matching py3.11's 3099+1 exactly — and `test_phase6_exception.py` occupies positions 2107–2164 (68.0%–69.8%), so py3.11 executed all 58 of M9's tests and they passed, while py3.12 stopped before them and the repository has no py3.12 execution of them.** **`cancelled` is not green, and nothing here claims it is** — see §8 of the review report and residual `P6-D59`. |
| **M10 — the Compensation** (`P6-CP-10`, LANDED) | One `compensations` table, six states, one machine, nine transitions (`CM-1`, `CM-1r`, `CM-2`, `CM-2n`, `CM-3`, `CM-4`, `CM-4f`, `CM-5`, `CM-5x` — an exact set match with §14), the seven already-registered F10 contracts and no eighth, and the partial index `UNIQUE (tenant, original_effect_id) WHERE state != 'NOT_POSSIBLE'` that makes **one active compensation per invalidated effect** something a database ENFORCES. **M10 is the machine whose whole job is to prove that an UNDO gets NO privileged path.** A POD was bound to the wrong load and an invoice for £2,850 went out on the strength of it; a human corrects the binding, and the money has to come back. The tempting implementation is a rollback — find the effect, call the adapter's void endpoint, mark the row undone — and ### **that is a second, UNGATED write route into a customer's accounting system, reached precisely when the system is already known to be wrong about something.** So the credit note is a **NEW external effect**: its own M2 Pipeline Instance, its own policy evaluation, its own brake check, its own M4 human approval, its own P3 checkpoint witness, its own single-use M3 grant, its own commit key, and its own **verified readback** — completion requires reading the world back, never the write merely being accepted. The `compensations` row is only the OBLIGATION to do that, with a named human owner (`owner_id NOT NULL` plus a composite FK into `tenant_humans`, so an ownerless compensation is not insertable) and the amount at stake written on it from the moment it exists. ### **AND YOU CANNOT UNDO WHAT YOU CANNOT PROVE YOU DID:** when the original effect is `UNKNOWN_OUTCOME`, M10 **refuses to compensate at all** (M-33) — *"cancel invoice #560010"* against a system where no such invoice exists can CREATE a credit note out of nothing — and eligibility is read from the **persisted grant ledger, never from a caller flag**. A human resolves the unknown to `VERIFIED` or `FAILED` through M3's `EF-5` first. **`COMPENSATION_FAILED` and `NOT_POSSIBLE` are the most dangerous states the system can be in**, because reality and the projection are KNOWN to diverge: no timer, retry, sweep, reaper or model moves them at any confidence; they stay loud, keep their named human owner and **carry the exposure** until a human establishes reality (`CM-5`), and a `BEFORE DELETE` trigger refuses the delete outright with the entity's own prose. Money-affecting compensation is **always** human-approved — structurally, and without registering anything, because the production `GateRegistry` stays EMPTY and the `adjust_invoice` action class therefore falls to the kernel's `HUMAN_APPROVAL_REQUIRED` default. There is **no seventh state and no expiry column**. Closure imports **M1's landed `resolve_decision_ref`** rather than writing a second K-1 executor, and `CM-5` emits the **already-registered shared F3 `RealityEstablished`** (producers `EF-5` and `CM-5`, discriminated by `subject="compensation"`) — ### **M10 minted no duplicate coordination contract** (rule 17). Ships dark: zero production importers, only its own suite, kit, probe and mutation battery reach it, no channel join, `checkpoint.py` stays the sole gate minter and M3 the sole effect authority; the F10→M9 escalation seam is **named and left UNWIRED** (`M10-AQ-12`), and no M11/M12/M13 work exists. ### **A LANDED INCREMENT, NEVER A PHASE ACCEPTANCE.** It cites the on-disk **focused independent review by a session that did not build it** (CLAUDE.md §7, **tier-1** — it lands a migration, it is load-bearing for tenant isolation, and it is money-affecting), which returned **SUPPORTED, confidence 0.90** with **zero findings** and zero adjudications: [review](p6-cp10-independent-review-report-a43feae.md). That reviewer **executed the product**: the 63-test M10 suite, the full probe (`behaviours as specified, 0 wrong`), the mutation battery (**33/33 caught, 0 escaped**, anti-vacuity control included), the M1–M4 neighbour matrix (432 passed), M9 (58 passed), the false-green suite (8 passed), and the ship-dark, gate-mint and F10-registry scans. Product Driver exercised **13/13 scenarios — the permanent `p6_m10_compensation` plus TWELVE generated — 667 assertions, 0 failed**, the largest generated contribution of any P6 landing. ### **THE REVIEW IS BOUND TO `a43feae`, NOT TO THE LANDING CANDIDATE `a833074`.** A post-push CI correction followed it, and the delta is **measured rather than asserted**: the whole `src/` tree is **byte-identical** at `715ddc0`, at `a43feae` and at `a833074`, and `.github/` is unchanged across the entire M10 range. What the correction touched is canonical bookkeeping, five guard test files, one new shared scanner and the mutation battery — so no reviewed runtime moved, and **no independent reviewer saw `a833074`** (`P6-D68`). ### **CI DID NOT CONCLUDE `SUCCESS` ON THIS COMMIT — AND IT IS THE STRONGEST CI POSITION OF ANY P6 LANDING.** Run `33594219060` concluded **`cancelled`**: ***Full test suite (py3.12)* SUCCESS — 3165 passed, 1 skipped, the entire suite completed**; the M3 *effect-grant* job **SUCCESS**; *Risk radar* skipped; *Full test suite (py3.11)* **cancelled at the workflow/runtime ceiling around 54% with no pytest `F` emitted before cancellation**; and *Safety invariants (fast)* **cancelled at its runtime ceiling, also with no `F`**. **Measured, not assumed: `pytest eval --collect-only` collects 3166 tests on this tree — matching py3.12's 3165+1 exactly — and `test_phase6_compensation.py` occupies positions 2061–2123 (65.1%–67.1%), so py3.12 executed all 63 of M10's tests and they passed, while py3.11 stopped before them and the repository has no py3.11 execution of them.** This is the first P6 landing whose completed CI suite ran the landing machine's own tests. **The six REAL failures CI run `33575760180` found on the pushed pre-correction head are ABSENT from the completed py3.12 run**, and all six were reproduced on `a43feae` and re-verified green on `a833074` at this landing. **`cancelled` is not green, and nothing here claims it is** — see §8 of the review report and residual `P6-D66`. |
| **Still owed** | **M11–M13**, 21 of the 134 transitions, gate **G1**, `AC-SAFE-028`. (The transition figure is derived, not carried, and counts what is written AND LANDED as of the `P6-CP-10` landing: M1's 14 + M2's 25 + M3's 13 + M4's 11 + M5's 8 + M6's 11 + M7's 7 + M8's 8 + M9's 7 + M10's 9 = 113 of 134 written, so 21 remain — and those 21 are exactly M11's 7, M12's 9 and M13's 5. Re-derived mechanically at this landing by parsing §14 of all thirteen machine files and counting rows, which discovered 13 files and 134 rows, not by carrying a prior figure. The `30` this cell read until the `P6-CP-10` landing was the post-M9 figure, the `37` before that the post-M8 figure, the `45` before that the post-M7 figure, the `52` before that the post-M6 figure, the `63` before that the post-M5 figure, the `71` before that the post-M4 figure, and the `95` before that the post-M2 figure.) |
| **Not scored** | `criteria_scored` is `[]` on all ten landed checkpoints. **A checkpoint is a landed increment, never a phase acceptance.** No P6 criterion is scored, and P6 has not reached phase acceptance (registry `status: READY`, `execution_state: IN_PROGRESS`), and **P7 stays `BLOCKED` / `NOT_STARTED`**. |
| **Posture** | M1 through M10 — all ten landed — **ship dark**: zero production importers; M2's/M3's import closure reaches no effect-capable adapter, nothing joins M4 to an outbound channel, and the only things outside the package that reach M5, M6, M7, M8, M9 or M10 are their own probes and suites. **No production effect or integration is enabled by any of them** — M10 included: it mints no gate decision, engages no brake, joins no channel, imports no timer service, and the production `GateRegistry` stays EMPTY — and `checkpoint.py` remains the sole minter of a gate decision. Re-measured at the `P6-CP-10` landing over discovered populations: **121** production modules scanned, `production importers of compensation: []` and **no** production module whose import closure reaches it; **20** channel-capable modules discovered and **none** whose closure reaches `compensation`; `modules that MINT a gate decision: ['checkpoint.py']`; **zero** `GateRegistry` constructions anywhere in the package, so the registered-action-class population is structurally EMPTY — the sole `GateEntry` construction is the kernel's own `GateRegistry._DEFAULT` fallback at `checkpoint.py:242`. |

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

Landing M8 scores no P6 criterion. **The build checkpoint that followed M8 was M9 — the Exception.**
*(Until the `P6-CP-9` landing this paragraph read "recorded as an IMPLEMENTED CANDIDATE, not a
landing", and the paragraph after it said M9 "is NOT landed and is NOT `P6-CP-9`". Both were TRUE
WHEN WRITTEN and are FALSE NOW. They are REPLACED rather than deleted — CLAUDE.md §5 rule 20 — so the
old phrasing stays recognisable if it returns, but a stale "review PENDING" line is an active false
instruction and is corrected here rather than left to send a fresh session to re-review something
reviewed.)*

**`M9` — the Exception — is LANDED as `P6-CP-9`, and the review it was waiting for exists on disk.**
Its code has been present since commit `b94f963` (`src/freight_recon/exception.py`,
`src/freight_recon/migrations/phase6_exceptions.py`, wired into `schema.py` and the P2 migrate path)
and is **byte-identical** at this landing — the three commits between the build and here touch only
`CURRENT.md` and the M9 test file, and `checkpoint.py`, `external_effect.py`,
`identity_binding_claim.py`, `conflict.py`, `observation.py`, `expectation.py` and `work_item.py` are
byte-unchanged across the whole range `b94f963~1..a6e9d3b`. The focused independent review by a
session that did not build M9 was performed against commit `a6e9d3b` / tree `7160f6e3` on a clean
tree and returned **SUPPORTED, confidence 0.88, zero findings, zero adjudications, 11/11 criteria
PASS**: [review](p6-cp9-independent-review-report-a6e9d3b.md).

### **LANDED IS NOT ENABLED, AND IMPLEMENTED + VERIFIED + LANDED IS NOT PRODUCTION.** `criteria_scored` stays `[]`, **P6 stays `status: READY` / `execution_state: IN_PROGRESS` and does not move**, no P6 criterion is scored, **P7 stays `BLOCKED` / `NOT_STARTED`**, and **nothing is enabled in production** — M9 ships dark, mints no gate decision, engages no brake, joins no channel, and has no oversight queue, dashboard, notifier or MTTR surface. `M9-AQ-1…AQ-6` are REPORTED, not resolved; `P6-D4` stays open at M12; `V10` thresholds stay caller-supplied.

**Two carried residuals name `closes_at: M9`, and M9 closes neither — stated rather than let pass.**
`P6-D1` (whether `ExceptionResolved` may stand in for K-1's missing `HumanResolved`; its disposition
says *"M9 owns that determination"*) is **not determined here** — that is `M9-AQ-1`, REPORTED, and M9
builds the human branch, imports M1's resolver unchanged and leaves the `RULE` branch **refusing**,
the safe direction the disposition already named. `P6-D3` (the Sev-0 raise for an owner retired around
`offboard_human`) is **not closed either** — M9 supplies a machine that can carry a `SEV0` Exception,
but **nothing wires M1's ownerless detector to it**; that wiring is `M9-AQ-4`, also REPORTED, and
wiring a seam is precisely what shipping dark forbids. Both rows stay open with their `closes_at`
markers unchanged.

**The M9 landing also carries the anti-vacuity correction at `a6e9d3b`.** CI run `33452247720` printed
a **real `F`** at ~20% on both interpreters —
`test_false_green_defenses.py::test_every_corpus_scanning_negative_assertion_proves_its_population`.
It was M9-caused and the guard was right: the build commit added four corpus-scanning negative
assertions and **none proved its population**, so each could pass while policing nothing. That was
proven real by mutation — relocating the machine's 71,841 bytes behind a 398-byte re-export shim left
all four **green** while they scanned no code, and turned all four **red** once the anchor was added.
`a6e9d3b` adds one positive assertion to each. No test was weakened and no existing negative
assertion was touched.

**The next build checkpoint was M10 — the Compensation.** *(That sentence read "The next build
checkpoint is M10" until this landing. It was TRUE WHEN WRITTEN and is FALSE NOW; it is REPLACED
rather than deleted — CLAUDE.md §5 rule 20 — because a stale next-checkpoint line is an active false
instruction that sends a fresh session to rebuild something landed.)*

**`M10` — the Compensation — is LANDED as `P6-CP-10`, and the review it was waiting for exists on
disk.** Its code has been present since commit `715ddc0` (`src/freight_recon/compensation.py`,
`src/freight_recon/migrations/phase6_compensations.py`, wired into `schema.py` and the P2 migrate
path) and the **entire `src/` tree is byte-identical** at `715ddc0`, at `a43feae` and at the landing
candidate `a833074` — one tree hash, `bef554e3…`, at all three. `checkpoint.py`, `work_item.py`,
`pipeline_instance.py`, `external_effect.py`, `approval.py`, `observation.py`,
`identity_binding_claim.py`, `conflict.py`, `expectation.py`, `exception.py` and `brake.py` are
byte-unchanged across the whole range `715ddc0~1..a833074`, and so is `.github/`. The focused
independent review by a session that did not build M10 was performed against commit `a43feae` / tree
`3b85cea8` on a clean tree and returned **SUPPORTED, confidence 0.90, zero findings, zero
adjudications, 11/11 criteria PASS**: [review](p6-cp10-independent-review-report-a43feae.md).

### **THE REVIEW IS BOUND TO `a43feae`, AND NO INDEPENDENT REVIEWER SAW `a833074`.** Two claims are
kept apart and neither is inflated into the other: *an independent review of the M10 implementation
tree*, which happened; and *a post-review candidate correction verified by targeted tests and by a
completed CI suite*, which is what `a833074` has. The correction changed **no `src/` file, no
migration runtime, no checkpoint semantics and no M1–M9 machine semantics** — measured, not asserted
(§9 of the review report). What it changed is canonical bookkeeping (`compensations` classified
tenant-first in the Phase-0 manifest, registered in the canonical partition and in the migration
walk), one new shared ADR-010 boundary scanner (`eval/phase0/gate_scan.py`), five guard test files
and the mutation battery. Recorded as `P6-D68`.

### **CI FOUND SIX REAL FAILURES ON THE PUSHED CANDIDATE, AND ALL SIX WERE CANONICAL BOOKKEEPING OR A
STALE GUARD SUBJECT — NOT AN M10 RUNTIME DEFECT.** Run `33575760180` on `a43feae` reported **6
failed, 3156 passed, 1 skipped** on py3.12. At this landing all six were reproduced on a throwaway
worktree of `a43feae` — **exactly six, and only six** — and all six pass on `a833074`. Three were
bookkeeping: `compensations` is a real canonical table that the partition guard, the REG-1 manifest
and the migration walk could not see. Three were **stale guard subjects**: P0 guards that defended
the ADR-010 boundary by reading **raw file text**, which cannot tell `if gate is FORBIDDEN:` apart
from a docstring saying *"this machine mints NO gate decision"* — and M10's docstring says exactly
that. AST proof: `compensation.py` and `phase6_compensations.py` hold six gate-token occurrences and
**zero are executable**. ### **The guards were catching M10 for DESCRIBING the authority it defers
to.** What narrowed is what the guards **read**; who is permitted is untouched, the kernel allowlist
is unchanged, `compensation.py` is not in it, and production `GateRegistry` registration remains
**EMPTY**. Three new mutants make `compensation.py` commit the real forbidden acts — deciding
`AUTONOMOUS_WITHIN_CAPS` in code, carrying an uncited `DEFAULT_GATE` literal, and registering a
production gate for `adjust_invoice` — and each turns its guard **RED**. The battery is **36/36
caught, 0 escaped**, re-run on the committed tree at this landing.

### **LANDED IS NOT ENABLED, AND IMPLEMENTED + VERIFIED + LANDED IS NOT PRODUCTION.** `criteria_scored`
stays `[]` on all ten checkpoints, **P6 stays `status: READY` / `execution_state: IN_PROGRESS` and does
not move**, no P6 criterion is scored, **P7 stays `BLOCKED` / `NOT_STARTED`**, and **nothing is enabled
in production** — M10 ships dark, mints no gate decision, engages no brake, joins no channel, imports no
timer service, and has no oversight queue, dashboard, notifier or MTTR surface. `M10-AQ-1…AQ-13` are
REPORTED, not resolved; `V1` stays open validation; M12 and M13 are unbuilt. **(This sentence read
"M11, M12 and M13 are unbuilt" at the `P6-CP-10` landing and was true then; it is FALSE now — M11's
implementation has since been committed. M11 is still NOT a landed checkpoint; see the M11 status note
below.)**

**One carried residual names `closes_at: M10`, and M10 does not close it — stated rather than let
pass.** `P6-D2` — `CorrectionInvalidatedAnEffect` is listed in M1 §33 "Events consumed" but has no §14
row, and §27 routes it out of band to M10 — is **not determined here**. That is `M10-AQ-1`: M10 owns a
callable `raise_from_correction(…)` seam over the already-registered correction facts and **mints no
unregistered event name**, which is the safe direction the disposition already named, but it is not the
determination the row is waiting for. The row stays open with its `closes_at` marker unchanged.

**`P6-D40` is carried forward unchanged and was NOT re-verified at this landing.** No mutation battery
was run against the status guards here and none is claimed.

Landing M10 scores no P6 criterion. **The next build checkpoint was M11 — the Policy** (its
implementation has since been committed; see the M11 status note directly below).

## M11 — the Policy: implementation COMMITTED, NOT a landed checkpoint (status corrected 2026-09-04)

> This note exists because the `P6-CP-10` landing narrative above called M11 "unbuilt," which is no
> longer true, while no landing has occurred either. It states **only** what the evidence supports.

**Implementation is present and committed at `20cec74`.** The six deliverables exist on disk:
`src/freight_recon/policy.py` (the machine — seven states `DRAFT/PROPOSED/APPROVED/ACTIVE/SUPERSEDED/
REVOKED/EXPIRED`, transitions `PO-1`…`PO-7`, the eight already-registered F11 contracts and no ninth);
`src/freight_recon/migrations/phase6_policies.py` (the tenant-first `policies` table, wired into
`src/freight_recon/schema.py` and the P2 migration walk `src/freight_recon/migrations/phase2_tenant_first.py`);
`eval/tests/test_phase6_policy.py`; `scripts/probe_phase6_policy.py`; `scripts/mutate_phase6_policy.py`;
and the carrier-boundary edit in `eval/phase0/gate_scan.py`. The `policies` row is recorded in the
tenant-first table partition above (`P6 tenant — M11 (1) — policies`).

**What a builder observes when running the committed tree** — builder-observed at `20cec74` on
2026-09-04; **this status note does not prove these results and does not try to** (a status document
cannot prove itself); the independent reviewer reproduces them, and until then they are builder
evidence, not verified landing evidence:
`.venv/bin/python -m pytest -q eval/tests/test_phase6_policy.py eval/tests/test_phase0_null_gate.py
eval/tests/test_phase0_errata_guards.py` → **80 passed**; `scripts/probe_phase6_policy.py --all` →
`behaviours as specified, 0 wrong` with zero alarm markers; `scripts/mutate_phase6_policy.py` →
**34/34 caught, 0 escaped**, anti-vacuity control green, tree restored byte-identical; the M1–M10 and
P3-kernel neighbour suites → 707 passed; the event-contract, replay, false-green, tenant-posture and
hermeticity suites → 448 passed. `checkpoint.py` remains the sole gate minter (`policy.py` constructs
no `GateEntry`/`GateRegistry`); the production `GateRegistry` population stays **EMPTY**; no production
module imports the machine (`policy.py`).

### **THIS IS NOT A LANDING, AND NOTHING HERE CLAIMS IT IS.**
- There is **no `P6-CP-11` recorded** in this status authority. M11's tier-1 **independent review** (a
  session that did not build it) is **OWED** and has not run; a build session may not review its own
  work. Until that review, M11 is *implementation committed*, not *landed*.
- `criteria_scored` stays `[]`; **no P6 criterion is scored**; **P6 stays `status: READY` /
  `execution_state: IN_PROGRESS`**; **P7 stays `BLOCKED` / `NOT_STARTED`**; nothing is enabled in
  production.
- CI green on `20cec74` is **not** independently confirmed here; only the scenario's named suites were
  re-run locally. CI on a fresh checkout remains the source of truth.
- The "P6-CP-11" label carried in the M11 code docstrings/comments names the *implementation increment*;
  it does not assert a landing, and no landing is recorded here.

## Risks and standing constraints

| | |
|---|---|
| **R-07 — ungated live-write paths** | **CONTAINED.** The record is in [`phase-0-baseline-manifest.yaml`](phase-0-baseline-manifest.yaml) (`expected_legacy_paths.status: CONTAINED`). External-effect paths are structurally forced through the governed boundary or fail closed. ### **CONTAINED IS NOT ENABLED:** no production write is enabled, the deployed governed route answers a recorded `ROUTE_NOT_CONFIGURED` refusal, the production `GateRegistry` population stays EMPTY until U8.1/P8, and no autonomy was granted. |
| **Live-write paths** | P0's six production-reachable paths are all cut: EP-6/7/9/10 physically DELETED; EP-3/EP-8/EP-14 cut to structurally read-only surfaces; EP-1's write half routed through the governed write route and the checkpoint kernel. |
| **Adapter imports** | P0's 31 direct adapter-import edges are gone: the boundary-aware gate's effect-capable violation surface is **EMPTY**, positively anchored by inspected sources and authorized detection edges. Enforced by `eval/tests/test_import_gate.py` on every CI run. |
| **Knowledge base** | Hardcoded `tenant="default"` remains at `ops_control.py` (×5) and `action_callback.py::_learn_correction`. Tracked by symbol, never by line number; verified by guard. |
| **Nonblocking debt** | P5: `IR-R5`–`IR-R12`, `ADJ-P5-01`–`ADJ-P5-03`. P6/M1: R-01/R-02/R-03, A-01/A-02/A-03, `P6-D6`, `P6-D8`. P6/M2: `P6-D17`–`P6-D23`, `P6-D9`, `P6-D12`, `P6-D13`. P6/M3: `P6-D29`, `P6-D30`. P6/M4: `P6-D31`–`P6-D34`. P6/M5: `P6-D35`–`P6-D40`. P6/M6: `P6-D41`–`P6-D46`. P6/M7: `P6-D47`–`P6-D52`. P6/M8: `P6-D53`–`P6-D58`. P6/M9: `P6-D59`–`P6-D64`. P6/M10: `P6-D65`–`P6-D70`. Plus `P6-D24`–`P6-D27` and the G2 residuals. **These are debt rows, and a debt row is a complete deliverable.** Do not open a remediation campaign against them. |

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
| **P6 tenant — M10** (1) | `compensations` |
| **P6 tenant — M11** (1) | `policies` |

P5, P6/M1, P6/M2 and P6/M4 declare **no** tenant-exempt table, and the guard asserts that emptiness
rather than omitting it: an event nobody owns is an event that will eventually be read by the wrong
brokerage, an approval scoped to no brokerage is a consent nobody gave.

## ⛔ What must NOT begin

| Not yet | Why |
|---|---|
| **Enabling any external effect on live traffic** | The capability ships dark. Enabling it is a separate, founder-authorized decision, and live supervised writes are P12 behind the undischarged **RR-01**. |
| **Weakening the checkpoint kernel** | `CheckpointPassed` stays unconstructable, the witness table append-only, and the claim CAS's WHERE-clause revalidation may never lose a predicate. |
| **Rebuilding or polishing M1, M2, M3, M4, M5, M6, M7, M8, M9 or M10** | All ten are landed and no further code is owed. Their residuals are debt rows. **The P3/P4 per-thread-connection concurrency correction at `d70a4e7` is landed too and must not be reworked.** |
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

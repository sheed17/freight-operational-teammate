# P6-CP-1 — SEPARATE TARGETED ADJUDICATION

**Adjudicated candidate: content commit `ca8c070646f2a5f84fc6cafd926d78d1530ebeff`**
**(tree `29ad9c25e75619effd4fa2675af320031aea9e6b`; metadata commit `64f6f6c62a785c6f4377b8c96a6000acc1e18f35`)**

**VERDICT: ADJUDICATE PASS — P6-CP-1 READY FOR FINALIZER**

Adjudicator: a separate session. It did not implement M1, did not remediate M1 at any candidate,
did not review any P6-CP-1 candidate, did not author `ca8c070` or `64f6f6c`, and did not author the
independent review it adjudicates. Adjudication date: 2026-08-15.

> This is an adjudication **source artifact**. It scores **no** P6 acceptance criterion, marks no
> phase or unit complete, closes no risk, lands no checkpoint, and performs no finalization. It does
> not begin M2. It authorises exactly one act: a fresh finalization pass for P6-CP-1.

---

## 1. Mechanical binding

Every identity below was re-derived in this repository rather than inherited from the mandate. An
earlier adjudication attempt failed only because it was launched from a different repository
(`/Users/sammyfammy/neyma-product-driver`); nothing from that attempt is relied on here.

| Bound object | Value | How established |
|---|---|---|
| repository | `/Users/sammyfammy/freight-logistics-operational-teammate` | `git rev-parse --show-toplevel` |
| remote | `github.com/sheed17/freight-operational-teammate.git` | `git remote -v` |
| branch | `p5/u5-1-g2-spec-correction` | `git rev-parse --abbrev-ref HEAD` |
| candidate content commit | `ca8c070646f2a5f84fc6cafd926d78d1530ebeff` | `git cat-file -t` → commit |
| candidate tree | `29ad9c25e75619effd4fa2675af320031aea9e6b` | `git rev-parse ca8c070^{tree}` |
| metadata commit | `64f6f6c62a785c6f4377b8c96a6000acc1e18f35` | single parent `ca8c070`; HEAD |
| metadata scope | exactly the five `STATUS_METADATA_FILES` | `git diff ca8c070 HEAD -- src eval scripts` is EMPTY |
| independent review commit | `7dff7f1c64c34aa6752e692fb630dfa3c3914406` | single parent `ca8c070`; adds one file, 337 lines |
| review preserve ref | `refs/preserve/p6-cp1-independent-rereview-ca8c070` | `git for-each-ref refs/preserve` |
| review report blob | `52c2efea58e89aed3704748e110a4c0d09353260` | `git rev-parse 7dff7f1:docs/implementation/p6-cp1-independent-rereview-report-ca8c070.md` |
| working tree | CLEAN at entry and at exit | `git status --porcelain` |

**Naming correction, recorded not actioned.** The mandate named the review ref
`refs/preserve/p6-cp1-independent-**review**-ca8c070`. The ref that exists is
`refs/preserve/p6-cp1-independent-**rereview**-ca8c070`. It resolves to the expected `7dff7f1`, so
the object identity is correct and only the mandate's spelling was wrong.

**The review's verdict, read in full:** ACCEPT FOR P6-CP-1 ADJUDICATION. It reviews `ca8c070` /
`29ad9c25e` by name, states its own independence, and explicitly declines to adjudicate.

## 2. Governing authority, read rather than assumed

- `IMPLEMENTATION-REGISTRY.yaml` → `meta.status_convention`: *"content commit first, then exactly
  one status-metadata commit that records it."*
- `eval/tests/test_status_reality.py::repo_state` — the legal states `FINALIZED` / `PRODUCING` /
  `BASELINE`, and the stray-path rule for a metadata commit.
- `test_status_reality.py` P6 landing rule — an `IN_PROGRESS` P6 must carry a `landed_checkpoints`
  entry with **on-disk** `implementer_evidence` **and** `independent_review_report`, and
  `criteria_scored` must be unset for a continuation checkpoint.
- `scripts/finalize_status.py` — writes the derived status block, `meta.baseline_commit`,
  `meta.validated_tree`, `meta.suite`, and nothing else.

What this adjudicator may do: accept or reject. What it may not do: score any P6 acceptance
criterion, land the checkpoint, or derive status. Those remain the landing commit's and the
finalizer's.

## 3. F-04 — a parked event is executed only under its own semantics. **CLOSED.**

Structural, not conditional:

- `consume` returns before any cascade when `drain_handler_for is None` (`event_inbox.py:389`), so
  the default is OFF.
- `_drain_for` calls `drain_handler_for(park.envelope)` **per event** (`event_inbox.py:707`) — the
  handler is derived from the envelope about to be consumed, never from the seeder.
- The parameter is **keyword-only** (declared after `*`), so `(self, envelope, handler)` is
  unchanged and no existing call site can bind it positionally.
- M1 supplies no factory and therefore cascades nothing.

**Adjudicator-written probe, wider than the candidate's own regression.** ONE store, ONE missing
Work Item, **four** parked triggers across **three** distinct aggregate types (`work_item`,
`pipeline_instance`, `conflict`) — `HumanDecided`, `PipelineStarted`, `PipelineClosed`,
`ConflictRaised`. Consumption is driven by each event's own trigger with the **seeding shape first**
(`HumanDecided` rides on the very referent the cohort waits on). At every step, over a proven
remaining population:

- `drained == ()` — nothing cascaded;
- the consumed event's own park closes, and **no other park closes**;
- **no other event acquires an inbox receipt** — the loss-with-a-receipt signature;
- the number of `IllegalTransitionAttempted` records equals the number of genuinely ILLEGAL
  refusals observed, and each names a trigger actually sent — no fabricated refusal;
- redelivery of all four afterwards is `DUPLICATE_NOOP` with a byte-identical state digest.

**The probe was proven able to fail.** Under mutant **W31** (the cascade restored to the seeding
invocation's handler) it goes RED. A first version of this probe was *not* W31-capable — it seeded
from an event riding on a different aggregate than the cohort's referent, so nothing could cascade;
that gap was found and corrected before the probe was believed. A separate positive control opts in
with a deliberately wrong factory and proves misrouting is observable, so the correctness assertion
is falsifiable rather than vacuous.

**W31a** (factory consulted with the seeding event) is a MISS for this adjudicator's probes by
construction — their factory ignores its argument — and is caught by its designated repository test
`test_the_drain_derives_each_parked_events_handler_from_that_event`, which was run under the mutant
and observed to fail on the wrong envelope.

## 4. F-05 — durable park state tells the truth. **CLOSED.**

The fix is an **ordering** change, not a repair-by-later-UPDATE: the `DRAINED` stamp moved out of the
self-release branch and onto the two paths that have finished with the event — the apply, and the
`STALE_NOOP` that means the same thing. Every path that re-parks leaves the row truthfully `PARKED`,
which matters because `_park_locked`'s `ON CONFLICT DO UPDATE` refreshes only `attempts` and
`last_attempt_at` and cannot restore `park_state`.

**Adjudicator-written probe.** An event with **three** prerequisites resolving one per round, the
self-prerequisite first — the exact ordering that produced the defect. At every intermediate round:
API `PARKED_MISSING_AGGREGATE`, durable row `PARKED`, `resolved_at` NULL, `parked()` still returns
it, the handler never ran, the accountable owner intact. After TTL, `expire_overdue()` surfaces it
**with its accountable human**. Under mutant **W32** the probe fails with the original signature
exactly: *"API said PARKED, durable row says 'DRAINED'"*.

A second probe covers the already-`EXPIRED` park whose prerequisite later arrives: consumed exactly
once, carries an `APPLIED` receipt, redelivery is `DUPLICATE_NOOP`, and the row stays `EXPIRED`
rather than being silently rewritten — an escalation already handed to a human is not retracted.

## 5. Preservation of F-01, F-02, F-03

Battery evidence: **W27/W27a** (F-01), **W28/W28a/W28b** (F-02), **W29/W29a/W29b/W29c/W30** (F-03)
all caught.

**F-02 re-attacked independently by this adjudicator.** Eighteen hostile owner candidates — NULL,
empty, blank, `system`, `SYSTEM`, `Neyma`, `neyma`, `ops-team`, `unassigned`, `model`, `detector`,
`null`, `nobody`, `admin`, `automation`, `agent`, `claude`, an unrecorded human — **18/18 refused**,
with a positive control proving a recorded ACTIVE human is accepted. Further: offboarding a human who
still owes open work is REFUSED (`OwnershipRefused`, naming the open item); an offboarded human is
refused as a new owner; a foreign-tenant human is refused; and a **direct SQL `UPDATE … owner_id =
NULL` is refused by a database trigger**. That last point is *stronger* than residual `P6-D3` claims,
and is recorded here so the record is not weaker than the mechanism.

**F-03 rests on a population-derived oracle, not on examples.** All **13** triggers are classified
from §14's `creates` flag and the registry `aggregate_type` into four classes — creation/self,
prerequisite/self, prerequisite/cross, no-canonical-contract — each asserted **non-empty**, with
per-class convergence asserted over three deliveries and explicit counters. Exactly one creation
trigger is derived (`WorkItemCreated`), not enumerated. The eight non-contract shapes are the
deterministic-malformed population.

## 6. Caller/API compatibility — enumerated, not inferred

AST enumeration over **337** discovered Python sources:

- **7** `DedupInbox` construction sites: exactly **one production** (`work_item.py:1238`, M1), one
  evidence tooling (`scripts/postgres_p5_gate.py`, no resolver, so nothing can park), five tests.
- **114** real `.consume(` call nodes. **Exactly 5 opt in**, all in
  `eval/tests/test_phase5_event_transport.py`. **ZERO production callers opt in.**
- The smuggling route the review did not test: `WorkItemMachine.consume(**facts)` routes unknown
  keywords into `_Facts.extra` via `_split_facts` and **never forwards them to `box.consume`**. No
  M1 caller can enable the cascade even deliberately.
- `requires_existing` is unbroadened; the implicit self-aggregate skip is intact; no creation flow
  became self-dependent.

The one honest behaviour change: five P5 transport cases previously received the cascade by default
and now request it via `phase5_kit.agnostic_drain`. Capability preserved, default changed — the
prescribed remediation.

## 7. False-green and mutation assessment

- **Battery: 41/41 caught, exit 0**, re-executed by this adjudicator.
- **W31 and W32 applied independently** with an in-memory save/restore harness — never
  `git checkout` / `restore` / `stash` / `clean` — `__pycache__` purged on both sides, and
  `src/freight_recon/event_inbox.py` verified **byte-identical by sha256**
  (`b1de10e724d229891b5c66958428e1040502448e878d3830fd9c028db9dfbb67`) after every run. Each mutant
  reproduced the *real* defect signature, not merely a red test.
- **Anti-weakening check:** the candidate removes **exactly 4 lines** across all test files, and all
  four are `consume(...)` calls re-issued with an explicit opt-in. **Zero assertions removed,
  weakened or rewritten**; `phase5_kit.py`, `test_phase6_work_item.py` and the mutation script have
  zero deletions.
- **Manifest identity:** set difference computed directly — **+4 additions, 0 removals, 0
  duplicates**, 2866 → 2870, all four present by exact identity. The guard compares sets
  (`missing`/`extra`), so a same-count substitution fails.
- **P5's own certification survives the amendment to its inbox:** replay battery **24/24**,
  contracts battery **37/37**.
- `AC-EVT-006`'s arrival-order drain evidence is intact and still passes, with the opt-in added and
  every assertion preserved.

## 8. Canonical suite, gates, and one honest limitation

`SUITE-RESULT.json` and `GATE-RESULT.json` both bind to commit `ca8c070` / tree `29ad9c25e`, and
this adjudicator **recomputed** `config_sha256`, `runner_sha256`, `manifest_sha256` and **both
payload hashes** against the live tree: all MATCH. The records were therefore neither hand-edited nor
carried forward from another tree.

**Suite re-execution in this session: 2849 passed / 20 failed / 1 skipped / 2870 collected.** All
twenty failures are `test_action_callback.py` (19) and
`test_p4_deployed_governed_route.py::test_run_callback_server_accepts_and_holds_the_deployed_seams`
(1), every one a `PermissionError: [Errno 1] Operation not permitted` raised from `socket.bind()` —
this session's sandbox forbids listening sockets. None imports the candidate's runtime, and the
candidate touches no HTTP code. **2849 + 20 = 2869**, with identical collected (2870), identical skip
count and identical skipped-node identity — an exact reconciliation with the recorded
2869 / 0 / 1.

**Clean-clone gate: partially reproduced.** Steps 1–4 passed (no active_workspace in clone, python
floor host, fresh venv, python floor venv). Step 5 failed on `SSLCertVerificationError` reaching
`pypi.org` — the gate builds a venv from declared dependencies and this session's sandbox blocks
that TLS path. Environmental, not a property of the candidate. The recorded gate binds to the
candidate commit and tree with `passed: true` across nine steps and a payload hash that recomputes.

**This limitation is stated rather than papered over:** full-green suite and clean-clone PASS were
*not* independently re-observed end to end here. They were reproduced by the independent reviewer,
the recorded artifacts recompute against the candidate tree, and the entire 20-node delta is
attributed to a host capability this session lacks and lies outside the candidate's blast radius.

## 9. Product invariant

> Every open operational obligation has a structurally accountable human owner, and out-of-order or
> blocked operational facts cannot disappear, execute under the wrong semantics, falsely report
> completion, lose ownership, or become permanently undiscoverable.

Adjudicated as supported. Ownership is structural (FK into `tenant_humans`, 18/18 hostile refused,
enforced even against direct SQL). A blocked fact cannot disappear (`parked()` retains it), cannot
execute under the wrong semantics (§3, mutation-proven), cannot falsely report completion (§4,
mutation-proven), cannot lose ownership (park rows carry the owner; `expire_overdue` returns it), and
cannot become permanently undiscoverable (TTL escalates onto a named human). P6 ships **dark**: over
172 inspected production and script sources, **zero** import `work_item.py`; only the migration
module is wired into `schema.py`.

## 10. Sequencing determination — the metadata commit is NOT a violation

`64f6f6c` precedes the independent review `7dff7f1` in commit time. Resolved mechanically against
the repository's own rules rather than treated as an automatic blocker:

- The two-commit convention is **general** — every content commit may be recorded by exactly one
  status-metadata commit.
- The review → adjudication → finalizer ordering in `CURRENT.md` is stated for a **closure content
  commit**, one that changes what the status authority claims. `ca8c070` is a **candidate**: it
  scores nothing, `execution_state` stays `NOT_STARTED`, `checkpoint_state` stays `NO_CHECKPOINT`,
  `independent_review_report` stays `null`.
- `64f6f6c` claims no acceptance. It records executed suite and gate results against the candidate
  tree and touches only the five `STATUS_METADATA_FILES`.
- It is the consistent pattern across all four P6-CP-1 candidates: `2ed750e→c86fae8`,
  `761fcd7→3b31031`, `f5af910→6861bb9`, `ca8c070→64f6f6c`.
- Repository state is a legal `FINALIZED` under `repo_state()`.

## 11. Findings

### Material blockers

**NONE.** No wrong-handler consumption, no event loss, no false `DRAINED` state, no undiscoverable or
unexpirable park, no duplicate consumption, no fabricated refusal record, no ownership loss, no
M-26 violation, no caller semantic drift, no weakened or removed assertion, no F-01/F-02/F-03
regression, no P5 decertification, and no false acceptance.

### Nonblocking debt (recorded, not actioned — CLAUDE.md §13.3)

Upheld from the independent review:

- **R-01** — `IMPLEMENTATION-REGISTRY.yaml` → `units[P6].candidate_awaiting_review` and `CURRENT.md`
  still say "186 acceptance and hostile nodes" and "32/32 mutants", describing an earlier candidate.
  This adjudicator confirmed by grep that **nothing executable asserts either figure**, and the error
  understates.
- **R-02** — `superseded_candidate` records only the first rejection (`2ed750e`), not `761fcd7` or
  `f5af910`. Prose-only; the commit chain is complete.
- **R-03** — the review that rejected `f5af910` is not preserved, and neither is `2ed750e`'s. Worth
  closing before P6 is adjudicated complete so the candidate's full review lineage is
  reconstructable.

Opened by this adjudication:

- **A-01** — the review's "115 `.consume(` call sites" is a textual count; one of the 115 is a
  docstring mention at `work_item.py:476`. The real figure is **114**. The error is in the
  conservative direction and does not affect the opt-in finding.
- **A-02** — making the cascade opt-in narrows the automatic-drain affordance for any *future*
  consumer that does not supply a factory. `AC-EVT-006`'s arrival-order evidence is fully intact, and
  this is already covered by existing residual **P6-D6**, which assigns the facts-carrying drain to
  the Pipeline Instance unit. Recorded so a later machine does not rediscover it as a surprise.
- **A-03** — the mandate's spelling of the review preserve ref was wrong (§1). Cosmetic.

None can produce a wrong customer outcome, violate an invariant, or make a later phase unsafe.

## 12. Verdict and the exact next act

**ADJUDICATE PASS — P6-CP-1 READY FOR FINALIZER.**

The next act is **EXACTLY ONE FRESH FINALIZER FOR P6-CP-1**, performed by a session that is not this
one. One mechanical caveat, which is not a defect in the candidate:

### A finalizer run alone cannot land the checkpoint.

`scripts/finalize_status.py` rewrites only the derived status block and
`meta.baseline_commit` / `validated_tree` / `suite`. Landing P6-CP-1 additionally requires
`execution_state → IN_PROGRESS` and a `landed_checkpoints` entry citing an **on-disk**
`independent_review_report` — and `test_status_reality.py` refuses a landed checkpoint without one.
The preserved review report is **not** in the branch tree. So the finalization act is:

1. **One content commit** bringing `p6-cp1-independent-rereview-report-ca8c070.md` and this
   adjudication report on-disk under `docs/implementation/`, and writing the `landed_checkpoints`
   record with `criteria_scored` unset;
2. **then exactly one finalizer** under an exclusively-held `finalizer_lock`, producing exactly one
   status-metadata commit touching only the `STATUS_METADATA_FILES`.

That is the sequence P5's U5.7+U5.8 used at `de526c1` and the P4 closure used at
`42ea24c → c30a43b → d3cf1de → 06ebfdb`. M2 may not begin before it.

---

*Adjudicator note on method: every load-bearing claim in §3–§7 was re-derived in this repository with
probes this session wrote itself, and each was shown to fail under a mutant restoring the
corresponding real defect — with one probe found NOT capable of failing and corrected before it was
believed. A passing check that was never capable of failing is not evidence. No production code,
test, specification, candidate content or review evidence was modified; every mutation was in memory
with byte identity verified afterwards; the branch and working tree are untouched and nothing was
pushed.*

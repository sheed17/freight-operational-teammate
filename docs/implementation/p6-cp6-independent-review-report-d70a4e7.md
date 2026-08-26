> # ⛔ HISTORICAL REVIEW — NOT CURRENT AUTHORITY
> **This is evidence of a past moment, not status.** It is an INDEPENDENT REVIEW: it set no
> acceptance criterion, marked no phase complete, closed no risk, enabled nothing and authorized no
> external effect. It reviewed the `P6-CP-6` candidate (machine **M6 — the Identity Binding Claim**)
> at commit `d70a4e78c6426e4cf1f880804d4c36b5893347bf` (tree
> `d74cf84bb4bcc25dd8fc8e18d81cc1d13cf16a86`, branch `p5/u5-1-g2-spec-correction`, working tree
> clean) and returned **SUPPORTED, confidence 0.90**.
>
> ### **IT DID NOT REVIEW THE COMMIT THAT CARRIES IT.** The landing commit that brought this file
> in-tree did not exist when the review was performed. Nothing here may be cited as an independent
> review of that commit.
>
> ### **AN EARLIER M6 REVIEW EXISTS AND IS STALE. DO NOT CITE IT AS FINAL EVIDENCE.** A first
> Product Driver M6 run reviewed commit `460d5c78b4c3cc01fa83f4780cbcb220cd396f07` / tree
> `3f143d6c605a…`. After that commit was pushed, CI exposed a **real P3/P4 exactly-once concurrency
> defect**, and the correction changed the tree. **A review is bound to a tree; when the tree moved,
> that review stopped being a review of anything in the repository.** It is described in §2 for
> lineage and is superseded, in full, by the fresh run recorded here. See §2 and §9.
>
> ### **P6-CP-6 IS A CHECKPOINT, NOT A PHASE ACCEPTANCE.** P6 is **NOT COMPLETE**, no P6 acceptance
> criterion is scored, and P7 is not unlocked. M6 continues to **ship dark**.
>
> ### **NO ADJUDICATION FOLLOWED THIS REVIEW, AND NONE IS OWED.** M6 is tier-1 under
> [`CLAUDE.md`](../../CLAUDE.md) §7 — it lands a migration, it is load-bearing for tenant isolation,
> and it decides which real-world entity an artifact belongs to, which is an input to money — which
> requires builder + **one focused independent review by someone who did not write it**, mutation
> proof that the guard can fail, and CI. The adjudication chains and finalizer rituals cited by the
> `P6-CP-1` and `P6-CP-2` records were retired in the 2026-08 engineering-process simplification and
> must not be revived on the strength of those older artifacts.
>
> ### **CI DID NOT CONCLUDE `SUCCESS` ON THIS COMMIT, AND THIS RECORD DOES NOT PRETEND OTHERWISE.**
> See §9. Read that section before citing this document as evidence of a green repository.

# P6-CP-6 — FOCUSED INDEPENDENT REVIEW — candidate `d70a4e7`

**Verdict: `SUPPORTED` · confidence `0.90` · findings `0` · adjudications `0` · criteria `9/9 PASS`**

| | |
|---|---|
| **Reviewed tree** | commit `d70a4e78c6426e4cf1f880804d4c36b5893347bf`, tree `d74cf84bb4bcc25dd8fc8e18d81cc1d13cf16a86`, branch `p5/u5-1-g2-spec-correction`. The review record's `reviewed_fingerprint` reads **`tracked_dirty: 0`, `untracked: 0`**, identity `d70a4e78c642/d74cf84bb4bc/-` |
| **Reviewer lineage** | A session that did not build M6. The review record states `inherited_builder_context: false` and the run's review ledger states `independent: true`, `invalidations: []`, `superseded_by: ""`; reviewer session `cff18da2-83e2-42e6-89d7-5eedc0d30288`, builder session `d36efac2-efde-4d3a-9b1a-d9a6baa8e23f` |
| **Performed** | `2026-08-26T07:44:00+00:00` |
| **Source artifact** | Product Driver run `20260826-071443`, `accepted/independent-review.json` (separate repository, `neyma-product-driver`) — byte-identical to `iteration-01/independent-review.json` in the same run, the run's only iteration. Its prose is quoted verbatim below; nothing is upgraded, softened or summarised into a stronger claim |
| **Adjudications recorded** | **none** (`adjudications: []`) |
| **Findings** | **none** (`findings: []`). §8 records the nonblocking items this landing identified from the run's own evidence — they are **not** reviewer findings and are not presented as such |
| **Scope declared by the run** | `P6/M6`, `level: TASK`, parent phase `P6` (`READY` / `IN_PROGRESS`), `claims_phase_completion: false`, `phase_completion_requested: false` |
| **Review requirement** | `required: true`, `fresh_session_required: true`, triggers `REPOSITORY_AUTHORITY` and `COMPLETION_AUDIT`. **SATISFIED** by this review |
| **Reviewer executed the product** | **Yes.** `evidence_reproduced: true` and `claimed_evidence_reproduced: true` — see §5 |
| **Reviewer blocked on anything** | **No.** `blocked_on.kind: NONE` — *"All verification I needed was reproducible within the read-only plus declared-scenario boundary."* |

---

## 1. The verdict, verbatim

> "P6/M6 (Identity Binding Claim) is supported by evidence I reproduced against the exact state
> under review (HEAD d70a4e78, tree d74cf84b, working tree clean). I re-ran the product's own
> verification: the M6 probe reported 'behaviours as specified, 0 wrong' across 62 cases; the
> mutation battery caught 13/13 (SD-6 provenance-derivation CHECK, provenance/match_method
> immutability triggers, MODEL_EXTRACTED evidence-span CHECK, one-CONFIRMED-per-subject partial
> unique index, IB-5x OWNER_ASSERTED-overwrite guard, tenant predicate — each proven failable); the
> 59-test acceptance suite passed; and three invented faults (not-a-real-fault, expire-claim,
> auto-resolve-conflict) each refused with exit 2 and a corpus-grounded message. Ship-dark posture
> holds: only the probe reaches identity_binding_claim, zero production importers, nothing joins the
> machine to a channel. F6 registers exactly six contracts and the machine mints no unregistered
> Claim*/Conflict*/Compensation*/Exception* event and no M7/M9/M10 table; no expiry/auto-resolve
> surface was invented. Migration DDL carries the required invariants. HEAD commit d70a4e7 is a
> separate P3/P4 per-thread-connection concurrency correction, out of M6 scope; its workflow.py diff
> changes only connection lifecycle and does not touch the claim CAS WHERE predicates or M6 runtime.
> This is a landed increment, not a phase acceptance, and I do not treat it as one."

### **THE REVIEWER READ THE CONCURRENCY CORRECTION AND SCOPED IT ITSELF.** The last two sentences are
not this landing's gloss. The reviewer ran `git log --oneline -8 d70a4e78`, `git show --stat d70a4e7`,
`git show --stat 7bf189f` and `git show d70a4e7 -- src/freight_recon/workflow.py`, and concluded from
the diff that the correction changes connection lifecycle only and leaves the claim CAS predicates and
M6's runtime untouched.

## 2. Why the previous M6 review is STALE, and what happened between the two

### 2.1 The first M6 review, and the tree it was bound to

Product Driver run `20260825-204229` reviewed M6 at commit
`460d5c78b4c3cc01fa83f4780cbcb220cd396f07` / tree `3f143d6c605a6a22dc324312f07e692685083af4` and
returned `SUPPORTED`, confidence 0.90, zero findings. Its suite ran **ten** scenarios — the permanent
`p6_m6_identity_binding_claim` (293 assertions) plus nine generated ones — all `PASSED`.

### **THAT REVIEW IS NOT THIS LANDING'S EVIDENCE, AND MAY NOT BE CITED AS IT.** A review is bound to a
tree. `460d5c7` is not the tree being landed, and the change between them was **not** cosmetic: it was
the repair of a real exactly-once defect at the effect boundary. The first review is recorded here for
lineage and for one specific fact it establishes that the fresh run does not: the nine generated
adversarial scenarios (§8, `P6-D46`).

### 2.2 The defect CI found AFTER `460d5c7` was pushed

**GitHub Actions run `32925093992`**, job *Safety invariants (fast)*, failed:

```
eval/tests/test_adapter_boundary_acceptance.py::test_concurrent_execute_yields_exactly_one_effect
```

**Observed: two contenders raced one Effect Grant and total external writes was `0`.** Not two — zero.
Neither contender reached the adapter.

### **THIS WAS A REAL PRODUCT DEFECT AT THE EFFECT BOUNDARY, NOT A FLAKY TEST.** The investigation
recorded in commit `d70a4e7` establishes the mechanism rather than inferring it:

- `WorkflowStore` opened **one** `sqlite3.Connection` with `check_same_thread=False` and handed it to
  every thread.
- **A SQLite transaction belongs to the CONNECTION, not to the thread that opened it.** `BEGIN
  IMMEDIATE` in `_write_txn` was therefore never *"my transaction"* — it was the connection's.
- Two threads interleaved `BEGIN`/`COMMIT`/`ROLLBACK` on one transaction, so **the write lock that is
  supposed to serialize the claim CAS was never contended for.**
- Both failure shapes were **reproduced on the pre-fix tree, not theorised**: the **zero-write**
  timeline (the legitimate winner dies at ADR-004 §3.7 step 6 with *"cannot start a transaction within
  a transaction"*, *before* `operation.perform`; the loser's CAS then reads `CLAIMED` and refuses) and
  the **two-write** timeline (both contenders read `GRANTED`, both reach the adapter — exactly-once
  already broken).

`ADR-004` §8 makes this merge-gating: *"two concurrent pipelines, same commit key ⇒ exactly ONE
claims."* The zero-write shape is the one CI reported; the two-write shape is worse, and the pre-fix
tree could produce it.

### 2.3 The correction — commit `d70a4e7`

| | |
|---|---|
| **What changed** | `WorkflowStore.conn` is a property returning **this thread's** connection to the **same database file**, keyed on the `Thread` **object** (an ident is recycled; a `Thread` object is not, so the cache cannot alias a dead thread's unsettled transaction onto a new one). Dead threads' connections are reaped; `close()` closes them all |
| **What did NOT change** | ### **No process-local mutex was introduced** — so nothing here can hide a cross-process defect. **The database CAS remains the sole serialization authority**, and its six `WHERE` predicates are untouched. **M6's runtime was not changed at all** |
| **The test** | **STRENGTHENED, not weakened.** The race test now runs **120 races instead of one**, because a single-shot race caught the defect only ~2.5% of the time — [`CLAUDE.md`](../../CLAUDE.md) §6: a guard that never fires is a decoration. **The assertion itself is unchanged**, and its message now names *both* racers' outcomes, which the CI red did not |
| **Files touched** | `src/freight_recon/workflow.py` and `eval/tests/test_adapter_boundary_acceptance.py`. **Two files. Nothing under `src/freight_recon/identity_binding_claim.py` or its migration** |

**Mutation proof, from the correction commit's own record** (in-memory mutation, no file touched):
reinstating the shared connection **reproduces the defect at 15/600 races**; the corrected tree is
**0/800** — every race exactly one write, every loser a clean `ALREADY_CLAIMED` / `ALREADY_VERIFIED`
refusal. The strengthened test **catches the mutant 8/8 runs**. ### **THAT IS A MUTANT VERIFIED TO
REINTRODUCE THE REAL DEFECT, WHICH IS THE ONLY KIND THAT PROVES ANYTHING** ([`CLAUDE.md`](../../CLAUDE.md) §6).

### 2.4 Why a fresh M6 run was then required

The tree moved from `460d5c7` to `d70a4e7`. **`test_adapter_boundary_acceptance.py` is in the *Safety
invariants (fast)* job** — verified mechanically at this landing against `.github/workflows/ci.yml` —
which is the exact job that went red on `460d5c7`. A review bound to a superseded tree cannot speak for
the tree being landed, so a **fresh** Product Driver M6 run was executed against `d70a4e7`. That run is
what this record cites, everywhere.

## 3. What M6 is, in one line

**One `identity_binding_claims` row, seven states, eleven transitions, and the rule that
`provenance_class` is a DERIVED, IMMUTABLE function of `match_method` — enforced by a database CHECK
and a trigger, not by a comment.** Identity is the most common and most dangerous claim in freight:
*"this invoice belongs to that load."* M6 makes it a **first-class, evidenced, correctable,
escalatable decision** rather than a silent guess baked into a projection.

**What it REFUSES is the unit:**

- **A `MODEL_INFERRED` guess never confirms — at confidence 1.0 exactly as at 0.4.** Confidence is
  structurally invisible to every guard: it orders a queue, it never gates a transition (`GR-8`,
  entity §41). A guess routes to `AMBIGUOUS`, owned by a named human through a foreign key into
  `tenant_humans`.
- **A `MODEL_EXTRACTED` reading is EVIDENCE, not confirmation.** It re-enters deterministic matching
  (IB-3), and it **cannot exist without an evidence span** — a database `CHECK`, not a convention.
- **There is no best-guess fallback.** An exact trusted-ID match to *exactly one* open entity confirms
  (IB-2); a registered deterministic rule or reconciliation across ≥2 sources confirms (IB-2r);
  **everything else goes to a human.** Multiple candidates are `AMBIGUOUS`; a *single weak* candidate
  is still `AMBIGUOUS`.
- **An `OWNER_ASSERTED` binding survives the relinker.** `RecomputedByInferrer` against it is
  **`IB-5x` — an ILLEGAL transition** that persists nothing and records `IllegalTransitionAttempted`
  **and** `OwnerAssertedOverwriteAttempted` (the Sev-0 B3 tripwire). A retry storm changes nothing.
- **A disagreement raises a Conflict, never a winner.** `IB-6` moves the claim to `CONFLICTING`,
  **preserves the owner's binding intact**, and emits the registered `ConflictRaised`.
- **A human assertion binds an IMMUTABLE id, never an ordinal.** *"Assign unlinked 2"* resolves at
  render time to an `observation_id` and the action binds **that id or fails closed** — it never binds
  the new occupant of a moved slot (`L-B`).
- **A counterparty is `MODEL_EXTRACTED` at best** and is a fraud signal, never promoted to authority.
- **Correction (IB-7) is append-only and PROPAGATES.** It records a durable, M6-owned obligation
  **naming** the completed effects that rest on the wrong binding and therefore need a Compensation.
  **It names them; it fabricates none as completed, and M10 is not built.**
- **At most one `CONFIRMED` binding per subject** — `UNIQUE (tenant_id, subject_ref) WHERE state =
  'CONFIRMED'`, a partial index, plus OCC on the claim version. Tenant-first throughout.
- **Every `OWNER_ASSERTED` binding replays byte-identical.** A rebuild rebuilds projections, not the
  owner's mind.

**In freight terms: a carrier invoice that references a PRO number matching two open loads does not
get assigned to the more likely one. It stops, with a named human on it. And when a broker later says
"no — that one," the machine does not merely change the row: it records which already-completed
effects rested on the wrong answer, so nothing quietly stays wrong downstream.**

### 3.1 The transition table — re-derived mechanically, not carried

**`IB-1`, `IB-2`, `IB-2r`, `IB-2h`, `IB-3`, `IB-4`, `IB-5`, `IB-5x`, `IB-6`, `IB-7`, `IB-8` — eleven
rows, an exact set match with §14 of**
[`06-identity-binding-claim.machine.md`](../specifications/state-machines/06-identity-binding-claim.machine.md).

This landing parsed §14 of **all thirteen** machine files and counted the rows rather than trusting any
prior figure:

| Machine | Rows |
|---|---|
| M1 work item | 14 |
| M2 pipeline instance | 25 |
| M3 external effect / effect grant | 13 |
| M4 approval | 11 |
| M5 observation | 8 |
| **M6 identity binding claim** | **11** |
| M7 conflict | 7 |
| M8 expectation | 8 |
| M9 exception | 7 |
| M10 compensation | 9 |
| M11 policy | 7 |
| M12 rule | 9 |
| M13 brake | 5 |
| **TOTAL** | **134** |

**14 + 25 + 13 + 11 + 8 + 11 = 82 written of 134, so 52 remain.** The `63` figure that
[`CURRENT.md`](CURRENT.md) carried until this landing was the post-M5 figure and is corrected here.

The six canonical **F6** events are `ClaimProposed`, `ClaimConfirmed`, `ClaimEvidenced`,
`ClaimAmbiguous`, `ClaimCorrected`, `ClaimSuperseded` — **and no seventh.** `ConflictRaised` (IB-6) is
an **F7** contract that names IB-6 in its producer list, so — unlike M5 refusing the M9 exception event
whose sole producer is another machine — M6 legitimately emits it; it rides a minted conflict
aggregate, and `event_outbox` holds no foreign key into a `conflicts` table, so emitting it needs no M7
row. **No `conflicts` table, no `CF-*`, and above all no resolution path** — `AutoResolve` is illegal
(ADR-007 §5.3).

## 4. What the reviewer established ITSELF, and how

The reviewer ran the product in its own session. Its harness records **29** command outcomes, reported
here by the harness's own status vocabulary rather than collapsed into a single number:

| Harness status | Count | What it means here |
|---|---|---|
| **`RUNTIME_REPRODUCED`** | **8** | The reviewer executed the product and the output satisfied a named, deterministic expectation |
| `REVIEWER_INSPECTED` | 11 | The reviewer ran it and read the output, but **named no deterministic expectation, so it establishes NOTHING BY MACHINE** and is not counted as evidence here |
| `REFUSED` | 6 | The reviewer's command boundary rejected shell composition outside quotes (`&`, `;`, `>`, `|`) or an ad-hoc `python -c` outside the approved set. **A limit on the review, never a defect in the product** — and `blocked_on.kind` is `NONE` because the reviewer obtained the same facts by other approved means |
| `COMMAND_ERRORED` | 4 | ### **All four are negative controls exiting 2 exactly as designed.** See §4.1 — a harness classification artifact, not a failure |

**Reproduced by the reviewer, by execution** (the eight `RUNTIME_REPRODUCED`):

| # | What ran | What it established |
|---|---|---|
| 1 | `scripts/probe_phase6_identity_binding_claim.py` (full) | exit 0, *"behaviours as specified, 0 wrong"* — *drive the Identity Binding Claim machine through a brokerage narrative, and attack it* |
| 2 | the same probe, `--list-cases` | **62** case names — *the M6 probe can exercise every canonical risk family* |
| 3 | `scripts/mutate_phase6_identity_binding_claim.py` | **13/13 mutants caught** |
| 4 | `pytest eval/tests/test_phase6_identity_binding_claim.py -q` | **59 passed** |
| 5 | an AST sweep over `scripts` | the only script reaching the machine is `probe_phase6_identity_binding_claim.py` |
| 6 | an AST sweep over `src/freight_recon` | **zero production importers** of `identity_binding_claim` |
| 7 | an AST channel sweep over `src/freight_recon` | **nothing joins the machine to an inbound/outbound channel** |
| 8 | a read of `event_contracts_data.json` | **F6 registers exactly six contracts**; `ConflictRaised` is F7 with IB-6 among its producers |

**Recorded as `REVIEWER_INSPECTED`, and therefore NOT counted as machine-established evidence here:**
`git rev-parse HEAD` → `d70a4e78c642…`; `git rev-parse HEAD^{tree}` → `d74cf84bb4bc…`; `git status
--porcelain` → empty; the four `git log`/`git show` commands by which the reviewer scoped the
concurrency correction; and two source scans for invented expiry/auto-resolve surfaces and
cross-machine event minting. **These informed the reviewer's prose and its verdict; the harness named
no expectation for them, so this record does not present them as machine proofs.** The clean-tree claim
rests on the `reviewed_fingerprint` (`tracked_dirty: 0`, `untracked: 0`) — **not** on the `git status`
row, which produced an empty capture that no substring assertion could hold against
([`CLAUDE.md`](../../CLAUDE.md) §6, the vacuous-negative failure mode).

### 4.1 Four harness statuses that read like failures and are not — recorded, not tidied

Anyone reading the raw `independent-review.json` will see four `COMMAND_ERRORED` rows. **None is a
product failure, and none is being quietly dropped here.**

- `--inject not-a-real-fault` → exit **2**, *"unknown fault 'not-a-real-fault'. The fault vocabulary is
  CLOSED and BOUNDED: …"*
- `--inject expire-claim` → exit **2**, *"unknown fault 'expire-claim' is REFUSED: … a claim NEVER
  expires (entity §26) and has no deletion policy (entity §28). Accepting it would manufacture evidence
  for a transition nobody authorized."*
- `--inject auto-resolve-conflict` → exit **2**, *"unknown fault 'auto-resolve-conflict' is REFUSED: …
  ADR-007 §5.3 makes AutoResolve an ILLEGAL transition — a conflict that times out is a conflict
  resolved by a clock…"*
- `--fault not-a-real-fault` → exit **2**, an argparse **usage** error: `--fault` is not a flag this
  probe defines. **A reviewer typo, refused cleanly. It establishes nothing about the product and is not
  counted as if it did.**

For the first three, the scenario-derived expectation was `expect_exit_code: 0`, **which correct
behaviour could never satisfy** — the whole point of a negative control is that it exits non-zero. The
harness classifies any non-zero exit as `COMMAND_ERRORED`. **The product did the right thing; the
harness's expectation vocabulary could not say so.** Tracked as `P6-D45`.

## 5. What Product Driver independently exercised

M6 was **operated as a running unit, not merely tested**. This is the run's structured evidence.

### 5.1 Scenario evidence — 1 required scenario, 293 assertions, 0 failed

| | |
|---|---|
| `full_run` | `true` |
| `expected_required_ids` | `['p6_m6_identity_binding_claim']` |
| `assembly_problems` | `[]` |
| Outcome | `p6_m6_identity_binding_claim` (origin `permanent`, priority `P0`, required) — **`PASSED`** |
| Assertions | **293 total, 0 failed**, `failed_assertions: []`, `evidence_verified: true` |
| Generated scenarios | ### **ZERO ACCEPTED.** Nine were proposed and **all nine rejected at assembly** — see `P6-D46` |

The permanent scenario ran **30 commands** against the real machine, including the full probe, the
`--list-cases` and `--list-dimensions` introspections, the three refused negative controls, the M6
acceptance suite, the mutation battery, six DDL-introspection probes against a freshly created
canonical schema, the fresh-DB readiness oracle, four ship-dark AST sweeps, and the P3/P4/P5/M1–M5
regression batteries plus the M4 and M5 probes.

It carried **fifteen** risk families, **each with its claim `established: true`** and each naming the
checks and printed observations that established it: `authorization`, `unexpected_state_transition`,
`conflicting_evidence`, `missing_data`, `safety_invariant`, `concurrency`, `cross_tenant`,
`malformed_input`, `idempotency`, `retry_safety`, `restart_recovery`, `stale_state`,
`approval_required`, `persistence_failure`, `regression`.

**Fifty-six required invariant sentences were printed by the probe**, among them:

```
provenance_class IS DERIVED FROM match_method, NEVER CHOSEN
A CHANGE OF BELIEF IS A NEW CLAIM, NEVER AN EDITED PROVENANCE
PROVENANCE IS RUNTIME-ASSIGNED, NEVER SET FROM CONTENT
THERE IS NO BEST-GUESS FALLBACK
A MODEL GUESS ROUTES TO AMBIGUOUS AND NEVER CONFIRMS
CONFIDENCE 1.0 CHANGES NOTHING
CONFIDENCE IS INVISIBLE TO EVERY GUARD
A SINGLE WEAK CANDIDATE IS STILL AMBIGUOUS
AN OWNER_ASSERTED BINDING SURVIVES THE RELINKER
RECOMPUTING AN OWNER_ASSERTED BINDING IS AN ILLEGAL TRANSITION
THE INFERRER DISAGREEING WITH THE OWNER RAISES A CONFLICT, NOT A WINNER
THE ORDINAL RESOLVED TO AN IMMUTABLE ID OR THE ACTION FAILED CLOSED
COMPLETED EFFECTS THAT RESTED ON THE WRONG BINDING ARE NAMED FOR COMPENSATION
NO COMPENSATION IS FABRICATED AS COMPLETED
AT MOST ONE CONFIRMED BINDING PER SUBJECT
COMPETING CONFIRMATIONS SERIALIZE: ONE WINS, THE REST ARE REFUSED
A WRONG-TENANT HUMAN ASSERTION FAILS CLOSED
A COUNTERPARTY IS MODEL_EXTRACTED AT BEST, NEVER OWNER_ASSERTED
EVERY OWNER_ASSERTED BINDING REPLAYED BYTE-IDENTICAL
replay: 0 new claims, 0 rewritten provenance, 0 new authority, 0 external effects
THE M7 CONFLICT MACHINE IS NOT BUILT
THE M10 COMPENSATION MACHINE IS NOT BUILT
M6 MINTS NO GATE DECISION
behaviours as specified, 0 wrong
```

### 5.2 Mutation evidence — 13/13, each guard proven able to fail

### **A GUARD NEVER SEEN TO FAIL IS A DECORATION** ([`CLAUDE.md`](../../CLAUDE.md) §6). Each mutant
below reintroduces a real, named defect, and each was caught:

| # | Mutant — the defect it reintroduces | Result |
|---|---|---|
| 1 | a `MODEL_INFERRED` guess is allowed to CONFIRM — the IB-4 routing guard inverted and the CONFIRMED-provenance CHECK widened (entity §37, GR-8) | **CAUGHT** |
| 2 | a confidence THRESHOLD used as a confirmation guard — the `if confidence > 0.98` defeat ADR-007 §8 names, by hand | **CAUGHT** |
| 3 | the IB-5x provenance guard dropped — the relinker OVERWRITES an `OWNER_ASSERTED` binding (**the B3 regression**, GR-9, R-P3) | **CAUGHT** |
| 4 | the IB-4 weak-candidate guard removed — a single WEAK candidate auto-confirms instead of failing to a human (M-17) | **CAUGHT** |
| 5 | the SD-6 mapping CHECK widened to always-true — a caller can choose a provenance off the function (entity §13, R-P2) | **CAUGHT** |
| 6 | the `provenance_class` immutability trigger defanged — provenance editable in place instead of a new claim | **CAUGHT** |
| 7 | the `MODEL_EXTRACTED` evidence-span CHECK widened to always-true — a span-less extraction becomes writable | **CAUGHT** |
| 8 | the one-CONFIRMED-per-subject index loses `UNIQUE` — two canonical bindings for one subject become insertable (entity §17) | **CAUGHT** |
| 9 | the ordinal slot-change guard removed, bind falls back to POSITION — a human action whose slot moved binds the new occupant (L-B) | **CAUGHT** |
| 10 | IB-6 turned into an OVERWRITE — the inferrer supersedes the owner instead of raising a conflict (ADR-007 §4.3) | **CAUGHT** |
| 11 | the tenant predicate dropped from the claim read — one tenant reads another's binding (`[C-1]`) | **CAUGHT** |
| 12 | the correction fails to name the completed effects — the obligation is written carrying NO effects for compensation (ADR-007 §6, M-20) | **CAUGHT** |
| 13 | replay RE-DERIVES provenance instead of reading it from the event — an `OWNER_ASSERTED` binding rebuilt as `LINKER_INFERRED` (ADR-007 §7) | **CAUGHT** |
| | | **13/13** |

The battery prints its own provenance: *"written by the session that implemented the unit — evidence,
not adjudication."* ### **THE INDEPENDENT REVIEWER RE-EXECUTED IT AND GOT 13/13 IN ITS OWN SESSION**,
which is what makes it evidence about the tree rather than about the builder.

### 5.3 The M6 acceptance suite — 59 tests

`eval/tests/test_phase6_identity_binding_claim.py`: **55 test functions, 59 collected cases, 59
passed** — verified mechanically at this landing and independently re-run by the reviewer. It includes
entity §44's named adversarial tests: `test_owner_binding_survives_relinker` (the B3 regression),
`test_guess_never_confirms_at_confidence_1_0`, `test_single_weak_candidate_is_still_ambiguous`,
`test_correction_propagates_a_compensation`,
`test_ordinal_binding_resolves_to_immutable_id_or_fails_closed`,
`test_model_extracted_requires_evidence_span`, `test_two_confirmed_bindings_impossible`,
`test_no_provenance_laundering`, `test_inferrer_vs_owner_raises_conflict_not_a_winner`.

### 5.4 DDL introspection — the invariants are in the database, not in the Python

Against a **freshly created canonical schema**, the run confirmed on `identity_binding_claims`:

- `provenance_class` is a **CHECKed total function of `match_method`** (the full six-way SD-6 mapping),
  with an **immutability trigger** on both columns;
- the **seven** canonical states and the **six** `match_method` values as inline column CHECKs — **no
  eighth state, no seventh method**, and no imported `RESOLVED`/`EXPIRED`/`ARCHIVED`/`DELETED`;
- the tenant-first `UNIQUE … WHERE state = 'CONFIRMED'` **partial** index;
- the `MODEL_EXTRACTED` **evidence-span** CHECK and the `LINKER_INFERRED`/`RECONCILED` **`rule_id`**
  CHECK;
- foreign keys **only into tables that exist** — `observations`, `tenant_humans`, and self. **No FK into
  an unbuilt `conflicts`, `exceptions`, `compensations` or `evidence` table.**
- `schema_readiness_problems() == []` on a fresh canonical DB, with `identity_binding_claims` present
  and tenant-first.

### 5.5 Negative controls, and the closed fault vocabulary

The probe's fault vocabulary is **CLOSED**. Three invented faults were each refused with **exit 2** and
a corpus-grounded, traceback-free message — `not-a-real-fault` (unknown), `expire-claim` (entity
§26/§28: *a claim never expires*), `auto-resolve-conflict` (ADR-007 §5.3: *AutoResolve is illegal*).
### **A PROBE THAT WILL MANUFACTURE EVIDENCE FOR A TRANSITION NOBODY AUTHORIZED IS NOT A PROBE.**

### 5.6 Regressions — run WITH M6's table present in the schema

| Battery | Result |
|---|---|
| P3 — witness, claim CAS, step order, brake, fingerprint | **216 passed** |
| P4 — import gate, adapter boundary, governed write route, no-mock-effect | **99 passed** |
| P5 — event transport, replay/audit, durable timers, event contracts | **561 passed** |
| M1–M5 — work item, pipeline instance, external effect, approval, observation | **483 passed** |
| M5 probe (`probe_phase6_observation.py`) | exit 0 — *behaviours as specified, 0 wrong* |
| M4 probe (`probe_phase6_approval.py`) | exit 0 — *behaviours as specified, 0 wrong* |

The **P4 adapter-boundary battery is the one that went red on `460d5c7`.** It is green here, on the
corrected tree, inside the fresh run.

### 5.7 Ship-dark posture — measured, not asserted

| Check | Result |
|---|---|
| Production importers of `identity_binding_claim` | ### **`[]`** — zero |
| Scripts reaching it | **only** `probe_phase6_identity_binding_claim.py` |
| Channel join (23 named inbound/outbound modules) | **none** |
| Modules that MINT a gate decision | ### **`['checkpoint.py']`** — the checkpoint stays the one gate authority |
| M7 / M9 / M10 / Evidence tables created | **none** |
| Unregistered event minted (`Claim*`/`Conflict*`/`Compensation*`/`Exception*`) | **none** |
| Invented expiry / auto-resolve / sweep / purge surface | **none** |

**No production effect is enabled by M6.** The deployed governed route still answers a recorded
`ROUTE_NOT_CONFIGURED` refusal, and the production `GateRegistry` stays **EMPTY** until U8.1/P8.

### 5.8 The run's own audit

| Field | Value |
|---|---|
| `completion_audit.decision` | **`VERIFIED`**, confidence `0.85` |
| `completion_audit.headline` | *"P6/M6 is supported by the repository; P6 remains IN_PROGRESS."* |
| `implementation_present` | **`true`** |
| `missing_evidence` | `[]` |
| `contradictions` | `[]` |
| `scoped_completion.task_result` | **`VERIFIED`**, `task_outstanding: []` |
| `parent_phase_accepted` | **`false`** |
| `does_not_imply` | *"P6 is COMPLETE"* · *"any P6 acceptance criterion is scored"* · *"the units P6 still owes are built"* · *"the next phase is unblocked"* · *"phase acceptance has occurred"* · *"anything is enabled in production or on live traffic"* |
| Evaluator decision | **`ACCEPT`**, confidence `0.86`, `problems: []` |

## 6. The authority questions M6 preserved — REPORTED, NOT RESOLVED

**The corpus disagrees with itself on three points about M6.** The build reported all three and
implemented **only what every reading agrees on**. ### **NONE OF THE THREE IS RESOLVED HERE, AND THIS
LANDING RESOLVES NO AUTHORITY CONFLICT.** They are stated in
`src/freight_recon/identity_binding_claim.py`'s own module docstring and at the migration site, so a
reader of the code meets them where the decision would be made. Tracked collectively as `P6-D41`.

| | The question | What the code does, and what it refuses to decide |
|---|---|---|
| **`M6-AQ-1`** | IB-7's propagation raises a Compensation for each completed effect that rested on a wrong binding — but `CorrectionInvalidatedAnEffect` appears in M1 §33 *"events consumed"* with **no §14 row and no registered contract** (the same seam `P6-D2` records for M1) | Emits the **registered** `ClaimCorrected` and records a durable, M6-owned `propagation_obligation` on the claim row **naming** the completed effects. ### **IT MINTS NO UNREGISTERED EVENT NAME**, builds no `compensations` table and no `CM-*`. What the correction owes is *named*, never fabricated as discharged |
| **`M6-AQ-2`** | Entity §16's CHECK requires `LINKER_INFERRED`/`RECONCILED` to carry a `rule_id` — but ADR-007 §4.1 step 1 (exact trusted-ID match) and reconciliation carry **no customer rule** | Keeps the CHECK **exactly as written** and supplies a **built-in mechanism id** (`rule:builtin-exact-trusted-id`, `rule:builtin-reconciliation`) for the two deterministic mechanisms. ### **THAT HONOURS THE CHECK WITHOUT INVENTING A FREIGHT IDENTITY RULE — `V4` STAYS OPEN.** No MC+date+amount, BOL or PRO rule is defined. The alternative reading (IB-2 carries no `rule_id`) is REPORTED |
| **`M6-AQ-3`** | `CONFLICTING` is non-terminal human-owned, but M6's §14 gives it **no outgoing transition** — resolution belongs to M7, which is not built | Gives `CONFLICTING` **no M6-internal exit** while preserving the human binding intact. It invents no resolution path, and `AutoResolve` stays illegal. The state is a dead end **on purpose**, until M7 exists |

**`V4` — registered deterministic identity rules (MC+date+amount? BOL? PRO?) — remains OPEN
VALIDATION** per machine spec §43, with the fail-closed default the specification itself states (exact
ID match only; else `AMBIGUOUS` ⇒ human), and explicitly *"not a block"*. **It requires design-partner
evidence and may never be guessed** ([`CLAUDE.md`](../../CLAUDE.md) §5, rule 18).

The **migration hazard** machine §43 and entity §45 record is likewise carried, not closed: *existing
owner corrections must be re-captured as `OWNER_ASSERTED` or they will be silently re-derived as
`LINKER_INFERRED`.* Noted, not a block — and there is no data to migrate while M6 ships dark.

### **NO SESSION MAY CLOSE `M6-AQ-1`, `M6-AQ-2`, `M6-AQ-3` OR `V4` BY CHOOSING A READING.** These are
specification questions owed to a founder/architect decision. A plausible guess here becomes a
permanent, invisible decision enforced on real money later ([`CLAUDE.md`](../../CLAUDE.md) §5).

## 7. What did NOT change

**No runtime file is touched by this landing.** The landing commit changes documents only:
this report, [`CURRENT.md`](CURRENT.md) and
[`IMPLEMENTATION-REGISTRY.yaml`](IMPLEMENTATION-REGISTRY.yaml).

- **M6's runtime is byte-unchanged** since the corrections that preceded this landing:
  `src/freight_recon/identity_binding_claim.py` and
  `src/freight_recon/migrations/phase6_identity_binding_claims.py` last changed at `460d5c7`, and the
  concurrency correction at `d70a4e7` touched neither.
- **The P3/P4 concurrency correction is not modified here.** `src/freight_recon/workflow.py` and
  `eval/tests/test_adapter_boundary_acceptance.py` are untouched by this landing.
- **The checkpoint kernel is untouched.** `CheckpointPassed` stays unconstructable, the witness table
  append-only, the claim CAS's six WHERE predicates intact.
- **No M7, M9 or M10 implementation leaked in.** No `conflicts`, `exceptions` or `compensations` table;
  no `CF-*`, `EC-*` or `CM-*` transition.
- **No production importer, no live integration, no external effect enabled.**

## 8. Minor and nonblocking items — recorded, not actioned

### **THE INDEPENDENT REVIEW RETURNED ZERO FINDINGS AND ZERO ADJUDICATIONS.** Nothing below is a
reviewer finding and nothing below may be cited as one. Each was identified **at this landing** from
the run's own structured evidence, the M6 source, the specification corpus and the CI record. Each is
**RECORDED, NOT ACTIONED** ([`CLAUDE.md`](../../CLAUDE.md) §13 — the debt row is the complete
deliverable). None can produce a wrong customer outcome, violate an invariant, or make a later phase
unsafe, and the machine ships dark.

### `P6-D41` — the three §3.9 M6 authority questions are REPORTED, not resolved · `minor` · specification seam

`M6-AQ-1`, `M6-AQ-2` and `M6-AQ-3`, in full in §6, together with the standing `V4` open-validation item
and the entity §45 migration hazard. The code implements only what every reading agrees on, **invents
no reconciliation**, and says so in its own module docstring and at the migration site. These close
when a founder/architect decision is made — **not by a session choosing a reading.**

### `P6-D42` — this commit has NO GREEN CI CONCLUSION · `minor` · CI

Run `32944840998` on head `d70a4e7` concluded **`cancelled`**. Full detail, and the honest bound, in
§9. It closes only by a CI run on this branch that concludes `SUCCESS`.

### `P6-D43` — CI does not execute M6's probe or mutation battery · `minor` · CI coverage

Verified mechanically at this landing: `.github/workflows/ci.yml` contains **zero** occurrences of
`phase6_identity_binding_claim`. The `effect-grant` job runs **M3's** probe and battery on every push
precisely because `pytest eval` does not invoke them; there is no equivalent job for M4 (`P6-D33`), M5
(`P6-D37`) or M6. `eval/tests/test_phase6_identity_binding_claim.py` **is** inside `pytest eval` and did
run in the suite jobs. Closing this is a change to CI wiring, which a status/evidence landing
deliberately does not make.

### `P6-D44` — the run's gate and topology snapshots are stale and read as blockers · `minor` · evidentiary

Two fields in `record.json`'s `protocol_resolution` will mislead a session that reads only them:

- **`gates.independent_review: NOT_RUN`**, detail *"no independent review recorded for this state"*.
  **That snapshot was taken at `2026-08-26T07:37:35+00:00`, before the review executed at
  `07:44:00`.** The run's `independent-review-ledger.json` records the review with `independent: true`,
  a reviewer session distinct from the builder's, `inherited_builder_context: false`, verdict
  `SUPPORTED`, `invalidations: []` and `superseded_by: ""`. **The structured ledger and the review
  record are authoritative; the gate snapshot is stale.** (This is the M6 analogue of `P6-D34`/`P6-D38`.)
- **`topology.state.state: ILLEGAL`**, because the driver's legacy topology model read a recorded
  commit `d59b7400a472` out of `IMPLEMENTATION-REGISTRY.yaml` and compared it to HEAD `d70a4e78c642`.
  **That model is the retired two-commit content+metadata convention** the 2026-08 simplification
  removed ([`CLAUDE.md`](../../CLAUDE.md) §0 — *no status receipt, no two-commit convention, no
  preserve refs, no special Git topology*). The run's own `protocol_resolution.status` is
  **`CONSISTENT`** with `violations: []`, `deadlocks: []` and `next_safe_action: "proceed: topology and
  authority are consistent"`. **Nothing is owed here, and no topology ceremony may be run on the
  strength of that field.**

### `P6-D45` — the reviewer harness's status vocabulary mis-labels correct behaviour · `minor` · evidentiary

Four of the reviewer's 29 command rows carry `COMMAND_ERRORED` for reasons that are not failures:
three are negative controls exiting **2 exactly as designed** (and their scenario-derived expectation
was `expect_exit_code: 0`, which correct behaviour could never satisfy), and one is an argparse usage
error from a reviewer typo (`--fault` is not a flag this probe defines). Six further rows are `REFUSED`
by the reviewer's own command boundary — a limit on the review, never a defect in the product — and
`blocked_on.kind` is `NONE`. **Eleven rows are `REVIEWER_INSPECTED` with no named expectation and
therefore establish nothing by machine**; §4 counts them as nothing. Full detail in §4/§4.1. Recorded
so nobody reading the raw JSON mistakes a correct refusal for a defect, and so nobody cites an
inspected-only row as a machine proof.

### `P6-D46` — the fresh run accepted ZERO generated scenarios · `minor` · coverage disclosure

### **THIS IS A REAL REDUCTION IN GENERATED ADVERSARIAL COVERAGE BETWEEN THE STALE RUN AND THE FRESH
ONE, AND IT IS DISCLOSED RATHER THAN AVERAGED AWAY.**

The fresh run proposed **nine** generated scenarios and **rejected all nine at assembly**, each for the
same reason — an **unrecognised `risk_category` string**, a harness-taxonomy rejection with
`reasoner_error: ''` and `assembly_problems: []`:

| Proposed scenario | Rejected `risk_category` |
|---|---|
| `S1-ship-dark-isolation` | `ships-live-not-dark` |
| `S2-no-gate-no-overreach` | `scope-overreach-into-m7-m10` |
| `S3-b3-relinker-retry-storm` | `owner-decision-overwritten` |
| `S4-competing-confirmations-race` | `double-confirmation-race` |
| `S5-confidence-invisible-defeat` | `confidence-gated-confirmation` |
| `S6-cross-tenant-concurrent-race` | `cross-tenant-leak` |
| `S7-correction-of-correction-obligation` | `correction-obligation-dropped` |
| `S8-replay-byte-identical` | `replay-rewrites-owner-asserted` |
| `S9-mutation-battery-guards-fail` | `unfalsified-guard` |

So the fresh run's suite is **one permanent scenario, 293 assertions** — where the **stale** run
(`460d5c7`) ran ten scenarios: the same permanent one plus nine generated, **all PASSED**
(`m6-b3-relinker-retry-storm` 7, `m6-competing-confirmations-race` 7, `m6-confidence-invisible` 5,
`m6-laundering-refused` 6, `m6-w2-fault-closure-exit2-and-message` 10,
`m6-w2-provenance-immutability-trigger` 12, `m6-inferrer-vs-owner-conflict` 6,
`m6-ordinal-moved-fails-closed` 5, `m6-ships-dark` 9 — 67 further assertions, 0 failed).

**What is a true bound, and what is NOT one.** The nine rejected proposals target surfaces the
permanent scenario **does** exercise in its own 30 commands and 293 assertions — the ship-dark AST
sweeps, the gate-minter check, the B3/IB-5x guard, the competing-confirmation serialization, the
confidence-invisibility cases, the cross-tenant cases, the correction obligation, the byte-identical
replay, and the 13/13 mutation battery — and it passed on the corrected tree. ### **THAT IS NOT A CLAIM
THAT THE NINE GENERATED SCENARIOS WOULD HAVE PASSED ON `d70a4e7`.** They were **never assembled and
never run against this tree**; the honest statement is that this tree has **no result** for them,
neither passing nor failing. The stale run's passes are evidence about `460d5c7`, and the diff between
the trees does not touch M6 — but a different tree is a different execution, and this record does not
launder one into the other. **Closing this means a harness-taxonomy fix in the Product Driver
repository, which a status/evidence landing in this repository does not make.**

### `P6-D40` — carried forward, unchanged and unfixed, and now with a THIRD miss

The two guard gaps `P6-D40` recorded at the `P6-CP-5` landing are **still open and were re-verified as
open at this landing**, by an in-memory mutation battery over the status/control guard set
(`test_bootstrap_hermeticity`, `test_false_green_defenses`, `test_p5_canonical_event_mint`,
`test_phase0_identifiers`, `test_phase0_errata_guards`, `test_phase2_guard_registry`). Every mutant was
verified to **apply** before its result was believed, the harness saved and restored the two documents
**from memory** (`git checkout`/`restore`/`stash`/`clean` are forbidden here —
[`CLAUDE.md`](../../CLAUDE.md) §6), and the unmutated tree was confirmed green afterwards. **The
denominator is printed, and it is six:**

| Mutant | Result |
|---|---|
| `CURRENT.md` **deletes the `identity_binding_claims` PARTITION ROW** (the token still appears elsewhere in the file) | ### **MISSED** |
| `CURRENT.md` **stops naming `identity_binding_claims` ANYWHERE** | **CAUGHT** |
| P7 flipped `BLOCKED` → `READY` | **CAUGHT** |
| P6 flipped `READY` → `COMPLETE` | **CAUGHT** |
| **`P6-CP-6` scores a P6 acceptance criterion** (`criteria_scored: [independent_review]`) | ### **MISSED** |
| **`P6-CP-6` cites an `independent_review_report` that is not on disk** | ### **MISSED** |
| | **3 of 6 caught** |

**All three misses are pre-existing guard gaps, not defects this landing introduced.**

- **The two `P6-CP-6` misses are `P6-D40`'s, unchanged.** `criteria_scored: []` on all six P6
  checkpoints — the single most repeated prohibition in this record — still rests on discipline rather
  than on a guard, because `test_p5_canonical_event_mint.py` asserts it for **P5's** checkpoints and
  there is no P6 equivalent. And the registry's own invariant *"checkpoint_state
  INDEPENDENTLY_REVIEWED or ACCEPTED_FOR_CONTINUATION ⇒ the cited independent review report exists on
  disk"* lost its guard when `test_roadmap_completeness_control.py` was removed in the 2026-08
  simplification; nothing replaced it.
- ### **THE THIRD MISS IS NEW HERE AND IS A REAL PROPERTY OF THE GUARD, NOT A BATTERY ARTIFACT.**
  `test_bootstrap_hermeticity.py::test_the_canonical_table_partition_is_exact_and_disjoint` asserts
  each table name with `assert t in text` over **the whole of `CURRENT.md`**. Deleting the partition
  **row** therefore does not fail it whenever the token appears anywhere else in the document — and it
  now does, in this landing's own M6 cell. Only complete removal fails the guard.
  **[`CLAUDE.md`](../../CLAUDE.md) §6 names this exact shape: use whole-token or structural matching,
  not substrings.** The `P6-CP-5` record met the same behaviour and classified it as a defect *in its
  battery*; run against a second table it is better read as a bound on **the guard**, and it is
  recorded that way here. The partition's real strength is elsewhere and is unaffected: the same test
  asserts the **shape** (`p6_identity_binding_claims_tenant: 1`) and the **exactness and disjointness**
  of the classes against the migrations, and both of those are structural.

### **A CORRECTION TO THIS BATTERY, RECORDED BECAUSE IT IS THE FAILURE MODE §6 EXISTS TO CATCH.** A
first run of this harness reported two mutants as `COLLECTION_ERROR` and scored **0/5**. That was the
harness's defect, not the guards': its classifier searched for the substring `error` anywhere in
pytest's output and matched the interpreter's `DeprecationWarning` noise. Both mutants had in fact been
**CAUGHT** (`2 failed, 103 passed`). The classifier was corrected to detect a real collection error
(`ERROR collecting` / `errors during collection`) and to require a `failed` count in the summary line
before calling a non-zero exit a catch. **No result above was believed until after that correction.**

**Closing any of the three means writing guards, which a status/evidence landing deliberately does
not do.** Recorded, not actioned.

### Standing items, carried and unchanged — not new debt

- **The exhaustive `(state × trigger)` illegal sweep** is exercised at **representative** points for M6
  as it is for M3 (`P6-D30`), M4 and M5. Structurally mitigated: `apply()` derives legality **solely**
  from `legal_transitions()`, which returns empty for any non-enumerated pair, and `GR-1` then refuses
  uniformly. It is a **gate G1 phase-acceptance** item, not an M6 defect.
- **The F14 `ProvenanceStrengtheningAttempted` emission half** stays deferred to Phase 7 where P5's
  `IR-R9` places it, exactly as M5 handled it. The laundering **refusal** is mandatory and present now.
  The F14 tripwires that *are* M6's — `IllegalTransitionAttempted` and `OwnerAssertedOverwriteAttempted`
  — are emitted, and `CounterpartySelfAuthorizationDetected` is present.
- **`G2-D15`**, `V2`, `V3`, `P6-D1`–`P6-D40` and the P5/P6 residual sets are unchanged by this landing.
- **`P6-D2` intersects `M6-AQ-1`** and is not closed by it: `CorrectionInvalidatedAnEffect` has no
  registered contract, its `closes_at` is M10, and M6 mints no substitute.

## 9. ### CI — the honest record. The workflow did NOT conclude `SUCCESS`

**Pushed CI run `32944840998`**, head SHA `d70a4e78c6426e4cf1f880804d4c36b5893347bf`.

### **OVERALL WORKFLOW CONCLUSION: `CANCELLED`. NOT `SUCCESS`. NOT GREEN.**

| Job | Conclusion |
|---|---|
| **Safety invariants (fast)** | ### **`success`** |
| **Full test suite (py3.11)** | ### **`success`** |
| **P6/M3 effect-grant probe + mutation** | ### **`success`** |
| **Risk radar** | `skipped` (pull-request-only job) |
| **Full test suite (py3.12)** | ### **`cancelled` — by the workflow/runtime ceiling WHILE STILL EXECUTING, at approximately 59%. NO pytest failure was emitted; GitHub ended it with "The operation was canceled."** |

### **THE PROVENANCE OF THIS TABLE IS DISCLOSED RATHER THAN IMPLIED.** These job conclusions were
**supplied by the founder**, not re-read by the session that wrote this record. `api.github.com` is not
reachable from this session's sandbox — `gh run view 32944840998` was attempted here and failed with
`tls: failed to verify certificate: x509: OSStatus -26276` (TLS interception). **They are re-readable at
the run itself, and a later session with network access should read them there rather than trusting this
transcription.** No receipt is committed for any of it — [`CLAUDE.md`](../../CLAUDE.md) §0 forbids
committed suite receipts and none may be manufactured.

### 9.1 The one thing this run establishes that the previous two did not

### **THE EXACT JOB THAT EXPOSED THE CONCURRENCY DEFECT NOW PASSES ON THE CORRECTED TREE.**
*Safety invariants (fast)* is the job that failed on `460d5c7` in run `32925093992`
(`test_concurrent_execute_yields_exactly_one_effect`, `total_writes = 0`), and
`eval/tests/test_adapter_boundary_acceptance.py` is in that job's file list — verified mechanically at
this landing against `.github/workflows/ci.yml`. On `d70a4e7` that job concluded **`success`**. **That
is a specific, load-bearing pass, not a general green.**

### 9.2 What is a true bound, and what is NOT one

`eval/tests/test_phase6_identity_binding_claim.py` — M6's whole 59-case acceptance and hostile battery
— is inside `pytest eval`, which is exactly what the *Full test suite* job runs, **and that job passed
on Python 3.11 on this commit**. The *Safety invariants (fast)* job's 26 files are all under
`eval/tests/` and are therefore a strict subset of `pytest eval`; it passed too.

### **THAT IS NOT A CLAIM THAT PYTHON 3.12 PASSED.** A different interpreter is a different execution,
and the 3.12 job was cancelled *while running*, not after finishing. A passing 3.11 suite is evidence
about 3.11, and the honest statement is that **the repository has no Python 3.12 result for this commit
at all** — not a failing one, and not a passing one. The workflow conclusion is `cancelled` and stays
`cancelled` until a fresh run says otherwise.

*(The polarity is inverted from the `P6-CP-5` landing, where 3.12 passed and 3.11 was cancelled. Neither
run gives this branch both interpreters on one commit.)*

### 9.3 The founder decision

**The founder has explicitly chosen to proceed with the M6 landing on the evidence that exists**,
treating the cancellation as a **non-product CI runtime limitation** rather than as evidence of an M6
defect, on the grounds that the safety-invariants job — including the very test that exposed the
concurrency defect — passed, the Python 3.11 full suite passed, the M3 probe/mutation job passed,
Product Driver's behavioural verification passed, the 13/13 mutation proof passed, and the independent
review supported M6 against this exact tree.

### **THAT IS A FOUNDER DECISION, AND IT IS RECORDED AS A DECISION — NOT AS A VERIFICATION, AND NOT AS
A GREEN CI RESULT.** It is tracked as `P6-D42`.

## 10. What this review and this landing are not

- **Not a phase acceptance.** No P6 acceptance criterion is scored, and none may be from any lineage
  that built M6. P6 remains `READY` / `IN_PROGRESS`, `criteria_scored` is `[]` on all six checkpoints,
  and P7 stays `BLOCKED`.
- **Not an adjudication**, and none is owed. A single independent review is a review, not a chain.
- **Not CI evidence.** See §9. The workflow concluded `cancelled`.
- **Not an enablement.** M6 ships dark: zero production importers, only the probe reaches it, nothing
  joins it to an outbound channel, no external effect is enabled on live traffic, the deployed governed
  route still answers `ROUTE_NOT_CONFIGURED`, and the production `GateRegistry` stays EMPTY.
- **Not a resolution of `M6-AQ-1`, `M6-AQ-2`, `M6-AQ-3` or `V4`.** `P6-D41` reports them; it settles
  none, and no session may settle them by choosing a reading.
- **Not a re-opening of the P3/P4 concurrency correction.** That correction is landed at `d70a4e7` and
  is untouched here.
- **Not a citation of the stale `460d5c7` M6 review as final evidence.** See §2.
- **Not the start of M7.** No `conflicts` table, no `CF-*`, no resolution path. `CONFLICTING` has no
  M6-internal exit and that is deliberate.
- **Not a finalizer, a suite receipt, a preserve ref, a clean-clone ceremony or a special Git
  topology.** None is owed for this landing and **a session must not run one.**
- **Not a review of the commit that carries it** — see the banner.

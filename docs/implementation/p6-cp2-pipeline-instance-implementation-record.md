# P6-CP-2 — The Pipeline Instance: one durable attempt, and the effect that can only happen once

> ### **THIS IS THE IMPLEMENTING SESSION'S RECORD. IT IS EVIDENCE, NOT ACCEPTANCE.**
> It was written by the session that built machine M2. It is not an independent review, it is not an
> adjudication, and it scores no P6 acceptance criterion. What it owes is stated in §10.

---

## 1. What a broker can now do that they could not before

Neyma can hold, durably, **what it is currently doing about an obligation** — and can be relied on
not to do it twice.

```
Work Item          "Get load 4471's POD and bill it."        M1 — the obligation, and its owner
Pipeline Instance  "Attempt #1 to raise the invoice."        M2 — what Neyma is DOING about it
```

Concretely, for a brokerage:

- **The billing sweep can run twice and the customer still gets one invoice.** A second proposal for
  the same logical effect is **absorbed** onto the attempt already running, and the operator sees one
  card with the duplicate recorded against it. The Commit Key carries no amount, so a re-proposal at
  a different price is still the *same* effect — which is exactly why it must be absorbed rather than
  raced.
- **A rate change after the human approved kills the attempt rather than sending the old number.**
  The operator is told what changed, old value → new value, and that nothing was sent.
- **Ops can stop the line in the seconds between authorization and execution, and nothing goes out.**
  Not "usually" — the claim matches zero rows, so the adapter does nothing. Never both, never neither.
- **Releasing the brake does not resurrect the dead authorization.** A decision taken before a human
  stopped the line has to be re-taken, not resumed.
- **When the TMS connection drops mid-write, Neyma says it does not know** — and keeps saying so. It
  never becomes "failed", no deadline resolves it, and **nobody may retry that load** until a human
  establishes reality with evidence. That block is a database index, not a code path somebody has to
  remember.
- **A retry is a new attempt at the same effect, numbered**, so "attempt #3 to bill load 4471" is a
  fact an operator can read rather than a story reconstructed from logs.

### It ships dark

Nothing in the repository calls M2. Its transitive import closure reaches no effect-capable module,
the production `GateRegistry` population is still **EMPTY**, R-07 stays **CONTAINED**, and no
external effect was enabled by any of this.

---

## 2. What M2 actually represents in a freight company

`02-pipeline-instance.machine.md` §3: *"One durable attempt to produce one effect; the Pipeline
Instance IS the command."* There is no separate command object to lose and no in-memory "current
step" a restart forgets. The attempt is a row, and it carries: which obligation it serves, which
human is accountable, which logical effect it is at, which attempt number it is, which prior attempt
it replaces, which policy decided, which approval was bound, which witness and which grant authorized
it, and — when it went wrong — the specific question a human has to answer.

**The two properties it exists for:**

| Property | The mechanism |
|---|---|
| **One attempt at a time, one effect ever** | Layer 1 is `UNIQUE(tenant, commit_key) WHERE state NOT IN (CLOSED,REJECTED,VOIDED,FAILED)` on `pipeline_instances`. Layer 2 is P3's `ix_effect_grants_live_hold`, which holds a VERIFIED effect's key forever. Layer 1 stops two attempts from RUNNING; Layer 2 stops two effects from EXISTING. Neither is the other's backup |
| **Never both, never neither** | PL-8 and PL-9 put the pipeline's own writes inside the kernel's transaction, so there is no interval where the ledger says CLAIMED and the attempt does not, or the reverse |

### The reservation predicate IS §20's retry rule, and that is not a coincidence

    CLOSED · REJECTED · VOIDED · FAILED  terminal  ⇒ outside the index ⇒ key FREE ⇒ retry allowed
    NEEDS_VERIFICATION               non-terminal  ⇒ inside  the index ⇒ key HELD ⇒ no retry

*"We cannot say whether the effect happened, therefore nobody may try again"* is enforced by a
partial unique index. `NEEDS_VERIFICATION` never auto-resolves and never expires (§23), so the block
persists until a human establishes reality.

---

## 3. Exact machine / state / transition surface built

| | |
|---|---|
| **Machine** | M2, `state-machines/02-pipeline-instance.machine.md` |
| **States** | **16**, parsed from `registry.md` §4 and compared by set equality |
| **Terminal** | **4** — `CLOSED`, `REJECTED`, `VOIDED`, `FAILED`. Absolutely final by trigger: **no reopen door at all** (§24), unlike `work_items`' WI-13 |
| **Human-owned** | 2 — `AWAITING_APPROVAL`, `NEEDS_VERIFICATION` |
| **Transitions** | **25** — `PL-1, PL-1b, PL-2, PL-3, PL-4, PL-5, PL-6, PL-7a, PL-7b, PL-7v, PL-8, PL-8f, PL-9, PL-9v, PL-10, PL-10f, PL-10u, PL-11, PL-11c, PL-11d, PL-12, PL-13, PL-14, PL-15, PL-15x`. The denominator is read from `foundational-machine-acceptance.md`'s own coverage table, not typed |
| **Classification** | **16 PRODUCER · 8 CONSUMES · 1 NON_PRODUCING** (PL-15x, declared ILLEGAL by §14) |
| **Events emitted** | **13** F2 contracts. Each is verified against the canonical contract's own `producers` tuple, so a mis-attributed emission is a build failure and not a review finding |
| **Events consumed** | 8 — `ApprovalRequested`(AP-1), `GrantClaimed`(EF-2), `EffectExecuted`(EF-3), `EffectFailed`(EF-3f), `OutcomeUnknown`(EF-3u), `EffectVerified`(EF-4), `VerificationConflict`/`VerificationUnavailable`(EF-4c/4u), `RealityEstablished`(EF-5). All M3's or M4's; M2 emits none of them, and the contract gate would refuse it if it tried |
| **(state × trigger) grid** | 16 × 25 = **400** pairs; **23 legal**, **377 illegal**, swept exhaustively over a population proven by reaching every one of the sixteen states |
| **Tables added** | **1** — `pipeline_instances`, tenant-owned, tenant-first. Canonical total 20 → **21** |
| **Named merge-gating anchors** | `AC-MACH-208` (the checkpoint, atomic), `AC-MACH-209` (the claim CAS, single-use), `AC-MACH-210u` (`CLAIMED` + crash ⇒ `NEEDS_VERIFICATION`, never `FAILED`), `AC-MACH-215x` (no timer moves `NEEDS_VERIFICATION`) |

### The structural invariants, at the database

| Trigger / constraint | What it makes unspellable |
|---|---|
| `ix_pipeline_instances_live_reservation` | two live attempts at one logical effect |
| `trg_..._post_checkpoint_carries_its_witness_{insert,update}` + 2 foreign keys | `GRANTED` (or anything downstream) without a real witness AND a real grant — §41(a) |
| `trg_..._witness_binding_is_write_once` | a claimed effect borrowing another decision's authority |
| `trg_..._terminal_is_final` | retry-in-place on an attempt that may already have moved money (§15) |
| `trg_..._version_advances_by_one` | a lost update on a STRICT-ORDER aggregate (GR-3) |
| `trg_..._identity_is_immutable` | repointing the commit key, i.e. retargeting an authorization |
| `trg_..._owner_follows_the_work_item_{insert,update}` | an attempt accountable to somebody other than the human who owes the work (§5) |
| `trg_..._failed_carries_its_proof` | `FAILED` with no affirmative evidence (GR-5) |
| `trg_..._no_delete` | an attempt that may have touched the world disappearing |

---

## 4. How M2 uses M1 and P5 — reuse, not duplication

| Reused | How |
|---|---|
| **M1's recorded roster** | The attempt's owner is READ from the Work Item (§5), never taken as a string. `human_authority` is M1's reader, imported. A closed or cancelled Work Item cannot acquire a new attempt |
| **M1's `resolve_decision_ref`** | PL-15's GR-14 closure resolves through M1's K-1 implementation. Two implementations of "does this decision_ref resolve" is two places for one of them to start accepting `"done"` |
| **P5's transactional outbox** | Every emitted event, in the transition's own commit (GR-2) |
| **P5's dedup inbox** | GR-4 idempotency, M-26 parking with a named accountable human, and the ONE commit that carries both handler writes and the inbox row (M-24) |
| **P5's canonical contracts** | The contract gate refuses an envelope naming a producer the registry does not attribute — which is what makes §14's CONSUMES classification mechanical rather than a comment |
| **P3's seven-step checkpoint** | PL-8 calls `run_checkpoint_locked`; the witness, the grant, the state row and `CheckpointPassed` share one transaction |
| **P3's claim CAS** | PL-9 calls `claim_grant_cas_locked`; the CAS and the state row share one transaction |
| **P3's brake store, gate ladder, fingerprint** | Read, never re-implemented. M2 constructs no `GateEntry` and no `GateRegistry` — asserted by AST |
| **M-26 parking** | Used as-is, with the explicit `requires_existing` prerequisite M1's rejected candidate proved is necessary |

### The one change to certified code, and why it is an extraction rather than a new kernel

`run_checkpoint` and `claim_grant_cas` each owned their transaction, so a caller with its own row to
write in that commit could not use them — and the alternative, a machine that re-implements the seven
checks or the CAS, is the dual effect-authority system CLAUDE.md rule 17 forbids. Both are now thin
transaction wrappers over **the same body**, exposed as `run_checkpoint_locked` /
`claim_grant_cas_locked`. **The CAS's WHERE clause is untouched and keeps all six predicates**; every
refusal cause, every Sev-0 and every observation is the same, in the same order. What moved is who
owns the transaction and therefore who writes the records after it.

*Evidence:* P3's own battery (`test_phase3_claim_cas.py`, 22 nodes incl. the structural predicate-set
guard) and P5's (604 nodes) are green, and mutants **P7a** and **P6c** prove those guards still fail
when the CAS loses its brake revalidation or the ordering rule stops being enforced.

---

## 5. Material defects found during implementation

Every one of these was found by a mechanical check going red, not by reading.

| # | Defect | How it surfaced | Disposition |
|---|---|---|---|
| **1** | **`IllegalTransitionAttempted` was UNINSERTABLE on a strict-order aggregate.** GR-1/[C-4] require the refusal to be recorded; it rides at the attempt's *unchanged* version, which on `pipeline_instance` (F2, strict) is already owned by the transition that reached it. The insert aborted: the refusal worked and the **evidence of it could not be written**, on the one surface an operator is paged from | 11 of the 16 sweep states failed with `StrictOrderViolation` | **FIXED, and the fix is a correction toward the specification, not away from it.** `events/registry.md` §8 classifies ordering **by family** and names F14 Security **order-tolerant**. P5's trigger keyed on `aggregate_type` — a faithful proxy only while every event on a strict aggregate came from a strict family. The trigger now also requires the event to be in a strict family, with the name set **derived from the canonical contract data**, never restated. Mutant **P6b** restores the old text and the guard goes red; mutant **P6c** empties the strict set and P5's own ordering test goes red |
| **2** | **PL-1b's absorption was uninsertable for the same reason.** `DuplicateProposalAbsorbed` is an **F2** contract, so it is strictly ordered and must OWN its version — but the first implementation attached evidence without advancing the holder's version, reading §14's "*(reservation clash)*" as "no write at all" | `StrictOrderViolation` on the duplicate-proposal cases | **FIXED.** §14's Writes cell says *"attach evidence"*, and the transport proves that means a durable write: the absorption advances the version and records `absorbed_count` / `last_absorbed_ref`. The **state** does not change, which is what "no transition" actually meant. Mutant **P1b** restores it |
| **3** | **A stale trigger reads as a present one.** `create_phase5_schema` is create-only and skips a trigger that already exists *by name* — correct for a trigger whose text never changes, and the strict-ordering trigger's text just did | Found while fixing #1 | **FIXED.** P5's readiness oracle now compares the live trigger text to the canonical text, whitespace-normalised, and a divergence is UNREADY. Fail-closed: a refused database is fixable; a stale trigger that reads as present is invisible |
| **4** | **The claim-CAS structural guard had stopped covering anything.** `test_phase3_claim_cas` anchored on `inspect.getsource(claim_grant_cas)`; when the body moved it reported "could not be located" rather than a lost predicate | Went red during the extraction | **FIXED, and STRENGTHENED.** It now DISCOVERS the function containing the `GRANTED → CLAIMED` write, requires **exactly one**, and fails if none exists. A guard anchored on one symbol is a guard a refactor can aim at |
| **5** | **Eight mutants were first reported MISS, and every report was correct about the PROBE.** The co-commit mutants (P7/P8) were aimed at the brake case — which refuses on *both* sides of the boundary, so it cannot see the difference; the owner and second-ledger mutants had no INSERT-side or negative-case guard to fail | The mutation battery | **FOUR NEW GUARDS ADDED, NO GUARD WEAKENED.** Two fault-injection cases hand the machine a *stale row snapshot* (exactly what a concurrent writer produces) and assert the witness/grant/CAS roll back with the failed row write; plus an INSERT-side owner case and a built-non-compliant-table case for the second-ledger rule. 40/40 |

---

## 6. Product Driver result

**ACCEPT — 70 behaviours as specified, 0 wrong**, and **proven able to fail**: three mutants (FAILED
without a proof; the reservation losing its UNIQUE; a model driving the machine) each drove the
driver to a non-zero exit, and the tree was restored byte-for-byte afterwards.

The driver **operated the machine** through a brokerage narrative rather than asserting about it —
16 scenes, hostile attempts inline: load 4471 delivered and billable; the billing sweep proposing it
twice and again at a different price; a model trying to propose the attempt; the rate moving after
Dana approved; ops engaging the brake between authorization and execution; the released brake **not**
resurrecting the dead authorization; the voided attempt **not** freeing the effect until the grant is
revoked (the M3 seam, named rather than papered over); a second load whose write times out; thirty
days passing with the unknown outcome still open and still owned; Dana establishing reality with
evidence; three distinct hostile transitions against a closed attempt; a rival brokerage's event; an
event for an attempt that does not exist; and an event that names nobody.

Two of those scenes were **rewritten because the product was right and the probe was wrong** — the
brake-release scene and the revoke-before-retry scene. That is recorded here rather than tidied away.

> ### **The Product Driver's ACCEPT is an independent judgement of observed PRODUCT behaviour. It is
> NOT the targeted independent engineering review this candidate owes.**

*Scenario and probe:* `../neyma-product-driver/scenarios/p6_pipeline_instance.yaml`,
`../neyma-product-driver/scenarios/p6_pipeline_instance_probe.py`.

---

## 7. False-green resistance and mutation

| | |
|---|---|
| **M2 battery** | **40 / 40 mutants caught**, in-memory save/restore, `__pycache__` purged around every mutation, byte-for-byte restoration verified, guard required GREEN before and after each case |
| **What it attacks** | the reservation's UNIQUE and its predicate; PL-1b's evidence write and its identity; §20's retry rule; the witness requirement; the write-once binding; terminality; the version counter; identity immutability; `FAILED`'s proof at guard AND database; PL-15's outcome source; the timer prohibition; the illegal-attempt identity; the security half of [C-4]; the F14 ordering exemption in **both** directions; the two co-commits; the CAS's brake predicate; the confused-deputy check; the request's provenance; ER-13's pins; ownership at insert and update; the model prohibition; the H-transition check; GR-8; F-20; the fences; the caps; the fingerprint match; the projection source; verify+record; the second-ledger rule; the derived gate vocabulary; and one structural case that deletes a §14 row to prove `AC-MACH-000` is a set comparison |
| **Population-derived, not sampled** | the (state × trigger) sweep enumerates all 400 pairs and asserts 23 legal / 377 illegal after **proving all sixteen states reachable**; `pipeline_must_exist` is derived from the table; the spec denominator comes from the acceptance document |
| **Positive controls** | the AC-MACH-000 same-count substitution; the gate-mint scanner must FIND the kernel's own construction before its silence about other modules means anything; the second-ledger case builds a non-compliant table; the occurrence-key annotation case proves a payload read still fails; the F2 gap case fails if no gap is found |
| **Composed-store contention (SEQUENTIAL — corrected at the `P6-CP-2` landing)** | two writers contending for one transition on the SAME store (exactly one wins, one event); five proposals for one effect, issued **sequentially on one connection** (one reservation, four absorbed); and two fault-injection cases where a concurrent row write makes the machine's snapshot stale mid-checkpoint and mid-claim. ### **THESE CASES ARE SEQUENTIAL, NOT THREADED, AND THIS CELL PREVIOUSLY CALLED THEM "racing" — WHICH THEY ARE NOT.** The superseded wording read *"two writers **racing** one transition on the SAME store ...; five proposals **racing** one effect ..."*, kept here so the claim survives its own correction (CLAUDE.md §5 rule 20). There is no `threading` anywhere in this battery, `ReservationHeld` appears in it only as an import, and `test_two_attempts_racing_one_effect_produce_exactly_one_live_reservation` — whose NAME is left unchanged because it is a `TEST-NODE-MANIFEST.json` node identity — is sequential on one connection. Genuine 8-thread / 8-connection concurrency was exercised **by the independent reviewer and again by the adjudicator, not by this battery**: the safety invariant held (one attempt, one effect, no double bill — the Layer-1 UNIQUE index is the enforcer under real contention), but PL-1b **absorption** did not, so raced duplicates appear in no operator count. Recorded as **`P6-D18`**, nonblocking, and owed before M9's billing sweep — the first concurrent proposer |
| **`state_digest`** | every no-op case asserts the digest is byte-identical across the second delivery, so "nothing happened" is a measurement |

---

## 8. Canonical suite, clean clone, and what this session could NOT reproduce

| | |
|---|---|
| **M2 battery** | **139 / 139 passed** |
| **Canonical suite, ON THE COMMITTED TREE** | **2990 passed · 20 failed · 1 skipped**, and `2990 + 20 + 1 = 3011` reconciles exactly with the regenerated node manifest |
| **The 20 failures** | ### **ALL environmental, and all outside this candidate's blast radius.** `socket.bind` is refused by this session's sandbox (`PermissionError [Errno 1]`, reproduced directly), so 19 P4-era HTTP callback tests in `test_action_callback.py` and `test_p4_deployed_governed_route.py::test_run_callback_server_accepts_and_holds_the_deployed_seams` cannot start a listener. ### **These are the identical 20 nodes, with the identical cause, that the P6-CP-1 independent review disclosed.** None imports `pipeline_instance` |
| **The 1 skip** | the one canonical skip — *"no red-by-design cases remain: AC-SAFE-012/013 went green at Phase 1"* |
| **### Why the pre-commit run is NOT the number recorded here** | ### **A GREEN SUITE THAT PREDATES THE COMMIT IS NOT EVIDENCE ABOUT THE COMMIT (§9), AND THIS BUILD PROVED IT AGAIN.** The pre-commit run read `2988 · 20 · 3`. Committing changed it, twice and for two different reasons: the two extra skips were `test_status_reality` nodes that refuse to measure a **dirty** tree, and `test_phase2_guard_registry::test_every_guard_file_is_classified` **went red only once the new guard file was TRACKED**, because the guard registry discovers its population from `git ls-files`. That is the same untracked-file false green P5's independent review rejected a candidate for and that M1's own record names. It was caught by re-running the suite AFTER committing, and the fix was folded into this one content commit |
| **Clean-clone gate** | ### **NOT REPRODUCED.** It fails at step *install declared deps only* with `SSLCertVerificationError` reaching `pypi.org` — the sandbox's TLS, not anything in this tree |
| **Node manifest** | regenerated: **2870 → 3011 nodes**; the delta is additive-only (nothing removed) |
| **Finalizer** | ### **NOT RUN, AND NO RECEIPT FORGED.** It executes the suite and the clean-clone gate itself and would refuse both above — correctly. It is not this session's to run in any case (§10) |

---

## 9. Nonblocking debt

Recorded, not actioned (CLAUDE.md §13.3). None can produce a wrong customer outcome, violate an
invariant, or make a later phase unsafe **today**; the three marked ⚑ are canonical seams a reviewer
should attack first.

| ID | Finding | Why nonblocking |
|---|---|---|
| ⚑ **P6-D9** | §14's PL-8f Event cell reads `CheckpointFailed{step,reason}` **+ `PipelineVoided`**, but `events/registry.md` §3 attributes `PipelineVoided` to **PL-7v/PL-9v only**, and the contract gate enforces attribution. PL-8f emits `CheckpointFailed` alone | Fails in the safe direction: one fewer event, no fabricated producer attribution. The state still becomes VOIDED and the refusing step is recorded. Resolving it means amending a protected specification, which is not this unit's authority |
| ⚑ **P6-D11** | The F2 stream for one attempt has **version gaps**, because 8 of the 25 rows are `CONSUMES` — they advance the version and emit nothing on `pipeline_instance`. F2 is STRICT-ORDER, so a future consumer using the dedup inbox would park at the first gap | **Measured by a dedicated test rather than asserted.** Nothing consumes M2's F2 stream today: M2 ships dark and M3/M4 are unbuilt. It must be decided before any consumer of F2 exists |
| ⚑ **P6-D13** | `VerificationDeferred` is the one contract the registry attributes to a PL-* transition (PL-11d) while declaring `aggregate_type: effect_grant`. Its ordering key needs the **grant's** version, which is M3's. PL-11d performs its durable write and does not emit | A guessed version misorders a STRICT stream permanently and silently — strictly worse than an absent event that is written down and named in `DEFERRED_EMISSIONS` |
| **P6-D12** | PL-15's `VERIFIED` branch reaches a state whose only declared outgoing transition (PL-12) is a co-commit of PL-11, so an attempt whose reality was established as verified does not continue to RECORDED/PROJECTED/CLOSED in §14 | No transition was invented to close it. The grant reaches its own terminal `VERIFIED` on M3, and the pipeline is not lost — it is visible, owned and queryable |
| **P6-D14** | M2's own half of each co-commit is performed; the partner halves — M3's grant-state writes and event emissions, M4's `REQUESTED`/`CONSUMED` — land with those machines | Structural: the contract gate refuses an M2-produced envelope for an EF-*/AP-* contract, which is the correct refusal |
| **P6-D15** | A PL-9v void does not free the logical effect: the grant stays `GRANTED` until M3's EF-2r/EF-2x withdraws it, so a retry is refused at the mint with `COMMIT_KEY_HELD` | Fail-closed, and demonstrated end-to-end by the Product Driver. P3's `revoke_unclaimed` is that act's implementation today; M2 does not call it because M2 does not own the grant's state (SD-2) |
| **P6-D16** | The signed grant handle PL-8 returns is deliberately **not durable**, so a restart between PL-8 and PL-9 loses it | The fail-closed direction, and P3's design: the grant expires unclaimed and nothing happened. §35's "no async work between PL-8 and PL-9" is what makes it cheap |

Carried forward unchanged and **not discharged by this unit**: `P6-D1`–`P6-D8`, `IR-R5`–`IR-R12`,
`ADJ-P5-01`–`ADJ-P5-03`, `RR-01`–`RR-06`, `AD-01`, `AD-02`, `PD-02`, the G2 residuals
`G2-D4/D6/D8/D9/D10/D15/D16`, and the hardcoded knowledge-base `tenant="default"`.

> ### **`P6-D16` IS NOT THE LAST ASSIGNED ID — ADDED AT THE `P6-CP-2` LANDING.** The independent
> review and the targeted re-adjudication of candidate `1aaf943` produced nine further nonblocking
> residuals, recorded as **`P6-D17`–`P6-D23`** in this checkpoint's `landed_checkpoints` entry in
> [`IMPLEMENTATION-REGISTRY.yaml`](IMPLEMENTATION-REGISTRY.yaml). They are recorded, **not
> actioned** (CLAUDE.md §13.3). ### **The ID space above was itself a finding:** `P6-D14` had been
> given to three different things — this table's co-commit partner halves (the meaning kept here,
> unchanged), the prior adjudication's unpreserved `3d4046a` rejection review, and the review's
> PL-1b recommendation. The landing resolved the collision by assigning from `P6-D17` upward and
> recorded the collision itself as `P6-D22`, so it survives its own repair. **`P6-D10` stays unused
> rather than being recycled.** The PL-1b concurrency debt is **`P6-D18`**, and it is owed before
> M9's billing sweep.

---

## 10. What this candidate owes, and what it may not do

### **A FRESH TARGETED INDEPENDENT REVIEW BY A SESSION THAT NEITHER IMPLEMENTED NOR REMEDIATED IT**,
then a **SEPARATE targeted adjudication** by a third, then **exactly ONE finalizer** — the route
`P6-CP-1` (`ca8c070 → 64f6f6c → da84806 → cc986dd`), the P4 acceptance closure and the R-07 closure
each executed.

Until that review exists on disk, `checkpoint_state` stays where `P6-CP-1` left it,
`landed_checkpoints` names one entry, and this candidate is recorded in the registry as a
**candidate**.

- ⛔ **No P6 acceptance criterion is scored by this candidate, and none may be.** `criteria_scored`
  is `[]`. A checkpoint is a landed increment, never a phase acceptance.
- ⛔ **P6 is NOT COMPLETE.** M3–M13 and 95 of the 134 transitions are unbuilt. Gate **G1** and
  **AC-SAFE-028** are unreached.
- ⛔ Nothing here enables an external effect, registers a production policy gate, or grants autonomy.

### Where a reviewer should start

1. The three ⚑ seams in §9 — each is a place §14 and the event registry do not agree, and each was
   resolved by refusing to improvise. Attack the refusals.
2. The **checkpoint extraction** in `checkpoint.py`. It touches P3-certified code. The claim is that
   it is behaviour-preserving; the evidence is P3's and P5's own batteries plus mutants P7a/P6b/P6c.
3. The **six amended guards** (registry `guards_amended_and_why`). Each has a positive control. Check
   that each control genuinely fires and that no amendment traded a real property for a green test.
4. The **fault-injection cases** — they call two private methods (`_run_checkpoint`, `_run_claim`)
   with a stale snapshot. That is deliberate: it is the only way to make the row write fail *after*
   the kernel succeeded, which is the exact interleaving the co-commit exists to survive.

---

# ADDENDUM — TARGETED REMEDIATION AFTER THE INDEPENDENT REJECT OF `3d4046a`

> ### **WRITTEN BY THE REMEDIATING SESSION, WHICH DID NOT PERFORM THE REVIEW THAT REJECTED THIS
> CANDIDATE AND MAY NOT REVIEW, ADJUDICATE OR FINALIZE ITS OWN REPLACEMENT.**
> The replacement candidate owes exactly what the original owed: a **fresh targeted INDEPENDENT
> review**, then a **separate targeted adjudication**, then **one finalizer**, in that order, by
> three sessions none of which is this one.

## A1. The verdict, and what it did not touch

A fresh targeted independent review returned **REJECT — M2 NOT READY FOR ADJUDICATION** on candidate
`3d4046a` (tree `34cc2285`), on **two blocking defect classes**. It **held** the rest of the surface:
reservation and idempotency, retries, `NEEDS_VERIFICATION`, brake semantics, the model prohibition,
the checkpoint extraction, the database invariants, tenant behaviour, `AC-MACH-000`'s exact
population, the focused battery, the Product Driver and the existing mutation coverage. None of
those was redesigned here.

It also independently **confirmed P6-D9, P6-D11 and P6-D13 as real** canonical inconsistencies and
**nonblocking for M2 today**. They are preserved at their current hard boundaries and **nothing here
resolves one by invention**. **P6-D11 must be resolved before an actual F2 consumer is introduced in
M3** — that boundary is unchanged and did not become reachable.

## A2. F-01 — `CLAIMED` was reachable without the CAS

### Reproduced first, on the rejected tree

```
BEFORE  pipeline GRANTED · claimed_at None · grant ledger GRANTED · 1 witness
        consume a contract-valid canonical GrantClaimed with trigger CLAIM_ATTEMPTED
AFTER   pipeline CLAIMED · claimed_at None · grant ledger STILL GRANTED
        transition PL-9 · refusal_kind None
```

No kernel. No grant handle. No CAS. **The attempt said the authority to bill the customer had been
claimed; the ledger said nobody had claimed it** — one authorization that could be spent twice.

### Root cause

`apply()` special-cased the consequential triggers and routed them to P3's kernel. `consume()`
routed canonical events **straight into `_apply_locked`**, which selects a row and asks
`_guard_problem` — and `_guard_problem` had **no branch at all** for PL-8, PL-8f or PL-9. A row whose
real precondition is *the kernel's own atomic write* was satisfied by the absence of a guard. This
violates §15 (*"`CLAIMED` without a successful CAS → impossible"*), the M2↔M3 co-transition rule,
§17's serialization point, and the authority/brake model.

The **same** root cause, at lower severity: a consumed `CHECKPOINT_RUN` selected **PL-8f** by §16
precedence — the checkpoint's *failure* branch, whose `{step, reason}` are the kernel's refusal
output — and then raised `PayloadContractViolation` **inside the inbox transaction**, rolling the
receipt back. Reproduced: `inbox receipts: []`, so the event was redeliverable forever.

### The fix — structural, and derived rather than listed

| | |
|---|---|
| **Declaration** | §7's *"consequential transitions = **PL-8 (checkpoint) and PL-9 (claim) only**"* becomes DATA: `TransitionRow.consequential` names the kernel path that owns the row |
| **Population** | `KERNEL_OWNED_ROW_IDS` is the seeds **plus every row sharing a (from-state, trigger) pair with one**. That closure is what puts **PL-8f** in — because a row selectable by the same pair is a row the ordinary path can take *instead of* the kernel's. Add a row on `(CHECKPOINT, CheckpointRun)` tomorrow and it is covered without editing anything |
| **Refusal** | `_guard_problem` refuses that whole population **before any row branch**. `_apply_locked` is the ordinary path — the only path `consume()` has — so the refusal is a property of the function, not of the two call sites somebody remembered |
| **Classification** | `_apply_locked` classifies an all-kernel-owned refusal as **§15 / GR-1 illegality**, not an ordinary guard failure, so `IllegalTransitionAttempted` reaches the audit backbone **and** `security_events` inside the inbox's own commit. Refusing without recording would have been the quiet half of the same defect |
| **Dispatch** | `apply()`'s kernel routing is now derived from the **same** declaration, so dispatch and refusal cannot disagree — and a consequential row whose executor is missing **fails closed** instead of falling through to the ordinary path |

### What was deliberately NOT done

The kernel is **not** duplicated inside `consume()`; **no** grant state is fabricated; **no**
canonical invariant is weakened; and **P3's semantics are untouched** — not one CAS predicate moved,
no checkpoint step changed, no witness rule relaxed.

### Convergence

`GuardNotSatisfied` would have been the easy classification and the wrong one. The refusal is an
**outcome**, not a raise: the inbox receipt is written (`APPLIED`), redelivery is `DUPLICATE_NOOP`,
durable state is byte-identical across it, and the security record survives. Both halves of F-01
converge, and the poison loop is gone.

## A3. F-02 — the "ships dark" guard was false-green twice over

`test_m2_cannot_reach_an_effect_capable_adapter` was the headline safety claim of this unit and
could not have caught a leak.

1. **The population was hand-enumerated.** Nine names, three of which (`email_adapter`,
   `slack_adapter`, `tms_adapter`) are not modules of this repository at all, while
   `discovered_write`, `browser_agent` and `browser_tms_adapter` — all genuinely effect-capable —
   were absent. `browser_use_adapter` was listed although P4 deliberately **reclassified it out**.
2. **The walker read two of Python's six import spellings.** It followed `from .x import y` and
   `import freight_recon.x`. It was blind to `from freight_recon.x import y` — **the dominant
   spelling in `src/freight_recon/`** — and to `from . import x`, which is in **live use** at
   `governed_write_route.py:359` and `action_callback.py:629`, and to `importlib.import_module`.
   It also mis-resolved every relative import inside `migrations/`, having no package context.

### The fix — centralised, not a third walker

The transitive closure moved into **`eval/phase0/import_probe.py`**, the repository's own import
authority and already mutation-proven for the P4 gate: `package_import_closure` and
`effect_capable_reachable_from`. Every legal spelling is resolved with correct package context —
`import freight_recon.a.b`, `from freight_recon.a.b import n`, `from freight_recon import n`,
`from .a import n`, `from . import n`, `from ..a import n`, `importlib.import_module` (absolute and
relative literals) and `__import__`.

The M2 guard now derives **all three** of its inputs:

| input | authority |
|---|---|
| roots | `IMPLEMENTATION-SURFACE.yaml`'s recorded Pipeline Instance surface |
| effect-capable population | `import_probe.EFFECT_CAPABLE_ADAPTERS` — the same set the P4 gate partitions on |
| reachability | `package_import_closure`, spelling-complete |

plus a `require_population(10)` denominator and a **live positive control**: `effect_boundary` — P4's
containment boundary — must reach adapters, or the walker is broken and M2's assertion is vacuous.

**The real closure is 24 modules and reaches ZERO effect-capable adapters. M2 still ships dark.**

## A4. What could have failed, and did

| check | result |
|---|---|
| F-01 reproduction on the rejected tree | **REPRODUCED** (CLAIMED with no CAS; and `inbox receipts: []` for the checkpoint half) |
| F-01 reproduction on the replacement | **REFUSED** — GRANTED, `claimed_at` NULL, ledger GRANTED, `refusal_kind ILLEGAL`, receipt written |
| M2 focused battery | **158 / 158** (139 before; **+19 nodes**, manifest 3011 → 3030, **zero removed**) |
| M1 · P5 transport · P3 claim CAS · P3 matrix · P4 import gate · P0 adapter imports · browser-use read-only · P0 baseline manifest | **528 / 528** |
| M2 mutation battery | **55 / 55 caught**, byte-for-byte restoration (40 before; **+15 aimed at F-01/F-02**) |
| Product Driver — canonical scenario probe | **70 behaviours as specified, 0 wrong** (unchanged by the remediation) |
| Product Driver — new bypass scenes | **17 as specified, 0 wrong**, and **proven able to fail** under 3 mutants |

### The fifteen new mutants, and what each restores

`K1`/`K1a` restore **the rejected candidate's exact defect** — the kernel refusal removed — proved
against both the claim half and the checkpoint half. `K2` drops the (state, trigger) closure so PL-8f
alone becomes reachable again. `K3` degrades the §15 classification, so the bypass is still refused
and **no security record survives** — the quiet half. `K4` lets a consequential row with no executor
fall through. `K5` un-declares PL-9 consequential.

`D1`–`D4` inject a **real** import of a **real** effect-capable adapter in four spellings. `D5`
injects it **transitively**, two hops out in `tenant.py`, with M2 itself importing nothing new. `D6`
is the hand-list defect itself: an adapter appears in the **canonical** population and **no M2 test
is touched** — the old guard could not have noticed. `D7` removes the recorded surface the roots come
from. `D8` stops the walk following relative imports. `D9` cripples the frontier so the denominator
guard has to catch a walk that inspected almost nothing.

## A5. Environmental failures — reproduced, disclosed, not touched

The same **20** failures the independent review reproduced: 19 legacy callback-server tests and one
deployed-route test, all `socket.bind` `PermissionError` in this sandbox, **none of which imports
`pipeline_instance`**. The clean-clone gate fails at dependency installation on TLS interception
reaching PyPI, not on anything in the tree.

### **Not one of them was weakened, skipped, rewritten, or reported as passing.** The finalizer was
**not** run and no receipt was forged. **The final landing still owes a reproduction of the canonical
suite and the clean-clone gate from a capable host shell.**

## A6. Scope — what this remediation did not do

It did not begin M3, adjudicate, review itself, finalize or land `P6-CP-2`, reopen M1/P5/P3, change
product semantics, resolve `P6-D9`/`P6-D11`/`P6-D13`, enable a production effect, populate the
`GateRegistry`, push, or touch `main`. **`criteria_scored` is still `[]` and P6 is still NOT
COMPLETE.**

### One disclosed limitation

The F-01/F-02 hostile scenes belong in
`../neyma-product-driver/scenarios/p6_pipeline_instance_probe.py`. **That repository is outside this
session's sandbox write boundary**, so they were written as an extension that **imports** that probe
as a library — reusing its world, clock, scoring and canonical-envelope helpers rather than a second
set — and run from outside the product, for the reason the driver's own header gives: a
demonstration script committed into Neyma would be the first production caller of a capability that
ships dark. Merging them into the driver repository is a one-file act for a session with write
access there.

## A7. Where the next reviewer should start

1. **Is the kernel-owned population genuinely derived?** Add a row to `TRANSITIONS` on
   `(GRANTED, ClaimAttempted)` and confirm it is refused from `consume()` with no test edited.
2. **Is `_guard_problem`'s refusal reachable from every ordinary path?** Find a caller of
   `_apply_locked` that is not `apply()` or `consume()`, or prove there is none.
3. **Can the closure walker still be spelled around?** Try a spelling not in `D1`–`D4` — an aliased
   `importlib` bound to a local name, a `__import__` behind a variable — and decide whether the
   residual is honest (it is static analysis; a fully dynamic import is out of its reach and the
   dark-surface claim rests additionally on `test_nothing_in_production_calls_m2`).
4. **Does the §15 classification over-reach?** It reclassifies a refusal that would otherwise be
   `GuardNotSatisfied`. Check that no *administrative* row can reach it.

## A8. Commit topology — why this replaces `3d4046a` rather than sitting on top of it

`3d4046a` was an **unfinalized content commit**. The two-commit convention permits exactly one:
`test_status_reality.repo_state()` calls two of them *"not the producing state, it is two unfinalized
content commits, which the convention forbids"*, and it went red the moment the remediation was first
committed on top. The finalizer that would have closed `3d4046a` is not a builder's to run
(CLAUDE.md §11) and would refuse in this sandbox regardless — and forging its receipt is out of the
question.

So the remediation was collapsed onto `cc986dd` as a **single replacement content commit**. The
repository is back in the legal **PRODUCING** state (`repo_state() == "PRODUCING"`, working tree
clean), and nothing was lost:

| ref | what it holds |
|---|---|
| `refs/preserve/p6-cp2-rejected-candidate-3d4046a` | the REJECTED candidate, byte-exact — the review's subject |
| `refs/preserve/p6-cp2-remediation-prestate-8bb4cb0` | the remediation as first committed, before the collapse |

**The replacement's tree is byte-identical to the pre-collapse tree** (`e6bd0e0dd…` both times).
Only the topology changed. A reviewer comparing `3d4046a` against this commit sees exactly the
remediation diff and nothing else.

`git reset --soft` was used, which moves the branch pointer and touches neither the index nor the
working tree. **No `git checkout`, `restore`, `stash` or `clean` was run at any point in this
session** (CLAUDE.md §9) — the one status artifact a tool overwrote, the finalizer-owned
`GATE-RESULT.json`, was restored by writing its committed bytes back explicitly rather than by a
tree-wide checkout.

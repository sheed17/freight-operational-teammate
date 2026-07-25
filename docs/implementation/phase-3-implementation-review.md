# Phase 3 — Implementation Review (the implementer's record)

> ### **NOT CURRENT AUTHORITY — this is evidence, not status.**
> The status authority is [`CURRENT.md`](CURRENT.md). If this document and `CURRENT.md` ever
> disagree, `CURRENT.md` is right and this file is stale. Nothing here may be read as approving
> work, moving a gate, or authorising a phase transition.
>
> ### **THIS DOCUMENT DOES NOT ADJUDICATE P3 COMPLETE, AND MAY NOT BE READ AS DOING SO.**
> It is the record written by the session that implemented the kernel. Under the P3 acceptance
> contract, `independent_review` (weight 5) and `final_adjudication` (weight 4) must come from a
> session that did **not** implement P3. A completion verdict authored here would be
> self-adjudication — a defect with a passing status (CLAUDE.md §5 rule 20).
>
> **Status: P3 is IN PROGRESS — NOT COMPLETE. It remains the sole `READY` unit. `P4` is BLOCKED.**

---

## 1. What was built

| Module | Lines | Purpose |
|---|---|---|
| `src/freight_recon/checkpoint.py` | 1327 | the seven-step atomic checkpoint, `CheckpointPassed`, gate ladder, grant mint, claim CAS |
| `src/freight_recon/brake.py` | 418 | brake admission and the one-way ratchet |
| `src/freight_recon/fingerprint.py` | 204 | the `fp_v1` canonical fingerprint and field-level drift diff |
| `src/freight_recon/migrations/phase3_checkpoint.py` | 305 | the P3 DDL, triggers, `platform_brake` seed, readiness oracle |
| `scripts/migrate_phase3_checkpoint.py` | 94 | the standalone migration entry point |

Capability, stated without inflation: the two-key rule is enforced **inside the kernel**. The seven
checks run in canonical order inside ONE transaction with the witness insert and the grant mint;
`CheckpointPassed` has no public constructor; the witness table is append-only by database trigger,
tenant-first and 1:1 with its grant; `claim_grant_cas` performs the `GRANTED → CLAIMED` transition
revalidating state, expiry, brake token and policy version inside the UPDATE's own WHERE clause;
the brake store enforces the one-way ratchet; and `fp_v1` makes drift byte-decidable.

### ### **P3 SHIPS DARK — and that is not a caveat, it is the design.**
No production path routes through the kernel. The six production-reachable live-write paths (EP-1,
EP-3, EP-6, EP-7, EP-9, EP-10) and the 31 direct adapter-import edges are **physically untouched**,
exactly as P3's prohibited scope requires. ### **R-07 is OPEN — NOT CONTAINED.** Completing P3
would not change that; only completing **P4** does.

## 2. Test results

`eval/tests/test_phase3_{witness,claim_cas,brake,fingerprint,schema,checkpoint_matrix}.py` —
**181 passed, 0 failed**, including the AC-CKPT merge-gating matrix (7 steps × 15 conditions).

### ### Validation status — READ THIS BEFORE TRUSTING ANY NUMBER ABOVE
The **full-suite, final-tree validation required by the definition of done has NOT been run**, and
the finalizer has **not** been executed.

> ### **CORRECTED at the P3 remediation (independent-review finding F-B). THE ORIGINAL TEXT HERE
> WAS FALSE BY OMISSION** and is preserved-and-disarmed rather than deleted, because the way it
> was wrong is the lesson. It named the sandbox's `socket.bind()` restriction as **the** reason
> the finalizer had not run, and called that restriction "unrelated to P3" — which reads as *the
> suite is otherwise green and only the environment is in the way*. It was not. **The canonical
> suite FAILED on a real repository defect, and the finalizer would have refused for that reason
> alone.** Attributing a refusal entirely to the environment is how a genuine failure gets
> classified as noise. See [`p3-findings-remediation-review.md`](p3-findings-remediation-review.md).

**The actual blocker, measured on the reviewed tree `38f2714`:**

1. ### **The canonical suite failed on finding F-A.**
   `eval/tests/test_rebaseline_invariants.py::test_no_src_runtime_file_was_touched_by_the_rebaseline`
   FAILED, naming all six P3 `src/` files. It was a mis-anchored guard, not a P3 code defect — but
   it was a **real repository defect that fails anywhere**, in or out of a sandbox, and
   ### **`scripts/finalize_status.py` correctly REFUSED because of it.** A refusing finalizer was
   the control system working, not an obstacle to route around.
2. **Separately, the sandbox's `socket.bind()` denial is real but INTERMITTENT — and stating it
   precisely matters, because overstating it is the same error F-B is about.** Measured: direct
   `pytest` invocations fail all 19 `eval/tests/test_action_callback.py` cases with
   `PermissionError: [Errno 1] Operation not permitted`, reproduced at the syscall level for
   `127.0.0.1`, `localhost`, `::1` and `AF_UNIX`. But **both** finalizer-driven canonical runs on
   the committed remediated tree reported those 19 cases as PASSED. Same tree, same config, same
   interpreter. ### **So it must not be named as *the* blocker in either direction.**
3. **`scripts/finalize_status.py` executes the suite itself** (by design, since U-HANDOFF-1C), so
   it cannot produce a truthful record while the suite fails for any reason.

F-A is fixed by the remediation, and the finalizer's refusal on the remediated tree now has a
different and fully deterministic cause: **the status state is illegal** — `38f2714` and the
remediation commit are two unfinalized content commits, so `test_status_reality` fails ×3. That is
a deadlock, not a defect in the work: only the finalizer writes the status block, and it requires
a green suite, which requires a legal status state. The clean-clone gate is blocked earlier still —
pip cannot verify pypi.org's TLS certificate in this sandbox, so the gate never reaches the suite.
### **No finalizer or clean-clone success is claimed anywhere in this repository, and none was
obtained.**

Consequently the machine-maintained status block in [`CURRENT.md`](CURRENT.md) still records the
**pre-P3** commit, and that is the honest state: the suite figures there describe `d96e745`, not
this work. ### **No number in this document may be copied into the status block by hand.**

## 3. Guards replaced (CLAUDE.md §5 rule 20 — replaced, never deleted to go green)

P3 ended the conditions five guards were written to assert. Each was **replaced** with the invariant
that still protects the system, never relaxed:

| Guard | Was | Now |
|---|---|---|
| `test_the_canonical_table_partition_is_exact_and_disjoint` | 3 classes (7+1+3) | 5 classes (7+1+3+2+1=14), pairwise-disjoint, membership-exact |
| `test_tenant_offending_tables_exact_set_not_count` | P2 exemptions only | reads P3 exemptions from the migration module, so a new exempt table cannot appear unnoticed |
| `test_the_canonical_gate_population_is_provably_empty_today` | proved the gate population EMPTY | proves it non-empty **and confined to the checkpoint kernel** |
| `test_no_placeholder_policy_runtime_was_added_by_the_errata` | banned gate tokens anywhere | requires typed policy to cite its authority (ADR-010); also fixes a pre-existing substring-match defect |
| `test_the_p3_concepts_are_specification_only_while_p3_is_blocked` | READY ⇒ SPECIFICATION_ONLY | BLOCKED owner ⇒ not fully IMPLEMENTED, **and** an IMPLEMENTED claim must produce its symbols in `src/` |
| `test_9_phase_3_is_recorded_not_started` | hardcoded "P3 NOT STARTED" | derived: no document may declare **any** phase COMPLETE before the registry does |

## 3b. Mutation battery — **8/8 mutants caught**

Harness: [`scripts/mutate_phase3_guards.py`](../../scripts/mutate_phase3_guards.py), preserved and
re-runnable. Original bytes are held **in memory**; `__pycache__` is purged around every mutation;
restoration is asserted byte-for-byte and each guard is re-run green afterwards.
### **No `git checkout`/`restore`/`stash`/`clean` is used anywhere in it.**

| # | Mutation | Guard | Result |
|---|---|---|---|
| M1 | same-**count** member substitution in the table partition (`brakes` → `brakez`) | partition exactness | CAUGHT |
| M2 | drop the `platform_brake` exemption | tenant posture | CAUGHT |
| M3 | a gate decision escapes into a non-kernel module | gate confinement | CAUGHT |
| M4 | strip the ADR-010 citation from the kernel | policy authority | CAUGHT |
| M5 | an `IMPLEMENTED` concept cites a symbol that does not exist | surface vs tree | CAUGHT |
| M6 | a document declares P3 COMPLETE | premature-completion guard | CAUGHT |
| M7 | P3 loses its `NOT COMPLETE` marking | status record | CAUGHT |
| M8 | deny the preserved independent rebaseline report | BUILD-STATUS honesty | CAUGHT |

M1 is the load-bearing one: it substitutes a member **without changing the count**, which is the
defect class ("a number that had drifted away from the members it claimed to count") that every
count-based check in this repository has historically agreed with.

### ### Scope limit — state this plainly
This battery proves **the guards**, not the kernel. It does not mutate `checkpoint.py`'s seven-step
ordering, the witness trigger, or the claim CAS's WHERE-clause predicates.

> **UPDATE at the P3 findings remediation.** A **kernel** battery now exists: **K1–K11**, added to
> the same harness (never a second mutation route), covering the step-6/7 swap, every claim-CAS
> WHERE predicate including the two defense-in-depth ones, a constructable `CheckpointPassed`, the
> witness append-only trigger, both rescoped ledger consumers, and the rebaseline anchor.
> **19/19 caught** across both batteries. ### **This still is not adjudication** — the independent
> reviewer ran its own kernel mutations and RETURNED FINDINGS, and a battery written by a session
> inside the work it audits is evidence, never a verdict. See
> [`p3-findings-remediation-review.md`](p3-findings-remediation-review.md) §4.

## 4. ### Findings the independent reviewer must adjudicate

These are recorded because they are **not mine to decide** (CLAUDE.md §7).

**F-1 — `platform_brake` diverges from the literal spec text.** Entity spec
[`16-brake.md`](../specifications/entities/16-brake.md) point 7 resolves SD-12 as "the `GLOBAL`
brake is ONE platform-level row (`tenant_id = <platform sentinel>`), not N per-tenant rows." P3
implements the one-row decision correctly, but as a **separate tenant-exempt table with no tenant
column**, not as a sentinel value in a tenant column. Arguably stronger — a sentinel in a NOT-NULL
tenant column is the `tenant="default"` smell this repository exists to prevent — but it **is** a
deviation from the written representation and was not adjudicated anywhere. *Needs a verdict.*

**F-2 — P3 built typed policy that the P0 manifest defers to P8.**
[`phase-0-baseline-manifest.yaml`](phase-0-baseline-manifest.yaml) records `AC-CKPT-6-missing` as
`DEFERRED_BY_DEPENDENCY - REQUIRED AT PHASE 8`, `green_at_phase: P8`, `accountable_unit: U8.1`, on
the explicit ground that "typed policy and action classes do not exist until P8." P3's
`GateDecision` ladder and fail-closed `GateRegistry` are exactly those structures. Checkpoint step 5
is `policy_evaluation`, so the kernel plausibly could not avoid them — but either P3 reached beyond
its scope, or the manifest's P8 deferral needs re-adjudication. ### **This session deliberately did
NOT move that gate**; the manifest record stands untouched and the replacement probe explicitly
declines to claim `AC-CKPT-6-missing` green.

**F-3 — the working tree asserted a completion it could not support.** Before this session, the
control documents claimed "P3 ✅ COMPLETE" and cited *this file* as evidence while it **did not
exist**; the registry still said `READY` with all 14 criteria `PENDING`; and the status block
recorded the pre-P3 commit. A hand-edit had also **replaced** ARCHITECTURE.md's required "Phase 2
did NOT make consequential external effects safe" statement with a Phase-3 sentence, silently
dropping a mandated safety statement. All corrected here. Recorded because it is the exact
fabricated-artifact failure the U-HANDOFF-2B hostile review exists to catch, and it recurred anyway.

## 5. Tree identity at the time of writing

Recorded from `HEAD` `b3306148e2ad4efad76135e48b7b04572be9be15` (the pre-P3 status-metadata commit;
P3 itself is uncommitted at the time of writing).

| File | SHA-256 |
|---|---|
| `src/freight_recon/checkpoint.py` | `65dd5282c5092acc30bd3484d83bd1075a741529396c2e24a7376eb566cf2734` |
| `src/freight_recon/brake.py` | `ea7ef2c3c9832d4e2939185b763268ff2b00f1fd8d63734464a6dd87da6f6a41` |
| `src/freight_recon/fingerprint.py` | `4ebc01f3fa79a653d8921ddcfe751783e3c831bc250598ced35838df67a93b51` |
| `src/freight_recon/migrations/phase3_checkpoint.py` | `77f0caee45b872468ce56d2e1a70b4c228aecb20eca3e7fb83a485e3270892dd` |
| `scripts/migrate_phase3_checkpoint.py` | `95065a7d3154c729c571512fa6fe683bb5090a548a482b946cba2a0008f63a6a` |

### **These are NOT final-tree digests.** The contract requires digests over the finalized tree;
producing those requires the finalizer, which is blocked per §2. They are recorded so the
independent reviewer can detect whether the tree moved underneath this document.

## 6. What remains before P3 may be called COMPLETE

- [x] mutation proofs for every new and rescoped guard — **8/8 caught** (§3b), in-memory harness,
      byte-for-byte restoration verified
- [x] **kernel-level** mutation battery (drop a claim-CAS predicate, reorder a checkpoint step,
      make `CheckpointPassed` constructable) — **K1–K11 added at the remediation, all caught.**
      §3b proves the guards; K1–K11 prove the kernel. Neither adjudicates anything
- [ ] a GREEN full-suite validation run LAST on the final tree — F-A is fixed; what blocks it now
      is the ILLEGAL STATUS STATE (`test_status_reality` ×3: two unfinalized content commits), plus
      an intermittent sandbox socket-bind denial. ### **F-B: neither was ever the whole story, and
      the original one was a real defect, not environmental noise**
- [ ] `scripts/finalize_status.py` executed; the status block and `BUILD-STATUS.yaml` derived
- [ ] the clean-clone gate executed
- [x] F-1 and F-2 adjudicated — at the remediation, from the INDEPENDENT review's F-E and F-G
      (F-1 ACCEPTED: `16-brake.md` point 7 formally amended; F-2 ACCEPTED: P3 keeps the minimal
      structural gate contract, the P0 manifest's stale rationale corrected, AC-CKPT-6-missing
      stays deferred and ungreen)
- [x] an **INDEPENDENT** review by a session that did not implement P3 — ### **RECEIVED, AND P3
      DID NOT PASS IT**: 9 findings, 60/100, `NOT READY FOR FINAL ADJUDICATION`
      ([findings](p3-independent-review-findings.md)). All nine remediated
      ([dispositions](p3-findings-remediation-review.md)) — by a session that is neither the
      reviewer nor the adjudicator
- [ ] a **FRESH INDEPENDENT** review of the REMEDIATED tree — ### **required**; no session may
      certify its own fixes
- [ ] a **final adjudication** from that fresh independent evidence
- [ ] the registry's 14 acceptance criteria set from that evidence, and only then `status: COMPLETE`

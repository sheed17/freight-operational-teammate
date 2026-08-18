# TARGETED ADJUDICATION — P6-D11 · candidate `021a9a2`

**First, a correction to the brief.** The independent review report is **not** at `scratchpad/p6-d11-independent-review-report-021a9a2.md`. It is nowhere on disk, in the repo, or on any `refs/preserve/*` ref. It lived only in the reviewer session's ephemeral scratchpad, which has been cleared. I could not read it, so I did not summarize it — I re-derived every material claim myself. That absence is itself a finding (A-1 below).

---

## 1. Verdict: **ACCEPT**

The engineering is correct. No material correctness defect survives. Acceptance carries **three landing conditions on the route** (A-1, A-2, A-3) and **one new debt row** (P6-D27). None of them is a code change to `021a9a2`.

## 2. Candidate
`021a9a2816f5` / tree `f1df545d4fdb`, parented on the finalized baseline `c2def38`. Working tree clean. 15 files, +1315/−40; no schema migration; `event_replay.py` untouched.

## 3. Root-cause ruling: **CORRECTLY IDENTIFIED**
P5's `DedupInbox` implemented `aggregate_version > applied_version + 1 ⇒ PARK` — numeric **contiguity**. §8 required strict **order** and never said contiguity, and it cannot: GR-2 is discharged by a co-commit, so a transition whose canonical event belongs to another machine's aggregate advances this aggregate's version and emits nothing here. An intentional non-emission and a lost event are indistinguishable *from an absence*, so no producer-side care could fix it. Confirmed.

## 4. Architecture ruling: **PREDECESSOR-LINK IS THE CORRECT CANONICAL CONTRACT**
- **vs A (emit at every version)** — requires minting canonical events (founder authority), makes M2 emit facts about M4, and establishes the invariant *by convention*: the first future `CONSUMES` author who forgets silently reintroduces a permanent stall. Correctly rejected.
- **vs B (separate contiguous sequence)** — a second monotonic identity beside `aggregate_version`, which §4 identity, §8 ordering, the strict trigger, the replay fold and audit reconstruction all key on. Two numbers that must never disagree is the "two systems claiming one authority" shape. Correctly rejected on runtime risk, not effort.
- **vs C (reuse a co-committed sequence)** — I verified there is none: `event_outbox.sequence` is per-*tenant* insertion order and not in the envelope; `causation_id` is a cross-aggregate DAG and cannot express stream adjacency.
- **D is additionally sound on authority**: §6 states *"Additive (new optional field) = same version"*, so no version bump and no upcaster are owed. I confirmed an unlinked envelope omits the key entirely from `to_json()` — historical events are byte-identical and digests unchanged.

Derivation and persistence hold under every axis: **rollback** (rolled-back emission leaves history at 0), **concurrency** (derived after the OCC write, inside the transaction), **duplicate** (link is not in the dedup key; `DUPLICATE_NOOP`, handler ran once), **reorder** (parks, then drains in order), **restart** (durable cursor resumes), **replay** (untouched), **tenant** and **aggregate separation** (keyed on all three columns; tenant B reads 0 on the same aggregate id), **malformed** (self/forward/negative link → `MalformedEnvelope`), **forged** (`StreamLinkViolation` before the INSERT, so the state change rolls back with it), **cycles** (structurally impossible — links strictly decrease).

**Fail-safe preserved (the half that matters):** a genuinely lost predecessor still parks; a reordered event still parks and then drains in order. I reproduced both directly.

## 5. Silent-transition count: **NINE — correct**
Mechanically derived, not read: 8 `CONSUMES` rows (`PL-6, PL-9, PL-10, PL-10f, PL-10u, PL-11, PL-11c, PL-15`) + `PL-11d` (emits `VerificationDeferred` on the `effect_grant` aggregate) = **9**. My first naive predicate returned 10 by picking up `PL-15x`; that row is `illegal=True, to_state=None` — it persists nothing, advances no version, creates no gap. Correctly excluded. The record's own P6-D25 correction from "eight" to "nine" is right.

## 6. P6-D24 — **correctly classified as a nonblocking M3 obligation.** Concrete reasons:
1. **Untouched by this candidate.** The diff changes the park *predicate* and the observability payload only; `_park_locked`, the drain path and `ALREADY_PARKED` are unmodified. It is P6-CP-1's landed, adjudicated F-04 design.
2. **It fails safe, not silently wrong.** The event stays PARKED with arrival order, accountable owner and M-26 TTL — an owned problem surfaced to a human. It is never dropped, never applied out of order, never a wrong outcome. That is the line between an obligation and a defect.
3. **It is an explicit API contract**, not a latent trap: `drain_handler_for` is a named parameter on `consume`, and supplying it drains correctly (I reproduced the ordered drain).
4. M3 does not exist, so no consumer can be wrong today.

## 7. Strict-aggregate / family-filtering: **(A) a correct M3 authoring constraint**
I reproduced the reviewer's concern independently and it is **real**: `IllegalTransitionAttempted` (F14) rides at the attempt's *unchanged* version on the strict `pipeline_instance` aggregate, so it **becomes the declared predecessor** of the next F2 event. A consumer that family-filters it out parks on `CheckpointPassed` and returns `ALREADY_PARKED` on every redelivery.

But it is **(A), not (B)/(C)/(D)**, on three proven grounds:
1. **It pre-exists P6-D11.** Under the old contiguity rule the same filtering consumer also parks (`3 > 1+1`). This candidate does not introduce it.
2. **P6-D11 makes it satisfiable for the first time.** Contiguity required a strict consumer to observe an event at *every version* — impossible by canonical design. The link requires it to observe *every emitted event on the aggregate* — achievable, and the ordinary meaning of "strict per-aggregate ordering".
3. **The contract is already coherent in canon.** §8's existing bullet states order-tolerance is a property *across* aggregates, and that *within* one aggregate the universal ordering key `(tenant_id, aggregate_id, aggregate_version)` still holds. An F14 record ordered inside `pipeline_instance` is canon, not an accident — and P6-CP-2's family exemption on the trigger already keeps it from colliding with a transition's version ownership.

I did not accept "M3 will handle it": I proved the complete-stream consumer works end to end (applies `PipelineStarted` → `IllegalTransitionAttempted` → `CheckpointPassed`), so the constraint is implementable, not just assertable. **Condition A-3** below requires it be *written into §8* — M3's author is a fresh session with no history, and an unwritten constraint is, by this repository's own rule, not decided.

## 8. Stale P6-CP-2 prose: **must be corrected before the finalizer** (nonblocking for the code)
It is real and it **predates the candidate**: `CURRENT.md:22` ("THIS LANDING IS NOT FINALIZED… owes exactly one canonical finalizer run"), `CURRENT.md:967`, `CLAUDE.md:86`, `CLAUDE.md:278`. `c2def38` touched only 4 lines of `CURRENT.md` (the derived block) and left the narrative behind. The candidate carried it forward rather than creating it. Ordinarily this is §13.3 "record and move on" — but its content is an **active false instruction** that would send a fresh session to run a finalizer that is not owed, which you explicitly forbade. The candidate already edits both files, so correcting it is zero marginal risk.

## 9. `c2def38` / P6-CP-2 status: **FULLY FINALIZED. No further P6-CP-2 finalizer is owed.**
Established from receipts, not prose: `SUITE-RESULT.json` and `GATE-RESULT.json` both bind to commit `1abcb229` / tree `1f98154d` with `exit_status: 0` and `passed: true`, timestamped after the landing and before `c2def38`. `c2def38` touched exactly the five authorized status-metadata files. The four-step checkpoint topology is complete and matches P6-CP-1 exactly: `1aaf943 → b226717 → 1abcb229 → c2def38`. I ran no finalizer.

## 10. Surviving material defects: **none.** One new debt row:
**P6-D27 (new, nonblocking) — the chain-fork / emission-monotonicity gap.** The consumer's "apply anything at or below the high-water mark" branch is safe only while the link chain is a *path*. If a producer emitted a **lower** version after a higher one on one aggregate, two events would declare the same predecessor and the later-arriving lower one would apply *after* the higher — a silent strict-order violation. I constructed it at the outbox: it is not refused. Nonblocking because it is **unreachable through every canonical producer** — M2 allocates `item.version + 1` under OCC and its F14 record rides at the *current* (maximal) version, so emitted versions are non-decreasing; it ships dark with zero production importers; and it requires a future producer defect that is independently a strict-order violation. Honest caveat: the old rule failed *closed* here and the new one fails *open*, though only because the old rule parked everything, correct traffic included. Named mechanical close for whoever takes it: refuse at `emit` any strict-aggregate envelope whose `aggregate_version` is strictly below that aggregate's maximum emitted version (`<`, never `≤` — equality is the legitimate sibling and F14 case).

## 11–13. Evidence, mutation/regression, environment — all reproduced by me, not read

| | result |
|---|---|
| focused battery | **22/22** |
| P5+P6 regressions | **931 passed** (909 baseline + 22 new) |
| full canonical suite | **3031 passed / 20 failed / 1 skipped / 3052 collected** |
| manifest identity | **3052 declared == 3052 collected**, 0 missing, 0 unlisted |
| mutation battery | **15/15 caught**, exit 0 |
| Product Driver P6-D11 | **16 as specified, 0 wrong**, exit 0 |
| my own probes | part 1 — 16 checks; part 2 — 6 checks (F14 chain-link + fork) |

**Environment-only limitation, stated plainly:** all 20 failures are `PermissionError: [Errno 1] Operation not permitted` on `socket.bind` — 19 in `test_action_callback.py`, 1 in `test_p4_deployed_governed_route.py`. The candidate touches no callback, server or adapter path, so it cannot have caused them. **I did not obtain a green capable-host suite and am not claiming one.** The arithmetic expectation on a capable host is 3051 passed / 0 failed / 1 skipped — 3029 + 22 new — and establishing it is the finalizer's job, not mine. The clean-clone gate needs pypi.org TLS I do not have.

## 14. Does `021a9a2` require remediation? **No.** No product-code change is owed.

## 15. Exact canonical next step
Derived from precedent (P4 closure `42ea24c → c30a43b → d3cf1de → 06ebfdb`; R-07 `a31a94a → c26aeae → 035cb55 → 6e8127d`), **not** the P6-CP four-step form — this is a content change on a finalized baseline, and the record's own §9 says so. It is **not** a direct finalizer. Next is **one landing content commit**, by a session outside the build/review/adjudication lineages, carrying:

1. **A-1 (hard).** Preserve the independent review report in-tree + `.sha256` + `refs/preserve/p6-d11-independent-review-021a9a2`, registered in `CANONICAL-DOCUMENTS.md`. **It is currently lost.** If it cannot be recovered from the reviewer, a **fresh independent review must be commissioned** — this is exactly the N-01 failure `8b866f0` names: *"a landed P6 history would have cited evidence no later session could resolve."* Precedent there preserved the artifacts byte-exactly; it did **not** substitute the adjudicator's own verification for a missing report, and neither do I.
2. **A-2.** Correct the four stale P6-CP-2 "finalizer owed" sites (§8 above).
3. **A-3.** State in `events/registry.md` §8 that a strict-order consumer must consume the **complete** aggregate stream, never a family subset.
4. Record **P6-D27**; preserve this adjudication + ref.

Then **exactly one canonical finalizer**, from a host permitting `socket.bind` and reaching pypi.org over untampered TLS.

## 16. M3: **still BLOCKED** — now on the route, not the contract. The engineering boundary is closed; M3 opens only after the finalizer above, and inherits P6-D24 (supply `drain_handler_for`) and A-3 (consume the whole stream).

## 17. For you, in one paragraph

The fix is right, and it is the small one. Neyma's event log let a machine advance an attempt without emitting anything on that attempt's own stream — nine of M2's twenty-five steps do exactly that, by design, because the event belongs to a different machine. The consumer read every one of those silences as "a message got lost" and stopped. `CheckpointPassed` — the fact that says *this invoice is now cleared to be authorized* — sat parked behind a message no machine would ever send, on every load, forever, with nothing failing and nothing alerting. The resolution says a strict stream is **ordered, not gapless**, and has each event state which event came before it. A deliberate silence is now legible as nothing; a genuinely lost message still stops the line, still names an owner, still ages into a human's queue. I reproduced all of it, including two attacks I derived myself, and found no defect that can produce a wrong outcome. What is left is bookkeeping, but one piece of it is not optional: **the independent review that cleared this candidate no longer exists anywhere.** Its verdict is real, its report is gone, and this repository has already ruled once that citing evidence a later session cannot open is itself a defect. Recover it or commission a fresh review — then correct the four places still telling the next session to run a finalizer that already ran, write down that M3 must read the whole stream, and finalize. I have not finalized, landed, or begun M3.

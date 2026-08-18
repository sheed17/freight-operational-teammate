> # ⛔ HISTORICAL REVIEW — NOT CURRENT AUTHORITY
> **Preserved as received; the body below this banner is byte-identical to the artifact on
> `refs/preserve/p6-d11-independent-review-021a9a2` (commit `317fe12f`, blob
> `cb3f5d14b3771e13a7c693951ca9d033eca556d5`, sha256
> `78f6bcab166d9ab026751da56c7f031091c32a488f5e0b64312553fba632bac1`).** This is evidence of a past
> moment, not status. It is an INDEPENDENT REVIEW, **not** an adjudication: it set no acceptance
> criterion, marked no phase complete, closed no risk and authorized no finalization. It reviewed the
> `P6-D11` resolution at content commit `021a9a2816f5e5c20e611eb5b3d06b1fd3ed38f9` (tree
> `f1df545d4fdb68e2221399632d4ee76d18722ccc`) and returned
> **ACCEPT FOR SEPARATE TARGETED ADJUDICATION**.
>
> ### **IT DID NOT REVIEW THE COMMIT THAT CARRIES IT.** The landing commit that brought this file
> in-tree did not exist when this was written. Nothing here may be cited as an independent review of
> that commit. The separate targeted adjudication that followed it is
> [`p6-d11-targeted-adjudication-report-021a9a2.md`](p6-d11-targeted-adjudication-report-021a9a2.md).
>
> ### **THIS REPORT WAS LOST AND THEN RECOVERED, AND THAT IS RECORDED HERE RATHER THAN TIDIED
> AWAY.** No preservation ref was created when the review was performed; the reviewer wrote it to an
> ephemeral session scratchpad that was subsequently cleared. The targeted adjudicator went to read
> it, could not, **declined to substitute its own verification for it**, re-derived every material
> claim independently, and raised the absence as hard landing condition **A-1**. The landing session
> recovered these exact bytes from the reviewing session's own durable tool-invocation record — a
> single quoted heredoc whose tool result reads *"report written"* — after finding the file in no
> tree, ref, stash, reflog, worktree, lost-found or blob object in this repository. **Nothing was
> reconstructed from builder prose, adjudicator prose, memory, summaries or test output.**
>
> ### **ONE OF ITS FINDINGS IS A LANDING CONDITION THAT THIS LANDING DISCHARGED, AND ONE IS AN M3
> CONSTRAINT NOW WRITTEN INTO CANON.** **F-1** — the status authority telling a future session to
> run a `P6-CP-2` finalizer that `c2def38` had already run — was corrected by the landing commit
> that carries this file. **F-3** — a strict-order consumer that family-filters `IllegalTransition`
> `Attempted` out of the `pipeline_instance` stream parks forever on a predecessor it filtered — is
> now stated in `events/registry.md` §8. The body below is unedited; read it with those in hand.

# P6-D11 — FRESH TARGETED INDEPENDENT REVIEW

**Verdict: ACCEPT FOR SEPARATE TARGETED ADJUDICATION.**

- **Candidate:** `021a9a2816f5` · **tree `f1df545d4fdb68e2221399632d4ee76d18722ccc`** (matches the reported tree)
- **Baseline:** `c2def38` (P6-CP-2 landing finalizer metadata)
- **Reviewer lineage:** neither implemented, remediated, adjudicated nor landed this or any prior P6 unit.
- **Tier:** 2 — shared runtime / state boundary. **Tree left clean; nothing was remediated, adjudicated, finalized or landed.**

---

## 1. Root cause — reconstructed independently, not read

I drove the **real** `PipelineMachine` through the real narrative to `CLAIMED` and read the real outbox:

```
v1   prev=0   PipelineStarted     PL-1
v2   prev=1   PolicyEvaluated     PL-2
v3   prev=2   IntentValidated     PL-4
v5   prev=3   ApprovalBound       PL-7b
v6   prev=5   CheckpointPassed    PL-8
pipeline row: state=CLAIMED version=7
SILENT VERSIONS (advanced, emitted nothing on F2): [4, 7]
```

Replaying the **pre-fix rule** (`aggregate_version > applied_version + 1`) over that same real
stream parks `ApprovalBound` at v5 waiting for v4 — a version `PL-6` advanced while emitting
`ApprovalRequested` on M4's aggregate. Nothing will ever emit v4. `CheckpointPassed` queues behind
it. **Permanent, on every load, silent.** With the candidate, the real `DedupInbox` applies all five
and the handler receives `CheckpointPassed`.

`events/registry.md` §8 requires strict per-aggregate **ORDER** for F2/F3/F4/F11/F13; the inbox
implemented **CONTIGUITY**. §8 never said contiguity and cannot: GR-2 is discharged by a co-commit.
Confirmed against `TRANSITION-EVENT-AUDIT.yaml` and the P5 DedupInbox as shipped.

## 2. Silent-transition count — **NINE**, confirmed

M2 has exactly **25** rows (enumerated from `02-pipeline-instance.machine.md`). Nine advance the
`pipeline_instance` version and emit nothing on that stream:

- **8 `CONSUMES`:** `PL-6`, `PL-9`, `PL-10`, `PL-10f`, `PL-10u`, `PL-11`, `PL-11c`, `PL-15`
- **+ `PL-11d`** — emits `VerificationDeferred`, which §3 declares under **F3** on the grant aggregate

`PL-15x` is correctly excluded: an illegal refusal advances no version. The prior "eight" was wrong;
**P6-D25 is correct.**

## 3. Architecture — D is the right branch

| | assessment |
|---|---|
| **A** emit an F2 event at every version | **Correctly rejected.** Mints canonical events under authority this session does not hold, makes M2 assert facts about machines that do not exist, and holds the invariant by convention — the next `CONSUMES` row reintroduces it silently. |
| **B** a second contiguous stream sequence | **Correctly rejected.** A second monotonic identity beside `aggregate_version` — which §4 identity, §8's ordering key, the `trg_event_outbox_strict_version_owner` trigger, the replay fold and the audit are all built on. Verified those five really do key on it. |
| **C** reuse an existing co-committed sequence | **Correctly rejected, and I verified the premise.** The outbox `sequence` is a per-tenant outbox column and is **not an envelope field**; `causation_id` is a cross-aggregate DAG. No such sequence exists. |
| **D** explicit predecessor link | **Chosen and sound.** Additive, optional, digest-covered, derived from durable append-only state rather than a counter, verified at the boundary that owns the record, and conservative on omission. |

Judged against every axis in the brief — determinism, dedup, reorder, loss, duplicate, crash,
rollback, concurrency, causality, tenant and aggregate isolation, forgery, cycles, effect safety,
M3–M13 compatibility, simplicity — D holds. Independently measured:

- **Rollback does not advance the chain** — an emit inside a rolled-back txn leaves `last_emitted_version` at its prior value, and the retry declaring that value is accepted.
- **A stale derivation is refused, not accepted** — a second connection deriving `prev=1` after v2 landed raises `StreamLinkViolation` **before** the insert, so the state write rolls back with it.
- **4 concurrent writers cannot fork the chain** — `BEGIN IMMEDIATE` + derivation under the write lock produced `(0→1)(1→2)(2→3)(3→4)(4→5)(5→6)`: unbroken, no duplicate version.
- **Replay is deterministic and order-independent** across a gap-carrying stream, with `witnesses=0 grants=0 adapter_calls=0` (GR-11 intact).
- **The link round-trips and is inside the digest**; `from_document` rebuilds it, `upcast` preserves it, and the relay refuses a row whose bytes no longer hash to their recorded digest.
- **Unlinked envelopes are byte-identical** — `None` is omitted from the document, so GC-1 is unchanged (verified: `build_gc1_corpus.py --check` current).

**Two-sided defence against forgery.** The producer cannot lie (the outbox re-derives from its own
append-only record in the caller's transaction and refuses a mismatch pre-insert); the transport
cannot alter it (digest). Cycles are unconstructable at the envelope: `prev >= own version` and
negatives raise `MalformedEnvelope`.

## 4. Findings

| id | severity | finding |
|---|---|---|
| **F-1** | **nonblocking — but a correction is owed at the next step** | **The status authority states a finalizer is owed that has already run.** `CURRENT.md` and `CLAUDE.md` say `P6-CP-2` "owes exactly one canonical finalizer run". It does not — see §6. The candidate **inherited** the claim (it originated in landing commit `1abcb229`, which the metadata commit `c2def38` could not correct under the two-commit convention) but **restated it in new prose** rather than correcting it. Not a runtime defect; `CURRENT.md` is the sole status authority, so this is the "canonical documents disagree" condition and should be fixed by the landing commit. |
| **F-2** | nonblocking — confirms the candidate's own **P6-D26** | The link is required by canon and enforced **only where declared**. Today the exposure is nil: `src/` has exactly **two** envelope construction sites — M1 (`work_item`, not strict) and M2 (strict, linked). A future strict producer that omits it degrades to contiguity, i.e. reintroduces P6-D11 for that machine. It **fails safe** (parks, never skips). Recommend a mechanical guard when the second strict producer lands — not now, since making omission a hard refusal would break P5's certified surface. |
| **F-3** | nonblocking — **new, surfaced by this review**; an M3 constraint | `IllegalTransitionAttempted` is an **F14 order-tolerant** contract riding on the **strict** F2 aggregate at the attempt's unchanged version. When it lands at a version a `CONSUMES` row left silent it becomes the **sole occupant** of that version and therefore a **load-bearing link**. I reproduced this: an attack at `AWAITING_APPROVAL` (v4, silent) makes `ApprovalBound` declare `prev=4`, and a consumer receiving **only F2** parks on it forever. **Unreachable today** — the relay publishes every pending row for an aggregate to one sink and does no family filtering, and the builder's own case covers the all-events consumer. But the constraint is undocumented: *a consumer of a strict aggregate must consume every event on that aggregate, not a family subset.* Worth stating in §8 beside P6-D24. Note it is **not a regression**: pre-fix that consumer parked anyway. |
| **F-4** | observation | The **inbox trusts** the declared link; authenticity rests on the outbox's emit-time verification plus the digest. Sound for an in-process transport. If the F2 stream ever crosses a trust boundary the link needs the same treatment as `aggregate_version`. |
| **F-5** | observation | The AST single-site guard matches `EventEnvelope(...)` only via `ast.Name`; an aliased/attribute-qualified construction or `dataclasses.replace` would evade it. Mutant M9 proves it catches the realistic case. |

**No material correctness or safety issue survives.**

## 5. P6-D24 — disposition: **A, a valid nonblocking M3 obligation, correctly characterized**

Not deferred — reproduced. Without `drain_handler_for`: v5 and v3 park, v1 applies, and **redelivery
of either parked event returns `ALREADY_PARKED` without re-evaluating the gap** — they leave only by
M-26 expiry. With a drain factory on the unblocking consume, the handler sees `[1, 3, 5]` and the
park is empty.

It is **A** because: it is pre-existing P6-CP-1 `F-04` design and **untouched by this diff**; it is
deliberate (you may not consume another caller's parked envelope through a handler you guessed at);
it **fails safe** — the park is owner-attributed with a TTL that surfaces an owned exception; and
P6-D11 **strictly reduces** exposure to it (pre-fix every attempt parked; post-fix only genuine loss
or reorder does). The record's wording matches the mechanism exactly.

## 6. Status / history — **`P6-CP-2` IS ALREADY FULLY FINALIZED**

`c2def38` records a **completed** canonical finalizer run. Evidence I checked directly:

- `SUITE-RESULT.json` and `GATE-RESULT.json` both bind to **commit `1abcb229` / tree `1f98154d`** — the P6-CP-2 **landing** content commit — and both postdate it. Suite 3029/0/1 against a 3030-node manifest; clean-clone gate `passed: true`.
- `BUILD-STATUS.yaml`'s finalizer-maintained `derived:` block is rebound to the same pair.
- The topology `1aaf943 → b226717 → 1abcb229 → c2def38` mirrors P6-CP-1's `ca8c070 → 64f6f6c → da84806 → cc986dd` exactly.

**No additional P6-CP-2 finalizer is owed.** Running one would be acting on stale prose (F-1).
`021a9a2` is correctly treated as **new P6-D11 content on top of that finalized baseline**.

## 7. Verification executed

| what | result |
|---|---|
| Focused `test_p6_d11_strict_order_stream_link.py` | **22 / 22 passed** |
| P5 transport · contracts · replay & audit · timers · mint · M1 · M2 | **909 / 909 passed** |
| **Canonical suite** `pytest eval/ -q` | **3031 passed · 1 skipped · 20 failed — all 20 environment-only, proven** |
| Mutation battery `mutate_p6_d11_stream_link.py` | **15 / 15 caught**, byte-for-byte restore, guard green after each |
| Product Driver `p6_d11_f2_consumer_boundary_probe.py` | **16 as specified, 0 wrong** |
| Product Driver — **my own** mutants | **3 / 4 drove it RED**; the 4th is out of its scope by construction (see below) |
| Product Driver `p6_pipeline_instance_probe.py` (M2's own) | **70 as specified, 0 wrong** |
| `generate_event_contracts.py --check` | matches the specification |
| `build_gc1_corpus.py --check` | corpus and pinned digests match |
| Status/receipt guards | 14 passed |
| **My own hostile matrix** (independent of the builder's cases) | **20 / 20** |

**The 20 failures are environment-only and I proved it rather than asserting it.** Every one is
`PermissionError: [Errno 1] Operation not permitted` from `ThreadingHTTPServer → server_bind`
(20 failures, 20 PermissionErrors — I confirmed `socket.bind` is denied in this sandbox), and I ran
the same two files **at the baseline `c2def38` in an isolated worktree**: **identical 20 failures.**
They predate the candidate and cannot be caused by an envelope field. Node accounting is clean:
manifest 3052 = baseline 3030 + 22 new P6-D11 nodes; 3031 + 20 + 1 = 3052. Nothing deselected,
skipped, suppressed or reinterpreted.

**Product Driver honesty note.** My mutant PD-3 (an absent link read as "nothing precedes me") left
the probe **GREEN**. That is a coverage boundary, not a false green: the probe drives the real M2,
where every event declares a link, so the fallback branch is unreachable from it. The Neyma battery's
`M8` covers that branch and catches it. **No Product Driver verification defect found**, and no work
is owed in the harness repo.

## 8. Answers

1. **INDEPENDENT REVIEW: ACCEPT** for separate targeted adjudication
2. `021a9a2816f5` · tree `f1df545d4fdb68e2221399632d4ee76d18722ccc`
3. Root cause as §1 — strict ORDER implemented as numeric CONTIGUITY; an intentional non-emission is indistinguishable from a loss under that inference
4. **Nine** silent transitions (8 `CONSUMES` + `PL-11d`); M2 has 25 rows
5. Architecture sound; the link is derived from durable state, verified at the owning boundary, and conservative on omission
6. Better than A/B/C for the reasons in §3, each premise independently checked
7. F-1 … F-5, none blocking
8. **P6-D24 = A**, correctly characterized (reproduced)
9. Product Driver **16/0**, meaningful, proven able to fail; no harness defect
10. Mutation **15/15**, plus my own 4 against the Product Driver
11. Regressions clean — 909/909, M1 and M2 intact, M2 still ships **dark** (zero importers of `pipeline_instance.py` in `src/` or `scripts/`)
12. Canonical suite green apart from 20 proven-environment-only `socket.bind` failures
13. **Yes — `c2def38` already fully finalized `P6-CP-2`**
14. **No additional `P6-CP-2` finalizer is owed**
15. **`021a9a2` requires no remediation.** F-1 is a documentation correction for the landing commit, not a product change
16. **Ready for separate adjudication**
17. **M3 remains BLOCKED** — on the route only: this content change owes a separate adjudication and one canonical finalizer. It is **not** blocked on the P6-CP-2 finalizer (discharged) and **not** on the F2 ordering contract (engineering-closed)

## 9. What this gives Neyma, in freight terms

A load is delivered, the broker approves raising the invoice, and Neyma runs the seven-check
checkpoint that says *this effect may now be authorized*. Before this change that authorization
**never reached the machine that acts on it** — it sat behind a version number that no machine would
ever produce, because the step before it was a handoff whose record belongs to the approval, not to
the attempt. The card stopped moving. On every load. Nothing failed and nothing alerted.

Now each event on an attempt **says which event it follows**, so a deliberate silence reads as
nothing and a real hole still reads as a hole. **The approved invoice reaches the next step; a
genuinely lost message still stops the line and lands on a named human with a clock on it.** That
second half is the one that matters: a fix that merely stopped stalling would have been the larger
and quieter bug.

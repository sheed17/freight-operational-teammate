# P6-D11 — the STRICT-ORDER F2 version-gap, resolved

**Unit:** `P6-D11` · **Tier:** 2 (shared runtime / state boundary — CLAUDE.md §13.2) · **Date:** 2026-08-17
**Baseline:** `c2def38` (the finalized `P6-CP-2` / M2 topology)
**Status:** **RESOLVED.** M2 was reopened in exactly one place — see §6.

> ### **THIS IS THE IMPLEMENTING SESSION'S RECORD, NOT AN INDEPENDENT REVIEW.**
> It does not score a P6 acceptance criterion, does not mark P6 COMPLETE, and does not begin M3.

---

## 1. The capability, in freight terms

Load 4471 delivered. Dana approved raising the invoice. Neyma ran the seven-check checkpoint and
emitted `CheckpointPassed` — the fact that says *this effect is now authorized to be authorized*.
**M3 reads that fact and mints the Effect Grant. Before this unit, it never would have.**

The attempt's `CheckpointPassed` rides at aggregate version 6 of a stream whose version 4 carries no
event, because the transition that reached version 4 (PL-6, "route to a human") emits
`ApprovalRequested` — **M4's** event, on the **approval** aggregate, not this one. The dedup inbox
read the missing version as *"an earlier event has not arrived yet"*, parked, and waited for a fact
no machine will ever produce.

**The card would have stopped moving. On every load. Forever. Nothing fails, nothing alerts** — the
park's M-26 TTL eventually hands a human an event that cannot be unblocked, once per attempt.

---

## 2. Root cause

`events/registry.md` §8 requires **STRICT per-aggregate ordering** for F2/F3/F4/F11/F13. The inbox
implemented that as **contiguity**: `aggregate_version > applied_version + 1 ⇒ PARK`.

**Contiguity was never what §8 said, and it cannot be what §8 says.** `GR-2` is discharged by a
**co-commit**: a transition whose canonical event belongs to another machine's aggregate advances its
own aggregate's version and emits nothing on its own stream. Eight of M2's twenty-five §14 rows are
exactly that — `PL-6`, `PL-9`, `PL-10`, `PL-10f`, `PL-10u`, `PL-11`, `PL-11c`, `PL-15` — and
**`PL-11d` is a ninth non-emission** on `pipeline_instance` (its `VerificationDeferred` rides on the
`effect_grant` aggregate, debt `P6-D13`). ### **The "eight" figure in the prior records undercounts
the gap sources by one; nine transitions advance the version without emitting on this stream.**

So a version with no event on a strict stream is **normal**, and the inbox was inferring a loss from
an absence. An intentional non-emission and a lost event are **indistinguishable from an absence**,
which is why no amount of care at the producer could fix it.

Measured, before the fix, on the real machine driven to `CLAIMED`:

```
attempt version 7    F2 stream: v1 v2 v3 __ v5 v6 __
consume v1 PipelineStarted    APPLIED
consume v2 PolicyEvaluated    APPLIED
consume v3 IntentValidated    APPLIED
consume v5 ApprovalBound      PARKED_VERSION_GAP     <- waiting for v4, which nothing emits
consume v6 CheckpointPassed   PARKED_VERSION_GAP     <- M3 never mints the grant
after 5 full redeliveries: still parked
```

---

## 3. The decision

> ### **STRICT PER-AGGREGATE ORDERING MEANS *ORDER*, NEVER *CONTIGUITY* — AND THE SUCCESSOR DECLARES WHAT IT FOLLOWS.**

One **additive, optional** envelope field, `previous_aggregate_version` (§1): the `aggregate_version`
of the event this producer emitted immediately before this one **on this aggregate's stream**; `0` for
the stream's first event. Required of every producer on a strict-order aggregate.

The consumer's rule becomes **block iff `previous_aggregate_version` is ABOVE the applied high-water
mark** — never on the mere absence of a version number. An envelope declaring no link (every
historical event, every order-tolerant producer) falls back to the contiguity rule verbatim:
**absence may never be read as "there is nothing before me".**

This is ER-16's principle applied one level down: ### **a fact is reconstructed from POSITIVE
evidence, never from an absence.** The inbox stops inferring; the successor states.

### Why not the alternatives

| | Why not |
|---|---|
| **A — every aggregate version emits an F2 event** (mint explicit no-op/state-transition events) | Requires **minting canonical events** — founder/architect authority, and a change to §3's 105 and to G2's settled 117/9/6/2/0 classification. It makes M2 emit `ApprovalRequested`-shaped facts about **M4, a machine that does not exist**, which the contract gate correctly refuses. And it establishes the invariant **by convention**: the first future `CONSUMES` row whose author forgets reintroduces the identical permanent stall, silently. §13.4 — a foundation the next phase can undo is not a foundation |
| **B — a separate contiguous producer/event-stream sequence** | Sound, and rejected on cost. It adds a **SECOND monotonic identity per aggregate** beside `aggregate_version`, which §4's transition-natural identity, §8's ordering key, the strict version-ownership trigger, the replay fold and the audit reconstruction are all built on. Two numbers that must never disagree is the shape of "two systems claiming one authority" (§4 terminology). It also requires changing §8's stated ordering key. **D obtains the same guarantee as a link inside the existing key space** and changes neither |
| **C — order on an existing co-committed sequence** | **There is none that works.** `event_outbox.sequence` is per-**tenant** insertion order, is a transport artifact, and is not in the envelope; `causation_id` is a cross-aggregate DAG and cannot express "adjacent on this stream". Investigated and discarded on evidence, not assumed away |
| **D — the stream link (ADOPTED)** | One optional envelope field, **zero schema migration**, §8's ordering key unchanged, replay untouched, every historical event byte-identical. And it is **strictly more informative** than B: a genuinely lost event is detected from its successor's **positive declaration** rather than from a hole |

**The repository's own replay path was already right and is the corroborating evidence:**
`event_replay.py` folds per aggregate in `aggregate_version` order and asserts **nothing** about which
versions exist. Order, not contiguity. Only the inbox's *inference* was wrong.

---

## 4. Runtime behaviour, before and after

| | before | after |
|---|---|---|
| M3 consuming a real M2 attempt | `CheckpointPassed` **PARKED_VERSION_GAP**, permanently. Zero grants minted, on every load | **APPLIED.** The grant is minted |
| a genuinely **lost** event | parks | ### **still parks**, with its arrival order, its accountable owner and its M-26 TTL — unchanged |
| **reordered** delivery | parks, drains in order | ### **unchanged** |
| **duplicate** delivery | `(consumer, tenant, event_id)` no-op | ### **unchanged** — the link is not in the dedup key |
| a producer stating a **false** predecessor | n/a | **`StreamLinkViolation` before the INSERT**, so the state change travelling with it is rolled back too |
| a **historical / unlinked** envelope | contiguity rule | ### **contiguity rule, byte-identical** |
| replay / `GC-1` digest | gap-tolerant | ### **untouched** |
| `IllegalTransitionAttempted` on `pipeline_instance` | parks after a run of `CONSUMES` rows — the refusal works, **the evidence of it cannot be consumed** | applied, at both an occupied and a silent version |

---

## 5. The mechanism, and where it lives

1. **`event_envelope.py`** — the field, its validation (`0 ≤ previous < aggregate_version`; a
   forward or self link is a `MalformedEnvelope`), and its place in the canonical `ev_v1` bytes.
2. **`event_outbox.py`** — `last_emitted_version(aggregate_type, aggregate_id, below=…)`, the
   **shared derivation every strict producer uses**, read from the append-only, never-pruned emitted
   record rather than from a counter; and the **verification** at `emit` that refuses a declared link
   the aggregate's own history does not hold. ### **The producer cannot lie about it**, because the
   boundary that owns emission checks it.
3. **`event_inbox.py`** — the gap rule, with the fallback for unlinked envelopes.
4. **`pipeline_instance.py`** — **one line**, inside `_envelope()`, the single factory through which
   M2 builds every envelope. An AST guard asserts that stays the only construction site.

**No schema migration.** The link travels inside `envelope_json`; the derivation reads
`aggregate_version`, which is already indexed by `ix_event_outbox_aggregate`.

### **WHY THE VERIFICATION AT `emit` IS LOAD-BEARING AND NOT BELT-AND-BRACES.** Every M2 transition
derives its predecessor **after** its OCC write, inside the same transaction, so the value cannot be
stale — except `PL-1`, which builds its envelope **before** `BEGIN IMMEDIATE` because the attempt
does not exist yet. That read is structurally `0` (nothing can precede version 1 on an aggregate id
that has never been used), and `emit` re-derives and re-checks it **inside** the transaction anyway.
So the one place the producer reads outside the lock is the one place the answer cannot be wrong,
and it is checked again regardless. A future producer that gets the ordering wrong is refused rather
than published.

---

## 6. M2 was reopened, in exactly one place, and that was necessary

CLAUDE.md §11 forbids rebuilding or polishing M2. This is neither: M2 is **the producer**, and a
resolution that left the producer silent would be a resolution of nothing. The change is **one
keyword argument in `_envelope()`**, the single factory every M2 emission already routed through.
No transition, guard, state, kernel path, table or classification moved. `AC-MACH-000`'s exact
population, the reservation, the claim CAS and the §15 kernel-owned derivation are untouched.

---

## 7. Evidence

| what | result |
|---|---|
| `test_p6_d11_strict_order_stream_link.py` — the focused hostile battery | **22 / 22** |
| P5 transport · P5 contracts · P5 replay & audit · P5 timers · P5 mint · M1 · M2 | **909 / 909** |
| `scripts/mutate_p6_d11_stream_link.py` | ### **15 / 15 mutants caught**, byte-for-byte restoration, guard green after each |
| Product Driver — `p6_d11_f2_consumer_boundary_probe.py` | **16 behaviours as specified, 0 wrong** |
| Product Driver — proven able to fail | **3 / 3** mutants drove it to a non-zero exit; tree restored |
| Product Driver — `p6_pipeline_instance_probe.py` (M2's own, unchanged) | **70 as specified, 0 wrong** — the M2 narrative is intact |

`M1` restores the exact pre-fix contiguity rule and is the mutant this battery would be worthless
without. **Most of the battery attacks the SAFETY half**, because a fix that merely stopped parking
would be a larger and quieter bug than the one it closed: `M2` removes the block, `M3` inverts the
comparison, `M4` lets a reordered delivery through, `M6`/`M6b`/`M6c`/`M6d` forge the link four ways,
`M8` reads an absent link as "nothing before me", and `M9` adds a second envelope construction site
in M2.

---

## 8. Findings recorded, not actioned (§13.3)

| id | finding | why nonblocking |
|---|---|---|
| **P6-D24** | ### **A strict-order consumer MUST supply `drain_handler_for`, or a parked event never leaves the park except by M-26 expiry** — a redelivery of an already-parked event is counted (`ALREADY_PARKED`) and does not re-evaluate the gap. This is P6-CP-1's deliberate F-04 design and is **not** introduced or changed here; it is recorded because a reader of the inbox alone would not discover it, and **M3 owes the factory** | Correct behaviour, demonstrated by the Product Driver. It is a requirement on M3, stated so M3's author inherits it rather than rediscovering it as a stall |
| **P6-D25** | The prior records say **eight** `CONSUMES` rows leave gaps. Nine transitions actually advance the version without emitting on `pipeline_instance`: the eight, plus `PL-11d`, whose `VerificationDeferred` rides on `effect_grant` (`P6-D13`) | The resolution is indifferent to the count — the link is derived per event from the emitted record, not from a list of rows. Corrected in `events/registry.md` §8 and here |
| **P6-D26** | The link is **required** of strict-order producers by the canonical registry and by review, and **enforced mechanically only where it is declared** (the outbox verifies a declared link; it does not refuse an absent one). Making absence a hard refusal would break P5's certified surface, whose hand-built strict-family envelopes carry no link | The fallback is the **conservative** rule, so an omission degrades to today's behaviour and never to unsafe behaviour. M2 is guarded structurally (the AST single-construction-site case). A future machine's review must check it, and §8 now states the obligation |

Carried forward unchanged: `P6-D9`, `P6-D12`, `P6-D13`, `P6-D14`–`P6-D23`, `P6-D1`–`P6-D8`, the G2
residuals, and the hardcoded knowledge-base `tenant="default"`.

> ### **`P6-D26` IS NOT THE LAST ASSIGNED ID — ADDED AT THE `P6-D11` LANDING.** The fresh targeted
> INDEPENDENT review and the SEPARATE targeted adjudication of candidate `021a9a2` are on disk at
> [`p6-d11-independent-review-report-021a9a2.md`](p6-d11-independent-review-report-021a9a2.md) and
> [`p6-d11-targeted-adjudication-report-021a9a2.md`](p6-d11-targeted-adjudication-report-021a9a2.md).
> They confirmed this record's `P6-D24`, `P6-D25` and `P6-D26` rather than overturning any of them —
> the review **reproduced** `P6-D24` instead of deferring to this record, and the adjudication
> classified it **`A`, a valid nonblocking M3 obligation, correctly characterized**. `P6-D24` is now
> also carried in the P6 unit's `residual_risks_carried_forward` in
> [`IMPLEMENTATION-REGISTRY.yaml`](IMPLEMENTATION-REGISTRY.yaml), so M3's author inherits it from the
> machine-readable authority and not only from this record. **No shared-runtime change was made for
> it.**
>
> ### **ONE NEW NONBLOCKING DEBT WAS OPENED BY THE ADJUDICATION: `P6-D27`, the chain-fork /
> emission-monotonicity gap.** If a producer emitted a **lower** `aggregate_version` after a higher
> one on one aggregate, two events would declare the same predecessor and the later-arriving lower
> one would apply after the higher — a silent strict-order violation, which the adjudicator
> constructed at the outbox and found **is not refused**. Its ruling, preserved rather than
> paraphrased: **nonblocking, because it is unreachable through every canonical producer** — M2
> allocates `item.version + 1` under OCC and its F14 record rides at the current (maximal) version,
> so emitted versions are non-decreasing; it ships dark with zero production importers; and it needs
> a future producer defect that is independently a strict-order violation. **Its honest caveat, also
> preserved:** *the old rule failed closed here and the new one fails open — though only because the
> old rule parked everything, correct traffic included.* **Not remediated by the landing.**
>
> ### **AND ONE CANONICAL CONTRACT WAS ADDED THAT THIS RECORD DID NOT ANTICIPATE.** The review's
> **F-3** — an `IllegalTransitionAttempted` (F14) riding on the **strict** F2 `pipeline_instance`
> aggregate can become the declared predecessor of the next F2 event, so a consumer that
> family-filters it out parks forever — was ruled by the adjudicator to be an **M3 authoring
> constraint that must be written into canon, not left to be rediscovered as a stall**.
> `events/registry.md` §8 now states that **a strict-order consumer must consume the COMPLETE
> aggregate stream, never a family subset.** It introduces **no new sequencing mechanism**: it is a
> requirement on the SUBSCRIPTION, and the adjudicator proved it satisfiable end to end before
> requiring it.
 **`P6-D13` is narrowed but not
closed:** `PL-11d` still does not emit, and its ordering key is still the grant's version, which is
M3's — but a `VerificationDeferred` emitted by M3 on `effect_grant` will now carry a link derived the
same way, so the seam is smaller than it was.

---

## 9. What this does NOT do

- ### **It does not begin M3, and it does not authorize beginning M3** on its own.
- It does not score a P6 acceptance criterion and does not mark P6 COMPLETE.
- It mints **no** canonical event; §3 still enumerates 105.
- It changes **no** transition, classification, state, guard or kernel path.
- It enables **no** production write. The capability still ships dark: `pipeline_instance` has zero
  production importers and its import closure reaches no effect-capable adapter.
- It is **not** an independent review of itself. `P6-D11` owes the same route every unit here owes:
  a **fresh targeted independent review** by a session that neither implemented nor remediated it,
  then a **separate adjudication**, then **exactly one canonical finalizer**.

# P5 U5.4+U5.5+U5.6 — golden corpus, inert replay, audit reconstruction: implementer's evidence

> ### **THIS IS EVIDENCE, NOT ACCEPTANCE.** Written by the session that implemented the increment.
> No criterion is scored, P5 stays `READY` / `IN_PROGRESS` / **NOT COMPLETE**, and all 14 P5
> acceptance criteria remain `PENDING`. A battery that agrees with its author is evidence; it is
> never adjudication (CLAUDE.md §11).

---

## What Neyma can do now

**Rebuild operational truth from the facts it emitted, and explain how it got there — without
touching the world.**

    state changes → canonical facts → durable transport → deterministic replay
                  → reconstructed operational state → auditable explanation

Emit through the transactional outbox, kill the process, restart, read the durable log back, and
the reconstruction is **byte-identical** to the one built from the golden fixture. Then ask why an
aggregate is in its state and get the eighteen audit fields answered from the beliefs **of that
day** — not from today's policy, brake or provenance.

## Why this is ONE increment and not three

The acceptance spec makes the coupling mechanical rather than a matter of taste:

| | |
|---|---|
| `AC-EVT-007` | *"replay `GC-1` ⇒ 0 witnesses, 0 grants, 0 adapter calls"* — the replay's oracle **is** the corpus |
| `AC-EVT-008` | *"`GC-1` ⇒ the SAME projection DIGEST"* — the corpus's oracle **is** a replay |
| `AC-AUD-002` | folds the same history, queried per-effect |

All three `depends_on: [U5.3]` and nothing else; all Tier 2; all inside P5's `allowed_scope`.
Splitting them would have meant building a fixture whose oracle cannot run, then a replay with
nothing to replay.

## The load-bearing property, and how it is guaranteed

M-27 requires replay to be side-effect free **STRUCTURALLY**: *"replay performs no live
revalidation ⇒ it cannot construct a `CheckpointPassed` ⇒ it cannot mint an Effect Grant ⇒ it
cannot act."*

So the guarantee is asserted as an **import closure**, not as a count of zeros afterwards.
`test_replay_cannot_reach_an_effect_capable_module` walks **every import spelling** reachable from
`event_replay` + `event_audit` — absolute and relative from-imports, `from freight_recon import X`,
plain `import`, and `importlib`/`__import__` string constants — and asserts the closure contains no
adapter, no effect boundary, no checkpoint kernel, no brake store, no `WorkflowStore`, no network
client. Mutants **R1**, **R2** and **R19** add such an import in different spellings and confirm the
guard goes red — which is the registry's mandated proof (*"required — replay must be proven unable
to call an adapter"*).

*(An earlier version of this paragraph said "every **relative** import", which was accurate about
the code and was exactly the problem: see B-1 below.)*

Supporting it: `replay()` takes no connection and its source contains no `execute(`, `INSERT`,
`UPDATE`, `DELETE` or `commit(`; `explain()` takes no store, which is the mechanism behind
`AC-AUD-002` rather than a promise about it.

## What replay reconstructs at P5, stated precisely

ADR-008 says replay applies events *"through the transition tables"*. **The transition tables are
P6.** Inventing them here would be building P6 inside P5 under another name.

What exists at P5 is the canonical event corpus, so replay reconstructs **event-level aggregate
state**: per `(tenant, aggregate_type, aggregate_id)`, the ordered fold of the facts its events
declare. That is the substrate P6 will apply transition guards *to* — not a placeholder for them.

## Real defects found — four, all in this build, all caught by attacking it

| | The defect | Why it mattered |
|---|---|---|
| **1** | **Nondeterministic reconstruction.** The fold applied fields in ARRIVAL order | §8 gives NO global order, so one history can legitimately arrive in different orders — a relay leasing aggregates differently, a recovery after a crash. The same corpus rebuilt to a different digest, so the pinned oracle would have pinned a property of one **delivery** rather than of the **history**. Now ordered by §8's key, tie-broken by `event_id`, making the rebuild a pure function of the SET of events. The suite shuffles GC-1 five ways |
| **2** | **A redelivered fact was folded twice** | The outbox re-sends an identical row after a crash and GC-1 carries one deliberately, so a duplicate delivery reconstructed a history that never happened. Deduped on `(tenant, event_id)` — §1's dedup identity and the inbox's own key — so the rebuild and the live consumer agree about "already seen" |
| **3** | **The audit silently disagreed with the rebuild.** `what_was_known` flattened facts across a multi-aggregate chain | More than one aggregate declares an `approval_id`, so last-write-wins reported the **compensation's** approval as the **effect's**. Two readings of one history that disagree is the failure this whole increment exists to make impossible. Now keyed per aggregate and folded exactly as replay folds, with a node asserting the two agree field by field |
| **4** | **Two contract authorities inside one rebuild** | The fold resolved through the global registry while the read path used an explicit set, so a rebuild that validated cleanly then failed at the fold |

## The independent review REJECTED this, on five blocking findings — all real

### **THE MOST SERIOUS ONE DEFEATED THE UNIT'S OWN LOAD-BEARING GUARANTEE.** The M-27 import-closure
walk tested `isinstance(node, ast.ImportFrom) and node.level`, and `node.level` is **0** for an
absolute import — so `from freight_recon.effect_boundary import execute_effect` walked straight
past it. This package contains **26 absolute imports in exactly that style**, and for
`effect_boundary` and `checkpoint` this walk is the **sole** control: P4's import gate covers only
effect-capable *adapters*, and `effect_boundary` is the containment boundary itself. The registry's
mandated proof (*"replay must be proven unable to call an adapter"*) was being proven against one
import spelling in four, because mutants R1/R2 both injected the relative form.

`eval/phase0/import_probe._module_name` had already solved this, and its docstring says why: *"The
guard could be bypassed by changing import style, which is exactly the 'effect path hidden behind
an alias' case it exists to catch."* CLAUDE.md §9 lists this blind spot as a repeat offender. **This
was the fifth instance.** The walk now covers all four spellings — absolute and relative
from-imports, `from freight_recon import X`, plain `import`, and `importlib`/`__import__` string
constants — parametrized across every one, with mutant **R19** re-gating on `node.level` to prove it.

| | The defect | Why it mattered |
|---|---|---|
| **B-1** | The import-closure walk saw only RELATIVE from-imports | The mandated M-27 proof, defeatable by import spelling |
| **B-2** | `_pin` still flattened across the chain, answering **5 of the eighteen** | The audit of an **effect** reported the **compensation's** SD-3 set. Green only because a redelivered event happened to sit last in corpus order — a fixture's arrangement was holding up a correctness assertion |
| **B-3** | `explain()` was not redelivery-invariant; `as_of` used corpus position, not time | An audit reporting one grant claimed **twice** is materially misleading: `GrantDoubleClaimAttempted` is a real F14 security event |
| **B-4** | `chain_for` walked causation **forward only** | An effect's explanation lives mostly in what came *before* it. The `eg-5501` chain excluded `CheckpointPassed`, `ApprovalGranted` and `WorkItemCreated`, so **6 of 18** returned UNRECONSTRUCTIBLE against facts sitting in the same corpus — including *"WHY the checkpoint passed or failed"* and *"the accountable owner"*. Chain 8 → 14 events; unreconstructible 6 → 3, all three now honest absences |
| **B-5** | Redelivery dedup was first-wins-by-ARRIVAL | Two different bodies under one `event_id` made the rebuild order-dependent again — same set, two orders, two digests — and swallowed the corruption. §1 makes `event_id` globally unique, so that is a corpus that cannot be read, and it is now refused |
| **B-6** | **Found by the fix for B-3:** `explain()` depended on corpus order | One chain in two arrival orders gave two explanations. Same class as the fold defect; the chain is now ordered by `occurred_at`, so an explanation is a pure function of the SET of facts |

Also fixed: `None` leaking where the module's own rule mandates `UNRECONSTRUCTIBLE` (**M-1**); a
**vacuous** AC-AUD-002 node that built a newer `PolicyActivated` and *discarded* it, comparing two
identical calls on one list (**M-2**) — the world now genuinely moves and the explanation must not;
and thresholds tuned to current behaviour (`at_least=12` against the 12/18 then achieved) replaced
with **exact sets**, which is what let B-4's six-field hole read as a pass (**M-3**). GC-1 gained
the `provenance_refs` and `evidence_refs` it carried none of (**N-1**), so AC-AUD-004's evidence
traversal is exercised rather than merely specified.

### **THE SHIPPED BATTERY WAS 36/36 GREEN AND EVERY ONE OF THESE WAS INVISIBLE TO IT.** Six new
mutants (R19–R22, R24, R25) now target each finding, because none of them had a mutant that could
reach it. **R23 was retired rather than left green**: once the ordering fix landed, its two
expressions became equal by construction and it could no longer fail — a mutant that cannot fail is
a decoration.

## AC-EVT-009 and the schema-version span — resolved without inventing history

`AC-EVT-009`'s oracle is *"v1+v2+v3 in one corpus ⇒ one digest; run twice ⇒ identical"*, and GC-1
must span *"≥1 schema version change"*. **Every one of the 118 canonical contracts is at `v1`.**
A schema version change requires a breaking change plus a registered upcaster (§6) — a
specification amendment under founder/architect authority, the same authority that minted 98 → 105.

### **NEITHER THE ORACLE NOR THE SPAN REQUIRES THE VERSIONED CONTRACT TO BE ONE OF THE 105**, and
GC-1 is labelled *"(immutable fixture)"*. So the chain is proven through the **real replay path**
with a **test-only** contract: v1 `amount: 100` → ×100 → v2 `amount_minor` → renamed → v3
`total_minor: 10000`. One digest, identical across runs, deterministic under shuffling, and a
missing hop refuses rather than folding the body as-is.

**GC-1 itself stays purely canonical**, because that is what makes *it* trustworthy. A test asserts
every contract is still v1, so the day a real `v2` is minted the node goes red — the signal that
GC-1 owes the span inline.

### The seam, and why it is not a validation bypass

`replay(..., contracts=…)` and `event_contracts.read_against` resolve an explicit contract set.
They change what a **rebuild accepts**; they can never change what may be **emitted** — the
outbox's gate calls `validate()` with no contract parameter and resolves through the module-global
registry. `test_the_reconstruction_seam_cannot_widen_what_may_be_emitted` proves it: the synthetic
event replays fine and the outbox still refuses it. Both paths share **one** validation
implementation (`_validate_against`), written once so a rebuild can never quietly start accepting
what an emitter would refuse.

## Divergence detection, and its deliberate restraint

`compare_to_live` returns findings shaped to the `ProjectionRebuildDiverged` contract
(`entity_ref`, `field`, `live`, `rebuilt`). ### **IT ENGAGES NO BRAKE AND EMITS NOTHING.** §11
requires that event to auto-engage a tenant brake; F14's cross-cutting rule requires that
*replaying* a security event never re-engages one — *"the auto-action fired once, at the original
occurrence"*. A detector acting from inside a rebuild cannot tell those apart, so it reports, and a
caller that knows which case it is decides. Same posture as P4's orphan-effect detective sweep;
**no production caller exists yet.**

## Verification

| | |
|---|---|
| **Battery** | `eval/tests/test_p5_replay_and_audit.py` — **44 nodes** |
| **Failure modes attacked** | replay after restart (through the real outbox, store closed and reopened) · missing events · duplicated events · ordering variation (five shuffles) · corrupted payload · unsupported historical version · upcasting during replay · tenant contamination · partial history · invalid aggregate reconstruction · audit-vs-rebuild disagreement · replay reaching effect-capable code · nondeterministic reconstruction |
| **Mutation** | `scripts/mutate_phase5_replay.py` — ### **24/24 caught**, including R1/R2 (the mandated adapter-unreachability proof) and R3/R4/R11, which reintroduce three defects this build actually shipped. Builder mutants regenerate GC-1, because a builder mutation is inert until the fixture is rebuilt |
| **U5.3 battery** | still **37/37** after the seam was added — C1 was re-anchored to the live validation gate and **C37** added for `contract_for`'s own refusal, which C1 no longer isolated |
| **Regression** | full `eval/` suite: see `SUITE-RESULT.json` for the figures bound to the finalized tree |

## Nonblocking debt recorded, not actioned

| ID | Finding | Why nonblocking |
|---|---|---|
| **U546-D1** | GC-1 does not span a schema version change INLINE; `AC-EVT-009` is proven by the test-only fixture in section 8 | Minting a production `v2` is a founder/architect specification amendment. A guard asserts every contract is still v1, so the premise cannot outlive its truth |
| **U546-D2** | `compare_to_live` has **no production caller** — nothing schedules a rebuild or a divergence sweep, and the F14 event is not minted | Scheduling and minting belong to the phase that owns projections (P6+). Same posture as P4's detective sweep; the mechanism exists and ships dark |
| **U546-D3** | `EX-1` — the acceptance fixture, *"a completed consequential trace (POD→invoice→payment) 90 days old"* — does not exist, so `AC-AUD-005`'s latency figure is unmeasured | That chain is produced by the freight-domain machines, which are **P6**. This increment is the reconstruction MECHANISM; claiming `AC-AUD-*` green today would claim a freight capability that does not exist |
| **U546-D4** | Replay reconstructs event-level aggregate state, not P6 entity projections | Entities are P5's `prohibited_scope`. The ordered history a machine-aware folder needs is exactly what this produces |

## What this increment deliberately did NOT do

* **`checkpoint.py` and `effect_boundary.py` are byte-unchanged**, as are both Phase-0 safety guards.
* **No freight workflow** (CLAUDE.md §11); the 13 machines stay P6.
* **Nothing was enabled.** Replaying the entire corpus writes to no durable surface — asserted by
  comparing row counts across six canonical tables before and after.
* **No P5 criterion is scored.** All 14 stay `PENDING`.

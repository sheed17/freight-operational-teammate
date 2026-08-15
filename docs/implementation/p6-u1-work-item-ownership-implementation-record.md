# P6-U1 — The Work Item, and accountable human ownership as a mechanism

> ### **THIS IS THE IMPLEMENTER'S RECORD. IT IS EVIDENCE, NOT ACCEPTANCE.**
> It was written by the session that wrote the code, the battery and the mutation battery. Under
> [`CLAUDE.md`](../../CLAUDE.md) §11 that session may not adjudicate its own work.
>
> ### **THIS IS A CANDIDATE, NOT A LANDED CHECKPOINT — `P6-CP-1-CANDIDATE`.** The registry still
> records P6 as `execution_state: NOT_STARTED` / `checkpoint_state: NO_CHECKPOINT` and records **no**
> landed checkpoint, because `test_status_reality.py` requires every landed checkpoint to cite an
> on-disk **independent review report**, and it says in its own words that *"P4-CP-1's null review
> report is a recorded gap, not a precedent to copy"*. No such report exists yet, and this session
> may not write one. That is the precedent P5 set: its outbox and inbox were working code at
> candidate `d807261` while the registry read `NOT_STARTED`, and the fields moved only at the
> replacement commit `de526c1`, which carried its review on disk. **Candidate first; landed when
> reviewed.** **No P6 acceptance criterion is scored here**, and P6 is **not** complete. What this
> candidate owes next is named in §8.

---

## 1. What a broker can now do that they could not before

**Every unit of work Neyma holds has exactly one accountable human owner — structurally, not by
documentation.** That sentence has been [`CLAUDE.md`](../../CLAUDE.md) rule 13 since P0. Until this
checkpoint it was a sentence.

Concretely, for a brokerage:

- An obligation — *"we owe this customer an invoice for load 4471"* — **cannot come into existence
  without a named human accountable for it.** Not `system`, not "the ops team", not the last person
  who touched the load.
- That owner is a **foreign key into a record of authority**: a row somebody put there, attributed to
  the human who put it there. An owner Neyma never recorded is not a bad value — it is an
  **unspellable** one.
- **Ownership moves only by a recorded act.** Three of the fourteen transitions move it, and a test
  asserts that over the transition table rather than reviewing it.
- **Somebody leaving does not silently orphan their work.** Retiring a human is **refused** while
  they still owe this brokerage open work, and the refusal names the items so the operator reassigns
  them.
- **An obligation is never closed by silence, by a finishing pipeline, or by the word "done".**
  Closure requires a `decision_ref` that RESOLVES to an authenticated human decision.
- **An obligation that got old surfaces unprompted** — and only on a durable timer that actually
  fired, never on a caller asserting an age.
- **Reopening never rewrites history.** A short-pay three weeks later opens a new phase; the original
  closure event is byte-identical afterwards.

> ### **IT SHIPS DARK.** Nothing in the product calls it. No external effect, no checkpoint witness,
> no effect grant, no production caller — all four asserted mechanically, not announced (§6).

---

## 2. Why the two tables, and why ownership is a foreign key

`owner_id NOT NULL` is the mechanism the target spec names for **M-35 / I1** — *"Never null. Never
'the system.'"* Taken alone it is a **non-empty string check**, and a non-empty string check is
satisfied by `owner_id='system'`, by `'the ops team'`, and by whatever the caller had in hand. That
is ownership by documentation, which is the thing P6 exists to replace. So:

```
work_items(tenant, owner_id)  ->  tenant_humans(tenant, human_id)      and the owner must be ACTIVE
```

`tenant_humans` is the referent [`entities/01-work-item.md`](../specifications/entities/01-work-item.md)
point 18 already required — *"`owner_id` FK → an authenticated user of the tenant"* — and which had
nowhere to point. It is **not** user administration: [`ADR-017`](../architecture/decisions/ADR-017-tenant-and-integration-lifecycle.md)
gives users-and-roles to the web control plane at **P11**. This is the *record*, not the admin
surface.

Three properties of that record are worth stating because each is a refusal:

| Property | What it forbids |
|---|---|
| The role CHECK admits only §7's **two HUMAN roles** (`POLICY_OWNER`, `AUTHORIZED_HUMAN`) | §7's other two rows — *Automated detector* and *Agent / model* — are the two actors the architecture spends the most words forbidding from owning anything. Neither can be written into this table, therefore neither can be written into `work_items.owner_id` |
| `recorded_by_kind` is CHECK-constrained to `'human'` | If a model could record a human's authority, **the model would be choosing who may own work**, and rule 13 would be enforced against a roster the model wrote |
| A CHECK refuses non-human identities (`system`, `model`, `agent`, `detector`, …) by name | `owner_id='system'` refuses at INSERT rather than at review time |

---

## 3. The machine: the transition table is data

[`TRANSITIONS`](../../src/freight_recon/work_item.py) is the fourteen rows of
[`state-machines/01-work-item.machine.md`](../specifications/state-machines/01-work-item.machine.md)
§14, **as data**. `AC-MACH-000` enumerates it and asserts a bijection with the specification by
**EXACT SET EQUALITY of transition identifiers** — and a positive control performs a same-count
substitution and asserts the oracle rejects it, so "the oracle is a set comparison" is demonstrated
rather than claimed.

`WI-14` is `DELEGATES_TO`, and it is applied **mechanically**: its five declared targets have
`ESCALATED` added to their from-states at table-build time, they keep their own guards, and they keep
their own `producer_transition_id` — because the events registry attributes those events to
WI-3/5/6/7/12, and an event whose producer id named WI-14 would be a fact about a transition the
registry does not have. A hand-copied delegation drifts silently, because both halves stay internally
consistent.

### 3.1 Guard failure and illegal transition are different things

The registry's §2 default is precise, and collapsing the two is expensive in **both** directions:

```
(state, trigger) not in the table   ⇒ raise · persist nothing · IllegalTransitionAttempted into the
                                      outbox AND security_events, atomically, in a commit of its own
(state, trigger) in the table but a
guard is false                      ⇒ raise · persist nothing · emit NOTHING AT ALL
```

Every unmet guard becoming a security event teaches an operator to ignore security events. Every
illegal trigger filed as an ordinary refusal loses the only signal that something is driving the
machine from a state it should not be able to reach.

### 3.2 What is reused, not rebuilt

The outbox is [`event_outbox.TransactionalOutbox`](../../src/freight_recon/event_outbox.py); the
idempotency of a consumed trigger is [`event_inbox.DedupInbox`](../../src/freight_recon/event_inbox.py)
on `(tenant, consumer_id, event_id)`; the age deadline is P5's **durable timer** (M-36); the audit
backbone is the canonical event log, which is what
[`entities/17-audit-event.md`](../specifications/entities/17-audit-event.md) points 8/15/17 already
make it. **No event transport, replay, audit, timer, persistence, idempotency or PostgreSQL machinery
was duplicated.**

`decision_ref` resolution (K-1) reads the outbox directly for exactly that reason: building a second
audit store would be the second authority §5 rule 17 forbids in its own domain.

---

## 4. Defects this candidate found in its own work

> ### **STATED PLAINLY, BECAUSE A BUILD REPORT WITH NO DEFECTS IS A BUILD REPORT NOBODY LOOKED AT.**

**D-1 — the `IllegalTransitionAttempted` record was rolled back with the refusal it records.**
GR-1 requires an illegal transition to persist nothing **and** to emit the security event. Those two
cannot share a transaction, because the transaction is the one being abandoned. The first
implementation wrote the record inside it: the refusal worked, and `security_events` was **EMPTY**
after a hostile attempt. Every test that asserted only the raise passed. Fixed by abandoning the
attempt first and recording it in a commit of its own. Mutant **W3** reintroduces it.

**D-2 — a trigger for a Work Item that did not exist yet looped forever.**
With no reference resolver the inbox had nothing to check, the handler raised `UnknownWorkItem`, the
inbox rolled back **its own row** along with the failure, and the transport redelivered the same event
indefinitely. M-26 already had the answer. Fixed by supplying the resolver and the `requires` pair, so
the event parks with its arrival order, its accountable human and a TTL, and expires into an owned
problem rather than a log line.

**D-3 — the pre-commit suite was GREEN because the new guard module was still UNTRACKED.**
### **THIS IS THE SAME FALSE GREEN P5's INDEPENDENT REVIEW REJECTED A CANDIDATE FOR, reproduced
here by the same mechanism.** `test_phase2_guard_registry.guard_files()` discovers control guards
through the central inventory, and the inventory reads `git ls-files` — so while
`test_phase6_work_item.py` was untracked the classification guard could not see it and the whole
suite ran green. It went **red the moment the file was committed**, and
`scripts/finalize_status.py` **refused to write any status**. The classification entry is the fix;
the lesson is recorded beside it in the registry module rather than only here. ### **A suite run
against an untracked new guard module is not evidence about the commit that tracks it** — which is
CLAUDE.md §9's "run validation LAST, on the final tree" with a second edge nobody had written down.

**D-4 / D-5 — two mutants reported MISS, and both reports were correct about the PROBE.**
[`CLAUDE.md`](../../CLAUDE.md) §9: *"A mutation that does not reintroduce the real defect proves
nothing — verify the mutant actually misbehaves before believing a MISS."*

- **W18** removed the OCC `AND version = ?` predicate and the guard stayed green, because the test
  used a state-CHANGING interleaving that the UPDATE's *other* predicate caught on its own. Re-aimed
  at a **WI-4 self-loop**, where the state is identical on both sides and only the version predicate
  can see it — and tightened to require exactly `VersionConflict`, because a caller told to
  reload-and-retry should not receive a database constraint abort escaping through the OCC layer.
- **W16** disabled the closure-carries-a-decision trigger and the guard stayed green, because the
  table CHECK covers the NULL case. The trigger's own job is the case the CHECK **cannot see**: a
  terminal Work Item whose `closure_decision_ref` is the **blank string** — closed by a value that
  references nothing, which is precisely the hole K-1 exists to close. Asserted now.

Both guards are stronger than before, and neither was weakened to make a mutant pass.

---

## 5. Evidence

| What | Result |
|---|---|
| [`test_phase6_work_item.py`](../../eval/tests/test_phase6_work_item.py) | **178 nodes, all passing** |
| Canonical suite, whole tree | see the status block in [`CURRENT.md`](CURRENT.md) — volatile figures live there only |
| [`mutate_phase6_work_item.py`](../../scripts/mutate_phase6_work_item.py) | ### **27 / 27 mutants caught**, byte-exact restoration verified per case |
| Illegal-transition sweep | 7 states × 13 triggers = **91 pairs**; **27 legal**, **64 illegal**, every illegal pair driven to a real Work Item in that state |
| `AC-MACH-000` | exact-set bijection with §14's fourteen identifiers, plus a positive control proving a same-count substitution FAILS |
| Product Driver | **ACCEPT** — see §7 |

**The denominators are printed, not implied.** The specification parser asserts it found exactly 14
rows before any comparison is made; the illegal sweep asserts the 91/27/64 split rather than only the
remainder; the ownerless detector is proven over a population of three real items **and** proven able
to fail by breaking a row directly.

---

## 6. The dark posture, measured

| Claim | How it is established |
|---|---|
| No production caller | An AST scan of `src/freight_recon/` and `scripts/` requires the importer set of `work_item.py` to be **EMPTY**. Discovered, never enumerated |
| Cannot reach an effect | M1's **transitive import closure** reaches no effect-capable module, walked over every import spelling — relative, absolute, plain and `importlib.import_module`. [`CLAUDE.md`](../../CLAUDE.md) §9 lists that blind spot as a repeat offender in this repository |
| Mints nothing | Driving **every one of the seven reachable states** leaves `checkpoint_witnesses`, `effect_grants` and `brakes` unchanged, counted against real tables |
| Tenant boundary | Every ownership, decision, timer and transition case runs `T_A`/`T_B`. A `T_B` trigger never moves a `T_A` machine, and the machine does **not** read across the boundary to establish whether an item exists elsewhere — [C-1] rejects a cross-tenant question rather than answering it carefully |

---

## 7. What the Product Driver did

Per [`CLAUDE.md`](../../CLAUDE.md) §13.6 the driver was pointed at **code that runs**, not at a plan.
It operated the machine through a brokerage narrative — load 4471 delivered, billed, aged, handed
over, the owner offboarded, paid, closed, then short-paid and reopened — with the hostile attempts
inline. **27 behaviours as specified, 0 wrong.** The evaluator returned **ACCEPT**.

Two things about that run are worth recording honestly:

- **Its one FIX was against the SCENARIO, not the product.** A probe asked for schema readiness on a
  connection where `PRAGMA foreign_keys` was off; the readiness oracle correctly answered *"every
  tenant-consistent foreign key is decoration"*. That was the oracle working. The probe now builds
  the database the way `WorkflowStore` does.
- **The evaluator made the same scoping point this record makes:** only M1 was exercised. P6's
  Pipeline Instance and the remaining twelve machines still need their own evidence.

The driver's narrative probe lives in the **driver** repository, not in Neyma — a demonstration script
committed here would be the first production caller of a capability that is not supposed to have one,
and would turn the dark-posture guard red.

> **The Product Driver's ACCEPT is an independent judgement of observed PRODUCT behaviour. It is not
> the targeted independent engineering review this candidate owes.**

---

## 8. What this candidate owes, and what P6 still owes

### It owes a review it may not perform on itself

A **fresh targeted independent review** by a session that neither implemented nor remediated this
candidate, and then a **separate adjudication**. Only then may `execution_state` become
`IN_PROGRESS`, `checkpoint_state` leave `NO_CHECKPOINT`, and this record become a
`landed_checkpoints` entry citing the report. No P6 acceptance criterion is scored here and none
may be.

### P6 is not complete

`foundational-machine-acceptance.md` requires **100% of the 134 legal transitions** across **13
machines**. This candidate builds **14 transitions on one machine**. Still owed:

- the **Pipeline Instance** (M2, 25 transitions) — the durable reservation, and the natural next unit
  because everything downstream depends on an owned unit of work having attempts;
- **M3–M13** — the remaining 95 transitions;
- **`AC-EVT-003`** (P5's `IR-R8`) — *every producer transition emits its required event in the
  transition's own commit* — which discharges only when all 134 land. M1's fourteen satisfy it for
  M1, and that is not the same thing.

### Recorded, not actioned

`P6-D1` … `P6-D7` are in this unit's `residual_risks_carried_forward` block in
[`IMPLEMENTATION-REGISTRY.yaml`](IMPLEMENTATION-REGISTRY.yaml), each with its severity and why it is
nonblocking. Per [`CLAUDE.md`](../../CLAUDE.md) §13.3 **the debt row is the deliverable** for these,
and it is a complete one.

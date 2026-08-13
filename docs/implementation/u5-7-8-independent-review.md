# P5 U5.7 + U5.8 — independent review report

> ### **HISTORICAL — NOT CURRENT AUTHORITY.** This review's verdict, **REJECT**, is about content
> commit `d807261`, which was **REPLACED** and is preserved unmodified at
> `refs/preserve/p5-u57-rejected-candidate-d807261`. Both material defects it found were remediated
> in the replacement candidate, and the canonical suite is green there. **Do not read the REJECT as
> the current state of U5.7+U5.8.** What remains live from this document is the list of seven
> nonblocking residuals and the checkpoint ruling, both of which the replacement acted on.

Transcribed by the campaign controller from the reviewer's return; subagents cannot write files. The
reviewer built nothing and remediated nothing. It reviewed content commit `d807261`. All mutation
work was done in `git archive` extracts and throwaway clones under `/private/tmp`.

## VERDICT ON `d807261`: REJECT (material defect)

> *"The runtime engineering is strong and survived everything I threw at it. The rejection is **not**
> about the outbox or inbox mechanism — it is that the candidate leaves the canonical suite **red**,
> and the commit message asserts it green. Remediation is roughly four lines."*

Both material defects were remediated in the replacement candidate this document accompanies, and the
full canonical suite is **2267 passed / 0 failed / 3 skipped** at the remediated tree.

### D1 — the canonical suite was RED at `d807261`, and the claimed evidence was false

```
2 failed, 2267 passed, 1 skipped in 396.93s
FAILED eval/tests/test_false_green_defenses.py::test_no_control_guard_hand_enumerates_a_file_population
FAILED eval/tests/test_phase2_guard_registry.py::test_every_guard_file_is_classified
```

Both introduced by that commit; both pass at its parent `19c8764`.

**Root cause, established mechanically.** `eval/control/inventory.py:48` discovers the control-guard
population from `git ls-files`. In a throwaway clone at `d807261`,
`git rm --cached eval/tests/test_phase5_event_transport.py` — file left on disk, byte-identical —
turns both failures into passes. The builder's validating run therefore happened while the new test
module was still **untracked**, i.e. not against the committed tree. This is exactly the class of
false green the repository's U-HANDOFF-1C defenses exist to catch, and they caught it.

**Remediated:** the module is registered in `GUARD_REGISTRY` with a classification and reason, and the
hand-enumerated module list at `test_phase5_event_transport.py:1372` was replaced with **discovery**
(`src.glob("event_*.py")` plus the phase-5 migration, with a population floor) rather than a
`FIXED-SPECIFICATION` annotation — a hand-typed list would silently stop covering a fifth transport
module the moment one is added, which is the decay H-6 exists to prevent.

### D2 — the registry described enforcement that does not exist

`IMPLEMENTATION-REGISTRY.yaml:1871` recorded *"the partial UNIQUE strict-order index over the five
families"*, and the review-surface note at `:1913` asked the reviewer to check whether that index
asserts one event per `(tenant, aggregate, version)`. **There is no such index** — the build replaced
it with `trg_event_outbox_strict_version_owner` and explained why at length in the commit message;
the registry entry was never updated. `event_envelope.py:89-90` carried the same stale claim.

**Remediated** in all three places, with the reviewer-attack note rewritten to record the *answer*
rather than re-pose the question.

## What the reviewer attacked, and what held

**Atomicity.** `emit` refuses outside an open transaction, including on an `isolation_level=None`
connection; with an explicit `BEGIN IMMEDIATE` on that same connection, rollback leaves zero rows. No
bypass parameter exists (AST-verified; `emit`'s signature is `(self, envelope)`). Both crash windows
leave neither write.

**Idempotency.** The same `event_id` from a different `consumer_id` correctly does **not** dedup.
Redelivery is `DUPLICATE_NOOP` with a byte-identical digest and an unmoved state digest, across a real
process restart.

**Ordering — the trigger.** It enforces what it claims: two different `producer_transition_id`s at one
`(tenant, aggregate_type, aggregate_id, aggregate_version)` in a strict family aborts; the real EF-2
`GrantClaimed` + `EffectAttempted` pair inserts; order-tolerant families are untouched; the trigger is
correctly tenant-scoped. The inbox mirror is genuinely fixed: a strict co-emitted sibling at
`== applied_version` is applied, not discarded, and gap-parking plus drain reassembles 1,2,3 in order
regardless of arrival order.

**Tenant isolation.** A cross-tenant event yields `REJECTED_CROSS_TENANT`, zero handler calls, zero
rows across `event_inbox` / `pending_references` / `inbox_aggregate_cursor`, and an unchanged state
digest.

**Concurrency, with real threads.** 6 emitter threads × 10 emits on separate connections: 60 rows,
sequences unique and contiguous `1..60`, zero errors. 4 concurrent relays draining one outbox: 60
deliveries, 60 distinct events, **zero duplicates**, no out-of-order delivery within any aggregate,
nothing left PENDING.

**Migration.** Dry-run → apply → rerun is idempotent. A migrated database's `sqlite_master` is
**byte-identical** to a fresh one. A partially-applied migration is reported by the readiness oracle
and repaired by re-running.

**Production dark.** No default sink, no adapter or network imports, zero witnesses and zero grants
after consuming, `GateRegistry` constructed nowhere in `src/`.

**Are the 133 tests real?** Ten protected rules neutered in extracts; **nine went red** — transaction
requirement (1F), dedup key (6F), tenant check (2F), strict-version trigger (2F), the strict-stale
mirror bug (2F), handler-outside-transaction (20F), default sink (1F), append-only triggers (7F),
mark-published-before-publish (4F).

## Nonblocking residuals — recorded, not actioned

1. **A rule the tests do not cover.** Relaxing whole-aggregate exclusivity in `_claim`
   (`HAVING SUM(...) = 0` → `>= 0`, `event_outbox.py:457`) survived all 133 nodes. The rule *is*
   load-bearing — with an aggregate partially leased, the mutant delivers v2 before v1 while base
   correctly withholds. One node with a partially-leased aggregate would close it.
2. **A handler that commits leaves an `APPLIED` inbox row for a failed consumption**, so the event is
   permanently lost. Requires a handler to violate a documented prohibition, and no consumer exists
   yet. `test_a_handler_that_commits_is_a_defect_the_inbox_surfaces` asserts only the raise, not the
   row. A `conn.in_transaction` check after `handler(event)` would make it structural.
3. **Redelivery of an EXPIRED park silently vanishes** — `_park_locked`'s `ON CONFLICT DO UPDATE` only
   bumps `attempts`, leaving `park_state` `EXPIRED`, so it can never drain. The reported outcome is
   false. Mitigated by expiry already having handed the park to an owner.
4. **The strict trigger enforces same-version ownership but not monotonicity.** A different transition
   emitting v3 after v5 inserts cleanly and the inbox applies it. The fix is complete for the claim
   made; the residual moves to the producer.
5. `_drain_for` can raise out of `consume()` after the original event committed `APPLIED`.
6. `OutboxRelay.drain` returns a `RelayResult` with `claimed`/`aggregates` dropped. Cosmetic.
7. `ev_v1` lowercases enum names where §1 says "enums by name". Flagged, not adjudicated.

## Ruling on the checkpoint

**Land `P5-CP-1`; flip `execution_state` `NOT_STARTED` → `IN_PROGRESS`.** The U5.1/U5.2 precedent does
not carry: the registry grounds `NOT_STARTED` on a stated predicate — *"has work actually landed
INSIDE this phase?"* — which held while U5.1 and U5.2 touched specification and control only, and is
now false. Leaving it converts a correct record into the live-falsehood defect the registry cites
against itself twice. The two fields move together, since `execution_state NOT_STARTED` forbids any
`landed_checkpoints` entry.

Required: `checkpoint_state: CHECKPOINT_ACCEPTED_FOR_CONTINUATION` (**not** phase acceptance, zero
criteria scored), an on-disk `implementer_evidence` path, an on-disk `independent_review_report` path
— *"`P4-CP-1` carries `independent_review_report: null` with an apologetic note; do not repeat that
here"* — and a canonical suite receipt showing green at the remediated commit.

## What the reviewer did not verify

The 105 event contracts, payload schemas, upcasters, GC-1, replay sandbox, PostgreSQL — all out of
scope. `ev_v1`'s divergence from `fp_v1` against ADR-005 §3.4 / registry §1 (read the reasoning, found
it coherent, did not diff it against the specifications). OS-level crash consistency (fsync / power
loss) — all crash tests are process-level rollback. Whether `ex_v1`'s appending of `event_name` to §4's
four-field identity is a correction or a weakening. `IMPLEMENTATION-SURFACE.yaml`, `CURRENT.md`,
`LEGACY-DISPOSITION.md` and `TEST-NODE-MANIFEST.json` beyond the cited registry lines.

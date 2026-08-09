# NEYMA P5 U5.1 — REPLACEMENT CANDIDATE `1ae365a`: TARGETED GOVERNANCE RE-ADJUDICATION

**Replacement content candidate `1ae365aee76d89ebdc78bbb619a4db8b778a1cad` (tree
`0e52a61c6bef77df42610fa8ea9d142092b4f021`) over certified predecessor
`6e8127dab02e3443183d06825836f5a805f53de0`, on branch `p5/u5-1-g2-spec-correction`.**

Replacement for **REJECTED** candidate `38b4bda6cb3ea6c5e5c9a302fd64d23450e6fc62`.

Adjudicating the fresh independent review that returned **REJECT — TARGETED REMEDIATION REQUIRED**.

Written outside the product branch and tree. No product commit. No amend. No ref created, moved or
deleted. No finalizer. No remediation. The candidate was not modified. No event was minted. No P5 unit
was begun.

---

## VERDICT

> ### **REJECT — TARGETED REMEDIATION REQUIRED**
>
> **Both blocking findings are UPHELD. I reproduced both end-to-end, independently, in a git-backed
> `--no-local` clone, and both returned `53 passed / 0 failed` — byte-identical to the unmutated
> baseline in the same environment. Zero mutation-attributable failures in either case.**
>
> **Three rulings materially change the shape of the finding:**
>
> 1. ### **R-01 and R-02 are ONE defect, not two.** `_declared_cocommit_machines` reduces a
>    structured co-commit declaration to a set of machine integers, discarding the state token that
>    names the counterpart row. 4(a) therefore binds **machine-to-machine in both directions**, so
>    every row on machine `M` inherits every co-commit declaration any row on `M`'s partner machine
>    ever wrote. R-01 is the intra-class manifestation (existing consumers exchange partners); R-02 is
>    the cross-class manifestation (an `EVENT_REQUIRED` row **annexes a declaration written for a
>    different row**). **One predicate closes both.**
>
> 2. ### **R-01's magnitude is 23, not 120.** The exhaustive matrix is **23 false-accepting
>    (consumer, event) pairs across the 8 durable consumers, with 0 false rejects.** The number 120
>    is the total across all **9** consumers, of which **97 are `RU-3`'s** — the zero-durable-write
>    row that the review's own §3.2 table shows at 98 accepts and that its prose then claims to
>    exclude. The arithmetic is right; the attribution is wrong. This **narrows R-01 roughly fivefold
>    and does not overturn it**: 23 > 0, and the 23 include the exact `PL-10`/`PL-11` exchange.
>
> 3. ### **The remediation is smaller than the review supposed: guard and test work only.** The
>    complete owner-identifying datum is **already present in all twenty co-commit declarations** —
>    no specification data need change, no event is minted, the frozen 98 is untouched. Binding on
>    `(machine, To-state)` bidirectionally accepts **every** current valid consumer with **zero false
>    rejects** and closes **both** reproduced exploits and every other confirmed exploit class except
>    one, whose root cause lies in `events/registry.md` §3 — a **frozen, forbidden surface** — and
>    which is therefore an **explicitly justified carried residual, not a blocker**.
>
> ### **U5.1 is GUARD-BLOCKED, not FOUNDER-BLOCKED. The reviewer's classification is CONFIRMED.**
> No founder or architect decision is required. The founder/architect gate stays exactly where G2
> placed it: the seven event names, `AP-9`'s emit-vs-derive among them.
>
> **Topology: OPTION A** — preserve `1ae365a`, replace it in place with one corrected candidate whose
> sole parent is `6e8127d`. Verified from `PROGRESS-PROTOCOL.md`:198–201 and from the P4/R-07
> precedent by direct object inspection. **`1ae365a` MAY NOT proceed to the U5.1 finalizer.**

---

## A. SESSION INDEPENDENCE

A **fresh targeted re-adjudicator**. Did **not**: implement P4; participate in the P4/R-07 campaign;
perform the G2 architecture adjudication; build `38b4bda`; review or adjudicate `38b4bda`; build
`1ae365a`; perform the independent review of `1ae365a`. Resumed **no** previous Claude session.

Performed no remediation, no finalization, no event minting, no further P5 work. Did not modify the
candidate, the product branch, any ref, `driver.config.yaml`, the Product Driver configuration, or the
Desktop repository. All mutation testing was confined to a disposable `--no-local` clone and a
`git archive` tree export in the session scratchpad, outside both repositories.

The replacement-builder handoff and the independent review were both treated as **untrusted
testimony**. Every controlling claim below was re-derived from Git objects, from repository authority,
or by execution against the candidate's own guard.

**The Product Driver `max_content_commits=7` was NOT used.** Per the prior adjudication §15 and G2 §K
it is a `_CONTENT_COUNT_RE` defect reading the `07` of *"R-07 content commit"* as a cardinal. Topology
below is judged from Git objects and `PROGRESS-PROTOCOL.md` only.

---

## B. IDENTITY — RESOLVED MECHANICALLY BEFORE SUBSTANTIVE ADJUDICATION

| Property | Required | Observed | Result |
|---|---|---|---|
| HEAD | `1ae365ae…` | `1ae365aee76d89ebdc78bbb619a4db8b778a1cad` | ✅ |
| Tree | `0e52a61c…` | `0e52a61c6bef77df42610fa8ea9d142092b4f021` | ✅ |
| Parent | exactly `6e8127d` | `6e8127dab02e3443183d06825836f5a805f53de0` | ✅ |
| Parent count | 1, not a merge | `git rev-list --parents -n1` → one parent | ✅ |
| Descendant of `38b4bda`? | **NO** | `git merge-base --is-ancestor 38b4bda HEAD` → **false** | ✅ |
| Content commits above `6e8127d` | exactly 1 | **1** | ✅ |
| Branch | `p5/u5-1-g2-spec-correction` | same; HEAD is the candidate | ✅ |
| No finalizer run | none | `git rev-list 1ae365a..branch` → **0**; receipts still bind `a31a94a` | ✅ |
| No subsequent P5 content | none | reflog `@{0}` is the candidate commit | ✅ |
| Nothing pushed | no remote P5 ref | **0** `p5/` refs under `refs/remotes` | ✅ |
| `main` / `origin/main` | unmoved | both `152574e4f4f2969468c9d31b1e705188896175b5` | ✅ |
| `p4/adapter-containment-completion` | `6e8127d` | `6e8127dab02e3443183d06825836f5a805f53de0` | ✅ |
| `refs/preserve/p5-u51-prestate-6e8127d` | unmoved | `e77ab673021831ff71fb7f74c58c88fce8b377c3` | ✅ |
| Total refs | 72 | **72** | ✅ |
| Untracked set | the two authorized F-04 artifacts | exactly those two | ✅ |
| **Index digest** | — | `ba83298a04abd2bdb2496470ec0d6d6a4560e0daa6df47fda0a86a9f5a2a5e73` | ✅ |
| **Worktree-status digest** | — | `2babbc0cce82e8374d038244574325e32d9bc7e9e2f208f57ee0293a1bf9cac0` | ✅ |

> ### **Both digests match the values the independent review recorded, byte for byte.** The index and
> ### worktree state are unchanged since the review. Nothing moved between the two sessions.

**Identity confirmed. Re-adjudication proceeds.**

### Controlling-evidence digests — verified before reliance

| Document | Expected | Recomputed | Result |
|---|---|---|---|
| Targeted adjudication of `38b4bda` | `bc120883f09bd67ed0fd80da48c8aa589e8e4b125db16c7f6872378713d9bf6e` | identical | ✅ |
| Fresh independent review of `1ae365a` | `ebaefaa1945ec87fc4810265f2219f07cf98306e1a4713fe41cfa47e32ec5533` | identical | ✅ |
| Replacement-builder handoff (located mechanically) | `c86d7a6f99f735a0af59a131422ac8f986bd554ffe2088e130fed38c53ae3e64` | identical | ✅ |
| Independent review of `38b4bda` | `27906bcec34bc7e660ed27d84f5cdcdf6be37ef436b113eb564c048e293f8a43` | identical | ✅ |

Review verdict as received: **REJECT — TARGETED REMEDIATION REQUIRED**. ✅ Matches.

**Replacement-builder handoff located mechanically** at
`.driver-state/handoffs/p5-u51-g2-spec-correction-replacement-candidate-1ae365a.md`.

---

## C. REJECTED-CANDIDATE PRESERVATION — VERIFIED INDEPENDENTLY

| Ref | Object | Result |
|---|---|---|
| `refs/heads/archive/p5/u51-rejected-38b4bda` | `38b4bda6…` | ✅ |
| `refs/preserve/p5-u51-rejected-candidate-38b4bda` | `38b4bda6…` | ✅ |
| `refs/preserve/p5-u51-rejected-worktree-38b4bda` | `863b6e86…` | ✅ |
| `refs/preserve/p5-u51-rejected-candidate-targeted-review-38b4bda` | `fe20030a…` | ✅ |
| `refs/preserve/p5-u51-rejected-candidate-targeted-adjudication-38b4bda` | `f2626d71…` | ✅ |
| `refs/preserve/p5-u51-prestate-6e8127d` | `e77ab673…` | ✅ unmoved |

`1ae365a` is **not** a descendant of `38b4bda`, so the rejected candidate's review and adjudication
remain attributable **only to `38b4bda`**. Preservation is complete and matches the P4/R-07 protocol.

---

## D. RATIFIED POSITIVES — REVERIFIED, NOT ACCEPTED ON TESTIMONY

Every item below was re-derived by this session. **None is reopened.**

| Claim | This session's verification | Result |
|---|---|---|
| Exact class membership | own parser over the candidate's own `_g2_state()`: `PRODUCER 110 · CONSUMES 9 · NON_PRODUCING 6 · DELEGATES_TO 2 · EVENT_REQUIRED 7 = 134`, **zero classifier errors** | ✅ |
| `PL-15x` / `IB-5x` → `NON_PRODUCING` | both classified `NON_PRODUCING`; `IllegalTransitionAttempted` is rule-owned by `GR-1`, so rule 3 refuses them | ✅ |
| Event registry byte-unchanged | `docs/specifications/events/registry.md` tree object `6133927c…` at **both** refs | ✅ |
| Canonical event count | **98** owned (F1–F13); 111 F1–F14 contracts | ✅ |
| `state-machines/registry.md` byte-unchanged | `76cff142…` at both refs | ✅ |
| `src/` byte-identical | `0204261b…` at both refs | ✅ |
| `scripts/` `configs/` `data/` `docs/architecture/` `docs/specifications/acceptance/` | tree-object identical at both refs | ✅ |
| `PROGRAM-WEIGHTS.yaml`, `phase-0-baseline-manifest.yaml`, `SUITE-RESULT.json`, `GATE-RESULT.json` | byte-identical; receipts still bind `a31a94a` | ✅ |
| Delta scope | 23 paths, **all `M`**, zero added, zero deleted; set difference against the allowed prefixes is **empty** | ✅ |
| P5 acceptance contract | `units[8].acceptance_criteria`: **14 criteria · Σ weights exactly 100 · all `PENDING` · verbatim ORDERED match** to `PROGRAM-WEIGHTS.yaml` `acceptance_template` | ✅ |
| P4 COMPLETE / R-07 CONTAINED | `CURRENT.md` records both; `phase-0-baseline-manifest.yaml` byte-unchanged | ✅ |
| Production `GateRegistry` EMPTY | **zero** `GateRegistry(` constructions across `src/` + `scripts/` | ✅ |
| Seven founder-gated obligations | exactly `PL-7a`, `AP-9`, `CF-7`, `EC-7`, `PO-2`, `PO-3`, `RU-8`; `open_founder_gated_obligations: 7`; status `G2_PARTIALLY_DISCHARGED_FOUNDER_GATED` | ✅ |
| `TEST-NODE-MANIFEST` | `6e8127d` 2073 → `38b4bda` 2091 → `1ae365a` **2102**; `node_count == len == len(set)` at all three | ✅ |
| Both `AP-9` exploits fail closed | `AP-9→ApprovalConsumed` cites 4(b)+4(c)+4(a)+4(d); `AP-9→BrakeReleased` cites 4(a)+4(d) | ✅ |
| **Canonical suite** | own `--no-local` clone at `1ae365a`, fresh in-repo `.venv`, `pip install -e ".[dev]"`, `-c pytest-canonical.ini`, `PYTEST_ADDOPTS` cleared: ### **2101 passed · 1 skipped · 0 failed** (400s) | ✅ |
| G2 guard block | **53 passed / 0 failed** in a git-backed clone | ✅ |

> **Disclosure.** My first full-suite run reported 4 failures. All four were **my own harness
> deviation**: `test_mailbox_intake_cli_smoke` and `test_mailbox_workflow_cli_smoke` invoke
> `<repo>/.venv/bin/python` by absolute path, and I had placed the venv outside the clone. Re-run with
> an in-repo `.venv` per the canonical procedure: **2101 passed, 1 skipped, 0 failed.** The builder's
> and the reviewer's suite claims are **exactly reproduced**. No candidate-attributable failure exists.

---

## E. THE CONTRACT AS ACTUALLY WRITTEN — CLAUSE-BY-CLAUSE

The repository does **not** use the adjudication's `4(a)–(d)` numbering. `TRANSITION-EVENT-AUDIT.yaml`
`consumes_valid.rules` uses `1`, `2`, `3_owner_is_a_transition`, `4_zero_write_is_descriptive_only`,
`5a`–`5d`, `6_downgrade_prohibition`, `7_fail_closed`. **The repository's terminology is used below**;
the adjudication's `4(a)–(d)` maps to `5a`–`5d`, its rule 5 to `6_downgrade_prohibition`, its rule 6 to
`7_fail_closed`.

Implementation: `eval/tests/test_bootstrap_hermeticity.py:544` `_consumes_relationship_errors`.

| Clause | What it PROVES | What it FAILS to prove | Necessary? | Sufficient? | Vacuous for a class? |
|---|---|---|---|---|---|
| **1** event exists | the name is in the §3 corpus | nothing relational | yes | no | no |
| **2** not self-owned | `T` ∉ producers(`E`) | nothing relational | yes | no | no |
| **3** owner is a transition | every §3 owner resolves to a corpus row | which row it is | yes | no | no |
| **4** zero-write descriptive | `GR-2` does not bind | — (correctly exempts nothing) | yes | n/a | n/a — it *is* the exemption-free case |
| **5a** co-commit bidirectional | `M(owner) ∈ declared(T)` **and** `M(T) ∈ declared(owner)` | ### **WHICH ROW on that machine.** Only two integers are ever compared | ### **yes — and it is the load-bearing clause** | ### **NO** | never vacuous, but ### **satisfiable VICARIOUSLY** — see §F |
| **5b** not mutually exclusive | not same-machine, From-intersecting, To-divergent | anything cross-machine | yes | no | ### **vacuous for EVERY legitimate consumer** — 5c forces cross-machine, and 5b returns `False` immediately when machines differ. It is a pure anti-`AP-9` guard |
| **5c** cross-machine | `M(T) ≠ M(owner)` | which row | yes | no | no |
| **5d** replay coverage | declared fields ⊆ ∪ consumed payloads | ### nothing at all when the row declares **no field** | yes | no | ### **STRUCTURALLY VACUOUS for durable-by-state-transition rows** |

### 5d's vacuity class — mechanically characterised

`_durable_write` (line 335) returns `True` when `To ∖ From ≠ ∅` **or** `Writes` is non-bare.
`_declared_write_fields` (line 479) reads only backticked declarations and `name=value` assignments in
the pre-`co-commit` segment. A row that is durable **by state transition** and whose `Writes` cell is
`—` or prose therefore contributes `∅` fields, so `missing = ∅ − covered = ∅` **unconditionally**.

**Verified by exhaustive evaluation — 5d never engages for 4 of the 8 durable consumers:**

| Consumer | `Writes` (pre-co-commit segment) | Fields 5d reads | 5d engages? |
|---|---|---|---|
| `PL-6` | *(empty)* | ∅ | ### **NO** |
| `PL-9` | *(empty)* | ∅ | ### **NO** |
| `PL-10` | `ext: **the world was touched**` (prose) | ∅ | ### **NO** |
| `PL-11` | *(empty)* | ∅ | ### **NO** |
| `PL-10f` | `` `failure_proof` `` | `{failure_proof}` | yes |
| `PL-10u` | `` `exposure,unknown_reason` `` | `{exposure, unknown_reason}` | yes |
| `PL-11c` | `` `unknown_reason` `` | `{unknown_reason}` | yes |
| `PL-15` | `` `decision_ref` `` | `{decision_ref}` | yes |

> ### **5d is vacuous for precisely the rows GR-2 most needs it for — the ones whose entire durable
> ### write IS the state change.** And it is vacuous for `PL-7a` after laundering, which is why R-02
> ### works.

**The review's characterisation of both clauses is correct and is UPHELD.**

---

## F. R-01 AND R-02 ARE ONE DEFECT — THE CENTRAL RULING

The review presents R-02 as *"a second independent defect."* **It is not.** Both are consequences of a
single line:

```python
def _declared_cocommit_machines(cell: str) -> set[int]:                 # line 473
    return {int(n) for n in _MACHINE_TOKEN.findall(_writes_segments(cell)[1])}
```

The declaration `` co-commit M3 `ATTEMPTED` `` is reduced to `{3}`. The state token — which names
**which row on M3** — is discarded. Consequently:

> ### **A co-commit declaration is not owned by the row that wrote it. It is pooled across the whole
> ### machine. Every row on machine `M` inherits every declaration any row on `M`'s partner machine
> ### ever wrote.**

That single property produces both findings:

| | Manifestation | Mechanism |
|---|---|---|
| **R-01** | *intra-class* — two existing consumers exchange partners | both are M2 rows, both partners are M3 rows; the pooled `{3}` / `{2}` sets are unchanged by the exchange |
| **R-02** | *cross-class* — an `EVENT_REQUIRED` row is laundered into `CONSUMES` | `PL-7a` supplies its own forward token; the **reverse** leg is satisfied by `EF-3`'s `` co-commit M2 `EXECUTED` `` — a declaration **written for `PL-10`'s benefit** and annexed by `PL-7a` |

**This is the precise answer to R-02 Question A.** The guard does **not** positively prove eligibility
to consume. It proves that the newly claimed relationship is **locally well-formed** — a machine
integer appears in a co-commit segment. That is **syntax validity**. **Architectural eligibility** —
that this consumer and this producer are the two legs of one authorized semantic operation — is never
established, because the only row-specific evidence in the whole check is **authored by the candidate
row itself**. `5a` is nominally bidirectional; at row granularity it is **not**, because the reverse
leg can be discharged vicariously by a sibling.

> ### **That is the circularity the brief warned against: under the shipped guard, the same candidate
> ### row both asserts and supplies the only row-specific proof of its own exemption.**

**One predicate closes both. The remediation contract in §M reflects that.**

---

## G. R-01 — RULING

> ### **UPHELD. CONFIRMED DEFECT. HIGH. BLOCKING. Magnitude corrected 120 → 23.**

### G.1 `PL-10` ⇄ `PL-11` — reproduced end-to-end (R-01 Question C)

Coordinated spec + audit mutation in a disposable `--no-local` git-backed clone at `1ae365a`:

```
02-pipeline-instance.machine.md   PL-10 Event: `EffectExecuted` — `CONSUMES:EffectExecuted`
                                            →  `EffectVerified` — `CONSUMES:EffectVerified`
                                  PL-11 Event: `EffectVerified` — `CONSUMES:EffectVerified`
                                            →  `EffectExecuted` — `CONSUMES:EffectExecuted`
TRANSITION-EVENT-AUDIT.yaml       PL-10: consumes [EffectVerified], owner [EF-4]
                                  PL-11: consumes [EffectExecuted], owner [EF-3]
```

| Measurement | Result |
|---|---|
| Class totals before / after | **110 / 9 / 6 / 2 / 7 = 134** — identical |
| Class **membership** before / after | **identical** |
| Classifier errors | **0** both sides — the declarations are well-formed, simply false |
| G2 guard block, unmutated baseline | ### **53 passed, 0 failed** |
| G2 guard block, mutated | ### **53 passed, 0 failed** |
| **Mutation-attributable failures** | ### **ZERO** |

*(My baseline is a clean 53/0 because I used a git-backed clone; the review's tree copy produced two
environmental failures on both sides. The comparison is sound in both cases; mine is sharper.)*

### Per-row analysis as the brief requires

| Field | `PL-10` mutated | `PL-11` mutated |
|---|---|---|
| Consumer | `02-pipeline-instance:PL-10` `` `CLAIMED` → `EXECUTED` `` | `02-pipeline-instance:PL-11` `` `EXECUTED` → `VERIFIED` `` |
| Claimed event | `EffectVerified` | `EffectExecuted` |
| Candidate-resolved §3 owner | `EF-4` | `EF-3` |
| Owner machine | M3 | M3 |
| Owner row / token | `EF-4` `` `ATTEMPTED` → `VERIFIED` ``; declares `` co-commit … + M2 `VERIFIED` `` | `EF-3` `` `CLAIMED` → `ATTEMPTED` ``; declares `` co-commit M2 `EXECUTED` `` |
| Consumer's own declaration | `` co-commit M3 `ATTEMPTED` `` | `` co-commit M3 `VERIFIED` `` |
| **Why the relation is FALSE** | `PL-10` certifies its durable write is recorded by an event emitted at `EF-4`, a **later** pipeline moment. A full-history replay reconstructs `EXECUTED` from an event that fires after verification. | Converse: `PL-11` certifies `VERIFIED` is recorded by `EffectExecuted`, emitted at `EF-3`, **before** any readback exists. |
| **Why the candidate accepts it** | 5a forward: `3 ∈ {3}` ✅ (the state token `ATTEMPTED` vs `EF-4`'s `VERIFIED` is discarded). 5a reverse: `2 ∈ {2}` ✅ (`EF-4`'s `VERIFIED` vs `PL-10`'s `EXECUTED` discarded). 5b silent (cross-machine). 5c ✅. **5d vacuous — `PL-10` declares no field.** | Identical, mirrored. |
| Both rows counted **GR-2 discharged** | ✅ by `test_every_durable_write_is_recorded_by_an_event_or_a_registered_open_obligation` | ✅ |

### G.2 The exhaustive matrix (R-01 Question D) — constructed from the repository

Every one of the **9** `CONSUMES` rows evaluated against every one of the **111** F1–F14 canonical
contracts, using the candidate's own `_consumes_relationship_errors` under its own
`_consumes_context` — 999 evaluations. Ground truth = the declared relationship set, plus any pair
whose §3 owner set is contained in the consumer's genuine co-transition partners.

| Consumer | Durable | 5d fields | co-commit `(M, state)` as written | Current accepts | ### Current FALSE ACCEPTS |
|---|---|---|---|---|---|
| `PL-6` | yes | — | `(4, REQUESTED)` | 1 | **0** *(tight only by accident — M4 has one qualifying owner)* |
| `PL-9` | yes | — | `(3, CLAIMED)`, `(4, —)` | 9 | ### **8** |
| `PL-10` | yes | — | `(3, ATTEMPTED)` | 8 | ### **7** |
| `PL-10f` | yes | `failure_proof` | `(3, FAILED)` | 1 | **0** |
| `PL-10u` | yes | `exposure`,`unknown_reason` | `(3, UNKNOWN_OUTCOME)` | 1 | **0** |
| `PL-11` | yes | — | `(3, VERIFIED)` | 8 | ### **7** |
| `PL-11c` | yes | `unknown_reason` | `(3, UNKNOWN_OUTCOME)` | 3 | **1** |
| `PL-15` | yes | `decision_ref` | `(3, VERIFIED)`, `(3, FAILED)`, `(10, COMPLETED)` | 1 | **0** |
| `12-rule:RU-3` | ### **no** | n/a | — | 98 | *(97 — rule **4**, descriptive, exempts nothing; **correct**)* |

```
CURRENT GUARD, 8 DURABLE CONSUMERS   true accepts 12 · true rejects 853 · FALSE ACCEPTS 23 · false rejects 0
CURRENT GUARD, ALL 9 CONSUMERS       FALSE ACCEPTS 120   (= 23 durable + 97 from RU-3's rule-4 exemption)
```

**Itemised false accepts (durable consumers only):**

| Consumer (declares) | Falsely accepted |
|---|---|
| `PL-10` (`EffectExecuted`) | `EffectAttempted`, `EffectFailed`, **`EffectVerified`**, `GrantClaimed`, `OutcomeUnknown`, `VerificationConflict`, `VerificationUnavailable` |
| `PL-11` (`EffectVerified`) | `EffectAttempted`, **`EffectExecuted`**, `EffectFailed`, `GrantClaimed`, `OutcomeUnknown`, `VerificationConflict`, `VerificationUnavailable` |
| `PL-9` (`GrantClaimed`) | `ApprovalRequested`, `EffectAttempted`, `EffectExecuted`, `EffectFailed`, `EffectVerified`, `OutcomeUnknown`, `VerificationConflict`, `VerificationUnavailable` |
| `PL-11c` (`VerificationConflict`,`VerificationUnavailable`) | `OutcomeUnknown` |

> ### **RULING ON THE NUMBER 120.** The review states *"120 false-accepting (consumer, event) pairs
> ### in total across the durable consumers, excluding `RU-3`'s correct zero-write case."* The figure
> ### is the total across **all nine** consumers; **97 of the 120 are exactly `RU-3`'s pairs**, which
> ### the sentence claims to exclude and which the review's own §3.2 table displays. The defect
> ### magnitude is **23**. The review's own per-consumer table sums to 23. **The headline number is
> ### internally inconsistent with the review's own evidence and is corrected here.** R-01 stands:
> ### 23 > 0, and the 23 contain the reproduced exchange.

**`RU-3`'s 97 are NOT a defect.** Rule 4 is adjudicated: a zero-durable-write row is **descriptive**
and its marker **exempts nothing**. `RU-3` `` `COMPILED` → *(blocked)* `` performs no durable write, so
`GR-2` never binds it and no relationship is owed. The review's own **R-08** rules this correct, and I
**RATIFY** that. Counting these as false accepts overstates the defect roughly fivefold.

---

## H. R-01 QUESTION B — THE TRUE RELATIONSHIP KEY

### H.1 The complete existing structured owner identity

Direct inspection of **all twenty** co-commit declarations in the corpus. Every one carries a machine
token **and** a backticked canonical state token, and in every case that state token is the
counterpart row's **`To` state**:

| Consumer declares | Owner's `To` | ✓ | Owner declares | Consumer's `To` | ✓ |
|---|---|---|---|---|---|
| `PL-6` → `` M4 `REQUESTED` `` | `AP-1` = `REQUESTED` | ✅ | `AP-1` → `` M2 `AWAITING_APPROVAL` `` | `PL-6` = `AWAITING_APPROVAL` | ✅ |
| `PL-9` → `` M3 `CLAIMED` `` | `EF-2` = `CLAIMED` | ✅ | `EF-2` → `` M2 `CLAIMED`, M4 `CONSUMED` `` | `PL-9` = `CLAIMED` | ✅ |
| `PL-10` → `` M3 `ATTEMPTED` `` | `EF-3` = `ATTEMPTED` | ✅ | `EF-3` → `` M2 `EXECUTED` `` | `PL-10` = `EXECUTED` | ✅ |
| `PL-10f` → `` M3 `FAILED` `` | `EF-3f` = `FAILED` | ✅ | `EF-3f` → `` M2 `FAILED` `` | `PL-10f` = `FAILED` | ✅ |
| `PL-10u` → `` M3 `UNKNOWN_OUTCOME` `` | `EF-3u` = `UNKNOWN_OUTCOME` | ✅ | `EF-3u` → `` M2 `NEEDS_VERIFICATION` `` | `PL-10u` = `NEEDS_VERIFICATION` | ✅ |
| `PL-11` → `` M3 `VERIFIED` `` | `EF-4` = `VERIFIED` | ✅ | `EF-4` → `` … + M2 `VERIFIED` `` | `PL-11` = `VERIFIED` | ✅ |
| `PL-11c` → `` M3 `UNKNOWN_OUTCOME` `` | `EF-4c`/`EF-4u` = `UNKNOWN_OUTCOME` | ✅ | `EF-4c`/`EF-4u` → `` M2 `NEEDS_VERIFICATION` `` | `PL-11c` = `NEEDS_VERIFICATION` | ✅ |
| `PL-15` → `` M3 `{VERIFIED,FAILED}`, M10 `COMPLETED` `` | `EF-5` = `{VERIFIED,FAILED}`; `CM-5` = `COMPLETED` | ✅ | `EF-5`, `CM-5` → `` M2 `{VERIFIED,FAILED}` `` | `PL-15` = `{VERIFIED,FAILED}` | ✅ |

**The guard extracts the machine integer and discards the state token. The review's claim is
CONFIRMED by direct inspection of every declaration.**

### H.2 The minimal sufficient mechanically decidable key — RULING

> ### **The authoritative relationship key is the ordered pair of `(state machine, target state)`
> ### assertions, required in BOTH rows' `Writes` co-commit segments:**
>
> - **forward** — ∃ `s ∈ To(owner)` such that `(M(owner), s)` is declared in `T`'s co-commit segment;
> - **reverse** — ∃ `s ∈ To(T)` such that `(M(T), s)` is declared in the owner's co-commit segment;
> - **fail closed** — if either row has no canonical `To` state, or declares a machine token with no
>   accompanying backticked canonical state token, the relationship is **UNDECIDABLE** and the build
>   **FAILS** (`7_fail_closed`).

**What the key must include:** state machine · target state of the counterpart · the bidirectional
requirement already in `5a`. **Nothing else.**

**What it must NOT include — these would be architecture invention and are REFUSED:**

| Candidate datum | Ruling |
|---|---|
| producer / consumer **transition ids** inside the declaration | ### **REFUSED** — no declaration carries one; adding them invents a convention |
| **source (`From`) state** | ### **REFUSED** — no declaration carries one; see §J |
| canonical **event name** inside the declaration | ### **REFUSED** — `PL-9`'s `` M4 `ApprovalConsumed` `` is the corpus's only event-named leg and is a data irregularity, not a convention |
| **commit / operation identity** | ### **REFUSED** — `causation_id` is a runtime carrier; the adjudication §2 already ruled the declared co-commit is the specification-level artifact |
| new column in the transition tables | ### **REFUSED** — specification change requiring its own authorization |

> ### **No new architecture is required. No specification data need change. All twenty declarations
> ### already carry the datum. The remediation is a guard/parser correction and its tests.**

### H.3 A trap the remediating builder must not fall into

`TRANSITION-EVENT-AUDIT.yaml` `consumes_valid.insufficient_by_themselves` names **"that the TARGET
STATE matches"** among predicates that may never become *the* predicate. **That does not bar this
key, and I rule so explicitly.**

The prohibition is against **target-state similarity substituting for the co-transition relation** —
which is the `DELEGATES_TO` predicate, as the prior adjudication §2 states. The ruling here makes the
**existing bidirectional co-commit declaration row-specific**; it is a **conjunct added to `5a`**, not
a disjunct replacing it. **`5a`, `5b`, `5c` and `5d` all remain required in full.** A remediation that
weakens or removes any of them in exchange for the state binding is **out of contract**.

### H.4 Feasibility probe — reproduced independently, not accepted from the review

I implemented the key against the candidate's own `_consumes_relationship_errors` and re-ran the full
999-cell matrix and both exploits.

| Measurement | Current guard | + `(M, To-state)` row binding |
|---|---|---|
| Durable-consumer **false accepts** | ### **23** | ### **2** *(both adjudicated NOT false — see below)* |
| Durable-consumer **false rejects** | 0 | ### **0** |
| Every current valid consumer accepted | ✅ | ### **✅ all 12 declared pairs, including `PL-15`'s two-branch, two-machine case** |
| `PL-10` ⇄ `PL-11` exchange | ACCEPTED | ### **REJECTED — both directions cited** |
| `PL-10 → EffectVerified` | ACCEPTED | ### **REJECTED** |
| `PL-11 → EffectExecuted` | ACCEPTED | ### **REJECTED** |
| `PL-9 → ApprovalRequested` | ACCEPTED | ### **REJECTED** |
| `PL-7a` one-token laundering | ACCEPTED | ### **REJECTED (reverse leg)** |
| `AP-9 → ApprovalConsumed` / `→ BrakeReleased` | rejected | ### **still rejected** |
| One-token laundering of the other six obligations | rejected | ### **still rejected** |

**Exact failure text produced for the two blocking exploits:**

```
PL-10/EffectVerified: FORWARD - declares co-commit [(3,'ATTEMPTED')], owner EF-4 enters M3 ['VERIFIED']
PL-10/EffectVerified: REVERSE - owner EF-4 declares co-commit [(2,'VERIFIED')], consumer enters M2 ['EXECUTED']
PL-7a/EffectExecuted: REVERSE - owner EF-3 declares co-commit [(2,'EXECUTED')], consumer enters M2 ['CHECKPOINT']
```

> ### **The reverse leg is what closes `PL-7a`.** Under the shipped guard, `EF-3`'s declaration is
> ### pooled across all of M2 and `PL-7a` annexes it. Under the row binding, `EF-3` must name the
> ### state the consumer **enters** — `EXECUTED`, not `CHECKPOINT`. **A candidate can no longer
> ### launder a row using only its own cell.**

### H.5 The two residual accepts — ADJUDICATED, and neither is a false accept

| Pair | Analysis | Ruling |
|---|---|---|
| `PL-9 → EffectAttempted` | `events/registry.md` §3 declares `` `EffectAttempted`(EF-2) `` — the **same owner row** as `GrantClaimed`. `PL-9`'s own `Writes` cell states `` co-commit: M3 `CLAIMED` + M4 `ApprovalConsumed` + `EffectAttempted` (emitted BEFORE the call) ``. Same owner row, same transaction, same authorized semantic operation. | ### **NOT A FALSE ACCEPT — the relationship is architecturally TRUE.** My ground-truth label was over-strict |
| `PL-11c → OutcomeUnknown` | `OutcomeUnknown`'s §3 owners are `EF-3u/EF-4c/EF-4u`. **`EF-4c` and `EF-4u` are `PL-11c`'s genuine partners.** Only `EF-3u` is causally wrong, and it passes because `EF-3u` and `EF-4c`/`EF-4u` all declare `` M2 `NEEDS_VERIFICATION` `` and **both `PL-10u` and `PL-11c` target `NEEDS_VERIFICATION`** — the `(M, To-state)` key is not injective when two rows on one machine share a target state | ### **CARRIED RESIDUAL — inherited, explicitly justified, NON-BLOCKING** |

**Why the `PL-11c` residual may not be closed by this unit — and the seventh exploit class.**

The review reports the probe *"closes six of seven confirmed exploit classes"* and asks which is the
seventh. **It is this one.** Three closures were considered and all three are refused:

| Candidate closure | Ruling |
|---|---|
| Narrow §3's producer list for `OutcomeUnknown` to `{EF-3u}` | ### **FORBIDDEN.** `docs/specifications/events/registry.md` is a forbidden surface (prior adjudication §15); the 98 is frozen. The candidate already records exactly this at `PL-10u.precision_residual` — *"Narrowing sec 3's producer list is a producer-map change and is not available to this unit"* — which I **RATIFY as correct** |
| Add the `From` state to co-commit declarations | ### **REFUSED.** No declaration carries one; this invents a convention. Not mechanically necessary |
| Require each `(owner, machine, state)` to resolve to exactly one consumer row (injectivity) | ### **REFUSED — verified to OVER-REJECT.** `EF-5`'s `` M2 `{VERIFIED,FAILED}` `` resolves to `PL-11`, `PL-10f` and `PL-15`; `EF-3u`'s to `PL-10u` and `PL-11c`. This produces **false rejects of legitimate rows**, which is worse than the residual |

> ### **RULING.** Under `events/registry.md` §3 **as frozen**, `EF-4c` and `EF-4u` **are** canonical
> ### producers of `OutcomeUnknown` and **are** `PL-11c`'s declared co-transition partners. Measured
> ### against canonical authority rather than against a narrower causal reading, `PL-11c →
> ### OutcomeUnknown` is **not a proven false accept**; it is an **imprecision inherited from a frozen
> ### producer map**. The remediation must **record** it as a named carried residual with its
> ### authority citation — extending the existing `precision_residual` note from `PL-10u` to `PL-11c`
> ### — and must **not** attempt to fix it.
>
> ### **Against the frozen §3 producer map, the row binding therefore achieves ZERO false accepts and
> ### ZERO false rejects across the current canonical corpus.**

---

## I. R-02 — RULING

> ### **UPHELD. CONFIRMED DEFECT. HIGH. BLOCKING. Reclassified as the cross-class manifestation of
> ### R-01's single root cause (§F), not an independent defect.**

### I.1 Reproduced end-to-end

`02-pipeline-instance.machine.md`, row `PL-7a` `` `VALIDATED` → `CHECKPOINT` ``:

```
Writes:  —                                              →   co-commit M3 `ATTEMPTED`
Event:   EVENT_REQUIRED:G2-OB-PL-7A-AUTONOMOUS-ADMISSION-UNRECORDED   →   CONSUMES:EffectExecuted
```

`TRANSITION-EVENT-AUDIT.yaml`, consistently: `PL-7a` moved out of `EVENT_REQUIRED.members` into
`CONSUMES.members` (`owner: [EF-3]`, `owner_machine: [M3]`, `durable_write: true`); its
`G2-OB-PL-7A-…` obligation record **deleted**; `CONSUMES: 9→10`; `EVENT_REQUIRED: 7→6`;
`open_founder_gated_obligations: 7→6`.

| Measurement | Result |
|---|---|
| G2 guard block, unmutated baseline | ### **53 passed, 0 failed** |
| G2 guard block, laundered | ### **53 passed, 0 failed** |
| **Mutation-attributable failures** | ### **ZERO** |
| `open_founder_gated_obligations` | ### **7 → 6**, unchallenged |
| Class arithmetic | `110 + 10 + 6 + 2 + 6 = 134` — internally consistent, and **wrong** |

**Verified `PL-7a` is exactly what the review says it is** — `TRANSITION-EVENT-AUDIT.yaml`
`founder_gated_event_obligations`:

```
G2-OB-PL-7A-AUTONOMOUS-ADMISSION-UNRECORDED | 02-pipeline-instance:PL-7a | severity: HIGHEST GOVERNANCE
why_it_matters: PL-7a is the SOLE autonomous entry into CHECKPOINT (gate = AUTONOMOUS_WITHIN_CAPS)
                - the bounded-autonomy admission point.
```

**The declared relationship is plainly false.** `PL-7a` fires **before any grant exists**; `EF-3`
(`CLAIMED→ATTEMPTED`) fires far later. `EffectExecuted`'s §5 payload is `—`, so a replay reconstructs
nothing at all.

**Why only `PL-7a`, verified independently:** the same one-token laundering against `AP-9`, `CF-7`,
`EC-7`, `PO-2`, `PO-3` and `RU-8` **fails closed** in every case. `PL-7a` is the only durable
`EVENT_REQUIRED` row on **M2** — the one machine for which an M3 owner already declares a reciprocal
(written for `PL-10`) — **and** whose `Writes` cell names no field, so `5d` is vacuous.

### I.2 R-02 Question B — the `EVENT_REQUIRED` downgrade rule

> ### **RULING — the fail-closed downgrade contract.**
>
> A transition may leave `EVENT_REQUIRED` for `CONSUMES` **only** when **all** of the following hold,
> every one decided from data the candidate row does **not** itself author:
>
> 1. **`1`, `2`, `3`, `5a`–`5d` and `7_fail_closed` hold in full** — as
>    `6_downgrade_prohibition` already requires.
> 2. ### **The `5a` reverse leg is ROW-SPECIFIC.** The §3 owner row's own `Writes` cell must declare a
>    co-commit naming **the state the downgrading transition enters**. A declaration naming only the
>    machine, or naming a different state, is **not** evidence for this row. *This is the clause that
>    makes the proof non-circular: the owner row is authored on a different machine, for a different
>    purpose, and pre-exists the downgrade.*
> 3. ### **The consumed event's §3 producer relationship must PRE-EXIST the downgrade.** The pre-existing
>    authorities are, in order: `events/registry.md` §3's producer map (frozen); the owner row's
>    `From→To` in its own machine file; the owner row's `Writes` co-commit declaration.
> 4. ### **The obligation registry must be discharged EXPLICITLY, not by deletion.** Removing a row
>    from `founder_gated_event_obligations` is only legal when the discharge is one of:
>    (i) a **canonical event** minted under founder/architect authority; or
>    (ii) a **pre-existing structural** `CONSUMES` / `DELEGATES_TO` / `NON_PRODUCING` proof satisfying
>    (1)–(3). ### **No third route exists. Silent deletion is a build failure.**
> 5. ### **No candidate-authored self-certification.** Prose is never a predicate, in any class. A
>    token the candidate adds to its own `Writes` cell is an **assertion**; it may satisfy the forward
>    leg and nothing more.

### I.3 R-02 Question C — protecting the exact `EVENT_REQUIRED` set

The candidate holds the set by `{spec obligation ids} == {registered obligation ids}` together with
`open_founder_gated_obligations == len(obligations)`. **Verified: no hard-coded `7` pins the
population** — which is precisely why the consistent downgrade is invisible.

> ### **RULING. An explicit guard MUST bind the exact `EVENT_REQUIRED` SET, not merely its count.**
>
> The invariant, stated precisely:
>
> - ### **SET IDENTITY.** The registered founder-gated obligation set must equal, by **exact set
>   equality of transition keys**, the frozen adjudicated seven:
>   `{02-pipeline-instance:PL-7a, 04-approval:AP-9, 07-conflict:CF-7, 09-exception:EC-7,
>   11-policy:PO-2, 11-policy:PO-3, 12-rule:RU-8}`.
>   The guard must read this set from a **named, dated, adjudication-attributed record** and must
>   assert membership both ways. A count is **not** the invariant; the count is a consequence.
> - ### **AUTHORIZED-DISCHARGE EVIDENCE.** A member may leave the set only with a recorded discharge
>   naming which route of §I.2(4) was taken and citing the authority. Absent that record, departure
>   is a **build failure**.
> - ### **NO DISAPPEARANCE WITHOUT PROOF.** A transition that leaves `EVENT_REQUIRED` must land in a
>   class whose independent truth predicate it satisfies, proven from structured columns. It may never
>   land in `CONSUMES` on the strength of a token its own row added.
> - ### **NO SELF-CERTIFICATION.** The discharge record may not be authored by the same edit that
>   performs the reclassification without the §I.2 proof also holding.
> - ### **FAIL CLOSED.** Undecidable discharge is a build failure — never a pass, never a skip.
>
> **Hostile node required:** the exact `PL-7a` laundering above — spec `Writes` token plus consistent
> audit edit plus obligation deletion — must **FAIL**, with a positive control that the unmutated
> seven-member set **PASSES**.

---

## J. THE REVIEWER'S META-FINDING — ADJUDICATED EXPLICITLY

> **The reviewer states: *"`AP-9` survives only by accident of its current shape … the invariant does
> not generalize."***

> ### **UPHELD, and mechanically confirmed with the exact reason.**

`AP-9` is defended by three shape properties, none of them properties of the contract:

| Defence | Why it is `AP-9`-specific |
|---|---|
| `5b` mutual exclusivity | requires `AP-7` to be **same-machine** with `AP-9`. Silent for every cross-machine pair — i.e. for every legitimate `CONSUMES` row |
| `5c` cross-machine | fires only for the `ApprovalConsumed` variant |
| `5d` replay coverage | bites only because `AP-9` declares `frozen=true`, a **named field**. Silent for the four state-only consumers |
| `5a` reverse | holds only because `AP-9` is on **M4** and no M3 row declares co-commit with M4 |

**`PL-7a` has none of them.** It is on M2 — the machine `EF-3` already declares — and its `Writes`
cell names no field. **A durable-writing row on M2 with no named field has no protection at all.**

> ### **RULING. Closure of the two `AP-9` probes is NOT proof that F-01 / F-07 is closed, and this
> ### re-adjudication does not treat it as such.** Both `AP-9` probes genuinely fail closed for the
> ### intended relationship reasons — that is real progress and is credited — but the guard they pass
> ### through is not the invariant the adjudication required. **F-01 and F-07 are PARTIALLY
> ### REMEDIATED, not closed.**

---

## K. HOSTILE-TEST COVERAGE DEFECT — UPHELD AND AGGRAVATED

`test_hostile_two_consumers_may_not_swap_their_producers` (`test_bootstrap_hermeticity.py:1387`) uses
`PL-10f` ⇄ `PL-11c`. Its own docstring reads:

> *"Both remain M2 rows consuming M3-owned events with declared co-commits, so **4(a)/4(b)/4(c) are
> all satisfied — the swap is caught by 4(d) alone**."*

| Question | Ruling |
|---|---|
| Why was the chosen pair caught? | **`5d` alone.** `EffectFailed` carries `failure_proof`; the `Verification*` events carry `unknown_reason`. After the swap neither consumer's field is in its event's payload. The node asserts `"replay" in errors` — so it asserts, by name, that only `5d` fired |
| Why was `PL-10` ⇄ `PL-11` not caught? | Neither row declares a field, so `5d` is **vacuous**, and the docstring already concedes `5a`/`5b`/`5c` are satisfied. **Nothing remains to fire** |
| Was the parameterisation representative? | ### **NO.** Two structurally distinct sub-classes exist — field-declaring consumers and state-only consumers. The node samples **only** the class where the catching clause engages |
| Is exhaustive validation feasible? | ### **YES.** 9 consumers × 111 contracts = **999 evaluations**, which I ran in **~2 seconds** against the candidate's own predicate |

> ### **AGGRAVATION, RECORDED.** The builder's own docstring **documents** that `5a`, `5b` and `5c` do
> ### not catch a producer swap, and then selects the one pair where `5d` compensates. **The
> ### information sufficient to find R-01 was written into the candidate's own test comment.** This is
> ### not a subtle miss; it is a generalisation the builder declined to make. The review's **R-09** is
> ### UPHELD and strengthened.

> ### **RULING. The remediation MUST replace hand-selected sampling with an assertion over the FULL
> ### finite relation matrix.** A finite canonical matrix exists and is cheap. Required:
>
> - a node asserting the **complete** 9 × 111 matrix: every declared pair **accepted**, and
>   **every undeclared pair rejected**, with the single named `PL-11c → OutcomeUnknown` residual
>   listed as an **explicit, justified, authority-cited exception** — never a silent allowance;
> - the swap node extended to `PL-10` ⇄ `PL-11` (the state-only pair) **alongside** the existing
>   `PL-10f` ⇄ `PL-11c` pair, each asserting its failure **reason**;
> - the `PL-7a` laundering node of §I.3;
> - positive controls throughout, so no node can pass vacuously.

---

## L. BUILDER JUDGMENT CALLS AND CARRIED FINDINGS

### Judgment call A — strict payload coverage, no derivability escape

> ### **RULING: KEEP UNCHANGED.**

Within authority: strictly narrower than the adjudicated `5d` permission, and a builder may implement
less latitude than granted. Verified to reject **no** current row — all four field-declaring consumers
satisfy strict coverage. The review's classification *"conservative but valid"* is **RATIFIED**.

**Explicitly ruled:** it does **not** compensate for R-01 or R-02, because `5d` never engages for the
four state-only consumers where the contract is weakest. **It must not be broadened, narrowed, or
otherwise touched in order to fix relationship identity.** Do not conflate the two.

**R-06 (derivability escape) — DEFERRED, not owed by U5.1.** The structured derivation authority the
prior adjudication contemplated is the consumer's **registered deterministic transition guard**
(`events/registry.md`:7). That is **not** a structured column today, and making it one is a
specification change requiring its own authorization. No corpus row needs it. Recorded as an open
question for whichever unit first introduces a row that does.

### Judgment call B — no per-branch owner proof on `PL-15`

> ### **RULING: CORRECT. Not merely acceptable — correct. The review's R-07 residual is OVERTURNED.**

The builder's premise is **verified**: `CM-5` is `` `{COMPENSATION_FAILED,NOT_POSSIBLE}` → `COMPLETED` ``
on M10. A `DELEGATES_TO`-style rule requiring the owner to itself transition to the delegated state
would **reject `CM-5`** — a row the prior adjudication §3 itself named a valid owner of
`RealityEstablished`. `PL-15`'s branch discriminator is carried by the event: `RealityEstablished`'s §5
payload is `` `decision_ref, outcome` `` — verified at `state-machines/registry.md`:162.

**Additional ground discovered by this session:** the `(M, To-state)` row binding required in §H
**independently resolves `PL-15`'s branches correctly and with zero false rejects** —
`PL-15`'s `` M3 `{VERIFIED,FAILED}`, M10 `COMPLETED` `` binds `EF-5` through `(3,VERIFIED)`/`(3,FAILED)`
and `CM-5` through `(10,COMPLETED)`, in both directions. **The remediation strengthens `PL-15` without
any per-branch rule.** Adding one would be over-enforcement.

> **Do not add a per-branch owner requirement.**

### Prior findings — dispositions

| ID | This re-adjudication |
|---|---|
| **F-01** | ### **UPHELD — PARTIALLY REMEDIATED, STILL BLOCKING.** Architecture correct, both `AP-9` probes closed for the intended reasons, but the invariant does not generalize (§F, §J) |
| **F-02** | ### **RATIFIED REMEDIATED.** `PHASE-OUTPUTS.md`:153 now states the real block; the new guard reads forbidden tokens from the audit's own `retired_status_tokens` and requires `superseded_by`. Historical evidence documents untouched — absent from the 23-path delta |
| **F-03** | ### **RATIFIED REMEDIATED AS SPECIFIED.** The ±120-char window is replaced by a same-clause requirement; the carve-out is sentence-scoped; the hostile node asserts the reproduction sentence FAILS. The adjudicated bypass is closed |
| **F-04** | ### **RATIFIED — INHERITED, NON-BLOCKING, NOT THIS UNIT'S.** Untracked at **both** refs (`git ls-tree` → 0/0); preserved at `refs/preserve/p4-r07-third-finalization-report-6e8127d` (`61d42466…`); `shasum -c` → **OK**; neither deleted nor modified. Belongs to the next R-07-adjacent correction with F-06 |
| **F-05** | ### **RATIFIED PRESERVED.** `AP-9` remains `EVENT_REQUIRED:G2-OB-AP-9-FREEZE-FACT-UNRECORDED` under its fail-closed default; both laundering variants fail closed. No event designed, named or proposed |
| **F-06** | ### **RATIFIED NOT TOUCHED.** The `README.md` R-07 blockquote is byte-identical to `6e8127d` — no `+`/`−` line in the delta mentions R-07 |
| **F-07** | ### **UPHELD — PARTIALLY REMEDIATED.** Nine genuine hostile nodes, each calling the live predicate through `_consumes_context` overlays, each asserting its failure reason with a positive control. **The defect is coverage, not vacuity** (§K) |
| **R-01** | ### **UPHELD — BLOCKING. Magnitude NARROWED 120 → 23** (§G) |
| **R-02** | ### **UPHELD — BLOCKING. NARROWED to the cross-class manifestation of R-01's single root cause** (§F, §I) |
| **R-03** (union payload coverage over XOR alternatives) | ### **UPHELD — non-blocking CARRIED RESIDUAL.** Unsound in principle; harmless today; it is one of the two mechanisms admitting `PL-11c → OutcomeUnknown`. Per-event coverage is **not required** — the residual is already justified by the frozen producer map (§H.5). **Record it; do not fix it in this unit** |
| **R-04** (F-03 guard remains lexical) | ### **UPHELD, NARROWED — non-blocking, governance-attributable, NOT OWED BY U5.1.** The builder implemented the prior adjudication's own specified remedy faithfully; the residual is inherent to that remedy, not a deviation. Whether a structural predicate is owed is a question for a later unit |
| **R-05** (F-02 carve-out breadth) | ### **UPHELD — non-blocking CARRIED RESIDUAL.** `retired\|superseded\|historical\|no longer\|was the\|before the` over the enclosing sentence is broader than needed. Narrowing is **optional**, not required |
| **R-06** (derivability escape) | ### **DEFERRED** — see judgment call A |
| **R-07** (`PL-15` per-branch) | ### **OVERTURNED** — the restraint is correct, not a residual (judgment call B) |
| **R-08** (zero-write rows accept any `CONSUMES`) | ### **RATIFIED CORRECT.** Rule 4 is adjudicated: descriptive, exempts nothing. **Not a defect.** Counting `RU-3`'s 97 pairs as false accepts is what inflated R-01's headline to 120 |
| **R-09** (swap-node selection bias) | ### **UPHELD AND AGGRAVATED** (§K). Folded into the remediation scope |
| **R-10** (F-04) | ### **RATIFIED INFORMATIONAL** — nothing owed by U5.1 |
| **R-11** (two handoffs lack `.sha256` sidecars) | ### **UPHELD — non-blocking, Product Driver storage hygiene.** `g2-transition-event-targeted-adjudication-6e8127d.md` and `p5-u51-g2-spec-correction-candidate-38b4bda.md`. **Not acted on by this session:** a sidecar generated now would attest to present state, not state at authorship, and generating one is outside a re-adjudicator's mandate. Recorded for the campaign owner |
| **New — `PL-15x`/`IB-5x`** | ### **RATIFIED REMEDIATED** ✅ enforced mechanically by rule 3 |
| **New — §182 citation** | ### **RATIFIED REMEDIATED** ✅ — `state-machines/registry.md` §5 line 182 verified verbatim |

---

## M. ARCHITECTURE VERSUS GUARD DEFECT — THE SEVEN QUESTIONS

| # | Question | Ruling |
|---|---|---|
| 1 | Is `CONSUMES` still architecturally legitimate? | ### **YES.** Ratified unchanged. `state-machines/registry.md`:182 verified verbatim: *"the event has one producer … and the other machine consumes it."* Not reopened |
| 2 | Is the strict payload-coverage rule legitimate? | ### **YES.** Within authority; rejects no current row; **keep unchanged** |
| 3 | Is the current owner/co-transition relationship proof sufficient? | ### **NO.** `5a` binds machine-to-machine, not row-to-row; `5d` is vacuous for state-only writes. **23 false accepts, 0 false rejects** |
| 4 | Can a candidate author manufacture a false valid `CONSUMES`? | ### **YES.** Reproduced twice end-to-end, each at **53 passed / 0 failed**, identical to baseline, at constant class totals **and** constant class membership |
| 5 | Can an `EVENT_REQUIRED` transition disappear without genuine discharge? | ### **YES.** `PL-7a` — sole autonomous entry to `CHECKPOINT`, severity `HIGHEST GOVERNANCE` — discharged by **one token**; `open_founder_gated_obligations` 7 → 6, unchallenged |
| 6 | What does remediation require? | ### **GUARD / TEST WORK ONLY.** ✗ canonical structured-data correction — all twenty declarations already carry the datum. ✗ architecture change — no new concept, column or convention. ✗ founder/architect decision — no event name, no schema, no touch to the frozen 98 |
| 7 | Is `1ae365a` eligible for finalization? | ### **NO** |

> ### **The reviewer's classification — GUARD-BLOCKED, not FOUNDER-BLOCKED — is CONFIRMED.**
>
> No **GOVERNANCE BLOCKER** verdict is available, because no architectural choice remains unresolved
> by repository authority. `state-machines/registry.md`:182 and §4 line 125, the `Writes` column's
> co-commit convention as established at the certified predecessor by `EF-2`, `events/registry.md`:7,
> and the prior adjudication §2/§5 together fix a complete, machine-checkable contract. The founder /
> architect gate stays exactly where G2 placed it: the seven event names, `AP-9`'s emit-vs-derive
> among them. **None of the remediation touches an event name or the frozen 98.**

---

## N. LEGAL REMEDIATION TOPOLOGY

> ### **OPTION A — PRESERVE `1ae365a` AND REPLACE IT IN PLACE WITH ONE CORRECTED CANDIDATE WHOSE SOLE PARENT IS `6e8127d`.**

**Grounds — from repository authority only, verified by this session.**

`docs/implementation/PROGRESS-PROTOCOL.md`:198–201:

> The two-commit convention permits `HEAD` to be **only** the certified content commit or the single
> finalizer-generated metadata commit directly above it, and `test_status_reality.py` resolves both
> through **first-parent** lookups (`HEAD^`, `HEAD^^`).

A second content commit places `HEAD` three commits above `6e8127d` — **not expressible in that
resolution**. ### **Option C is REFUSED.**

**Precedent — verified by direct object inspection, not from any report.** All four P4/R-07 candidates
share the **identical single parent `06ebfdb35a544df8e9cf36d739cc54a0b6877e1f`**:

| Candidate | Parent | Disposition |
|---|---|---|
| `11c9112` | `06ebfdb…` | REJECTED — preserved on archive branch + `refs/preserve/` |
| `4d12b0e` | `06ebfdb…` | REJECTED — preserved likewise |
| `3874d4a` | `06ebfdb…` | REJECTED — preserved likewise |
| `a31a94a` | `06ebfdb…` | **ACCEPTED** → the finalizer ran **once**, producing `6e8127d` |

Each rejection produced a fresh single content commit against the same parent; each replacement
received a completely fresh independent review **and** a separate targeted adjudication. **That is
Option A exactly, and it is this repository's own established mechanism.**

**Option B is REFUSED** — §M questions 3, 4 and 5 all fail; the defect is in the guard that certifies
GR-2, not a documentation residual. **Option D is REFUSED** — §M question 6; nothing is founder-gated.
**Option E is unnecessary** — Option A is repository-authorized and precedented.

### Replacement requirements — binding

| Item | Requirement |
|---|---|
| **Candidate to preserve** | `1ae365aee76d89ebdc78bbb619a4db8b778a1cad` (tree `0e52a61c…`) on **both** `archive/p5/u51-rejected-1ae365a` **and** `refs/preserve/p5-u51-rejected-replacement-candidate-1ae365a`, plus a worktree-state ref, matching the `38b4bda` and P4/R-07 protocol |
| **Review preservation** | the fresh independent review (`ebaefaa1…`) preserved **parented to `1ae365a`**, with its `.sha256` sidecar |
| **Re-adjudication preservation** | **this document** preserved parented to `1ae365a`, with its `.sha256` sidecar |
| **`38b4bda` preservation** | ### **UNCHANGED AND UNTOUCHED.** All five existing refs stay; its review and adjudication remain attributable **only to `38b4bda`** |
| **`refs/preserve/p5-u51-prestate-6e8127d`** | ### **STAYS** at `e77ab673…` |
| **Exact parent** | ### `6e8127dab02e3443183d06825836f5a805f53de0` — single parent, no merge, **exactly ONE content commit** |
| **Fresh re-review** | ### **REQUIRED — complete, by a session that did not build `38b4bda` or `1ae365a`, did not review either, and did not write this re-adjudication** |
| **Separate re-adjudication** | ### **REQUIRED — a further separate session** |
| **Finalizer** | ### **NOT until both succeed.** Then exactly ONE finalizer-generated metadata commit |

### Allowed remediation surfaces — exhaustive

1. `eval/tests/test_bootstrap_hermeticity.py` — the `(M, To-state)` row binding in `5a`; the
   `EVENT_REQUIRED` set-identity guard; the exhaustive relation-matrix node; the `PL-10`⇄`PL-11` swap
   node; the `PL-7a` laundering node.
2. `docs/implementation/TRANSITION-EVENT-AUDIT.yaml` — `consumes_valid` contract text so that what it
   asserts is what the guard proves; the frozen seven-member `EVENT_REQUIRED` set record; the
   `PL-11c → OutcomeUnknown` `precision_residual` note.
3. `docs/implementation/TEST-NODE-MANIFEST.json` — regenerated via `scripts/regenerate_test_manifest.py`.
4. **Optional, not required:** normalising `PL-9`'s `` M4 `ApprovalConsumed` `` leg to the state
   `` `CONSUMED` ``. Never exercised today and fail-closed if it ever were.
5. Replacement builder handoff (Product Driver storage, outside the product branch).

### Forbidden surfaces — unchanged from the prior adjudication §15, restated

Production `GateRegistry` · `src/freight_recon/effect_boundary.py` and every adapter ·
`phase-0-baseline-manifest.yaml` · `driver.config.yaml` · any Action Class registration · any
live-writer injection · ### **`docs/specifications/events/registry.md` — the 98 stays frozen; NO event
may be minted and NO §3 producer list may be narrowed to "solve" a consumer's relationship gap** ·
`docs/specifications/state-machines/registry.md` · `PROGRAM-WEIGHTS.yaml` ·
`SUITE-RESULT.json` / `GATE-RESULT.json` · the `README.md` R-07 blockquote (F-06) · `src/` ·
`scripts/` · `configs/` · `data/` · `docs/architecture/` · `docs/specifications/acceptance/`.

### Retain unchanged — all independently verified correct by this session

The `110 / 9 / 6 / 2 / 7` class model **subject to exact membership proof** · the `PL-15x` / `IB-5x`
`NON_PRODUCING` correction · **strict payload coverage (UPHELD)** · the `NON_PRODUCING` rules · the
`DELEGATES_TO` rules · `EF-3` → `EffectExecuted` · the frozen **98**-event registry · the seven
unresolved founder-gated event decisions · the acceptance contract **14 / Σ100 / all PENDING** · the
P4 / R-07 safety state · production `GateRegistry` **EMPTY** · the Phase-8 deferral · the F-02 and
F-03 remediations · the preservation discipline.

> ### **No unrelated redesign is authorized. The scope above is exhaustive.**

---

## O. FINALIZER ELIGIBILITY

> ### **`1ae365aee76d89ebdc78bbb619a4db8b778a1cad` MAY NOT PROCEED to the U5.1 finalizer.**
>
> The finalizer was **not run** by this session and must not be run on this candidate.
> `finalize_status.py` was not invoked.

| # | An acceptance must prove | Ruling |
|---|---|---|
| 1 | Zero false-accepting consumer/event relationships | ### **FAILS — 23** |
| 2 | Zero false-rejecting current valid consumers, or a justified residual | ### **PASSES — 0** |
| 3 | `EVENT_REQUIRED` cannot disappear through candidate-authored relationship prose | ### **FAILS — `PL-7a`, one token, 7 → 6** |
| 4 | `PL-10` / `PL-11` exploit closed | ### **FAILS** |
| 5 | `PL-7a` exploit closed | ### **FAILS** |
| 6 | Current nine consumers relationship-valid | ### **PASSES** — all nine true as declared; four are **unbound** by the guard |
| 7 | Current seven `EVENT_REQUIRED` obligations preserved | ### **PASSES** as shipped — but **not protected**, only counted |
| 8 | Event registry remains 98 | ### **PASSES** — byte-unchanged |
| 9 | Acceptance contract remains valid | ### **PASSES** — 14 · Σ100 · verbatim ordered · all PENDING |
| 10 | P4 / R-07 remain intact | ### **PASSES** — P4 COMPLETE, R-07 CONTAINED, `GateRegistry` EMPTY |

**Four of ten fail, and all four are the single defect of §F.**

---

## P. PROOF THE PRODUCT REPOSITORY WAS NOT CHANGED

Measured **after** every read, parse, export, clone, suite run and mutation run — and byte-identical to
the pre-adjudication measurement in §B **and** to the values the independent review recorded:

| Field | Value |
|---|---|
| HEAD | `1ae365aee76d89ebdc78bbb619a4db8b778a1cad` |
| Tree | `0e52a61c6bef77df42610fa8ea9d142092b4f021` |
| Branch | `p5/u5-1-g2-spec-correction` |
| Parent | `6e8127dab02e3443183d06825836f5a805f53de0` — single, not a merge |
| ### Index digest | ### `ba83298a04abd2bdb2496470ec0d6d6a4560e0daa6df47fda0a86a9f5a2a5e73` |
| ### Worktree-status digest | ### `2babbc0cce82e8374d038244574325e32d9bc7e9e2f208f57ee0293a1bf9cac0` |
| Total refs | **72** — unchanged; **this session created none** |
| Content commits above `6e8127d` | **1** |
| Commits above the candidate | **0** — no finalizer commit |
| Remote `p5/` refs | **0** — nothing pushed |
| `p4/adapter-containment-completion` | `6e8127d` — unmoved |
| `main` / `origin/main` | both `152574e4f4f2969468c9d31b1e705188896175b5` — unmoved |
| `refs/preserve/p5-u51-prestate-6e8127d` | `e77ab673021831ff71fb7f74c58c88fce8b377c3` — unchanged |
| `refs/preserve/p5-u51-rejected-candidate-38b4bda` | `38b4bda6…` — unchanged |
| Untracked set | exactly the two authorized F-04 artifacts |
| F-04 report | ### **`shasum -c` → OK.** Neither deleted, modified nor committed |

**Not done by this session:** no product commit · no amend · no ref created, deleted or moved · no
`checkout`, `reset`, `restore`, `stash`, `clean`, `rebase`, `merge`, `gc` or `prune` in the product
repository · no push, deploy or effect-enabling action · no `finalize_status.py` and no other finalizer
· no remediation · no modification of the candidate · no event minting · no change to the frozen 98 ·
no new canonical event name · no second P5 unit begun · no `driver.config.yaml` or Product Driver
configuration modification · no Desktop-repository modification · no P4 / R-07 reopening · no previous
Claude session resumed.

**Writes performed, in full:** this document and its `.sha256` sidecar, in non-product Product Driver
handoff storage, uncommitted; and one `--no-local` clone, one `git archive` tree export, two analysis
scripts and two virtualenvs in the session scratchpad, outside both repositories, containing all
mutation testing. Every mutation was applied inside the disposable clone and reverted with
`git checkout -q .` before the next run; the clone's final state was verified clean at `1ae365a`.

---

## VERDICT

> ### **REJECT — TARGETED REMEDIATION REQUIRED**

**Both blocking findings are UPHELD and both were reproduced end-to-end at zero
mutation-attributable failures. They are one defect: `5a` compares machine integers, so a co-commit
declaration is pooled across a machine instead of belonging to the row that wrote it — and `5d`, the
only clause that could compensate, is structurally vacuous for exactly the rows whose durable write IS
the state change.**

**The remediation is narrower than the review supposed. The owner-identifying datum — the counterpart
row's target state — is already written into all twenty co-commit declarations in the corpus and is
simply discarded by one line. Binding on it bidirectionally accepts every current valid consumer with
zero false rejects, closes both reproduced exploits and every other confirmed exploit class except one
inherited imprecision whose root lies in a frozen surface. No specification data changes. No event is
minted. No architecture is invented. No founder or architect decision is required.**

**This is not a rejection of the architecture, the classification work, the `PL-15x`/`IB-5x`
reclassification, the `NON_PRODUCING` or `DELEGATES_TO` proofs, the strict payload-coverage judgment,
the `PL-15` branch restraint, the F-02 and F-03 remediations, the acceptance-contract instantiation, or
the preservation discipline — every one of which this session independently verifies as correct and
which must be carried forward unchanged.**

**Unchanged and still binding:** no event was minted · the canonical total stays **98** · `AP-9` stays
`EVENT_REQUIRED` under its fail-closed default · the seven founder/architect obligations remain
**OPEN** · **G2 is still NOT fully discharged** · P5's event content stays blocked · P4 **COMPLETE**
and R-07 **CONTAINED** retained · production `GateRegistry` **EMPTY** · Phase-8 deferral intact ·
nothing pushed · **no finalizer authorized**.

---

**END OF TARGETED RE-ADJUDICATION**

**Candidate `1ae365aee76d89ebdc78bbb619a4db8b778a1cad` · tree `0e52a61c6bef77df42610fa8ea9d142092b4f021` ·
parent `6e8127dab02e3443183d06825836f5a805f53de0` · branch `p5/u5-1-g2-spec-correction`.**
**Independent review `ebaefaa1945ec87fc4810265f2219f07cf98306e1a4713fe41cfa47e32ec5533` — verdict
CONFIRMED, magnitude corrected, two findings merged into one root cause.**
**Rejected predecessor `38b4bda6cb3ea6c5e5c9a302fd64d23450e6fc62` verified preserved, unmodified, and
attributable only to itself.**

### **VERDICT: REJECT — TARGETED REMEDIATION REQUIRED. TOPOLOGY: OPTION A. GUARD-BLOCKED, NOT FOUNDER-BLOCKED.**

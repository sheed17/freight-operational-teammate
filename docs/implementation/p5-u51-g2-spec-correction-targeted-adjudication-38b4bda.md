# NEYMA P5 U5.1 — G2 SPEC/CONTROL CORRECTION: TARGETED GOVERNANCE ADJUDICATION

**Content candidate `38b4bda6cb3ea6c5e5c9a302fd64d23450e6fc62` (tree `e669ad3375822b0a458b5466d9ce8fb37fceddb3`)
over certified predecessor `6e8127dab02e3443183d06825836f5a805f53de0` (tree `515db7425b9ad18b4286b64436f9d240f2e865f6`).**

Written outside the product branch and tree. No product commit. No finalizer. No remediation.
The candidate was not modified. No event was minted. No P5 unit was begun.

---

## VERDICT

> ### **REJECT — TARGETED REMEDIATION REQUIRED**
>
> **F-01 is upheld, and it is worse than the reviewer proved.** `CONSUMES` is architecturally
> legitimate — it is not a third GR-2 exemption but a structured label over a relationship the
> repository already carries in byte-unchanged authority. **The defect is that the candidate treats
> the label as self-certifying.** Its guard proves only that a named event exists and is not
> self-owned; it proves *no relationship of any kind* between the consuming row's durable write and
> the consumed event.
>
> I reproduced the reviewer's `AP-9` laundering exactly — **42/42 G2 nodes, 2088 passed / 3 skipped
> / 0 failed** — and then reproduced it a second time with `AP-9` consuming **`BrakeReleased`**, an
> M13 brake event bearing no relationship whatsoever to an M4 approval freeze: **42/42 passed.** The
> class admits *any* of the 98 canonical events. This is not a check needing refinement; it is the
> absence of a relational check.
>
> ### **This is the same failure §F of the G2 adjudication refused by name — Interpretation B's
> ### self-certifying predicate — re-committed in structured syntax instead of prose.** `CF-7` once
> exempted itself with `*(no state change)*` while performing a durable write. `AP-9` can now exempt
> itself with `CONSUMES:BrakeReleased` while performing one. The syntax is machine-readable; what it
> asserts is checked no more than the prose was.
>
> **No founder/architect decision is required to fix this.** The authority to define `CONSUMES`
> already exists in the repository and is applied in §2 below. The founder gate remains exactly
> where G2 put it and where this candidate correctly left it: the seven event names, `AP-9`'s
> emit-vs-derive among them. **U5.1 is not founder-blocked. It is guard-blocked.**

---

## A. SESSION INDEPENDENCE

A **fresh targeted adjudicator**. Did not implement P4; did not participate in the P4/R-07 closure
campaign; did not author the G2 architecture adjudication; did not build `38b4bda`; did not perform
the independent review. Resumed **no** previous Claude session.

Performed no remediation, no finalization, no event minting, no further P5 work. Did not modify the
candidate, the product branch, any ref, `driver.config.yaml`, or the Desktop repository. All
mutation testing was confined to a single disposable `--no-local` clone outside both repositories.
The builder handoff and the independent review were both treated as **untrusted testimony**; every
controlling claim below was re-derived from Git objects and repository authority.

---

## B. CANDIDATE IDENTITY — RESOLVED MECHANICALLY, NOT ACCEPTED

| Property | Required | Observed | Result |
|---|---|---|---|
| Candidate | `38b4bda6…` | `38b4bda6cb3ea6c5e5c9a302fd64d23450e6fc62` | ✅ |
| Tree | builder said `e669ad33…` | `e669ad3375822b0a458b5466d9ce8fb37fceddb3` — resolved from Git | ✅ |
| Parent | exactly `6e8127d` | `6e8127dab02e3443183d06825836f5a805f53de0` | ✅ |
| Parent count | 1, not a merge | `git rev-list --parents -n1` → one parent | ✅ |
| Commits above `6e8127d` | exactly 1 | `git rev-list 6e8127d..38b4bda` → **1** | ✅ |
| Branch | `p5/u5-1-g2-spec-correction` | same; HEAD is the candidate | ✅ |
| Old P4 branch unmoved | `6e8127d` | `p4/adapter-containment-completion` = `6e8127d` | ✅ |
| Index clean | yes | `git ls-files -s ‖ sha256` = `0b630149d44f34e5c45a635258a72b2eb14b1de8a98cf893c3a46f64fd385c8e` | ✅ |
| Untracked set | the two authorized artifacts | exactly those two | ✅ |
| **Unchanged since review** | digests match | index `0b630149…` **and** worktree-status `2babbc0c…` are **byte-identical to §S of the independent review** | ✅ |
| Nothing pushed | no remote P5 ref | zero `p5/` refs under `refs/remotes`; `main`/`origin/main` both `152574e4…` | ✅ |
| No finalizer run | none | `git rev-list 38b4bda..branch` → **0**; `SUITE-RESULT.json`/`GATE-RESULT.json` byte-unchanged, still bound to `a31a94a` | ✅ |
| No subsequent P5 unit | none | reflog `@{0}` is the candidate commit; nothing after | ✅ |

> The worktree-status digest `2babbc0c…` is byte-identical across the **G2 adjudication at
> `6e8127d`**, the **independent review at `38b4bda`**, and **this session** — three independent
> measurements confirming the untracked set never moved.

**Candidate identity confirmed. Adjudication proceeds.**

### Report digests — verified before reliance

| Report | Expected | Computed | Result |
|---|---|---|---|
| Independent review | `27906bcec34bc7e660ed27d84f5cdcdf6be37ef436b113eb564c048e293f8a43` | `27906bcec34bc7e660ed27d84f5cdcdf6be37ef436b113eb564c048e293f8a43` | ✅ **match** |
| G2 targeted adjudication | *(not supplied)* | `27bbbfb4ffa7bfda3334ecfd8836ede1979c1bbe5a552bf6216c43fd38c63227` | recorded |
| P4/R-07 campaign closure | *(not supplied)* | `8bdb6ce0045b14a85333c0b5abb5a496d0dbee9d000f74e16ce3476ff750e34a` | recorded |
| Builder handoff | *(not supplied)* | `dbf6e3be232a627f8267b458ccd5dac703d4a4abdc4bd91cef0d7b8ae60241f5` | recorded |

Review verdict confirmed as **CONDITIONALLY ACCEPT — GOVERNANCE ADJUDICATION REQUIRED**.

---

## 1. QUESTION 1 — IS `CONSUMES` LEGITIMATE AT ALL?

> ### **B. `CONSUMES` IS NOT AN EXEMPTION; IT IS A STRUCTURED SECONDARY RELATIONSHIP UNDER AN EXISTING PRODUCER — BUT THE CANDIDATE'S PROOFS ARE INSUFFICIENT.**

### Reconciling explicitly with *"No third option"*

The G2 adjudication §G reads:

> **Completeness (GR-2 converse).** Every transition performing a durable write is a §3 producer of
> ≥1 event **or** carries a valid `DELEGATES_TO`. **No third option.**

Two readings are available. Under **(i)** the disjunction enumerates permitted *classification
labels*, and `CONSUMES` is a forbidden third label → answer A. Under **(ii)** it enumerates the ways
a durable write may *acquire an event*, and the question becomes whether a `CONSUMES` row's durable
write in fact has one.

**Reading (ii) is correct, and the G2 adjudication itself proves it — in four places.**

**1. §D expressly certifies the eleven rows as correct architecture.** *"Twelve rows name an event
they do not own — `PL-6`, `PL-9`, `PL-10`, `PL-10f`, `PL-10u`, `PL-11`, `PL-11c`, `PL-15`, `PL-15x`,
`IB-5x`, `RU-3`, `RU-8`. **Every one is correct architecture and would be a false positive under
Interpretation A.**"* Eight of those rows perform durable writes, are not §3 producers, and carry no
`DELEGATES_TO`. Under reading (i), §G would condemn the very rows §D certifies — **the document
would contradict itself across two sections.** A reading that makes an adjudication incoherent is
not the adjudication's meaning.

**2. §F states the ruling as two predicates, not a three-label vocabulary.** *"The producer predicate
is membership in a table, and the completeness predicate is the presence of a durable write."* §G's
sentence is the *completeness* rule. It is silent on what marker a co-transitioning row wears.

**3. The relationship, the word, and the mechanism all pre-exist in byte-unchanged authority.**

- `docs/specifications/state-machines/registry.md:182` — *"**No event is emitted by two incompatible
  transitions.** Where two machines co-transition (M2↔M3, M2↔M4), the event has **one producer**
  (listed above) and the other machine **consumes** it."*
- `docs/specifications/state-machines/02-pipeline-instance.machine.md:9-10` — a dedicated
  `## M2↔M3 co-transition rule` section: *"`PL-8` (mint) and `PL-9` (claim) are co-transitions with
  M3 … M2 does not own the grant state — **M3 does** — but the two rows transition in the same
  commit."*
- `docs/specifications/state-machines/registry.md:125` — *"`GRANTED` … and `CLAIMED` … are the
  **same conceptual event surfaced on the two machines that share the moment** … they are
  co-transitioned, not two meanings."*
- `docs/specifications/events/registry.md:7` — *"Consumers react according to **their own
  deterministic transition guards**; the event does not instruct them."*

Both `events/registry.md` and `state-machines/registry.md` are **byte-unchanged** in this candidate.
The builder invented neither the relation nor the vocabulary.

> **Citation correction, binding on the replacement.** The builder's commit message, the audit's
> `contract` text, and the independent review all cite this as **`events/registry.md` §182**. It is
> **`state-machines/registry.md`:182**; `events/registry.md`:182 is `ER-14`. The substance is
> unaffected, but a control document citing the wrong file for its governing authority must be
> corrected.

**4. The adjudication already refused to let "names an event it doesn't own" excuse a durable write.**
`RU-8` appears in §D's list of twelve non-owning rows and was nonetheless ruled **EVENT_REQUIRED**.
So §D had *already* separated *consumes* — a description of the Event cell — from *GR-2 discharged*
— a property of the durable write. **That is precisely the distinction the candidate collapsed.**

### What is therefore unauthorized

Not the class. **The self-certification.** §F refused Interpretation B because its predicate was
*"prose-dependent and self-certifying — a row can exempt itself by writing the right words in the
Event column,"* and noted the failure was not hypothetical: `CF-7` and `EC-7` exempted themselves
with `*(no state change)*` while performing durable writes. The candidate's `CONSUMES` token is
structured rather than prose, but it is exempting on the strength of **what it asserts about itself**,
with the assertion unchecked. Moving from `*(no state change)*` to `CONSUMES:BrakeReleased` changes
the syntax, not the failure mode.

**Not A** — the relationship pre-exists and §D certifies it.
**Not C** — disproved twice by direct reproduction (§4).
**Not D** — the existing authority is sufficient and is applied in §2. No founder decision is needed
to define `CONSUMES`. (One remains needed for the seven event names — a different question.)

---

## 2. QUESTION 2 — GR-2 SEMANTICS, MECHANICALLY

`state-machines/registry.md` §3, **GR-2**:

> **The state change + emitted events are ONE commit** (transactional outbox). **No state change
> without its event; no event without its transition.**

**Operative meaning of "no state change without its event":** for every durable state change `D`
there exists an emitted canonical event `E` such that a **full-history replay reconstructs `D`**.
`events/registry.md` §2 fixes the rationale — *"Audit evidence | the emitted event is the audit
record"* — and `AC-EVT-008` fixes the test: a full-history rebuild reproduces the pinned `GC-1`
projection digest byte-for-byte. A durable write no replay can reconstruct has no audit record.

| Question | Ruling |
|---|---|
| May a `CONSUMES` transition itself perform durable writes? | **Yes.** Eight of the eleven do. |
| Under what exact condition can another transition's event satisfy GR-2? | When the consumer's durable write is **reconstructible on replay** from *(producer event payload)* + *(the consumer's own registered deterministic guard)* + *(the consumer's prior replayed state)*, **and** both writes commit in one transaction. |
| Must both state changes be one atomic semantic operation? | **Yes.** That is GR-2's "ONE commit", and it is the property the candidate's own audit text asserts. |
| Must the producer payload encode the consumer's resulting state? | **No — not literally.** `events/registry.md`:7 forbids it: *"the event does not instruct them."* Required instead: the payload carries enough for the consumer's own guard to fire deterministically, and every field in the consumer's `Writes` column is covered by the payload or derivable from that guard. |
| Must both transition IDs appear in event metadata? | **No.** `producer_transition_id` is the **producer's** (envelope §1). Recording the consumer's id would manufacture the duplicate ownership the ‡ clause exists to prevent. |
| Must producer and consumer share a causal/transaction identity? | **Yes** — the transaction is the binding one. `causation_id` (`events/registry.md`:151) is the natural carrier at runtime; at specification level the testable artifact is a **declared co-commit**. |
| May mutually-exclusive transitions ever satisfy one another? | ### **NEVER.** This is the decisive missing invariant. If the producer's transition did not fire, its event was never emitted, so it can record nothing. `AP-9` (`GRANTED→GRANTED` frozen) and `AP-7` (`GRANTED→CONSUMED`) cannot both fire on one approval. |
| May merely sharing an event family satisfy GR-2? | **No.** |
| May sharing a target state satisfy GR-2? | **No.** That is the `DELEGATES_TO` predicate, which additionally requires the target be a §3 producer. |
| May sharing a commit satisfy GR-2 without payload coverage? | **No.** Co-commit yields atomicity; it does not yield reconstructibility. **Both are required.** |

### The mechanically testable rule — **CONSUMES-VALID**

For a row `T` marked `CONSUMES:E₁[,E₂…]`:

1. Every `Eᵢ` exists in the §3 canonical corpus.  *(candidate proves this)*
2. `T` ∉ `producers(Eᵢ)`.  *(candidate proves this)*
3. **If `T` performs no durable write**, GR-2 does not bind it. The marker is then descriptive and
   carries **no exempting force**; an enumerated GR-1 refusal row must be `NON_PRODUCING` instead.
4. **If `T` performs a durable write**, all four must hold, read from **structured columns only**:
   - **(a) CO-COMMIT DECLARED BIDIRECTIONALLY** — `T`'s `Writes` cell declares the co-commit with the
     owner's machine, **and** the owner row's own `Writes` cell declares the reciprocal.
   - **(b) NOT MUTUALLY EXCLUSIVE** — `owner(Eᵢ)` and `T` must not be rows of the same machine whose
     `From` sets intersect and whose `To` states differ.
   - **(c) CROSS-MACHINE** — `T`'s machine ≠ the owner's machine. A within-machine "consumption" is
     either production or delegation.
   - **(d) REPLAY COVERAGE** — every field named in `T`'s `Writes` column appears in some `Eᵢ`'s
     declared payload (`state-machines/registry.md` §5) or is derivable from `T`'s registered guard.
5. **Downgrade prohibition.** `EVENT_REQUIRED → CONSUMES` requires 4(a)–(d) in full.
   `NON_PRODUCING → CONSUMES` requires the row first acquire a durable write **and** satisfy 4.
6. **Fail closed.** Any `CONSUMES` row for which 4(a)–(d) cannot be **decided** fails the build —
   never a pass, never a skip.

**4(b) + 4(c) alone defeat both exploit variants in §4.** 4(a) additionally exposes the ten
under-declared rows in §3.

---

## 3. QUESTION 3 — PER-ROW DISPOSITION OF THE 11 CURRENT `CONSUMES` ROWS

Durable-write test applied as the audit defines it: durable **iff** `To` names a canonical state
absent from `From`, **or** `Writes`/`Prov` is non-empty and not an em-dash. Producer ownership
re-derived by this session from `events/registry.md` §3.

| # | Transition | Durable write | Event | §3 owner | Causal / co-transition | Payload coverage | Replay | Independent domain fact? | **Disposition** |
|---|---|---|---|---|---|---|---|---|---|
| 1 | `02:PL-6` `VALIDATED→AWAITING_APPROVAL` | **yes** (state; `Writes` = —) | `ApprovalRequested` | `AP-1` (M4) | genuine M2↔M4; **co-commit NOT declared** either way (M2 §4: only PL-8/PL-9 co-commit) | n/a — state only | reconstructs from `PolicyEvaluated{gate_decision}` + own guard | no — mirrors M4 | **VALID CONSUMER** *(co-commit declaration owed)* |
| 2 | `02:PL-9` `GRANTED→CLAIMED` | **yes** | `GrantClaimed` | `EF-2` (M3) | ### **bidirectional co-commit declared** — PL-9 `Writes`: *"co-commit: M3 `CLAIMED` + M4 `ApprovalConsumed`"*; EF-2 `Writes`: *"co-commit M2 `CLAIMED`, M4 `CONSUMED`"* | covered | exact | no | ### **VALID CONSUMER — the paradigm case, and the only row fully satisfying 4(a) today** |
| 3 | `02:PL-10` `CLAIMED→EXECUTED` | **yes** (state; `Writes` = *"ext: the world was touched"*) | `EffectExecuted` | `EF-3` (M3) | genuine M2↔M3 mirror; co-commit undeclared | n/a — state only | `EffectExecuted` + own guard | no | **VALID CONSUMER** *(co-commit declaration owed)* |
| 4 | `02:PL-10f` `CLAIMED→FAILED` | **yes** (state + `failure_proof`) | `EffectFailed` | `EF-3f` (M3) | exact mirror (`EF-3f`: `CLAIMED→FAILED`, `Writes failure_proof`) | ✅ `EffectFailed{proof}` covers `failure_proof` | exact | no | **VALID CONSUMER** *(co-commit declaration owed)* |
| 5 | `02:PL-10u` `CLAIMED→NEEDS_VERIFICATION` | **yes** (state + `exposure,unknown_reason`) | `OutcomeUnknown` | `EF-3u`,`EF-4c`,`EF-4u` — **verified from §3** | mirror of `EF-3u` | ✅ `EF-3u Writes exposure, unknown_reason` | exact | no | **VALID CONSUMER** *(co-commit owed; owner set is broader than the causal path — precision owed)* |
| 6 | `02:PL-11` `EXECUTED→VERIFIED` | **yes** (state; `Writes` = —) | `EffectVerified` | `EF-4` (M3) | mirror; `EF-4`'s declared co-commit is verify+record (with PL-12), not with PL-11 | n/a | exact | no | **VALID CONSUMER** *(co-commit declaration owed)* |
| 7 | `02:PL-11c` `EXECUTED→NEEDS_VERIFICATION` | **yes** (state + `unknown_reason`) | `VerificationConflict`,`VerificationUnavailable` | `EF-4c`,`EF-4u` — verified | exact mirrors | ✅ both write `unknown_reason=…` | exact | no | **VALID CONSUMER** *(co-commit declaration owed)* |
| 8 | `02:PL-15` `NEEDS_VERIFICATION→{VERIFIED,FAILED}` | **yes** (state + `decision_ref`) | `RealityEstablished` ‡ | `EF-5`,`CM-5` | genuine | ✅ §5 payload `decision_ref, outcome` | exact | no | **VALID CONSUMER** *(co-commit owed; the two-element `To` set is resolved by the event's `outcome` — this is delegation-shaped and owes the same exactly-one-owner-per-branch proof)* |
| 9 | `02:PL-15x` `NEEDS_VERIFICATION`+`TimerFired` | ### **NONE** (no `To`; `Writes` = —) | `IllegalTransitionAttempted` ‡ | `GR-1` — a **rule**, not a corpus row | GR-1 attaches universally | n/a | persists nothing | no | ### **NON_PRODUCING** — misclassified |
| 10 | `06:IB-5x` `CONFIRMED`+`RecomputedByInferrer` | ### **NONE** (no `To`; `Writes` = —) | `IllegalTransitionAttempted` ‡ | `GR-1` (rule) | as above | n/a | persists nothing | no | ### **NON_PRODUCING** — misclassified |
| 11 | `12:RU-3` `COMPILED → *(blocked)*` | ### **NONE** (`*(blocked)*` is not a canonical state; `Writes` = —) | `ConflictRaised` ‡ | `CF-1`,`IB-6`,`EF-4c` | **causation**, not co-transition | n/a | GR-2 does not bind | yes — M7's conflict is its own fact | **VALID CONSUMER (zero-write causation)** — carries **no exempting force** |

### The `PL-15x` / `IB-5x` misclassification — a divergence from an adjudicated disposition

Both rows are **structurally identical** to `EF-5x`, `CM-5x` and `BR-5`, which this same candidate
classifies `NON_PRODUCING:GR1_ILLEGAL_REFUSAL`: enumerated GR-1 refusal rows, no `To` state, `Writes`
= em-dash, persisting nothing. The only difference is that `PL-15x` and `IB-5x` historically named
`IllegalTransitionAttempted` inline in their Event cell.

**The G2 adjudication §H Step 7 already ruled on exactly this:**

> `PL-15x` and `IB-5x` naming it inline is **redundant documentation, not a different contract**. The
> inconsistency the audit flagged is **cosmetic**; normalising it is spec-only with **no runtime
> change**.

The candidate normalised three of the five and left two carrying a different class token. This is
not a safety defect — both are zero-durable-write — but it is a **divergence from an adjudicated
per-row disposition**, and it weakens the class's coherence by mixing durable-write co-transition
mirrors with zero-write refusal rows under one label. **The independent review did not catch it.**

### Corrected classification

```
PRODUCER 110 · CONSUMES 9 · NON_PRODUCING 6 · DELEGATES_TO 2 · EVENT_REQUIRED 7  = 134
```

**The number 11 is not preserved.** Nine survive as consumers — eight durable co-transition mirrors
plus one zero-write causation row — and two move to `NON_PRODUCING`.

**Decisively: none of the eleven is `ACTUALLY PRODUCER`, and none is `EVENT_REQUIRED`.** F-01 is a
**latent control weakness, not a live falsehood in the present corpus.** That distinction is what
makes the remediation narrow rather than structural, and it is why this is a REJECT for a targeted
fix rather than a governance blocker.

---

## 4. QUESTION 4 — THE `AP-9` EXPLOIT: REPRODUCED, AND EXTENDED

Run in a disposable `--no-local` clone at `38b4bda` (tree verified `e669ad33…`), fresh venv,
declared deps only, canonical config `pytest-canonical.ini`, `PYTEST_ADDOPTS` cleared.
**Baseline before mutation: 42 passed.**

| Question | Finding |
|---|---|
| `AP-9` has a durable safety-relevant state change involving `frozen=true` | ### **YES** — `04-approval.machine.md` §14 `Writes` = `frozen=true`; §15 *"Reuse of a frozen (AP-9) approval → ILLEGAL"*; §13 *"MUST NOT be reused until reality established"*. A guard input to an ILLEGAL determination |
| Existing event history cannot reconstruct `frozen=true` | ### **YES** — no F4 event carries the approval `frozen` flag. §5's F4 payloads: `ApprovalConsumed` = —, `ApprovalVoided` = `cause, drift_diff?`, `ApprovalGranted`/`Denied`/`Revoked`/`Expired` = —. A full-history rebuild reconstructs an approval that is **not frozen — i.e. reusable.** The rebuilt state is **less safe than the original** |
| Moving `AP-9` into `CONSUMES` makes the controls green | ### **YES — REPRODUCED** |
| The nominated producer is unrelated or mutually exclusive | ### **YES** — `ApprovalConsumed`'s §3 owner is `AP-7` (`GRANTED→CONSUMED`), verified by this session. `AP-9` is `GRANTED→GRANTED`. Same machine, same `From`, divergent `To`: **they cannot both fire on one approval** |
| Current `CONSUMES` validation fails to prove causal/payload ownership | ### **YES** |

### Reproduction — variant 1 (the reviewer's)

`04-approval.machine.md`: `EVENT_REQUIRED:G2-OB-AP-9-FREEZE-FACT-UNRECORDED` → `CONSUMES:ApprovalConsumed`.
`TRANSITION-EVENT-AUDIT.yaml`: `AP-9` moved from `EVENT_REQUIRED.members` to `CONSUMES.members` as
`{key: 04-approval:AP-9, consumes: [ApprovalConsumed], owner: [AP-7]}`; its obligation entry deleted;
`open_founder_gated_obligations: 7 → 6`; `CONSUMES: 11 → 12`, `EVENT_REQUIRED: 7 → 6`.

| Run | Result |
|---|---|
| G2 guard block (`test_bootstrap_hermeticity.py`) | ### **42 passed, 0 failed** |
| Complete canonical suite | ### **2088 passed, 3 skipped, 0 failed** (398s) |

**Exactly matching the independent review.**

### Reproduction — variant 2 (this session's extension)

`AP-9` → `CONSUMES:BrakeReleased`, owner `BR-4` (M13 Brake) — an event with **no machine, no
aggregate, no family, no causal and no temporal relationship** to an M4 approval freeze. `BrakeReleased`
is human-only-release; `AP-9` is a system freeze on a different machine.

| Run | Result |
|---|---|
| G2 guard block | ### **42 passed, 0 failed** |

> ### **The class does not require even same-machine, same-aggregate or same-family proximity. It admits ANY of the 98 canonical events.**

This is materially stronger than the reviewer's demonstration and it changes the character of the
finding: the missing invariant is **not a refinement of an existing relational check — there is no
relational check at all.**

### The exact missing invariant

**CONSUMES-VALID 4(a)–(d)** (§2). The minimal pair that defeats both variants is **4(b) + 4(c)**: the
consumed event's §3 owner must be a corpus row **in a different machine** standing in a **declared**
co-transition with the consuming row, and **must not be mutually exclusive with it**.

**No event was invented. Emit-versus-derive remains founder/architect gated and this session takes no
position on it.**

---

## 5. QUESTION 5 — MINIMUM STRUCTURAL PROOF FOR `CONSUMES`

`CONSUMES` is permitted in principle (§1). Required contract = **CONSUMES-VALID** (§2). Against the
brief's checklist:

| Must it prove? | Ruling |
|---|---|
| consumer transition exists | **YES** — already proven |
| producer transition exists | **YES** — for `GR-1`-owned events the owner is a **rule**, so those rows must be `NON_PRODUCING`, not `CONSUMES` (§3 rows 9–10) |
| producer is canonical for the named event | **YES** — already proven |
| producer and consumer participate in the same authorized semantic operation | ### **YES — 4(a)+(b)+(c). The core missing requirement** |
| explicit structural link exists in canonical data | ### **YES — the bidirectional `co-commit` declaration in both rows' `Writes` cells** |
| no prose-only relationship | ### **YES.** The `## M2↔M3 co-transition rule` blockquote may **never** be the predicate — narrative sections are exactly what §F refused |
| producer event payload covers every durable consumer state mutation | **YES, as 4(d)** — coverage-or-derivability, not literal encoding (`events/registry.md`:7 forbids instruction) |
| replay reconstructs both producer and consumer state | **YES** — this is the operative GR-2 test (AC-EVT-008) |
| causal identity preserved | **YES** — the transaction binds; `causation_id` carries it at runtime |
| zero producer ownership impossible | **YES** — already asserted by the bijection guard |
| duplicate producer ownership impossible | **YES** — already asserted; unchanged |
| mutually-exclusive producer/consumer pair rejected | ### **YES — 4(b). Absent today. This is what laundered `AP-9`** |
| unrelated event-family membership insufficient | ### **YES — 4(c)+(a). Absent today** |
| `EVENT_REQUIRED` cannot be downgraded without structural proof | ### **YES — rule 5** |
| `NON_PRODUCING` cannot convert without durable-write semantics | **YES — rule 5** |
| unknown relationship fails closed | ### **YES — rule 6** |

### Precise machine-checkable source of truth

| Predicate | Authority | Status |
|---|---|---|
| Producer identity | `events/registry.md` §3 producer-transition field — sole authority | unchanged from G2 §G |
| Durable write | `From → To` + `Writes`/`Prov` columns of each `## 14. Transition table` | unchanged |
| **Co-commit relation** | ### **the `Writes` column's `co-commit` declarations, required in BOTH rows** | ### **new — and it already exists as structured data.** `EF-2` carries *"co-commit M2 `CLAIMED`, M4 `CONSUMED`"*; `PL-9` carries *"co-commit: M3 `CLAIMED` + M4 `ApprovalConsumed`"*. The seven under-declared durable consumers and their owners need the same cell content added — **spec-only, mints no event, does not touch the 98** |
| Mutual exclusivity | `From`/`To` sets within a machine — already parsed | new, computed from existing data |
| Payload coverage | `state-machines/registry.md` §5 payload column | new |
| Prose | ### **never a predicate, in any class** | binding |

---

## 6. QUESTION 6 — DID THE BUILDER EXCEED AUTHORITY?

**Architecture legitimacy and control sufficiency separate cleanly, and they answer differently.**

### Architecture legitimacy — **NO, the builder did not exceed authority**

Encoding §182's pre-existing consume relation as a structured token falls within *"classification
markers only"* on `*.machine.md`, which G2 §L expressly allows. The relation, the word and the eleven
rows all pre-exist; `events/registry.md` and `state-machines/registry.md` are byte-unchanged; the
frozen 98 is untouched. The builder **disclosed the tension in handoff §G and asked a reviewer to
confirm it** rather than asserting it silently. That is correct conduct under the stop-boundary
discipline, and it is why this is not answer A.

### Control sufficiency — **YES, in three specific acts**

**1. Silent amendment of the adjudicated contract text.** The guard
`test_every_durable_write_is_recorded_by_an_event_or_a_registered_open_obligation` carries the
docstring: *"There is no **fourth** option and no silent exemption."* §G says *"**No third option**."*
Rewriting the adjudicated wording — inside the control artifact that enforces it, by the party the
contract binds — is an amendment, not an implementation detail. It should have been raised, not made.

**2. A control document asserting an unproven and partly false safety property.**
`TRANSITION-EVENT-AUDIT.yaml` `contract.classification_vocabulary.CONSUMES` asserts: *"The durable
change this row makes **is recorded by that event, emitted in the same commit by its owner**."* The
guard proves none of it — and the assertion is **factually false today for ten of the eleven rows**,
since only `PL-9` carries a declared bidirectional co-commit (§3). ### **This is `CF-7`'s failure mode
re-committed: a document certifying a safety property about itself that nothing checks.**

**3. Divergence from an adjudicated per-row disposition.** `PL-15x` and `IB-5x` were classified
`CONSUMES` against §H Step 7's explicit ruling that their inline naming is *"redundant documentation,
not a different contract."*

### Ruling

> **A reasonable implementation detail requiring materially stronger guards — plus two over-reaches
> in the control text and one divergence from an adjudicated disposition. Not a material expansion
> of architecture beyond builder authority.**

---

## 7. F-02 — STALE `PHASE-OUTPUTS.md` PROSE

> ### **UPHELD, NARROWED. MEDIUM. Not independently blocking; in scope for the replacement.**

Verified live at `docs/implementation/PHASE-OUTPUTS.md:153`, P5 block, **Blocked on** row:

> *"### **The transition/event completeness finding must be adjudicated first** — COUNT NEEDS
> ADJUDICATION, 4 classes, [`TRANSITION-EVENT-AUDIT.yaml`]…"*

`git diff 6e8127d 38b4bda -- docs/implementation/PHASE-OUTPUTS.md` is **empty** — the candidate did
not touch it.

| Question | Ruling |
|---|---|
| A live canonical/control falsehood? | ### **YES.** `CANONICAL-DOCUMENTS.md:129` classifies `PHASE-OUTPUTS.md` as **IMPLEMENTATION_CONTROL**. Three live falsehoods: (a) G2 **has** been adjudicated, at `6e8127d`; (b) the vocabulary is **five** classes, not four; (c) `COUNT NEEDS ADJUDICATION` is a **retired status token** whose guard this candidate deliberately moved |
| Does it block acceptance? | **Not on its own.** It is **conservative-direction** drift — it *understates* progress, creates no false green, and cannot cause an unsafe act. Neither new anti-drift guard catches it (`\b24\b…(transitions?\|event)` and `\b(?:13\|121)\b\s*(?:of\s*134\|transitions)` both miss this wording) |
| Correct in a replacement candidate? | ### **YES.** A replacement is required for F-01 regardless, and this is squarely in scope: removing the stale G2 count is U5.1's stated purpose, and G2 §E names `PHASE-OUTPUTS.md` in the anti-drift guard population. It is on neither the forbidden list nor a freeze-critical surface |
| Or label it historical instead? | ### **NO.** It sits in a forward-looking *"Blocked on"* row purporting to state the **current** block. Relabelling it historical would make it false in a different way. It must be **corrected** |

**Remediation:** rewrite that one row to match `CURRENT.md:115` (G2 adjudicated, partially discharged,
seven founder-gated obligations), and extend the anti-drift guard to forbid `COUNT NEEDS ADJUDICATION`
appearing as a **live** claim anywhere in the control-document population.

---

## 8. F-03 — RETIRED 24-FIGURE GUARD

> ### **UPHELD AS REPORTED. MEDIUM-LOW. Real. Latent, not live. Not independently blocking — remediate with F-01.**

**Reproduced by this session**, appending one line to `docs/implementation/CURRENT.md`:

| Sentence appended | Result |
|---|---|
| `24 of the 134 transitions name no event outright.` *(control)* | ### **1 failed** — `test_the_retired_24_figure_does_not_reappear_in_control_documents`, as intended |
| `24 of the 134 transitions name no event outright, which is the non-producer population.` | ### **42 passed — GUARD BYPASSED** |

| Question | Ruling |
|---|---|
| A real anti-drift weakness? | ### **YES.** One appended clause revives the retired figure in **exactly its retired sense** across the entire guarded population (`CLAUDE.md`, `README.md`, `ARCHITECTURE.md`, `CURRENT.md`, `PHASE-OUTPUTS.md`) |
| Do current semantics distinguish the two senses of `24`? | ### **YES.** *24 canonical non-producer transitions* (live, computed, correct) vs *24 unnamed/non-event transitions* (retired, never mechanically computed). The audit's `retired_figures` records both; the live corpus uses only the correct sense. **The candidate does not conflate them** |
| Must the guard bind meaning structurally rather than by nearby prose keywords? | ### **YES.** A ±120-character proximity window is precisely the prose-proximity predicate §F refused for classification. It is no more defensible for anti-drift, and it is a defect **in a guard this candidate introduced** |
| Blocks the current candidate, or residual? | **Neither purely.** Latent — no current document abuses it. But it is this unit's own new guard, so it is this unit's to fix, and it rides the F-01 replacement at near-zero marginal cost |

**Remediation:** scope the carve-out to the **matched sentence** rather than a character window, and
require `24` and `non-producer` in the **same clause** — e.g. admit only
`24[^.\n]{0,40}non-producer transitions` — with a hostile node asserting the reproduction sentence
above **FAILS**.

---

## 9. F-04 — PRIMARY WORKTREE FAILURE

> ### **CONFIRMED — PRE-EXISTING AUTHORIZED WORKTREE ARTIFACT — NON-BLOCKING.** The review's classification is **upheld**, on this session's own control.

**Decisive control run independently**, single node
`test_every_implementation_document_is_classified_or_family_covered` in a clean clone at both refs:

| Ref | Without the artifact | With the artifact |
|---|---|---|
| `6e8127d` (certified predecessor) | ### **1 passed** | ### **1 failed** |
| `38b4bda` (candidate) | ### **1 passed** | ### **1 failed** |

### **Identical behaviour at both refs. The candidate is not implicated.**

| Check | Result |
|---|---|
| Offending file | `docs/implementation/p4-r07-third-finalization-pass-report-6e8127d.md` — untracked; the guard globs `docs/implementation/*.md` **on disk** |
| Predates the candidate? | **Yes** — mtime `2026-08-06 18:43`; candidate committed `2026-08-08` |
| Authorized and preserved? | **Yes** — `refs/preserve/p4-r07-third-finalization-report-6e8127d` → `61d4246620cfa9e8e5217e72c00edae767790d0e`, plus a `.sha256` sidecar |
| Did the candidate create it? | **No** |
| Was the test modified? | **No** — `git diff 6e8127d 38b4bda -- eval/tests/test_bootstrap_hermeticity.py` contains **zero** hunks touching this node |
| Clean clone | passes at both refs |
| Report deleted or modified? | ### **NO — neither. Left exactly as found** |

**Inherited residual, not this unit's:** the repository's convention gives each finalization-pass
report a row in `CANONICAL-DOCUMENTS.md`; the first two have one, the third does not. The guard is
telling the truth about a genuine P4/R-07-campaign gap. The R-07 record surface is **forbidden** to
U5.1. Carry to the next R-07-adjacent correction, alongside F-06.

---

## 10. F-05 — `AP-9` REPLAY SAFETY

> ### **UPHELD. HIGH (architecture), correctly OPEN, NOT a candidate defect. It does NOT prevent U5.1 acceptance or finalization.**

The two questions the brief demands be kept separate, answered separately:

**1. Does `38b4bda` correctly surface `AP-9` as unresolved `EVENT_REQUIRED`? — YES.**

| Requirement | Verified |
|---|---|
| Classified `EVENT_REQUIRED` | ✅ `EVENT_REQUIRED:G2-OB-AP-9-FREEZE-FACT-UNRECORDED` in `04-approval.machine.md` §14 |
| Obligation registered and complete | ✅ `transition`, `durable_write: "frozen=true"`, `severity: HIGHEST SAFETY OF THE SEVEN`, `semantic_obligation`, `why_it_matters`, `admissible_remedies` (both), `remedy_note: "DO NOT IMPROVISE THE EVENT DESIGN"`, `decision_required: founder/architect — emit-vs-derive` |
| No name invented | ✅ obligation id fails `^[A-Z][A-Za-z0-9]*$` and is absent from the corpus; `events/registry.md` byte-unchanged |
| Status honest | ✅ `meta.status = G2_PARTIALLY_DISCHARGED_FOUNDER_GATED`, `open_founder_gated_obligations: 7` |
| Fail-closed default recorded | ✅ *"treat any approval with an unresolved `OutcomeUnknown` as frozen"* |

**2. Does full G2 discharge require founder/architect event-schema authority? — YES.** Emit a new
`Approval*` event, or remove the durable write and derive `frozen` over
`OutcomeUnknown ∧ ¬RealityEstablished`. ### **This session resolves nothing and takes no position.**

**Ruling on the question actually asked:** ### **`AP-9` being deliberately unresolved does NOT prevent
U5.1 from being accepted or finalized.** G2 §L authorized exactly *"a bounded P5 U5.1 (G2 spec
correction + acceptance-contract instantiation); event-schema content gated on a founder/architect
event-naming decision."* **U5.1 may legitimately certify the fail-closed `EVENT_REQUIRED` state ahead
of a later founder-authorized event-schema unit.** Rejecting because `EVENT_REQUIRED` rows remain
would reject the unit for doing precisely what it was authorized to do.

**Sub-residual, recorded not blocking:** the fail-closed interim default is documentary only; no guard
enforces it. Correct — there is no runtime to bind it to, since P5's event content is blocked. A note
for whoever implements it.

---

## 11. F-06 — `README.md` R-07 BLOCKQUOTE ON A FORBIDDEN SURFACE

> ### **UPHELD AS CLASSIFIED. LOW. Non-blocking residual. NO remediation owed by U5.1 — touching it would have been a scope violation.**

`README.md:73-80`, verified **byte-identical at `6e8127d`** (`git show 6e8127d:README.md`):

> *"…and the record still says `OPEN — NOT CONTAINED`. … What has **not** happened is the recording
> of R-07 as contained, which is a separate commit."*

Both clauses are false as of the R-07 closure commit, and they contradict `README.md:65` in the same
file (*"**CONTAINED** — … the CONTAINED **record** is now written"*) and `CLAUDE.md:73`.

| Question | Ruling |
|---|---|
| Pre-existing? | ✅ byte-identical at the certified predecessor; the candidate's README diff touches only lines 53 and 68 |
| Correctly left untouched? | ### **YES.** The R-07 containment record is a **forbidden surface** for U5.1 under G2 §L. The builder disclosed it in handoff §L.5 and did not touch it — correct |
| Direction of error | **conservative** — it under-claims containment. It cannot cause an unsafe act |
| Owed by U5.1? | ### **NO.** Carry to the next R-07-adjacent correction with F-04's residual |

---

## 12. F-07 — NO HOSTILE NODE COVERS `CONSUMES`

> ### **UPHELD, SEVERITY RAISED to HIGH, and MERGED INTO F-01.**

The reviewer graded this MEDIUM "evidence deficiency." It is more. The builder's handoff §H claims
*"Seven are hostile cases, **one per adjudicated defect class**"* — and `CONSUMES`, **the only
exempting class without an independent truth predicate**, is the one class with no hostile node.
That absence is **causally why F-01 shipped**: the candidate's own tooling would have caught the
laundering had the battery been complete as claimed.

It is therefore **not a finding to schedule alongside F-01** — the hostile node **is** part of F-01's
remediation and is its acceptance test. It must assert **both** variants fail:
- the mutually-exclusive same-machine case (`AP-9` → `CONSUMES:ApprovalConsumed`, owner `AP-7`), and
- the wholly-unrelated cross-machine case (`AP-9` → `CONSUMES:BrakeReleased`, owner `BR-4`),

with a **positive control** that the genuine co-transition row `PL-9` passes, so the node cannot pass
vacuously.

---

## 13. COUNT COINCIDENCE vs SEMANTIC RECLASSIFICATION INTEGRITY

**Stated explicitly, as the brief requires.**

The 18 hostile mutations test **membership integrity**: that each class's *member identities* are
pinned by exact set equality, so no same-count substitution survives. All 18 fail closed. **I do not
reopen them** — including M2/M2b, which is nominally the same `EVENT_REQUIRED → CONSUMES` move on
`AP-9`.

**F-01 exposes a different dimension: semantic reclassification integrity.**

M2/M2b fails because the **audit was not updated to match the spec** — it trips the spec↔audit drift
assertion, not any check on whether the new classification is **true**. The F-01 exploit succeeds
precisely by updating the audit **consistently**, which is the ordinary shape of a legitimate builder
commit. Every set-equality guard is then satisfied, because *computed == recorded*. The arithmetic
still closes:

```
110 + 12 + 4 + 2 + 6 = 134        ← internally consistent, and WRONG
```

> ### **A candidate must not be accepted because its classes reconcile. Set equality between the specification and the audit proves the two documents AGREE. It proves nothing about whether either is TRUE.**

Every class except `CONSUMES` carries an independent **truth** predicate read from structured columns:

| Class | Independent truth predicate |
|---|---|
| `PRODUCER` | §3 membership — the row may not self-declare it |
| `NON_PRODUCING` | zero durable writes, proven from `From→To` + `Writes` |
| `DELEGATES_TO` | target exists · is a §3 producer · target-state match · exactly-one-owner · exact `To`-set coverage |
| `EVENT_REQUIRED` | obligation registered · id not event-shaped · absent from the corpus |
| ### `CONSUMES` | ### **NONE — a consistency check only** |

**That asymmetry is the finding.** An `EVENT_REQUIRED` row can be relabelled `CONSUMES` and made to
reconcile perfectly without proving any causal ownership whatsoever — and, per §4 variant 2, without
proving *any relationship of any kind*.

---

## 14. CANDIDATE ACCEPTANCE SCOPE — WHAT WAS AND WAS NOT REQUIRED

U5.1 is **intentionally not full G2 discharge**. It may legitimately leave founder/architect event-name
decisions unresolved for `PL-7a`, `AP-9`, `CF-7`, `EC-7`, `PO-2`, `PO-3`, `RU-8`, and the canonical
registry must stay at **98**. Verified by this session:

| Property | Result |
|---|---|
| `docs/specifications/events/registry.md` | ### **byte-unchanged** — `git diff` empty. The mechanical proof no event was minted |
| `docs/specifications/state-machines/registry.md` | byte-unchanged |
| Canonical event total | ### **98** — audit asserts it, the guard enforces it, the registry is frozen |
| Seven obligations | **OPEN**, each registered with its decision required |
| `PROGRAM-WEIGHTS.yaml` | byte-unchanged (the frozen template) |
| P5 acceptance contract | ### **14 criteria · weights sum exactly 100 · VERBATIM ORDERED match to the frozen template · all 14 PENDING** — verified by YAML comparison of `[(criterion, weight)]` |
| P5 triple | `READY / NOT_STARTED / NO_CHECKPOINT` — correctly unchanged |
| P4 | ### **COMPLETE / COMPLETE / PHASE_ACCEPTANCE_COMPLETE**, 14/14 PASS, weighted **100** |
| R-07 | ### **CONTAINED** — `phase-0-baseline-manifest.yaml` byte-unchanged |
| Production `GateRegistry` | ### **EMPTY** — zero constructions in `src/` + `scripts/` |
| `src/` · `scripts/` · `configs/` · `data/` · `.claude/` · `docs/architecture/` | byte-unchanged — no runtime or effect-safety boundary moved |
| `SUITE-RESULT.json` · `GATE-RESULT.json` | byte-unchanged, still bound to `a31a94a` |

### **This candidate is NOT rejected for leaving `EVENT_REQUIRED` rows open.** It is rejected because
its `CONSUMES` control does not discharge the §G completeness obligation it claims to discharge, and
because it leaves one live control falsehood the unit exists to remove.

---

## 15. TOPOLOGY RULING

> ### **A. REPLACE `38b4bda` IN PLACE AGAINST `6e8127d`, AFTER PRESERVING THE REJECTED CANDIDATE.**

**Grounds — mechanical, from repository authority only.**

`PROGRESS-PROTOCOL.md` §10:

> The two-commit convention permits `HEAD` to be **only** the certified content commit or the single
> finalizer-generated metadata commit directly above it, and `test_status_reality.py` resolves both
> through **first-parent** lookups (`HEAD^`, `HEAD^^`).

A second content commit would place `HEAD` three commits above `6e8127d` — **not expressible in that
resolution**, and precisely the *"stale beyond every legal state"* condition §10 records `main`
already occupying at `152574e`.

§10 also settles that remediation is legal pre-integration: *"a unit may be built, **reviewed,
remediated** and finalized locally without discharging it."*

**Precedent — verified by direct object inspection, not from a report.** The P4/R-07 campaign ran
four candidates. All four share the **identical single parent `06ebfdb`**:

| Candidate | Parent | Disposition | Preserved as |
|---|---|---|---|
| `11c9112` | `06ebfdb` | REJECTED | `archive/p4/r07-rejected-11c9112` + `refs/preserve/p4-r07-closure-rejected-candidate-11c9112` |
| `4d12b0e` | `06ebfdb` | REJECTED | `archive/p4/r07-rejected-replacement-4d12b0e` + `refs/preserve/…-rejected-replacement-candidate-4d12b0e` |
| `3874d4a` | `06ebfdb` | REJECTED | `archive/p4/r07-rejected-successor-3874d4a` + `refs/preserve/…-rejected-successor-candidate-3874d4a` |
| `a31a94a` | `06ebfdb` | **ACCEPTED** → finalizer produced `6e8127d` | — |

Each rejection produced a **fresh single content commit against the same parent**; each rejected
candidate was preserved on **both** an archive branch and a `refs/preserve/` ref; **each replacement
received a completely fresh independent review and a separate targeted adjudication**; the finalizer
ran **once**, only after the fourth was accepted. That is the repository's own established mechanism,
and it is Option A exactly.

**C is REFUSED.** No repository authority permits a second content commit.
**The Product Driver's `max_content_commits=7` was NOT used.** Per G2 §K it is a `_CONTENT_COUNT_RE`
defect reading the `07` of *"R-07 content commit"* as a cardinal; it is non-authoritative and topology
here was judged from Git objects and `PROGRESS-PROTOCOL.md` §10 only.
**B is REFUSED** on the grounds in §17.

### Replacement requirements

| Item | Requirement |
|---|---|
| **Candidate to preserve** | ### `38b4bda6cb3ea6c5e5c9a302fd64d23450e6fc62` (tree `e669ad3375822b0a458b5466d9ce8fb37fceddb3`) |
| **Preservation** | `archive/p5/u51-rejected-38b4bda` **and** `refs/preserve/p5-u51-rejected-candidate-38b4bda`; the independent review and this adjudication each preserved parented to the candidate, each with a `.sha256` sidecar — matching the P4/R-07 protocol. `refs/preserve/p5-u51-prestate-6e8127d` (`e77ab673…`) **stays** |
| **Exact parent** | ### `6e8127dab02e3443183d06825836f5a805f53de0` — single parent, no merge, exactly ONE content commit |
| **Allowed remediation surfaces** | `eval/tests/test_bootstrap_hermeticity.py` (narrowed `CONSUMES` guard; the F-07 hostile node; the F-03 carve-out; the F-02 anti-drift extension) · `docs/implementation/TRANSITION-EVENT-AUDIT.yaml` (CONSUMES contract text, §182 citation, `PL-15x`/`IB-5x` reclassification, counts) · the seven under-declared durable consumers' and their owner rows' `Writes` cells in `*.machine.md` (co-commit declarations) · `PL-15x`/`IB-5x` classification tokens · `docs/implementation/PHASE-OUTPUTS.md:153` · `docs/implementation/TEST-NODE-MANIFEST.json` (regenerated via `scripts/regenerate_test_manifest.py`) · everything already correct in `38b4bda`, carried forward unchanged |
| **Forbidden surfaces** | Unchanged from G2 §L — production `GateRegistry` · `src/freight_recon/effect_boundary.py` and every adapter · `phase-0-baseline-manifest.yaml` · `driver.config.yaml` · any Action Class registration · any live-writer injection. ### **Additionally: `docs/specifications/events/registry.md` — the 98 stays frozen and NO event may be minted to "solve" a consumer's payload gap** · `docs/specifications/state-machines/registry.md` · `PROGRAM-WEIGHTS.yaml` · `SUITE-RESULT.json`/`GATE-RESULT.json` · the `README.md` R-07 blockquote (F-06) |
| **Fresh re-review** | ### **REQUIRED — complete, by a session that did not build, did not review `38b4bda`, and did not write this adjudication** |
| **Separate re-adjudication** | ### **REQUIRED — a fourth session** |
| **Finalizer** | ### **NOT until both succeed.** Then exactly ONE finalizer-generated metadata commit |

---

## 16. FINALIZER ELIGIBILITY

> ### **`38b4bda` MAY NOT PROCEED to its one allowed finalizer-generated metadata commit.**
>
> The finalizer was **not run** by this session and must not be run on this candidate.

Against the eight statements an acceptance must make:

| # | Statement | Ruling |
|---|---|---|
| 1 | `CONSUMES` architecture is legitimate | ### **YES** — ruling B (§1) |
| 2 | `CONSUMES` controls are sufficient | ### **NO** ← **the sole failing item** |
| 3 | F-02 / F-03 nonblocking or resolved by interpretation | **PARTLY** — neither is independently blocking, but both are real, both are this unit's own to fix, and both ride the same replacement at near-zero marginal cost |
| 4 | `AP-9` may remain `EVENT_REQUIRED` | ### **YES** (§10) |
| 5 | Canonical event count remains 98 | ### **YES** — mechanically proven; registry byte-unchanged |
| 6 | P5 acceptance contract is valid | ### **YES** — 14 · sum 100 · verbatim ordered · all PENDING |
| 7 | P4 / R-07 remain intact | ### **YES** — P4 COMPLETE 14/14, R-07 CONTAINED, `GateRegistry` EMPTY |
| 8 | U5.1 scope is complete | ### **NO** — F-02 leaves a live control falsehood the unit exists to remove, and the `CONSUMES` control does not discharge the §G completeness obligation it claims to |

**Two of eight fail. Both are narrow and both are fixable without founder authority.**

---

## 17. ADJUDICATION VERDICT

> ### **REJECT — TARGETED REMEDIATION REQUIRED**

### Why not *ACCEPT WITH CARRIED NON-BLOCKING RESIDUALS*

That verdict requires F-01 to be non-blocking. It is not, for one reason: **the candidate's own
canonical control document asserts a safety property that nothing proves and that is false today for
ten of its eleven rows**, governing the one exempting class with no truth predicate. Accepting it
would finalize into the canonical audit a mechanism that converts the corpus's highest-severity open
safety obligation into a discharged one with a two-line edit — and §4 variant 2 shows it converts with
an **arbitrary, wholly unrelated** event, not merely a plausible one. That is not a documentation
residual. It is a hole in the guard that certifies GR-2.

### Why not *GOVERNANCE BLOCKER — FOUNDER/ARCHITECT DECISION REQUIRED*

Because the authority to decide `CONSUMES` **already exists in the repository** and is applied in §2:
`state-machines/registry.md`:182, the `## M2↔M3 co-transition rule`, the `Writes` column's `co-commit`
declarations, and `events/registry.md`:7's deterministic-consumer-guard rule together fix a complete,
machine-checkable contract. No founder decision is required to narrow the guard, reclassify
`PL-15x`/`IB-5x`, add co-commit declarations, or fix F-02/F-03 — **none of that touches an event name
or the frozen 98.**

The founder/architect gate remains exactly where G2 placed it and where this candidate correctly left
it: the seven event names, `AP-9`'s emit-vs-derive among them.

> ### **U5.1 is not founder-blocked. It is guard-blocked.**

### The narrowest legal replacement delta — six items, nothing else moves

1. **Narrow the `CONSUMES` guard** (`test_consuming_rows_name_an_event_owned_by_a_different_transition`)
   to enforce **CONSUMES-VALID 4(a)–(d)** for durable-writing consumers; fail closed on undecidable.
2. **Add the missing hostile node** (F-07): an `EVENT_REQUIRED` row relabelled
   `CONSUMES:<unrelated canonical event>` must **FAIL** — asserting **both** §4 variants
   (`ApprovalConsumed`/`AP-7`, mutually exclusive; `BrakeReleased`/`BR-4`, wholly unrelated) — with a
   positive control that `PL-9` passes.
3. **Correct `TRANSITION-EVENT-AUDIT.yaml`'s `CONSUMES` text** so what it asserts is what the guard
   proves; fix the `events/registry.md §182` → `state-machines/registry.md §182` misattribution.
4. **Reclassify `PL-15x` and `IB-5x`** to `NON_PRODUCING:GR1_ILLEGAL_REFUSAL` per G2 §H Step 7
   (`PRODUCER 110 · CONSUMES 9 · NON_PRODUCING 6 · DELEGATES_TO 2 · EVENT_REQUIRED 7 = 134`), and add
   the bidirectional co-commit declarations to the seven under-declared durable consumers and their
   owner rows.
5. **Rewrite `PHASE-OUTPUTS.md:153`**; extend the anti-drift guard to forbid `COUNT NEEDS ADJUDICATION`
   as a live claim.
6. **Scope the F-03 carve-out** to the matched sentence/clause, with a hostile node asserting the
   §8 reproduction sentence **FAILS**.

**No event is minted. The 98 stays frozen. The seven obligations stay open. `AP-9` stays
`EVENT_REQUIRED`. Everything else in `38b4bda` is carried forward unchanged — the classification work,
the `EF-3` re-attribution, the `DELEGATES_TO` resolution, the `NON_PRODUCING` proofs, the bijection
guards, the canonical-document corrections, and the P5 acceptance contract are all correct and
independently verified.**

---

## 18. FINDINGS DISPOSITION SUMMARY

| ID | Disposition | Severity | Blocking | Required remediation |
|---|---|---|---|---|
| **F-01** | ### **UPHELD and STRENGTHENED** — architecture ratified (B), controls refused | ### **HIGH** | ### **YES** | Narrow the guard to CONSUMES-VALID 4(a)–(d); correct the audit contract text; reclassify `PL-15x`/`IB-5x`; add co-commit declarations |
| **F-02** | **UPHELD, narrowed** — live control falsehood, conservative direction | MEDIUM | Not independently; **in scope for the replacement** | Rewrite `PHASE-OUTPUTS.md:153`; extend the anti-drift guard |
| **F-03** | **UPHELD as reported** — reproduced exactly | MEDIUM-LOW | No — but this unit's own new guard | Sentence/clause-scoped carve-out + hostile node |
| **F-04** | ### **CONFIRMED** — pre-existing authorized artifact, identical at both refs | INFORMATIONAL | No | **None owed by U5.1.** Report not deleted, not modified |
| **F-05** | **UPHELD** — hazard real, correctly left open | HIGH (architecture) | ### **No — does not prevent U5.1** | Founder/architect: emit-vs-derive. Not this unit |
| **F-06** | **UPHELD as classified** — pre-existing, forbidden surface | LOW | No | **None owed by U5.1.** Carry with F-04's residual |
| **F-07** | ### **UPHELD, severity RAISED, MERGED into F-01** | ### **HIGH** (was MEDIUM) | **YES**, as part of F-01 | The hostile node is F-01's acceptance test |
| **New** | `PL-15x`/`IB-5x` classified `CONSUMES` against G2 §H Step 7 | MEDIUM | With F-01 | Reclassify to `NON_PRODUCING:GR1_ILLEGAL_REFUSAL` |
| **New** | `§182` cited to the wrong registry file in the audit, the commit message and the review | LOW | With F-01 | Correct to `state-machines/registry.md` |

The review's **non-findings** (the G2 §H 7-vs-8 counting slip; `PL-15x`/`IB-5x` and the `GR-1` schema
gap G2-D8; `RU-3` vs G2-D9; G2-D4/D6/D8/D9/D10 recorded open; PD-02 as a tooling residual) are
**upheld as non-findings**, with the one exception that `PL-15x`/`IB-5x` **classification** is now a
finding in its own right, distinct from the G2-D8 schema question the reviewer correctly separated.

---

## 19. PROOF THE PRODUCT REPOSITORY WAS NOT CHANGED

Measured after every read, parse, clone and mutation run:

| Field | Value |
|---|---|
| HEAD | `38b4bda6cb3ea6c5e5c9a302fd64d23450e6fc62` |
| Tree | `e669ad3375822b0a458b5466d9ce8fb37fceddb3` |
| Branch | `p5/u5-1-g2-spec-correction` |
| Parent | `6e8127dab02e3443183d06825836f5a805f53de0` |
| Index digest (`git ls-files -s ‖ sha256`) | `0b630149d44f34e5c45a635258a72b2eb14b1de8a98cf893c3a46f64fd385c8e` |
| Worktree-status digest | `2babbc0cce82e8374d038244574325e32d9bc7e9e2f208f57ee0293a1bf9cac0` |
| Total refs | `67` |
| `p4/adapter-containment-completion` | `6e8127dab02e3443183d06825836f5a805f53de0` — **unmoved** |
| `main` / `origin/main` | both `152574e4f4f2969468c9d31b1e705188896175b5` |
| `refs/preserve/p5-u51-prestate-6e8127d` | `e77ab673021831ff71fb7f74c58c88fce8b377c3` |
| Untracked set | exactly the two authorized third-finalization artifacts |
| Commits above `6e8127d` | **1** |
| Commits above `38b4bda` | **0** |
| Remote `p5/` refs | **0** |

> Index and worktree-status digests are **byte-identical to §S of the independent review**, proving
> the candidate is unchanged since review and that this session mutated nothing.

**Not done by this session:** no product commit · no amend · no ref creation, deletion or move · no
`checkout`, `reset`, `restore`, `stash`, `clean`, `rebase`, `merge`, `gc` or `prune` in the product
repository · no push, deploy or effect-enabling action · no `finalize_status.py` and no other
finalizer · no remediation · no modification of the candidate · no event minting · no change to the
frozen 98 · no new canonical event name · no second P5 unit · no `driver.config.yaml` or Product
Driver modification · no Desktop-repository modification · no P4/R-07 reopening · the untracked
third-finalization report was neither deleted nor modified.

**Writes performed, in full:** this report and its `.sha256` sidecar (non-product handoff,
uncommitted); and one disposable `--no-local` clone plus its venv in the session scratchpad, outside
both repositories, containing all mutation testing.

**SHA-256 of this report** (computed over the file as written, before this line was appended; the
sidecar `p5-u51-g2-spec-correction-targeted-adjudication-38b4bda.md.sha256` carries the authoritative
digest of the final file):

```
a434017d315a55915ce5eaadaa44c442edaf3186c2b7bd45bebd00794bf93aac
```

---

## 20. WHAT IS OWED NEXT

1. **A narrow remediation pass** producing a **replacement content commit parented to `6e8127d`**,
   after preserving `38b4bda` on `archive/p5/u51-rejected-38b4bda` and
   `refs/preserve/p5-u51-rejected-candidate-38b4bda`. Scope: the six items in §17, nothing else.
2. **A completely fresh independent review** by a session that did not build, did not review
   `38b4bda`, and did not write this adjudication.
3. **A separate targeted re-adjudication** by a fourth session.
4. **Then exactly ONE finalizer-generated metadata commit.** Single parents throughout; no merge
   commit above a certified content commit.
5. **Unchanged and still binding:** the seven founder/architect event obligations remain **OPEN**, the
   canonical event total stays **98**, `AP-9` stays `EVENT_REQUIRED` under its fail-closed default,
   and P5's event content stays blocked.

---

**END OF TARGETED GOVERNANCE ADJUDICATION**

**Candidate `38b4bda6cb3ea6c5e5c9a302fd64d23450e6fc62` · tree `e669ad3375822b0a458b5466d9ce8fb37fceddb3` ·
parent `6e8127dab02e3443183d06825836f5a805f53de0` · branch `p5/u5-1-g2-spec-correction`.**
**Independent-review digest verified: `27906bcec34bc7e660ed27d84f5cdcdf6be37ef436b113eb564c048e293f8a43`.**

### **VERDICT: REJECT — TARGETED REMEDIATION REQUIRED.**

**F-01 ruling: `CONSUMES` is architecturally LEGITIMATE (not a third GR-2 exemption) but its controls
are INSUFFICIENT — no relational check exists at all, proven twice.
Topology: REPLACE IN PLACE against `6e8127d` (Option A).
Finalizer: NOT ELIGIBLE.
No event minted · total still 98 · P4 COMPLETE and R-07 CONTAINED retained · nothing pushed · product
repository unchanged.**

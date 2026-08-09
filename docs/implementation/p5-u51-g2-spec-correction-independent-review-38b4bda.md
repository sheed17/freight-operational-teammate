# NEYMA P5 U5.1 — G2 SPEC/CONTROL CORRECTION: FRESH INDEPENDENT REVIEW

**Content candidate `38b4bda6cb3ea6c5e5c9a302fd64d23450e6fc62` (tree `e669ad3375822b0a458b5466d9ce8fb37fceddb3`)
over certified predecessor `6e8127dab02e3443183d06825836f5a805f53de0` (tree `515db7425b9ad18b4286b64436f9d240f2e865f6`).**

Written outside the product branch and tree. No product commit. No finalizer. No adjudication.
No remediation. The candidate was not modified.

---

## VERDICT

> ### **CONDITIONALLY ACCEPT — GOVERNANCE ADJUDICATION REQUIRED**
>
> Everything the candidate claims to have measured, this session reproduced independently and
> exactly: 134 rows, 98 canonical events, 110 producers / 24 non-producers, the 110/11/4/2/7
> classification by exact membership, `2091 collected / 2090 passed / 0 failed / 1 skipped`, and
> a byte-unchanged `events/registry.md`. Eighteen adversarial mutations — including every
> constant-total membership swap the brief required — all failed closed. No canonical event was
> minted. No forbidden surface moved. The P5 acceptance contract is a verbatim, unscored
> transcription of the frozen template.
>
> ### **It is NOT a clean ACCEPT for one reason, and the reason is the one the builder itself
> ### flagged: `CONSUMES`.**
>
> `CONSUMES` is a **third exemption from the GR-2 converse** that the G2 adjudication's §G
> explicitly foreclosed (*"producer **or** valid `DELEGATES_TO`. **No third option**"*). Its
> substantive content is faithful to pre-existing architecture, but **its guard does not enforce
> the safety property its own definition asserts**, and this session proved that mechanically:
> **`AP-9` — the highest-severity open GR-2 violation in the corpus, the review's own §9 safety
> finding — was laundered out of `EVENT_REQUIRED` into `CONSUMES` by a coordinated spec+audit
> edit, and the entire 2091-node canonical suite stayed GREEN with zero failures.**
>
> Per the review brief's own instruction, that is a **blocking governance finding**, not something
> to accept silently. The adjudicator — not this reviewer and not the builder — must rule on
> whether `CONSUMES` is ratified, and if so must require the guard be narrowed so the class cannot
> function as an escape hatch.

---

## A. SESSION INDEPENDENCE

This session is a **fresh independent reviewer**. It did **not**: implement P4; participate in the
P4/R-07 campaign; perform the G2 architecture adjudication; author this candidate; act as builder
or adjudicator. It resumed **no** previous Claude session.

It performed **no** remediation, **no** adjudication, **no** finalization, **no** event minting and
**no** further P5 work. It did not modify the candidate, the product branch, any ref, or
`driver.config.yaml`. The Desktop repository was not touched. All work was done from the
authoritative home repository `/Users/sammyfammy/freight-logistics-operational-teammate`, with
mutation testing confined to **disposable `--no-local` clones** outside both repositories.

The builder handoff was treated as **untrusted testimony**. Every substantive claim below was
re-derived from the candidate and from repository authority with this session's **own** parser,
written from the normative documents rather than from the candidate's test code.

---

## B. CANDIDATE IDENTITY AND TOPOLOGY — VERIFIED FROM GIT

| Property | Required | Observed | Result |
|---|---|---|---|
| Candidate commit | `38b4bda6…` | `38b4bda6cb3ea6c5e5c9a302fd64d23450e6fc62` | ✅ |
| Candidate tree | builder said `e669ad33…` | `e669ad3375822b0a458b5466d9ce8fb37fceddb3` | ✅ resolved from Git |
| Parent | exactly `6e8127d` | `6e8127dab02e3443183d06825836f5a805f53de0` | ✅ |
| Parent count | 1 — not a merge | `git rev-list --parents -n 1` → one parent | ✅ |
| Commits above `6e8127d` | exactly 1 | `git rev-list 6e8127d..38b4bda` → 1 | ✅ |
| Second P5 content commit | none | none | ✅ |
| Branch | `p5/u5-1-g2-spec-correction` | same; created off `6e8127d` | ✅ |
| Old P4 branch | unmoved | `p4/adapter-containment-completion` = `6e8127d`; reflog `@{0}` is the third-finalization commit, nothing after | ✅ |
| Prestate preservation ref | present | `refs/preserve/p5-u51-prestate-6e8127d` → `e77ab673…` (commit, parent `6e8127d`) | ✅ |
| Primary index | clean | `git diff --cached` empty | ✅ |
| Unstaged modifications | none | `git diff` empty | ✅ |
| Untracked set | the two authorized third-finalization artifacts | exactly those two | ✅ |
| Push / remote P5 branch | none | no upstream configured; `refs/remotes/origin/*` has no `p5/` ref | ✅ |
| `main` / `origin/main` | unmoved | both `152574e4f4f2969468c9d31b1e705188896175b5` | ✅ |
| Total refs | 65 → 67 | 67 (branch + prestate ref) | ✅ |
| Finalizer | not run | `SUITE-RESULT.json` / `GATE-RESULT.json` both still bind `a31a94a`, absent from the diff | ✅ |

**Topology accepted.** As instructed, the Product Driver's `max_content_commits=7` was **not used**;
topology was judged from Git objects and `PROGRESS-PROTOCOL.md` §10 only.

---

## C. EXACT DELTA — 22 PATHS, ALL SPECIFICATION/CONTROL

`git diff --name-status 6e8127d 38b4bda` returns **22 entries, every one an `M` (modification)**:
**zero added paths, zero deleted paths.** The builder's "22 spec/control paths" is confirmed.

```
M ARCHITECTURE.md                                          M docs/product/OPEN-VALIDATION-ITEMS.md
M CLAUDE.md                                                M .../state-machines/01-work-item.machine.md
M README.md                                                M .../state-machines/02-pipeline-instance.machine.md
M docs/CANONICAL-DOCUMENTS.md                              M .../state-machines/03-external-effect-grant.machine.md
M docs/implementation/BUILD-STATUS.yaml                    M .../state-machines/04-approval.machine.md
M docs/implementation/CURRENT.md                           M .../state-machines/06-identity-binding-claim.machine.md
M docs/implementation/IMPLEMENTATION-REGISTRY.yaml         M .../state-machines/07-conflict.machine.md
M docs/implementation/TEST-NODE-MANIFEST.json              M .../state-machines/09-exception.machine.md
M docs/implementation/TRANSITION-EVENT-AUDIT.yaml          M .../state-machines/10-compensation.machine.md
M eval/tests/test_bootstrap_hermeticity.py                 M .../state-machines/11-policy.machine.md
                                                           M .../state-machines/12-rule.machine.md
                                                           M .../state-machines/13-brake.machine.md
```

**Verified EMPTY diffs** (`git diff 6e8127d 38b4bda -- <path>` returns nothing) for every forbidden
or freeze-critical surface:

| Surface | Result |
|---|---|
| `src/` · `scripts/` · `configs/` · `data/` · `.claude/` · `docs/architecture/` | **byte-unchanged** — no runtime, adapter, or effect-boundary movement |
| `docs/specifications/events/registry.md` | **byte-unchanged** — the mechanical proof no event was minted |
| `docs/specifications/state-machines/registry.md` | **byte-unchanged** |
| `docs/implementation/PROGRAM-WEIGHTS.yaml` | **byte-unchanged** — the frozen template |
| `docs/implementation/phase-0-baseline-manifest.yaml` | **byte-unchanged** — the R-07 CONTAINED record |
| `SUITE-RESULT.json` · `GATE-RESULT.json` | **byte-unchanged**, still bound to `a31a94a` |
| `driver.config.yaml` and every Product Driver file | untouched |

Production `GateRegistry` constructions in `src/` + `scripts/` (excluding the mutation script's own
attack literals): **zero**. Phase-8 `DEFERRED_BY_DEPENDENCY` deferral present. No Action Class
registration. **No unauthorized surface was touched.**

---

## D. THE 134-TRANSITION CORPUS AND THE CLASSIFICATION — INDEPENDENTLY REPRODUCED

Re-parsed with this session's **own** parser (escape-aware `(?<!\\)\|` split, `## 14.` section
scoping, header-name column resolution, `[A-Z]{2}-\d+[a-z]?` ID pattern), written from
`events/registry.md` §1/§3/§182 and `state-machines/registry.md` §3/§4 — **not** from the
candidate's test code.

| Measure | Builder | This session | Result |
|---|---|---|---|
| Machine files | 13 | **13** | ✅ |
| Transition rows | 134 | **134** | ✅ |
| Rows with an unparseable ID (silent loss) | 0 | **0** | ✅ |
| Duplicate row identities (per-file and global) | 0 | **0** | ✅ |
| Column-count misalignments | 0 | **0** — `EF-5x` repair confirmed (8 cells / 8 headers) | ✅ |
| Canonical events F1–F13 | 98 | **98** | ✅ |
| Distinct §3 producer transition ids | 110 | **110** | ✅ |
| Declared producers absent from the corpus | 0 | **0** | ✅ |
| Canonical events with zero producers | 0 | **0** | ✅ |
| Corpus rows that are §3 producers | 110 | **110** | ✅ |
| Corpus rows that are NOT producers | 24 | **24** | ✅ |

**Classification, computed independently by §3 membership + closed-token extraction:**

```
PRODUCER 110 · CONSUMES 11 · NON_PRODUCING 4 · DELEGATES_TO 2 · EVENT_REQUIRED 7   = 134
rows carrying ≥2 tokens: 0     non-producer rows carrying 0 tokens: 0
§3 producer rows carrying a token: 0   (producer identity is never self-declared)
```

**Exact membership — reproduced, not merely counted:**

- `CONSUMES` (11): `PL-6 PL-9 PL-10 PL-10f PL-10u PL-11 PL-11c PL-15 PL-15x IB-5x RU-3`
- `NON_PRODUCING` (4): `AP-8 EF-5x CM-5x BR-5`
- `DELEGATES_TO` (2): `WI-14 CF-6`
- `EVENT_REQUIRED` (7): `PL-7a AP-9 CF-7 EC-7 PO-2 PO-3 RU-8`

This is **exactly** the adjudication's §D list of twelve non-owning rows minus `RU-8`, which the
adjudication reclassified as the fourteenth defect. **`EF-3` is `PRODUCER`, not `EVENT_REQUIRED`** —
the accidental-double-count the brief asked about did **not** occur.

**Membership discipline is real, not aggregate.** `test_the_transition_corpus_is_positively_anchored…`
asserts exact set equality against `canonical_expected.yaml`; every class guard compares computed
**sets** to the audit's recorded members. Mutations M10–M13 below confirm same-count substitutions
fail.

**Disclosed numeric coincidence handled honestly.** 4+2+7 = 13 and 110+11 = 121 do reproduce the
retired pair's *values*, and the membership is genuinely different (`EF-3` left, `RU-8` entered).
The audit leads with the classification rather than a naming split, records `120/14` as an
explicitly `HISTORICAL` as-found measurement, and registers both `24` and `121 / 13` as retired.
That is the correct handling.

---

## E. HOSTILE REVIEW OF `CONSUMES` — THE DECISIVE ITEM

### E.1 What `CONSUMES` is, substantively

**The relationship pre-exists and so does the word.** `events/registry.md` §182 — **byte-unchanged**
in this candidate — states: *"No event is emitted by two incompatible transitions. Where two
machines co-transition (M2↔M3, M2↔M4), the event has **one producer** … and the other machine
**consumes** it."* The registry preamble adds that *"Consumers react according to their own
deterministic transition guards; the event does not instruct them."* The G2 adjudication's §D
enumerated these very rows as *"correct architecture"* that would be *"a false positive under
Interpretation A."*

**The eleven rows are correct.** All 11 targets exist in the canonical corpus, **none** is owned by
the consuming row itself, and every one is a genuine co-transition or causation:

| Row | Consumes | Owner (§3) | Durable write? |
|---|---|---|---|
| `PL-6` | `ApprovalRequested` | `AP-1` (M4) | yes (state) |
| `PL-9` | `GrantClaimed` | `EF-2` (M3, *"co-commit M2 `CLAIMED`"*) | yes |
| `PL-10` | `EffectExecuted` | `EF-3` (M3) | yes |
| `PL-10f` | `EffectFailed` | `EF-3f` (M3) | yes |
| `PL-10u` | `OutcomeUnknown` | `EF-3u/4c/4u` (M3) | yes |
| `PL-11` | `EffectVerified` | `EF-4` (M3) | yes |
| `PL-11c` | `VerificationConflict`,`VerificationUnavailable` | `EF-4c`,`EF-4u` (M3) | yes |
| `PL-15` | `RealityEstablished` | `EF-5`,`CM-5` (‡) | yes |
| `PL-15x` | `IllegalTransitionAttempted` | `GR-1` (‡, rule) | **no** |
| `IB-5x` | `IllegalTransitionAttempted` | `GR-1` (‡, rule) | **no** |
| `RU-3` | `ConflictRaised` | `CF-1`,`IB-6`,`EF-4c` (‡) | **no** |

The third option is **load-bearing for exactly 8 rows**, and all 8 are M2 rows mirroring M3/M4 —
precisely the `M2↔M3, M2↔M4` co-transition §182 describes. No durable write is left eventless, no
duplicate producer is created, no zero-owner path is introduced, and no consumer is secretly a
producer. **On the corpus as it stands today, `CONSUMES` is a faithful structured representation of
already-existing architecture.**

### E.2 Where it fails — the guard does not enforce its own definition

The audit's own `contract.classification_vocabulary.CONSUMES` asserts the safety property:

> *"The durable change this row makes **is recorded by that event, emitted in the same commit by its
> owner**."*

`test_consuming_rows_name_an_event_owned_by_a_different_transition`
(`eval/tests/test_bootstrap_hermeticity.py:637-661`) proves **only two things**:

1. the named event exists in the canonical corpus; and
2. the consuming row is not its own §3 producer.

It does **not** verify co-transition, co-commit, aggregate linkage, payload coverage, or any
relationship whatsoever between the consuming row's durable write and the consumed event.
`test_every_durable_write_is_recorded_by_an_event_or_a_registered_open_obligation` (line 664) then
accepts `CONSUMES` as full satisfaction of the GR-2 converse.

Compare the sibling classes, both of which carry an **independent structural proof**:
`NON_PRODUCING` proves zero durable writes from the structured columns; `DELEGATES_TO` proves target
existence, §3 producer status, target-state match, exactly-one-owner resolution and exact To-set
coverage. **`CONSUMES` is the only exempting class with no independent proof of the property that
makes it safe.**

### E.3 Proved, not asserted — `AP-9` laundered, suite green

A coordinated spec+audit edit (the ordinary shape of a builder commit) moved `AP-9` — which writes
`frozen=true`, a guard input to an ILLEGAL determination, and is the review's own §9 safety
finding — out of `EVENT_REQUIRED` and into `CONSUMES:ApprovalConsumed`, an event owned by `AP-7`, a
different, mutually-exclusive transition with no semantic relationship to the freeze fact:

```
docs/specifications/state-machines/04-approval.machine.md
  - `EVENT_REQUIRED:G2-OB-AP-9-FREEZE-FACT-UNRECORDED`
  + `CONSUMES:ApprovalConsumed`
docs/implementation/TRANSITION-EVENT-AUDIT.yaml
  - AP-9 removed from EVENT_REQUIRED members; added to CONSUMES members
  - the AP-9 obligation entry removed; open_founder_gated_obligations 7 -> 6
  - computed_classification CONSUMES 11 -> 12, EVENT_REQUIRED 7 -> 6
```

| Run | Result |
|---|---|
| G2 guard block (`test_bootstrap_hermeticity.py`, 42 nodes) | ### **42 passed, 0 failed** |
| Complete canonical suite, clean clone, canonical config | ### **2088 passed, 3 skipped, 0 failed** |

The two extra skips are `test_status_reality.py`'s `working_tree_clean()`-gated status-artifact
guards, which cannot inspect classification semantics. A committed variant produced three
`test_status_reality.py` failures, and a **control** — an entirely unrelated one-line extra commit —
produced **the same three failures**, confirming they are artifacts of adding a commit, not of the
laundering. **Nothing in the repository catches the laundering.**

`AP-9`'s durable write would then be recorded as satisfied by an event that does not carry it, the
open obligation count would drop to six, and G2 would appear closer to discharge than it is.

### E.4 Classification of `CONSUMES`

Against the brief's four options:

- **Not C.** It is not an unauthorized *new architectural concept* — §182 pre-exists and is
  byte-unchanged, and supplies the word itself.
- **Substantively A/B.** For today's corpus it is a faithful structured label over an existing
  relationship.
- **Mechanically D-shaped.** As implemented it is a working semantic shortcut that *can* mask event
  ownership defects, demonstrated above on the single most safety-critical row in the corpus.
- **Governance: authority not supplied.** The adjudicated §G contract closed the vocabulary at
  *"producer or valid `DELEGATES_TO`. **No third option**"*. Adding a third option is an amendment
  to the adjudicated contract. The builder disclosed this in handoff §G and asked a reviewer to
  confirm it. **Confirming or refusing a contract amendment is adjudicator authority, which this
  reviewer does not hold.**

Per the brief — *"If `CONSUMES` requires architecture authority not supplied by the G2 adjudication,
flag it as a blocking governance finding rather than silently accepting it"* — it is flagged.

---

## F. `EF-3` RE-ATTRIBUTION — VERIFIED, NO DISCRETION EXERCISED

| Check | Result |
|---|---|
| `EffectExecuted` existed before the candidate | ✅ `events/registry.md` §3 F3 — **byte-unchanged** |
| Repository authority already assigns it to `EF-3` | ✅ `` `EffectExecuted`(EF-3) `` in §3, corroborated by `events/03-external-effect-grant-events.md` |
| A new event was minted | ❌ **no** — `events/registry.md` diff is EMPTY |
| Canonical event total | ✅ **98**, computed independently from §3 F1–F13 |
| `producers_of["EF-3"]` | ✅ exactly `{EffectExecuted}` |
| Duplicate `EffectExecuted` ownership introduced | ❌ **no** — `PL-10` is `CONSUMES:EffectExecuted`, not a producer |
| Other canonical events changed meaning | ❌ **no** — the registry file is byte-identical |
| Event vocabulary expanded | ❌ **no** |

The new cell preserves the true safety point the old prose was making (a second `EffectAttempted`
would be a Sev-0 orphan, M3 §19/§38) while naming the event the row actually owns. **Zero naming
discretion.** Mutation M18 (reverting the cell) fails; M13 (moving the producer id to `EF-3f` at
constant producer count) fails.

---

## G. `NON_PRODUCING` — VERIFIED (4)

| Row | Marker | Zero-write proof, from structured columns |
|---|---|---|
| `AP-8` | `NON_PRODUCING:ENUMERATED_NO_OP` | `GRANTED → GRANTED` (To∖From = ∅); `Writes` = `—` |
| `EF-5x` | `NON_PRODUCING:GR1_ILLEGAL_REFUSAL` | no `→`; `Writes` = `—` |
| `CM-5x` | `NON_PRODUCING:GR1_ILLEGAL_REFUSAL` | same |
| `BR-5` | `NON_PRODUCING:GR1_ILLEGAL_REFUSAL` | same |

Reason codes are drawn from a closed set (`ENUMERATED_NO_OP`, `GR1_ILLEGAL_REFUSAL`); the marker is
structured, never prose. **Mutations confirm it is not an escape hatch:** M5 (give `AP-8` a durable
write) fails; M3 (relabel `NON_PRODUCING` → `CONSUMES`) fails; M6 (remove the marker) fails as
unclassifiable; M7 (restore the prose *"(no state change — does not produce an event)"* on `CF-7`)
fails — **prose cannot self-certify.**

---

## H. `DELEGATES_TO` — VERIFIED (2), G2-D3 CLOSED

`WI-14` → `DELEGATES_TO:BLOCKED=WI-5,WI-6;AWAITING_HUMAN=WI-7;CLOSED=WI-3;CANCELLED=WI-12`
`CF-6` → `DELEGATES_TO:RESOLVED_BY_RULE=CF-3;RESOLVED_BY_HUMAN=CF-4`

Every target exists, is a §3 producer, and **itself transitions to the state it is delegated for**;
each branch resolves to **exactly one** owner event; the union of declared branches equals the row's
own To set exactly, so no branch can be silently dropped. The 4-target/5-reference arity defect is
resolved by **target-state matching**, and the word *"respectively"* is gone from the entire corpus
with a guard asserting it stays gone (M16 restores it → fails).

Mutations M8 (nonexistent target), M9 (wrong-target), and the candidate's own hostile battery
(zero targets, non-producer target, ambiguous two-owner resolution) all fail closed. Delegation
cannot point at a non-producer, so a self- or cyclic reference cannot resolve to an owner.

---

## I. `EVENT_REQUIRED` — VERIFIED (7)

Exact set from repository state: **`PL-7a`, `AP-9`, `CF-7`, `EC-7`, `PO-2`, `PO-3`, `RU-8`** — and
**`EF-3` is not among them.**

| Requirement | Result |
|---|---|
| Absence of a canonical event is explicit | ✅ each row carries `EVENT_REQUIRED:<OBLIGATION_ID>` and a registered obligation stating the semantic obligation, blast radius and decision required |
| No placeholder is treated as a canonical event | ✅ all 7 obligation ids fail `^[A-Z][A-Za-z0-9]*$` and are absent from the canonical corpus; M15 (making one event-shaped) fails |
| No event name invented | ✅ registry byte-unchanged; total still 98 |
| Build/control logic does not pretend G2 is discharged | ✅ `meta.status = G2_PARTIALLY_DISCHARGED_FOUNDER_GATED`; M14 (flip to discharged) fails on two guards |
| Event-producing implementation cannot silently proceed | ✅ P5's `validation_blockers` and `CURRENT.md` both state the event content is blocked |
| Membership pinned by identity, not count | ✅ M10 (swap two obligation ids at constant count) fails |

**The one path by which an `EVENT_REQUIRED` row can be treated as complete is §E.3 —
reclassification to `CONSUMES`.** That is finding F-01.

---

## J. `AP-9` — SAFETY FINDING INDEPENDENTLY CONFIRMED

**Mechanically true.**

| Element | Evidence |
|---|---|
| Source of `frozen=true` | `04-approval.machine.md` §14, `AP-9` `Writes` column — a durable write |
| Where it affects legality | `04-approval.machine.md` §15: *"**Reuse of a frozen (AP-9) approval → ILLEGAL**"*; §13: *"MUST NOT be reused until reality established"* — a guard input to an ILLEGAL determination |
| Event payload coverage | **none.** A sweep of `docs/specifications/events/` finds no F4 Approval event carrying the approval's `frozen` flag. The `frozen` hits that exist concern *entity* freezing on other aggregates (`OutcomeUnknown`, `ConflictRaised`), not M4's approval field |
| Replay / reconstruction consequence | `AC-EVT-008` requires a full-history rebuild to reproduce the pinned `GC-1` projection digest byte-for-byte. Replaying only canonical events reconstructs an approval with `frozen` **unset** — i.e. **reusable**. **The rebuilt state is less safe than the original**, which inverts the purpose of replay |
| Fail-closed preserved by the candidate | ✅ `AP-9` is classified `EVENT_REQUIRED`, its obligation is registered and open, and the audit records the interim default: *treat any approval with an unresolved `OutcomeUnknown` as frozen* |

**Classification: `AP-9` genuinely requires founder/architect architecture authority before full G2
discharge.** The two admissible remedies — emit a new `Approval*` event, or remove the durable write
and derive `frozen` over `OutcomeUnknown ∧ ¬RealityEstablished` — are a design choice. The candidate
correctly declined to decide and invented nothing. **This reviewer likewise takes no position.**

One residual, recorded not blocking: the fail-closed default is **documentary only** — it is stated
in the audit and in `OPEN-VALIDATION-ITEMS.md`, and no guard enforces it. There is no runtime to
enforce it in today (P5 event content is blocked), so this is a note for whoever implements it, not
a defect in this candidate.

---

## K. P5 ACCEPTANCE CONTRACT — MECHANICALLY VERIFIED, FIELD FOR FIELD

Compared with YAML parsing, not by eye:

| Check | Result |
|---|---|
| Source template | `PROGRAM-WEIGHTS.yaml` `acceptance_template` — **byte-unchanged** in this commit |
| Criteria count | ### **14** |
| Verbatim ordered match to the frozen template (criterion **and** weight) | ### **True** — `[(criterion, weight)] == template[(criterion, weight)]` exactly, in order |
| Criterion added / removed | **none / none** |
| Weight changed | **none** |
| Sum of weights | ### **exactly 100** |
| Results | ### **all 14 PENDING** · `any PASS` = **False** · `any FAIL` = **False** |
| Score assigned | **none** — P5 weighted score computes 0 |
| Parent state | P5 had **no** `acceptance_criteria` at `6e8127d`, so nothing was displaced |
| Any other phase's contract touched | **none** — P3 and P4 blocks byte-identical |
| Extra fields | only `evidence`, which is **P4's existing convention** (P4 uses `criterion/evidence/result/weight`) |
| `independent_review` (5) / `final_adjudication` (4) | PENDING and recorded structurally un-self-suppliable |
| P5 triple | `READY / NOT_STARTED / NO_CHECKPOINT` — **unchanged**, correctly, since no P5 phase content landed |

**Instantiation is transcription, not authorship. Nothing is self-authored, altered, or scored.**

---

## L. G2 GUARD CLOSURE — TESTED, NOT TAKEN ON TRUST

Prior failure reproduced at `6e8127d` where applicable, and each guard's target corpus confirmed
nonempty (`require_population` is used throughout, and every hostile test carries a positive
control so none can pass vacuously).

| ID | Prior state at `6e8127d` | Candidate | Mutation bites? |
|---|---|---|---|
| **G2-D1** | Confirmed: the old `_computed_classes` assigns via a bare `else` into `evented` with **no canonical-name check**, so `RU-8`'s `*(Exception raised)*` passed as evented | unknown classification is an **error** | ✅ M6, M7 fail |
| **G2-D3** | *"respectively"* over 4 states / 5 references | target-state resolution; word removed corpus-wide | ✅ M8, M9, M16 fail |
| **G2-D5** | `EF-5x` 7 cells vs 8 headers, unguarded | row repaired (`Owner after` = `unchanged`); 0 misaligned live | ✅ M17 fails |
| **G2-D7** | anti-`24` guard collided with the true non-producer sentence | carve-out added | ⚠️ **see F-03** — the carve-out is over-broad |
| **G2-D11** | no bijection assertion | zero-owner, dangling-producer, duplicate-declaration, machine-span, producer-silence all asserted both ways | ✅ M12, M13 fail |
| **G2-D12** | audit recorded `121 / 13` | corrected; `120/14` labelled HISTORICAL; revival guard added | ✅ verified live |
| **G2-D14** | audit called `EF-3` non-producing | corrected and pinned by a named guard | ✅ M18 fails |

**Constant-total membership mutations — the brief's specific requirement — all fail:**

| # | Mutation (totals preserved) | Result |
|---|---|---|
| M1 | `PRODUCER` → `CONSUMES` (`WI-1`) | **FAILS** (bijection + classification + audit) |
| M2/M2b | `EVENT_REQUIRED` → `CONSUMES` (`AP-9`), spec-only / partial audit | **FAILS** |
| M3 | `NON_PRODUCING` → `CONSUMES` (`AP-8`) | **FAILS** |
| M4 | `CONSUMES` a nonexistent event | **FAILS** |
| M10 | Two obligation ids swapped at constant count | **FAILS** |
| M11 | `RU-8` removed + a duplicate row added (total stays 134) | **FAILS** (exact set equality) |
| M12 | One canonical event renamed, total stays 98 | **FAILS** |
| M13 | One producer id changed, producer count preserved | **FAILS** |
| M14 | Audit status flipped to fully discharged | **FAILS** |
| M15 | Obligation id made event-shaped | **FAILS** |

**Eighteen mutations, eighteen closed failures, each for the intended reason.** No guard was
observed to pass merely because it was green. **The one surviving mutation is §E.3 — the
*coordinated* `CONSUMES` laundering — which is finding F-01.**

**No invariant was weakened by deletion:** the node manifest delta is **+18 added, 0 removed**,
`node_count == len(node_ids) == len(set(node_ids)) == 2091`, and all 18 additions are G2 nodes.
The one authorized weakening — `test_transition_event_audit_matches_the_specs` moving off
`status == "COUNT_NEEDS_ADJUDICATION"` — is exactly what the adjudication §I.6 **required** to land
in the same commit.

---

## M. CANONICAL DOCUMENT CONSISTENCY

Swept the complete tracked corpus for `13 of 134`, `24 … transitions|event`, `121`, and
`COUNT NEEDS ADJUDICATION`.

**Corrected and consistent:** `CLAUDE.md`, `README.md`, `ARCHITECTURE.md`, `docs/CANONICAL-DOCUMENTS.md`,
`CURRENT.md`, `OPEN-VALIDATION-ITEMS.md`, `BUILD-STATUS.yaml`, `IMPLEMENTATION-REGISTRY.yaml`.
All now state the 110/24 producer split and the seven open obligations; both retired figures are
labelled retired. The canonical event total remains **98** everywhere. **The retired `24`-names-no-event
sense is not revived as current truth, and `24` appears only in its correct new sense (non-producer
transitions).** `24 canonical non-producers` and `14 unnamed rows` are not conflated: the audit
records `120/14` explicitly and only as `adjudicated_as_found … HISTORICAL`.

**Remaining live `13 of 134` / `COUNT NEEDS ADJUDICATION` hits are historical evidence documents**
(`p4-final-adjudication-report-0891d1a.md`, `u-handoff-1b/1c/1d`, `u-handoff-2b`,
`p4-r07-closure-handoff.md`), which are correctly `HISTORICAL (evidence)` under the authority map
and true as of their own commits.

**One exception — see finding F-02:** `docs/implementation/PHASE-OUTPUTS.md:153` still carries a
**live, false** claim.

---

## N. PRIMARY-WORKTREE SUITE FAILURE — §15 DETERMINATION

### **PRE-EXISTING AUTHORIZED WORKTREE ARTIFACT — NON-BLOCKING**

| Question | Answer |
|---|---|
| Exact failing path | `eval/tests/test_bootstrap_hermeticity.py:1256` `test_every_implementation_document_is_classified_or_family_covered`, asserting at line 1265. It globs `docs/implementation/*.md` **on disk**, so it sees untracked files |
| Offending file | `docs/implementation/p4-r07-third-finalization-pass-report-6e8127d.md` — untracked; name contains *"report"*, not *"review"*, so it is not family-covered, and it has no row in `CANONICAL-DOCUMENTS.md` |
| Does it predate the candidate? | **Yes.** File mtime `2026-08-06 18:43`; preserved at `refs/preserve/p4-r07-third-finalization-report-6e8127d` (`61d4246`, `2026-08-06 18:44`, parent `6e8127d`); candidate committed `2026-08-08 17:14` |
| Authorized preserved artifact? | **Yes** — its own preservation ref parented to `6e8127d`, plus a `.sha256` sidecar, and it is carried in the P5 U5.1 prestate ref `e77ab673` |
| Did candidate changes cause it? | **No.** `git diff 6e8127d 38b4bda -- eval/tests/test_bootstrap_hermeticity.py` shows the failing test was **not touched** |
| Does a clean checkout of the candidate contain the file? | **No** — verified absent from a fresh `--no-local` clone at `38b4bda` |
| Decisive control | Running that single node in a clone at **both** refs: `6e8127d` **passes** without the file and **fails** with it; `38b4bda` **passes** without the file and **fails** with it. **Identical behaviour at the certified predecessor** |

The failure is caused solely by the presence of an authorized, untracked, pre-existing artifact and
occurs identically at `6e8127d`. It is not a candidate defect and not a test/control defect
introduced here. **The report was neither deleted nor modified.**

*Inherited residual (not this unit's to fix, and on a forbidden surface):* the repository's own
convention gives each finalization-pass report an individual row in `CANONICAL-DOCUMENTS.md` — the
first and second have one. The third has neither a row nor tracked status, so the guard is telling
the truth about a genuine P4/R-07-campaign gap. Recorded for whoever owns the next R-07-adjacent
correction.

---

## O. VALIDATION — INDEPENDENTLY REPRODUCED

Run by this session in its **own** disposable `--no-local` clone at `38b4bda` (tree `e669ad33…`),
fresh venv, declared deps only (`pip install -e ".[dev]"` from `pyproject.toml`), canonical config
`pytest-canonical.ini` via explicit `-c`, `PYTEST_ADDOPTS` cleared:

```
2091 collected · 2090 passed · 0 failed · 1 skipped        exit 0
```

### **Exactly matches the builder's reported clean-clone counts.**

| Check | Result |
|---|---|
| Baseline delta | `2073 → 2091` = **+18 collected, 0 removed** — reproduced against the parent manifest |
| `TEST-NODE-MANIFEST.json` | `node_count = 2091`, `len(node_ids) = 2091`, `len(set(node_ids)) = 2091` — no duplicates; **+18 / −0** by identity, all 18 in the G2 block |
| Hidden deselections | **none** — collected 2091 = 2090 + 1 |
| The one skip | unchanged at 1, the approved `test_the_red_by_design_cases_are_strict_xfails` |
| Test weakening | none by deletion; the one authorized guard move is the adjudication-mandated status change |
| Declared dependencies | the clone installed from `pyproject.toml` only and the suite ran green — no undeclared dependency |

**Disclosure of a reviewer-side false start.** A first attempt used a venv named `.venv-rev` and
produced 4 CLI-smoke failures, because those tests hard-code `ROOT/".venv"/"bin"/"python"`. That was
**my environment error**, not a candidate defect; re-running with a correctly-named `.venv` produced
the green result above. Recorded so the figure is not misread.

The clean-clone **gate** (`scripts/clean_clone_gate.py`) was not re-executed by this session — it
writes `GATE-RESULT.json` into the tree it runs from, and the equivalent evidence (fresh clone,
fresh venv, declared-deps-only install, canonical config, complete suite, node-identity match) was
obtained directly above. Recorded as an evidence note, not a finding.

---

## P. P4 / R-07 SAFETY RETENTION — VERIFIED

| Property | Result |
|---|---|
| P4 | **COMPLETE** — `status COMPLETE / execution_state COMPLETE / checkpoint_state PHASE_ACCEPTANCE_COMPLETE`, 14/14 PASS, weighted **100** |
| R-07 | **CONTAINED** — `phase-0-baseline-manifest.yaml` `expected_legacy_paths.status: CONTAINED`, file **byte-unchanged** |
| Live/recorded violation-edge mismatch | zero — the effect-capable violation surface record is unchanged and its guards pass |
| Authorized detection edges | **13**, unchanged in `CLAUDE.md` and `CURRENT.md` |
| Production `GateRegistry` | **EMPTY** — zero constructions in `src/` + `scripts/` |
| Phase-8 Action Class registration deferral | **INTACT** — `DEFERRED_BY_DEPENDENCY` present across the control set |
| Production writes | **dark** — `src/`, `scripts/`, `configs/`, `data/`, `docs/architecture/` byte-unchanged |
| Action Class registration | **none** |
| P4 runtime containment | **no regression** — no runtime surface moved |
| P6–P14 | all **BLOCKED / NOT_STARTED / NO_CHECKPOINT**, zero scored |
| P4/R-07 campaign preservation refs | all present and unmoved |

**No certified P4 finding was reopened.** The candidate changed none of their relevant surfaces.

---

## Q. EVENT REGISTRY FREEZE — MECHANICALLY PROVEN

```
git diff 6e8127d 38b4bda -- docs/specifications/events/registry.md   ->  EMPTY
```

| Assertion | Proof |
|---|---|
| Byte-identical to `6e8127d` | the empty diff above |
| Canonical event total exactly 98 | **independently computed** from §3 F1–F13 by this session's own parser: **98** |
| No event added / removed / renamed | implied by byte-identity; additionally M12 (rename at constant 98) **fails** |
| No schema expanded through a backdoor | §1 envelope byte-unchanged; F14 count 13; F15 declares no producer |
| No placeholder treated as canonical | all 7 obligation ids are non-event-shaped and absent from the corpus; M15 **fails** |

### **The hard authorization boundary held. No canonical event was minted. The frozen total is unchanged at 98.**

---

## R. FINDINGS

### F-01 — `CONSUMES` exempts durable writes from GR-2 without proving the property its own definition asserts

| | |
|---|---|
| **Severity** | ### **HIGH** |
| **Class** | **governance ambiguity** (contract authority) **+ confirmed defect** (guard strength) |
| **Requirement** | G2 adjudication §G: *"Every transition performing a durable write is a §3 producer of ≥1 event **or** carries a valid `DELEGATES_TO`. **No third option.**"* — and `TRANSITION-EVENT-AUDIT.yaml` `contract.classification_vocabulary.CONSUMES`: *"The durable change this row makes **is recorded by that event, emitted in the same commit by its owner**."* |
| **Location** | `eval/tests/test_bootstrap_hermeticity.py:637-661` (`test_consuming_rows_name_an_event_owned_by_a_different_transition`); consumed at `:664-683`. Contract text: `docs/implementation/TRANSITION-EVENT-AUDIT.yaml` `contract.classification_vocabulary.CONSUMES` and `classes[CONSUMES].meaning` |
| **Reproduction** | In a clone at `38b4bda`, replace `AP-9`'s `EVENT_REQUIRED:G2-OB-AP-9-FREEZE-FACT-UNRECORDED` with `CONSUMES:ApprovalConsumed`; in `TRANSITION-EVENT-AUDIT.yaml` move `04-approval:AP-9` from `EVENT_REQUIRED.members` to `CONSUMES.members` as `{key: 04-approval:AP-9, consumes: [ApprovalConsumed], owner: [AP-7]}`, delete its obligation entry, set `open_founder_gated_obligations: 6`, and set `CONSUMES: 12 / EVENT_REQUIRED: 6`. Run the suite. **G2 block: 42 passed. Full canonical suite: 2088 passed, 3 skipped, 0 failed.** |
| **Consequence** | Any durable-writing transition can be exempted from GR-2 by naming **any** canonical event it does not itself own — no co-transition, co-commit, aggregate or payload relationship is required. Applied to `AP-9` this silently discharges the corpus's highest-severity safety obligation and understates the founder-gated count. `CONSUMES` is the only exempting class without an independent structural proof; `NON_PRODUCING` and `DELEGATES_TO` both have one. |
| **Blocks separate adjudication?** | ### **It IS the adjudication question.** It does not prevent the candidate proceeding *to* adjudication — it is precisely what the adjudicator must rule on, and the brief directs that it be flagged rather than silently accepted. |
| **Narrow remediation** | Adjudicator ratifies (or refuses) `CONSUMES` as an amendment to the §G contract. **If ratified**, require the guard to prove the relationship structurally — e.g. for each `CONSUMES:E` on a durable-writing row, assert the §3 owner of `E` is a corpus row whose own machine co-transitions with the consuming row, by an explicit declared co-transition/co-commit relation, and add a hostile node asserting that an unrelated `CONSUMES` target **fails**. Do not remediate before the ruling. |

### F-02 — `PHASE-OUTPUTS.md` still carries the pre-adjudication G2 claim as live truth

| | |
|---|---|
| **Severity** | **MEDIUM** |
| **Class** | **confirmed defect** (canonical/control document truthfulness) |
| **Requirement** | Review brief §12: *"no false current count remains"*; adjudication §I.6 (G2-D13) and §E, which names `PHASE-OUTPUTS.md` as part of the anti-drift guard population |
| **Location** | `docs/implementation/PHASE-OUTPUTS.md:153`, P5 block, **Blocked on** row |
| **Reproduction** | `sed -n '153p' docs/implementation/PHASE-OUTPUTS.md` → *"The transition/event completeness finding must be adjudicated first — **COUNT NEEDS ADJUDICATION, 4 classes**"* |
| **Consequence** | Two live falsehoods in an `IMPLEMENTATION_CONTROL` document: (a) G2 **has** been adjudicated, and the audit's `meta.status` is now `G2_PARTIALLY_DISCHARGED_FOUNDER_GATED` — `COUNT_NEEDS_ADJUDICATION` is a **retired** status token whose guard the candidate deliberately moved; (b) the classification is now a **five**-member closed vocabulary, and the old four prose classes are retired. A future agent reading the phase-outputs authority is told to adjudicate something already adjudicated and is not told the real block is founder/architect event naming. Neither of the candidate's two new anti-drift guards catches it: `test_the_retired_24_figure_does_not_reappear_in_control_documents` matches only `\b24\b…(transitions?\|event)`, and `test_the_retired_naming_split_does_not_reappear_as_the_current_finding` matches only `\b(?:13\|121)\b\s*(?:of\s*134\|transitions)`. This wording matches neither. |
| **Blocks separate adjudication?** | **No** — narrow, documentary, no mechanical effect. It should be corrected in the same remediation pass as F-01/F-03. |
| **Narrow remediation** | Rewrite that one row to match `CURRENT.md:115` (G2 adjudicated, partially discharged, seven founder-gated obligations), and extend the anti-drift guard to forbid `COUNT NEEDS ADJUDICATION` appearing as a **live** claim in the control-document population. |

### F-03 — the G2-D7 anti-`24` carve-out is keyword-proximity based and admits the retired sense

| | |
|---|---|
| **Severity** | **MEDIUM-LOW** |
| **Class** | **confirmed defect** (guard precision, in a guard this candidate introduced) |
| **Requirement** | Its own docstring: *"the carve-out therefore admits the phrase **only when the sentence says NON-PRODUCER**, which the retired figure never meant"* |
| **Location** | `eval/tests/test_bootstrap_hermeticity.py:755-778` |
| **Reproduction** | Append to `docs/implementation/CURRENT.md`: `24 of the 134 transitions name no event outright, which is the non-producer population.` → **suite GREEN (42 passed)**. Control, the identical sentence without the trailing clause: `24 of the 134 transitions name no event outright.` → **FAILS** on `test_the_retired_24_figure_does_not_reappear_in_control_documents`, as intended. |
| **Consequence** | The carve-out keys on the mere presence of `non-producer` within a ±120-character window, not on the sentence being **about** non-producers. Adding one word revives the retired figure in exactly its retired sense across the whole guarded population (`CLAUDE.md`, `README.md`, `ARCHITECTURE.md`, `CURRENT.md`, `PHASE-OUTPUTS.md`). No current document abuses this; the exposure is latent. |
| **Blocks separate adjudication?** | **No** |
| **Narrow remediation** | Scope the carve-out to the matched sentence rather than a character window, and require the `24` and `non-producer` tokens to occur in the same clause — e.g. admit only `24[^.\n]{0,40}non-producer transitions` — with a hostile node asserting the F-03 reproduction sentence **fails**. |

### F-04 — primary-worktree suite failure

| | |
|---|---|
| **Severity** | **INFORMATIONAL** |
| **Class** | ### **PRE-EXISTING AUTHORIZED WORKTREE ARTIFACT — NON-BLOCKING** |
| **Location** | `eval/tests/test_bootstrap_hermeticity.py:1256/1265`; artifact `docs/implementation/p4-r07-third-finalization-pass-report-6e8127d.md` (untracked) |
| **Reproduction** | §N above — the single node passes without the file and fails with it at **both** `6e8127d` and `38b4bda` |
| **Consequence** | None for this candidate. It surfaces an inherited P4/R-07-campaign gap: the third finalization report has neither a `CANONICAL-DOCUMENTS.md` row nor tracked status, unlike the first and second. |
| **Blocks separate adjudication?** | **No** |
| **Narrow remediation** | None owed by U5.1 — the R-07 record surface is forbidden to this unit. Recorded for the next R-07-adjacent correction. The report was **not** deleted or modified. |

### F-05 — `AP-9` replay-safety obligation is real and correctly left to founder/architect authority

| | |
|---|---|
| **Severity** | **HIGH (architecture), but correctly OPEN — not a candidate defect** |
| **Class** | **non-blocking residual risk** (recorded), confirmed by independent verification |
| **Location** | `docs/specifications/state-machines/04-approval.machine.md` §14 `AP-9` / §13 / §15; obligation `G2-OB-AP-9-FREEZE-FACT-UNRECORDED` |
| **Consequence** | §J above — a full-history rebuild reconstructs a **reusable** approval; the rebuilt state is less safe than the original. |
| **Blocks separate adjudication?** | **No** — it blocks *G2 discharge*, which is exactly what the candidate records. |
| **Narrow remediation** | Founder/architect decides **emit vs derive**. Sub-residual: the fail-closed interim default is documentary only; no guard enforces it (and there is no runtime to enforce it in yet). |

### F-06 — `README.md` R-07 blockquote contradicts its own table

| | |
|---|---|
| **Severity** | **LOW** |
| **Class** | **non-blocking residual** — pre-existing, correctly disclosed by the builder (handoff §L.5), correctly left untouched |
| **Location** | `README.md:73-80` |
| **Reproduction** | *"the record still says `OPEN — NOT CONTAINED`"* and *"What has not happened is the recording of R-07 as contained"* — contradicting `README.md:65` (*"RESOLVED AND RECORDED"*) and `CLAUDE.md:73` (*"CONTAINED"*) |
| **Consequence** | Documentary only. Not caught by the R-07 status-claim guard, which judges it non-live. |
| **Blocks separate adjudication?** | **No.** The R-07 containment record is a **forbidden surface** for U5.1; touching it would have been a scope violation. Leaving it was correct. |

### F-07 — no hostile node covers `CONSUMES`

| | |
|---|---|
| **Severity** | **MEDIUM** |
| **Class** | **evidence deficiency** |
| **Requirement** | Builder handoff §H: *"Seven are hostile cases, **one per adjudicated defect class**"* |
| **Location** | `eval/tests/test_bootstrap_hermeticity.py:806-897` (the hostile battery) |
| **Consequence** | The battery covers unclassifiable rows, two tokens, producer self-declaration, `NON_PRODUCING` + durable write, delegation zero/duplicate/wrong-target, column-short rows and the discharged-status flip — **but nothing tests that `CONSUMES` cannot launder a durable write.** This absence is why F-01 was not caught by the candidate's own tooling. |
| **Blocks separate adjudication?** | **No** — remediate with F-01. |
| **Narrow remediation** | Add a hostile node asserting an `EVENT_REQUIRED` row relabelled `CONSUMES:<unrelated canonical event>` **fails**, with a positive control that a genuine co-transition row passes. |

### Non-findings, explicitly recorded

- The G2 adjudication's own §H summary table labels the *MUST NAME AN EVENT* bucket **7** while
  listing **8** members (its own note concedes *"the MUST bucket is 8 rows"*). The candidate handled
  this correctly: 8 rows, `EF-3` discharged with zero design authority, 7 open. **Adjudication slip,
  not a candidate defect.**
- `PL-15x` / `IB-5x` consume `IllegalTransitionAttempted`, whose declared producer is the **rule**
  `GR-1`, not a corpus transition. This is not a zero-owner path hidden by `CONSUMES` — it is the
  adjudication's own **G2-D8** schema gap, recorded open in the audit and correctly excluded from
  the F1–F13 bijection.
- `RU-3` is classified `CONSUMES` rather than added to `ConflictRaised`'s ‡ producer list. `RU-3`
  performs **zero durable writes**, so GR-2 does not bind it, and the adjudication's own §D lists it
  among the non-owning rows. **G2-D9** is correctly recorded open rather than improvised.
- G2-D4, G2-D6, G2-D8, G2-D9, G2-D10 are all recorded open and none was silently discharged.
- PD-02 (the Product Driver `_CONTENT_COUNT_RE` regex defect) is correctly recorded as a
  tooling residual; no Product Driver file was modified and the erroneous `7` was not used as
  topology authority.

---

## S. PROOF THE PRODUCT REPOSITORY WAS NOT CHANGED

Measured after every read, parse, clone and mutation run:

| Field | Value |
|---|---|
| HEAD | `38b4bda6cb3ea6c5e5c9a302fd64d23450e6fc62` |
| Tree | `e669ad3375822b0a458b5466d9ce8fb37fceddb3` |
| Branch | `p5/u5-1-g2-spec-correction` |
| Parent | `6e8127dab02e3443183d06825836f5a805f53de0` (tree `515db7425b9ad18b4286b64436f9d240f2e865f6`) |
| Index digest (`git ls-files -s ‖ sha256`) | `0b630149d44f34e5c45a635258a72b2eb14b1de8a98cf893c3a46f64fd385c8e` |
| Worktree-status digest | `2babbc0cce82e8374d038244574325e32d9bc7e9e2f208f57ee0293a1bf9cac0` |
| Total refs | `67` |
| `p4/adapter-containment-completion` | `6e8127dab02e3443183d06825836f5a805f53de0` — unmoved |
| `main` / `origin/main` | both `152574e4f4f2969468c9d31b1e705188896175b5` |
| `refs/preserve/p5-u51-prestate-6e8127d` | `e77ab673021831ff71fb7f74c58c88fce8b377c3` |
| Untracked set | exactly the two authorized third-finalization artifacts |

> The worktree-status digest `2babbc0c…` is **byte-identical** to the value the G2 adjudication
> recorded in its §B at `6e8127d`, independently confirming the untracked set never moved.

**Not done by this session:** no product commit · no amend · no ref creation, deletion or move ·
no `checkout`, `reset`, `restore`, `stash`, `clean`, `rebase`, `merge`, `gc` or `prune` in the
product repository · no push · no `finalize_status.py` and no other finalizer · no adjudication ·
no remediation · no modification of the candidate · no event minting · no change to the frozen
98-event total · no second P5 unit · no `driver.config.yaml` or Product Driver modification · no
Desktop-repository modification · no P4/R-07 reopening · the untracked third-finalization report was
neither deleted nor modified.

**Writes performed, in full:** this report (non-product handoff, uncommitted) and its `.sha256`
sidecar; and disposable analysis artifacts in the session scratchpad
(`indep_parse.py`, `classify.py`, `mutate.sh`, `rows.json`, `canon.json`, suite logs) plus three
throwaway `--no-local` clones, all outside both repositories.

---

## T. TEST RESULTS SUMMARY

| Run | Result |
|---|---|
| Canonical suite, this session's clean clone at `38b4bda` | ### **2091 collected · 2090 passed · 0 failed · 1 skipped · exit 0** |
| Builder's reported clean-clone counts | **identical** |
| Baseline at `6e8127d` (builder-reported) | 2073 / 2072 / 0 / 1 — delta **+18 / 0 removed**, reproduced by node identity |
| G2 guard block at `38b4bda` | 42 passed |
| Hostile mutation battery (18 mutations) | **18 / 18 failed closed, each for the intended reason** |
| `CONSUMES` coordinated laundering (F-01) | ### **SURVIVED — 42 G2 nodes passed; full suite 2088 passed, 0 failed** |
| Anti-`24` carve-out abuse (F-03) | **SURVIVED** (control without the keyword correctly fails) |
| Worktree-artifact node at `6e8127d` vs `38b4bda` | **fails identically at both** with the artifact present; passes at both without it |

---

## U. WHAT IS OWED NEXT

1. **A separate targeted adjudication by a third session** that did not build, did not author the G2
   adjudication and did not write this review. Its first question is **F-01**: ratify or refuse
   `CONSUMES` as an amendment to the §G contract, and if ratified, mandate the narrowed guard.
2. If the adjudicator requires remediation, a **narrow** pass covering F-01 (guard), F-02
   (one row of `PHASE-OUTPUTS.md`), F-03 (carve-out precision) and F-07 (one hostile node). Nothing
   else in this candidate needs to move.
3. Then **exactly ONE** finalizer-generated metadata commit. Single parents throughout; no merge
   commit above a certified content commit.
4. **Unchanged and still binding:** the seven founder/architect event obligations remain OPEN, the
   canonical event total stays **98**, and P5's event content stays blocked.

---

**END OF FRESH INDEPENDENT REVIEW**

**Candidate `38b4bda6cb3ea6c5e5c9a302fd64d23450e6fc62` · tree `e669ad3375822b0a458b5466d9ce8fb37fceddb3` ·
parent `6e8127dab02e3443183d06825836f5a805f53de0` · branch `p5/u5-1-g2-spec-correction`.**

### **VERDICT: CONDITIONALLY ACCEPT — GOVERNANCE ADJUDICATION REQUIRED.**

**7 findings · 3 requiring remediation if the adjudicator so rules (F-01, F-02, F-03) · 1 evidence
deficiency (F-07) · 1 non-blocking worktree classification (F-04) · 2 recorded residuals (F-05, F-06).
No canonical event minted · event total still 98 · P4 COMPLETE and R-07 CONTAINED retained ·
nothing pushed · product repository unchanged.**

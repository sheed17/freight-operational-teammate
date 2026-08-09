# NEYMA P5 U5.1 — REPLACEMENT CANDIDATE `1ae365a`: FRESH INDEPENDENT REVIEW

**Replacement content candidate `1ae365aee76d89ebdc78bbb619a4db8b778a1cad` (tree
`0e52a61c6bef77df42610fa8ea9d142092b4f021`) over certified predecessor
`6e8127dab02e3443183d06825836f5a805f53de0`.**

Replacement for **REJECTED** candidate `38b4bda6cb3ea6c5e5c9a302fd64d23450e6fc62`.

Written outside the product branch and tree. No product commit. No finalizer. No remediation.
The candidate was not modified. No event was minted. No P5 unit was begun. No adjudication performed.

---

## VERDICT

> ### **REJECT — TARGETED REMEDIATION REQUIRED**
>
> **The remediation is real and substantially correct, and both adjudicated `AP-9` exploits now fail
> closed for the intended relationship reasons. But `CONSUMES-VALID` still does not bind a consumer to
> a specific owner ROW — only to the owner's MACHINE — and its replay-coverage rule 4(d) is
> structurally vacuous for a consumer whose durable write is a STATE TRANSITION rather than a named
> field. Those two gaps compose.**
>
> I reproduced two coordinated spec+audit mutations end-to-end against the candidate's own guard
> block, each with the **class totals and the class membership byte-identical**:
>
> 1. **`PL-10` ⇄ `PL-11` exchange the events they consume.** `PL-10` (`CLAIMED→EXECUTED`) now claims
>    its durable write is recorded by `EffectVerified`; `PL-11` (`EXECUTED→VERIFIED`) by
>    `EffectExecuted`. Both relationships are false. **Zero additional test failures.**
> 2. **`PL-7a` — an open `EVENT_REQUIRED` obligation of severity `HIGHEST GOVERNANCE`, the sole
>    autonomous entry into `CHECKPOINT` — is converted into a "proven valid" `CONSUMES:EffectExecuted`
>    that DISCHARGES GR-2, by adding one token (`co-commit M3 \`ATTEMPTED\``) to its `Writes` cell.**
>    `open_founder_gated_obligations` falls **7 → 6** and no guard objects. **Zero additional test
>    failures.**
>
> ### **That is F-01's failure mode — narrowed, not closed.** The adjudication rejected `38b4bda`
> ### because "the corpus's highest-severity open GR-2 obligation [could be] converted into a
> ### discharged one with a two-line edit." For `AP-9` that is now genuinely fixed. For `PL-7a` it
> ### still costs one token.
>
> **`AP-9` survives the new guard only by accident of its own shape** — it is same-machine with
> `AP-7` (4b/4c bite) and it declares a structured field `frozen=true` (4d bites). A durable-writing
> row on M2 whose `Writes` cell names no field has neither protection.
>
> ### **No founder/architect decision is required to fix this, and the remediation is narrow.**
> The datum that identifies the specific owner row **already exists, in structured form, in all twenty
> co-commit declarations the builder itself wrote** — `PL-10` declares ``co-commit M3 `ATTEMPTED` ``
> and `EF-3`'s `To` state *is* `ATTEMPTED`. The guard extracts only the integer `3` from that cell and
> discards the state token. A probe binding on the datum already present accepts **all** current
> durable consumers with zero false negatives and closes **six of seven** confirmed exploits,
> including both reproduced end-to-end. **U5.1 remains guard-blocked, not founder-blocked.**

---

## A. SESSION INDEPENDENCE

A **fresh independent reviewer**. Did **not**: implement P4; participate in the P4/R-07 campaign;
perform the G2 architecture adjudication; build `38b4bda`; conduct its independent review; conduct its
targeted adjudication; build `1ae365a`. Resumed **no** previous Claude session.

Performed no remediation, no adjudication, no finalization, no event minting, no further P5 work. Did
not modify the candidate, the product branch, any ref, `driver.config.yaml`, the Product Driver
configuration, or the Desktop repository. All mutation testing was confined to disposable `--no-local`
clones and tree copies in the session scratchpad, outside both repositories.

The replacement-builder handoff was treated as **untrusted testimony**. Every controlling claim below
was re-derived from Git objects, from repository authority, or by execution.

---

## B. IDENTITY — RESOLVED MECHANICALLY BEFORE SUBSTANTIVE REVIEW

| Property | Required | Observed | Result |
|---|---|---|---|
| Candidate | `1ae365ae…` | `1ae365aee76d89ebdc78bbb619a4db8b778a1cad` | ✅ |
| Tree | `0e52a61c…` | `0e52a61c6bef77df42610fa8ea9d142092b4f021` | ✅ |
| Parent | exactly `6e8127d` | `6e8127dab02e3443183d06825836f5a805f53de0` | ✅ |
| Parent count | 1, not a merge | `git rev-list --parents -n1` → one parent | ✅ |
| Descendant of `38b4bda`? | **NO** | `git merge-base --is-ancestor 38b4bda 1ae365a` → **false** | ✅ |
| Commits above `6e8127d` | exactly 1 | **1** | ✅ |
| Branch | `p5/u5-1-g2-spec-correction` | same; HEAD is the candidate | ✅ |
| Old P4 branch unmoved | `6e8127d` | `p4/adapter-containment-completion` = `6e8127d` | ✅ |
| Nothing pushed | no remote P5 ref | **0** `p5/` refs under `refs/remotes`; `main` = `origin/main` = `152574e4…` | ✅ |
| No finalizer run | none | `git rev-list 1ae365a..branch` → **0**; receipts still bound to `a31a94a` | ✅ |
| No later P5 unit | none | reflog `@{0}` is the candidate commit | ✅ |
| Index digest | — | `ba83298a04abd2bdb2496470ec0d6d6a4560e0daa6df47fda0a86a9f5a2a5e73` | recorded |
| Worktree-status digest | — | `2babbc0cce82e8374d038244574325e32d9bc7e9e2f208f57ee0293a1bf9cac0` | ✅ |
| Untracked set | the two authorized F-04 artifacts | exactly those two | ✅ |

> The worktree-status digest `2babbc0c…` is **byte-identical across four independent sessions** — the
> G2 adjudication at `6e8127d`, the independent review at `38b4bda`, the targeted adjudication, and
> this session. The untracked set never moved.

**Identity confirmed. Review proceeds.**

### Handoff digests — verified mechanically, not inferred from the prompt

| Report | Sidecar | Recomputed | Result |
|---|---|---|---|
| Replacement-builder handoff `…-replacement-candidate-1ae365a.md` | `c86d7a6f99f735a0af59a131422ac8f986bd554ffe2088e130fed38c53ae3e64` | identical | ✅ |
| Independent review of `38b4bda` | `27906bcec34bc7e660ed27d84f5cdcdf6be37ef436b113eb564c048e293f8a43` | identical | ✅ |
| Targeted adjudication of `38b4bda` | `bc120883f09bd67ed0fd80da48c8aa589e8e4b125db16c7f6872378713d9bf6e` | identical | ✅ |

**F-11 (evidence deficiency, LOW).** Two documents in Product Driver handoff storage carry **no
`.sha256` sidecar**: `g2-transition-event-targeted-adjudication-6e8127d.md` and
`p5-u51-g2-spec-correction-candidate-38b4bda.md`. Both are controlling or near-controlling evidence.
Non-blocking — every document this review actually relied on for a ruling has a verified sidecar — but
the gap should be closed.

---

## C. REJECTED-CANDIDATE PRESERVATION — VERIFIED, NOT ACCEPTED

| Ref | Object | Verified contents |
|---|---|---|
| `refs/heads/archive/p5/u51-rejected-38b4bda` | `38b4bda6…` | the rejected commit, tree `e669ad33…`, parent `6e8127d` |
| `refs/preserve/p5-u51-rejected-candidate-38b4bda` | `38b4bda6…` | same object, second stable ref |
| `refs/preserve/p5-u51-rejected-worktree-38b4bda` | `863b6e86…` | diff vs `38b4bda` is **exactly** the 4 authorized additions (2 F-04 artifacts + 2 `.playwright-mcp` paths) |
| `refs/preserve/p5-u51-rejected-candidate-targeted-review-38b4bda` | `fe20030a…` | review + sidecar, parented to `38b4bda`; blob digest recomputed = `27906bce…` ✅ |
| `refs/preserve/p5-u51-rejected-candidate-targeted-adjudication-38b4bda` | `f2626d71…` | adjudication + sidecar, parented to `38b4bda`; blob digest recomputed = `bc120883…` ✅ |
| `refs/preserve/p5-u51-prestate-6e8127d` | `e77ab673…` | **unmoved**, as required |

Both preservation commit messages state *"Parented to the rejected candidate. Not a phase commit and
not a content candidate."* **Every review and adjudication remains attributable only to `38b4bda`** —
neither preserved report mentions or is reachable from `1ae365a`, and the replacement is not a
descendant of `38b4bda`. Total refs `67 → 72`: exactly the five preservation refs.

**Preservation is complete and correct, and matches the P4/R-07 precedent.**

---

## 1. EXACT DELTA

### `6e8127d → 1ae365a` — 23 paths, every one `M`. Zero added, zero deleted.

| Class | Paths |
|---|---|
| **G2 spec/control** | 11 × `docs/specifications/state-machines/*.machine.md` · `docs/implementation/TRANSITION-EVENT-AUDIT.yaml` · `eval/tests/test_bootstrap_hermeticity.py` |
| **Canonical documentation** | `ARCHITECTURE.md` · `CLAUDE.md` · `README.md` · `docs/CANONICAL-DOCUMENTS.md` · `docs/implementation/CURRENT.md` · `docs/implementation/PHASE-OUTPUTS.md` · `docs/product/OPEN-VALIDATION-ITEMS.md` |
| **Audit / status** | `docs/implementation/BUILD-STATUS.yaml` |
| **Tests (manifest)** | `docs/implementation/TEST-NODE-MANIFEST.json` |
| **Acceptance contract** | `docs/implementation/IMPLEMENTATION-REGISTRY.yaml` (P5 instantiation) |
| **Unrelated** | ### **NONE** |

Every path is on the adjudication §15 allowed-surface list. `docs/implementation/PHASE-OUTPUTS.md` is
the one path added over `38b4bda` — the F-02 remediation, explicitly in scope.

### `38b4bda → 1ae365a` — 16 paths, all specification/control. No scope expansion.

### Byte-equality of protected surfaces vs `6e8127d` — all verified by tree-object comparison

| Surface | Tree object | Result |
|---|---|---|
| `src/` | `0204261b…` both refs | ### **IDENTICAL** |
| `scripts/` · `configs/` · `data/` · `docs/architecture/` · `docs/specifications/acceptance/` | — | **IDENTICAL** |
| `docs/specifications/events/registry.md` | `6133927c…` both refs | ### **IDENTICAL** |
| `docs/specifications/state-machines/registry.md` | `76cff142…` both refs | **IDENTICAL** |
| `docs/implementation/PROGRAM-WEIGHTS.yaml` | — | **IDENTICAL** |
| `docs/implementation/phase-0-baseline-manifest.yaml` (R-07 record) | — | **IDENTICAL** |
| `SUITE-RESULT.json` · `GATE-RESULT.json` | — | **IDENTICAL**, still bound to `a31a94a` |

**No runtime, adapter, external-effect-boundary, checkpoint/witness/grant/claim, R-07 or
production-write surface moved.** The set difference of changed paths against
`docs/|ARCHITECTURE.md|CLAUDE.md|README.md|eval/tests/test_bootstrap_hermeticity.py` is **empty**.

**Verdict: scope is exact. No unauthorized expansion.**

---

## 2. EXACT CLASS MEMBERSHIP — INDEPENDENTLY DERIVED

Re-derived with **my own parser**, written from the specification format, not from the candidate's
guard code and not from any aggregate count.

```
ROWS 134
COUNTS  PRODUCER 110 · CONSUMES 9 · NON_PRODUCING 6 · DELEGATES_TO 2 · EVENT_REQUIRED 7  = 134
classifier errors: []        duplicate transition ids: []        misaligned rows: []
canonical events (F1–F14 contracts): 111   F1–F13 owned: 98   producer ids: 110
orphan events: []            dangling producers: []
```

| Requirement | Result |
|---|---|
| 134 source transitions positively anchored | ✅ |
| Zero missing · zero duplicate ids · zero malformed rows | ✅ |
| Every transition classified; no row with 0 or 2 tokens | ✅ |
| No incompatible duplicate classification | ✅ — no §3 producer carries a token |
| Exact bidirectional reconciliation with the audit | ✅ — verified per class, both directions |
| ### `PL-15x` NON_PRODUCING (not CONSUMES) | ### ✅ `NON_PRODUCING:GR1_ILLEGAL_REFUSAL` |
| ### `IB-5x` NON_PRODUCING (not CONSUMES) | ### ✅ `NON_PRODUCING:GR1_ILLEGAL_REFUSAL` |
| `AP-9` remains EVENT_REQUIRED | ✅ |

**Membership matches the adjudicated expectation exactly — by set identity, not by sum.** The
adjudicated per-row disposition for `PL-15x`/`IB-5x` (G2 §H Step 7) is correctly restored, and it is
enforced mechanically: `IllegalTransitionAttempted`'s declared §3 producer is the **rule `GR-1`**, so
`CONSUMES-VALID` rule 3 refuses it. Both rows retain the true inline event naming, which I confirm
carries **zero classifier weight** — the classifier reads only `CLASS_TOKEN_RE`.

---

## 3–5. CONSUMES: DOES IT STILL SELF-CERTIFY?

### 3.1 Where validity is computed

`eval/tests/test_bootstrap_hermeticity.py:544` `_consumes_relationship_errors`, consumed by three
nodes (`…prove_an_authoritative_co_transition_relationship`, the GR-2 converse guard, and the hostile
battery). Inputs, all structured:

| Predicate | Source | Prose read? |
|---|---|---|
| event exists | `events/registry.md` §3 | no |
| owner identity | `events/registry.md` §3 producer field | no |
| owner is a corpus transition | the 134-row corpus | no |
| durable write | `From→To` + `Writes`/`Prov` | no |
| **co-commit relation** | the `Writes` column's `co-commit` **segment** | no |
| mutual exclusivity | `From`/`To` sets within a machine | no |
| payload coverage | `state-machines/registry.md` §5 | no |

**Confirmed:** validity is *not* derived from prose, name similarity, event existence alone, family,
target-state similarity, aggregate counts, or author assertion. The narrative
`## M2↔M3 co-transition rule` sections are genuinely not read. Field extraction is structural — a
backticked declaration or `name=value` only — so a field name cannot be smuggled into a sentence. The
`_writes_segments` split correctly separates *what is persisted* from *what co-commits*.

**This is a genuine, material improvement over `38b4bda`, and the architecture is faithfully the one
the adjudication ratified.**

### 3.2 But the relation binds the owner's MACHINE, not the owner ROW

`_declared_cocommit_machines` (line 473) returns `{int(n) for n in _MACHINE_TOKEN.findall(segment)}`.
4(a) then tests `owner_m not in declared` and `consumer_m not in reciprocal`. **The only quantity
compared is a machine number.**

Consequence, measured by exhaustively evaluating the candidate's own contract for every one of the
98 canonical events against each of the 9 consumers:

| Consumer | Fields declared | Events the contract ACCEPTS | **False accepts** |
|---|---|---|---|
| `PL-6` | none (4d vacuous) | 1 | 0 *(tight only by accident — M4 has one qualifying owner)* |
| `PL-9` | none (4d vacuous) | 9 | ### **8** |
| `PL-10` | none — `Writes` is prose | 8 | ### **7** |
| `PL-10f` | `failure_proof` | 1 | 0 |
| `PL-10u` | `exposure`,`unknown_reason` | 1 | 0 |
| `PL-11` | none (4d vacuous) | 8 | ### **7** |
| `PL-11c` | `unknown_reason` | 3 | 1 |
| `PL-15` | `decision_ref` | 1 | 0 |
| `RU-3` | zero durable write | 98 | *(rule 4 — descriptive only, exempts nothing; correct)* |

> ### **Where 4(d) declares a field, the contract is tight — exactly one event. Where the durable
> ### write is a STATE TRANSITION and no field is named, the contract admits every event owned by any
> ### corpus row on a machine the consumer declares co-commit with.**

**4(d) as implemented covers named fields only. A state-only durable write — `To ∉ From` with an
em-dash or prose `Writes` — is counted as durable by `_durable_write` but contributes zero fields to
coverage, so 4(d) is structurally vacuous for precisely the rows GR-2 most needs it for.**

### 3.3 The nine rows — proof table

Verdict column answers the brief's required enumeration. "VALID CONSUMER" means the declared
relationship is architecturally true **as declared**; the *contract* column records whether the guard
actually binds it.

| # | Consumer | Event(s) | §3 owner(s) | Owner M | Authoritative relation source | Durable | 4(d) fields | Replay consequence | Guard binds it? | **Verdict** |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | `02:PL-6` `VALIDATED→AWAITING_APPROVAL` | `ApprovalRequested` | `AP-1` | M4 | bidirectional co-commit (`PL-6→M4 REQUESTED`, `AP-1→M2 AWAITING_APPROVAL`) | yes (state) | none | state reconstructs from `ApprovalRequested{fingerprint, gate_decision}` + own guard | only by accident (1 qualifying M4 owner) | **VALID CONSUMER** |
| 2 | `02:PL-9` `GRANTED→CLAIMED` | `GrantClaimed` | `EF-2` | M3 | pre-existing bidirectional co-commit | yes (state) | none | exact — the paradigm case | ### **NO — accepts 8 wrong events** | **VALID CONSUMER** *(unbound)* |
| 3 | `02:PL-10` `CLAIMED→EXECUTED` | `EffectExecuted` | `EF-3` | M3 | bidirectional co-commit | yes (state; `Writes` prose) | none | `EffectExecuted` §5 payload is **`—`** | ### **NO — accepts 7 wrong events** | **VALID CONSUMER** *(unbound)* |
| 4 | `02:PL-10f` `CLAIMED→FAILED` | `EffectFailed` | `EF-3f` | M3 | bidirectional co-commit | yes | `failure_proof` | ✅ `EffectFailed{failure_proof}` | ✅ yes | **VALID CONSUMER** |
| 5 | `02:PL-10u` `CLAIMED→NEEDS_VERIFICATION` | `OutcomeUnknown` | `EF-3u`,`EF-4c`,`EF-4u` | M3 | bidirectional, all three owners | yes | `exposure`,`unknown_reason` | ✅ | ✅ yes | **VALID CONSUMER** *(owner-set breadth residual — §21)* |
| 6 | `02:PL-11` `EXECUTED→VERIFIED` | `EffectVerified` | `EF-4` | M3 | bidirectional co-commit | yes (state) | none | `EffectVerified{verification_outcome, health_signal}` | ### **NO — accepts 7 wrong events** | **VALID CONSUMER** *(unbound)* |
| 7 | `02:PL-11c` `EXECUTED→NEEDS_VERIFICATION` | `VerificationConflict`,`VerificationUnavailable` | `EF-4c`,`EF-4u` | M3 | bidirectional, both owners | yes | `unknown_reason` | ✅ both payloads carry it | partly — also accepts `OutcomeUnknown` | **VALID CONSUMER** |
| 8 | `02:PL-15` `NEEDS_VERIFICATION→{VERIFIED,FAILED}` | `RealityEstablished` ‡ | `EF-5`,`CM-5` | M3, M10 | bidirectional with **both** machines | yes | `decision_ref` | ✅ `{decision_ref, outcome}` | ✅ yes | **VALID CONSUMER** *(per-branch residual — §21)* |
| 9 | `12:RU-3` `COMPILED → *(blocked)*` | `ConflictRaised` ‡ | `CF-1`,`IB-6`,`EF-4c` | M7,M6,M3 | causation, not co-transition | ### **no** | n/a | GR-2 does not bind | n/a — rule 4 | **VALID CONSUMER (zero-write causation)** — carries **no exempting force** |

**All nine declarations are architecturally true as written. None is `ACTUALLY PRODUCER`, none is
`EVENT_REQUIRED`, none is `INVALID`.** The defect is not in the corpus; it is that the control
certifying the corpus does not bind four of these relationships.

### 3.4 The decisive test — can the candidate make a false relationship valid by editing spec and audit consistently?

The adjudication §13 named this exact shape: *"a candidate must not be accepted because its classes
reconcile."* **It can.**

---

## FINDING R-01 — `CONSUMES-VALID` DOES NOT BIND THE CONSUMER TO THE OWNER ROW

| Field | Value |
|---|---|
| **ID** | **R-01** |
| **Severity** | ### **HIGH** |
| **Class** | ### **CONFIRMED DEFECT** |
| **Blocking** | ### **YES** |
| **Requirement** | Targeted adjudication §2 rule 4(a)+(c) and §5: *"producer and consumer participate in the same authorized semantic operation"*; brief §4: *"unrelated canonical events cannot satisfy the relation"*; *"mutually-exclusive transitions cannot masquerade as co-transition partners"* |
| **Location** | `eval/tests/test_bootstrap_hermeticity.py:473` `_declared_cocommit_machines`; consumed at `:592` and `:598` |

**Reproduction (end-to-end, coordinated spec + audit, in a disposable copy):**

`docs/specifications/state-machines/02-pipeline-instance.machine.md` — exchange the Event cells of
`PL-10` and `PL-11`:

```
PL-10:  `EffectExecuted` — `CONSUMES:EffectExecuted`   →   `EffectVerified` — `CONSUMES:EffectVerified`
PL-11:  `EffectVerified` — `CONSUMES:EffectVerified`   →   `EffectExecuted` — `CONSUMES:EffectExecuted`
```

`docs/implementation/TRANSITION-EVENT-AUDIT.yaml` — update both members consistently
(`PL-10: consumes [EffectVerified], owner [EF-4]`; `PL-11: consumes [EffectExecuted], owner [EF-3]`).

| Measurement | Result |
|---|---|
| Class totals before/after | **110 / 9 / 6 / 2 / 7 = 134** — byte-identical |
| Class **membership** before/after | **identical** |
| G2 guard block, mutated tree | ### **51 passed, 2 failed** |
| G2 guard block, **unmutated baseline in the same environment** | ### **51 passed, 2 failed** — the identical two |
| Additional failures caused by the mutation | ### **ZERO** |

*(The two failures are environmental — `test_collection_succeeds_with_zero_errors` and
`test_a_clean_clone_has_no_workspace_database` require a `.git` directory the tree copy lacks. They
fail identically on the unmutated baseline, which is why the comparison is sound.)*

**Proof the mutation bit the intended relationship, not a syntax error:** my independent parser
re-parses the mutated tree cleanly — 134 rows, zero classifier errors, zero duplicates, zero misaligned
rows, counts unchanged. The declarations are well-formed; they are simply false.

**Consequence.** `PL-10` (`CLAIMED→EXECUTED`) certifies that its durable write is recorded by
`EffectVerified`, an event emitted at `EF-4` (`ATTEMPTED→VERIFIED`) at a different moment in the
pipeline; `PL-11` certifies the converse. A full-history replay reconstructs each state from an event
that fires at the wrong point. Both rows are counted as **GR-2 discharged** by
`test_every_durable_write_is_recorded_by_an_event_or_a_registered_open_obligation`.

**Further confirmed false accepts** (via exhaustive evaluation of the candidate's own contract):
`PL-9` → `ApprovalRequested` (M4, `AP-1`, an approval-request moment consumed by a grant-claim row) and
seven others per consumer; `PL-11c` → `OutcomeUnknown`. **120 false-accepting (consumer, event) pairs
in total across the durable consumers**, excluding `RU-3`'s correct zero-write case.

**Narrow remediation requirement.** Bind 4(a) to the owner **row**, not its machine. ### **The datum
already exists in structured form in every one of the twenty co-commit declarations this candidate
wrote** — the state token beside the machine token names the counterpart row's `To` state:

| Consumer declares | Owner's `To` | Owner declares | Consumer's `To` |
|---|---|---|---|
| `PL-10` → ``M3 `ATTEMPTED` `` | `EF-3` = `ATTEMPTED` ✅ | `EF-3` → ``M2 `EXECUTED` `` | `PL-10` = `EXECUTED` ✅ |
| `PL-11` → ``M3 `VERIFIED` `` | `EF-4` = `VERIFIED` ✅ | `EF-4` → ``M2 `VERIFIED` `` | `PL-11` = `VERIFIED` ✅ |
| `PL-6` → ``M4 `REQUESTED` `` | `AP-1` = `REQUESTED` ✅ | `AP-1` → ``M2 `AWAITING_APPROVAL` `` | `PL-6` = `AWAITING_APPROVAL` ✅ |
| `PL-15` → ``M3 `{VERIFIED,FAILED}`, M10 `COMPLETED` `` | `EF-5`, `CM-5` ✅ | both → ``M2 `{VERIFIED,FAILED}` `` | `PL-15` ✅ |

*(All twelve consumer/owner pairs verified; table abridged.)*

**Feasibility probe** — reading the token the guard currently discards:

- accepts **every** current durable consumer/owner pair — **zero false negatives**;
- rejects `PL-10→EffectVerified`, `PL-11→EffectExecuted`, `PL-9→ApprovalRequested`,
  `PL-10→GrantClaimed`, `PL-11→OutcomeUnknown`, and the R-02 laundering below.

This probe is offered as **evidence that the remediation is narrow and requires no new authority**. It
is **not** a prescribed design; the exact predicate is the remediating builder's to write and the
adjudicator's to approve.

---

## FINDING R-02 — AN OPEN `HIGHEST GOVERNANCE` OBLIGATION CAN STILL BE LAUNDERED WITH ONE TOKEN

| Field | Value |
|---|---|
| **ID** | **R-02** |
| **Severity** | ### **HIGH** |
| **Class** | ### **CONFIRMED DEFECT** |
| **Blocking** | ### **YES** |
| **Requirement** | Targeted adjudication §2 **rule 5, downgrade prohibition**: *"`EVENT_REQUIRED → CONSUMES` requires 4(a)–(d) in full"*; §17: the replacement must close the mechanism that *"converts the corpus's highest-severity open safety obligation into a discharged one with a two-line edit"* |
| **Location** | `_consumes_relationship_errors` 4(a)/4(d) interaction, `test_bootstrap_hermeticity.py:592–612` |

**Reproduction (end-to-end, coordinated spec + audit, in a disposable git-backed clone):**

`02-pipeline-instance.machine.md`, row `PL-7a` (`VALIDATED → CHECKPOINT`):

```
Writes:  —                                              →   co-commit M3 `ATTEMPTED`
Event:   EVENT_REQUIRED:G2-OB-PL-7A-…-UNRECORDED        →   CONSUMES:EffectExecuted
```

`TRANSITION-EVENT-AUDIT.yaml`: move `PL-7a` from `EVENT_REQUIRED.members` into `CONSUMES.members`
(`owner: [EF-3]`, `owner_machine: [M3]`, `durable_write: true`); **delete its obligation record**;
`CONSUMES: 9→10`, `EVENT_REQUIRED: 7→6`, `open_founder_gated_obligations: 7→6`.

| Measurement | Result |
|---|---|
| G2 guard block | ### **51 passed, 2 failed — identical to the unmutated baseline. ZERO additional failures.** |
| `open_founder_gated_obligations` | ### **7 → 6**, unchallenged |
| ### Full canonical suite, git-backed clone | ### **2098 passed · 1 skipped · 3 failed — and all three are topology artifacts of the mutation method, NOT semantic catches** |

**The three suite failures are excluded as evidence, on my own control.** They are
`test_status_reality.py::test_recorded_commit_and_tree_match_a_legal_repository_state`,
`::test_the_status_record_is_backed_by_a_real_suite_result` and
`::test_at_rest_the_artifact_population_matches_the_live_test_population`. I reproduced **exactly
those three** in a separate clone by appending a single blank line to an unrelated file and
committing — the status record binds to `a31a94a`, so *any* new commit in a clone trips them. They
say nothing about `PL-7a`. In a real remediation flow the builder makes a legitimate content commit
and the finalizer writes the receipts, so these three are satisfied and **the laundering is
invisible**.

**Mutation-attributable failures across the full 2102-node canonical suite: ZERO.**

**Proof the mutation bit the intended relationship.** An *incomplete* version of this edit — leaving
the obligation record in place — **is** caught, by
`test_the_founder_gated_event_obligations_are_explicit_and_cannot_be_silently_discharged` (spec ids ≠
registered ids). Completing the edit consistently, which is the ordinary shape of a legitimate builder
commit and precisely the shape the adjudication §13 warned about, removes the only objection. Nothing
in `CONSUMES-VALID` objects at any point.

**Consequence.** `PL-7a` is *"the SOLE autonomous entry into `CHECKPOINT` … the bounded-autonomy
admission point"*, severity **`HIGHEST GOVERNANCE`** — the second-sharpest of the seven obligations
after `AP-9`. Its declared relationship to `EffectExecuted` is plainly false: `PL-7a` fires **before
any grant exists**, while `EF-3` (`CLAIMED→ATTEMPTED`) fires far later; and `EffectExecuted`'s §5
payload is **`—`**, so replay reconstructs nothing at all.

**Why `AP-9` survives and `PL-7a` does not.** `AP-9` is defended by 4(b)/4(c) (same machine as `AP-7`)
and by 4(d) (`frozen=true` is a *named field*). Those are properties of `AP-9`'s shape, not of the
contract. `PL-7a` is on M2, cross-machine to M3, and its durable write is a state transition with no
named field — so 4(b), 4(c) and 4(d) are all silent, and 4(a) is satisfied by `EF-3`'s pre-existing
``co-commit M2 `EXECUTED` `` declaration, which was added for `PL-10`'s benefit and is reusable by
**any** M2 row.

**The same one-token laundering was tested against the other six obligations and correctly fails**:
`PO-2`, `PO-3`, `RU-8`, `CF-7`, `EC-7` are on machines M9/M11/M12 for which no M3 owner declares a
reciprocal, and `AP-9` fails as above. **`PL-7a` is exposed because it is the only durable
`EVENT_REQUIRED` row on M2 with no named field.**

**Narrow remediation requirement.** The owner-row binding of R-01 closes this (verified by probe).
Alternatively, or additionally, 4(d) must account for a **state-transition** durable write rather than
only named fields.

---

## 6. PAYLOAD COVERAGE — REVIEWED HOSTILELY

The builder disclosed removing the adjudicated 4(d) **derivability escape** (§2 4(d) permits *"appears
in some `Eᵢ`'s declared payload … **or is derivable from `T`'s registered guard**"*).

**Classification: (B) a valid conservative strengthening — but it does not buy what the builder
believes, and it must not be read as compensating for R-01.**

| Test | Result |
|---|---|
| Does strictness reject any **current** valid consumer? | ### **NO.** All four field-declaring consumers (`PL-10f`, `PL-10u`, `PL-11c`, `PL-15`) satisfy strict coverage. The four state-only consumers declare no field, so 4(d) never engages |
| Does strictness reject a **plausible structurally valid** relationship under existing authority? | **Potentially yes**, but no such row exists in the corpus today. `events/registry.md`:7 (*"the event does not instruct them"*) contemplates a consumer deriving state from its own guard; a future row doing so would be refused |
| Does removing derivability strengthen the exploits' failure? | **Only for `AP-9` variant 2**, and only because `frozen` is a named field. It contributes nothing to the four state-only consumers |
| Is it architecture beyond builder authority? | ### **NO.** It is strictly narrower than an adjudicated permission; a builder may implement less latitude than granted |

**No new derivability concept is invented here, and none is proposed.** If a future row needs the
escape, the structured derivation authority the adjudication contemplated is the consumer's
**registered deterministic transition guard** (`events/registry.md`:7) — which is *not currently a
structured column*, and making it one would be a specification change requiring its own authorization.
**Recorded for the adjudicator (§21-A), not decided here.**

**R-03 (non-blocking residual, LOW).** 4(d) coverage is computed as a **union** over all named events
(`covered |= payloads.get(name)`, line 574), not per-event. For a multi-event declaration over
*mutually exclusive alternatives* — only one of which fires per instance — union coverage is unsound in
principle: replay of the branch where the *other* event fired would not reconstruct the field. Harmless
today (`PL-11c`'s `unknown_reason` is in both payloads), and it is what admits `PL-11c → OutcomeUnknown`.

---

## 7. THE TWO ORIGINAL EXPLOITS — REPRODUCED INDEPENDENTLY

Both were reproduced against the replacement.

| Exploit | Mutation | Result | Failing guard(s) and exact reason |
|---|---|---|---|
| **A** | `AP-9` → `CONSUMES:ApprovalConsumed` (owner `AP-7`, mutually exclusive) | ### **FAILS CLOSED** | **4(b)** *"MUTUALLY EXCLUSIVE with it (same machine, From sets intersect, To states differ)"* · **4(c)** *"owned by 04-approval:AP-7 on its OWN machine (M4)"* · **4(a)** forward |
| **B** | `AP-9` → `CONSUMES:BrakeReleased` (owner `BR-4`, M13, unrelated) | ### **FAILS CLOSED** | **4(a)** both directions *"its own Writes cell declares co-commit with no machine"* / *"BR-4 … does NOT declare the reciprocal with M4"* · **4(d)** *"its durable write declares ['frozen'], which no consumed event's §5 payload carries"* |

**Proof the mutation bit the intended relationship:** each failure names `AP-9`, the specific
consumed event, the specific §3 owner row, and the specific rule — not a parse error. The hostile
nodes additionally assert the failure *reasons* by substring (`MUTUALLY`, `OWN machine`, `co-commit`,
`frozen`, `replay`), so neither can pass for an incidental cause, and each carries a positive control
(`PL-9` must still be accepted) so neither can pass vacuously.

**Both exploits fail for the intended relationship reason. F-01's headline claim is verified.** The
finding is that the invariant does not generalize (R-01, R-02).

---

## 8. EXTENDED HOSTILE BATTERY

| # | Attack | Result |
|---|---|---|
| 1 | `EVENT_REQUIRED` → arbitrary `CONSUMES`, as written (all 7 rows) | **FAILS CLOSED** (4a forward) |
| 2 | ### `EVENT_REQUIRED` → `CONSUMES` **after adding one `co-commit M3` token** — `PL-7a` | ### **ACCEPTED — R-02** |
| 3 | same, `PO-2` · `PO-3` · `RU-8` · `CF-7` · `EC-7` · `AP-9` | **FAIL CLOSED** |
| 4 | unrelated producer (`AP-9`→`BrakeReleased`) | **FAILS CLOSED** |
| 5 | mutually-exclusive producer (`AP-9`→`ApprovalConsumed`) | **FAILS CLOSED** |
| 6 | ### wrong canonical producer for a real event (`PL-10`→`EffectVerified`) | ### **ACCEPTED — R-01** |
| 7 | nonexistent producer / rule-owned event (`PL-15x`, `IB-5x` → `IllegalTransitionAttempted`) | **FAILS CLOSED** (rule 3, *"owned by a RULE"*) |
| 8 | nonexistent event (`NoSuchEvent`) | **FAILS CLOSED** (rule 1) |
| 9 | self-owner (`EF-3` consuming `EffectExecuted`) | **FAILS CLOSED** (rule 2) |
| 10 | missing co-transition relation (synthetic, neither side declares) | **FAILS CLOSED** |
| 11 | **one-sided** co-commit — `EF-3f` drops only its reciprocal | ### **FAILS CLOSED** — 4(a) is genuinely bidirectional |
| 12 | malformed structured relation / empty `CONSUMES` | **FAILS CLOSED** (*"CONSUMES names no event"*) |
| 13 | consumer/event relation in the wrong state machine (within-machine) | **FAILS CLOSED** (4c) |
| 14 | ### two `CONSUMES` rows swap producers — `PL-10f` ⇄ `PL-11c` | **FAILS CLOSED** (4d only) |
| 15 | ### two `CONSUMES` rows swap producers — `PL-10` ⇄ `PL-11` | ### **ACCEPTED — R-01** |
| 16 | relation exists but payload does not cover persisted state | **FAILS CLOSED** (4d) |
| 17 | edit both audit and spec consistently to assert a false relationship | ### **ACCEPTED — R-01, R-02** |
| 18 | machine token written `M03` | correctly parsed as M3 — no parser fragility |
| 19 | zero-durable-write row given an arbitrary `CONSUMES` (`AP-8`, `BR-5`, `RU-3`) | accepted — **correct per adjudicated rules 3/4**: descriptive, exempts nothing (**R-08**, non-blocking) |

**No finding rests on a parser crash.** Every fail-closed result above is a named semantic error
identifying the row, the event, the owner and the rule.

> ### The builder's own swap node (#14) selected `PL-10f` ⇄ `PL-11c` — the one pair where 4(d)
> ### happens to bite. The structurally identical pair `PL-10` ⇄ `PL-11`, where 4(d) is vacuous, was
> ### not tested. The hostile battery has a positive-result selection bias at exactly the point where
> ### the contract is weakest.

---

## 9. CONSTANT-TOTAL ATTACKS

| Attack | Totals held | Membership held | Result |
|---|---|---|---|
| `AP-9` ⇄ `PL-6` class swap (the builder's M3) | ✅ 110/9/6/2/7 | — | **FAILS CLOSED** — two independent predicates: the relational contract on the `AP-9` side, the obligation registry's transition binding on the `PL-6` side |
| Producer swapped with another producer | ✅ | ✅ | **FAILS CLOSED** — §3 membership decides `PRODUCER`; a producer carrying a token is an error |
| `NON_PRODUCING` ⇄ `CONSUMES` (`PL-15x` back to `CONSUMES`) | — | — | **FAILS CLOSED** — rule 3 |
| Two consumer owners exchanged — `PL-10f` ⇄ `PL-11c` | ✅ | ✅ | **FAILS CLOSED** — 4(d) |
| ### Two consumer owners exchanged — `PL-10` ⇄ `PL-11` | ### ✅ | ### ✅ | ### **ACCEPTED — R-01** |
| `PL-6` ⇄ `PL-9` owner exchange | ✅ | ✅ | half closed: `PL-6`→`GrantClaimed` rejected; ### `PL-9`→`ApprovalRequested` **ACCEPTED** |

**Counts are correctly not sufficient evidence — for four of the five classes. For `CONSUMES`, a
constant-total *and* constant-membership mutation that changes only the relationship survives whenever
4(d) is vacuous.** The asymmetry the adjudication §13 identified is **narrowed, not eliminated**.

---

## 10. THE SIX `NON_PRODUCING` ROWS

| Row | Marker | Zero-durable-write proof (structured columns) | Durable write added ⇒ | Marker removed ⇒ |
|---|---|---|---|---|
| `04:AP-8` | `ENUMERATED_NO_OP` | `GRANTED→GRANTED` (To∖From = ∅); `Writes` = `—` | **FAILS** | **FAIL-CLOSED**, 0 tokens |
| `03:EF-5x` | `GR1_ILLEGAL_REFUSAL` | no `To` state; `Writes` = `—` | **FAILS** | **FAIL-CLOSED** |
| `10:CM-5x` | `GR1_ILLEGAL_REFUSAL` | no `To` state; `Writes` = `—` | **FAILS** | **FAIL-CLOSED** |
| `13:BR-5` | `GR1_ILLEGAL_REFUSAL` | no `To` state; `Writes` = `—` | **FAILS** | **FAIL-CLOSED** |
| ### `02:PL-15x` | `GR1_ILLEGAL_REFUSAL` | no `To` state; `Writes` = `—` | **FAILS** | **FAIL-CLOSED** |
| ### `06:IB-5x` | `GR1_ILLEGAL_REFUSAL` | no `To` state; `Prov` = `—` | **FAILS** | **FAIL-CLOSED** |

All six verified independently: explicit structured classification, zero durable writes proven from
columns, prose cannot self-certify (the retained inline `IllegalTransitionAttempted` naming carries
**zero** classifier weight — confirmed, only `CLASS_TOKEN_RE` classifies), and no canonical event
obligation is hidden — `IllegalTransitionAttempted` remains rule-owned by `GR-1`, which is exactly why
these rows cannot be `CONSUMES`.

**`PL-15x` / `IB-5x` reclassification is correct and correctly enforced.** ✅

### The `PL-15` per-branch owner question — builder judgment call B

**Assessment: acceptable but residual (see §21-B).** The builder's stated reason is **factually
correct**, verified independently: `CM-5` is `{COMPENSATION_FAILED,NOT_POSSIBLE} → COMPLETED` on M10.
A `DELEGATES_TO`-style rule requiring the owner to *itself transition to the delegated state* would
reject `CM-5` — a row the adjudication itself named a valid owner. `PL-15`'s two-element `To` set is
resolved at runtime by `RealityEstablished{outcome}`, and `outcome` **is** in the §5 payload, so the
branch discriminator is carried by the event rather than by target-state matching. **Not a missing
safety invariant; a genuine structural difference between the two classes.** Recorded as residual.

---

## 11. `DELEGATES_TO` — TWO ROWS, ALL VERIFIED

| Row | Resolution | Errors |
|---|---|---|
| `01:WI-14` `ESCALATED→{BLOCKED,AWAITING_HUMAN,CLOSED,CANCELLED}` | `BLOCKED→WorkBlocked` · `AWAITING_HUMAN→HumanRequested` · `CLOSED→WorkItemClosed` · `CANCELLED→WorkItemCancelled` | none |
| `07:CF-6` `ESCALATED→{RESOLVED_BY_RULE,RESOLVED_BY_HUMAN}` | both → `ConflictResolved` | none |

Structured relation ✅ · valid targets ✅ · owners exist ✅ · **exactly one** event-producing owner per
branch ✅ · no cycle ✅ · no self-delegation ✅ · **`To`-set ↔ branch-union exact equality** ✅.

Attack results: zero targets → **fail-closed** · nonexistent target → **fail-closed** · non-producer
target → **fail-closed** · duplicate/ambiguous → **fail-closed** · self-delegation → **fail-closed** ·
malformed branch → **fail-closed**.

**WI-14 arity (G2-D3) remains correctly resolved by target state, never positionally.** The word
*"respectively"* is **absent from the entire machine corpus** — independently confirmed by direct file
scan.

---

## 12. `EVENT_REQUIRED` — SEVEN, INDEPENDENTLY DERIVED

`02:PL-7a` · `04:AP-9` · `07:CF-7` · `09:EC-7` · `11:PO-2` · `11:PO-3` · `12:RU-8`

Each: registered obligation whose id fails `^[A-Z][A-Za-z0-9]*$` and is **absent from the canonical
corpus** — no invented event name, no placeholder masquerading as an event ✅ · `transition`,
`durable_write`, `semantic_obligation`, `decision_required` all present and non-empty ✅ ·
`open_founder_gated_obligations: 7` ✅ · `meta.status = G2_PARTIALLY_DISCHARGED_FOUNDER_GATED` ✅ ·
`canonical_events_F1_F13: 98` ✅ · unresolved deliberately, fail-closed, unscored as complete ✅.

### **G2 is correctly still NOT fully discharged.** ✅

**Caveat, recorded:** the set is held by `{spec obligation ids} == {registered obligation ids}` plus
`open_founder_gated_obligations == len(obligations)`. **No hard-coded `7` pins the population**, which
is what makes R-02's consistent downgrade invisible.

---

## 13. `AP-9` SAFETY — RECONFIRMED

| Requirement | Result |
|---|---|
| `frozen=true` is safety-relevant | ✅ `04-approval.machine.md` §14 `Writes` = `frozen=true`; §15 *"Reuse of a frozen (AP-9) approval → ILLEGAL"* — a guard input to an ILLEGAL determination |
| Historical replay cannot reconstruct it | ✅ **No F4 event carries the approval `frozen` flag.** §5: `ApprovalConsumed` = `—`; `ApprovalGranted`/`Denied`/`Revoked`/`Expired` = `—`; `ApprovalVoided` = `cause, drift_diff?`. A rebuild reconstructs an approval that is **not frozen — i.e. reusable**; the rebuilt state is **less safe than the original** |
| Candidate does not hide `AP-9` through `CONSUMES` | ✅ classified `EVENT_REQUIRED:G2-OB-AP-9-FREEZE-FACT-UNRECORDED`; both laundering variants fail closed |
| Remains explicitly `EVENT_REQUIRED` | ✅ |
| Founder/architect event-schema authority still necessary | ✅ both admissible remedies recorded, with *"DO NOT IMPROVISE THE EVENT DESIGN"* and the interim fail-closed default |

**No event was designed, named or proposed by this review.**

---

## 14. EVENT REGISTRY HARD BOUNDARY

| Check | Result |
|---|---|
| `docs/specifications/events/registry.md` | ### **BYTE-UNCHANGED** — tree object `6133927c…` at **both** `6e8127d` and `1ae365a` |
| No event added / removed / renamed | ✅ — mechanically implied by byte-equality |
| Canonical total | ### **98** (F1–F13 owned), independently recounted by my own parser |
| Canonical producer changed unexpectedly | ✅ none — 110 producer ids, 0 orphans, 0 dangling |
| Schema widened to avoid a missing-event decision | ✅ no — `state-machines/registry.md` also byte-unchanged |
| `EF-3` remains associated with existing `EffectExecuted` | ✅ `` `EffectExecuted`(EF-3) `` in §3, F3 line |

### **The hard authorization boundary is intact.** ✅

---

## 15. F-02 REMEDIATION

`PHASE-OUTPUTS.md:153` is rewritten: the stale *"must be adjudicated first — COUNT NEEDS
ADJUDICATION, 4 classes"* row now states the real block (G2 adjudicated and partially discharged;
seven founder/architect-gated obligations; P5 event content blocked), consistent with `CURRENT.md`.

A new guard, `test_a_retired_g2_status_token_never_appears_as_a_live_claim`, reads the forbidden set
from the audit's own `retired_status_tokens` record (`COUNT_NEEDS_ADJUDICATION`, `4 classes`) rather
than hard-coding it, and requires each retirement to record its `superseded_by`.

| Check | Result |
|---|---|
| Live status reflects adjudicated state | ✅ |
| Historical evidence clearly historical | ✅ — `IMPLEMENTATION-REGISTRY.yaml:1372` quotes the old text in an explicitly historical framing |
| Laundering into another canonical document | ✅ none — the token appears live nowhere in `CONTROL_POPULATION` |
| ### Historical reports rewritten? | ### **NO.** `p4-r07-closure-handoff.md` and every `u-handoff-*` review are **absent from the 23-path delta** — untouched |

**Semantically equivalent current falsehoods — swept independently:**

| Probe | Caught? |
|---|---|
| direct restatement of the token | ✅ |
| the same falsehood **without** the token (*"must be adjudicated first, 4 classes"*) | ✅ — `4 classes` is itself a registered token |
| hyphenated variant `COUNT-NEEDS-ADJUDICATION` | ✅ |
| token in a sentence containing *"was the"* / *"before the"* | ❌ **bypass** |

**R-05 (non-blocking residual, LOW).** The historical carve-out keys on
`retired|superseded|historical|no longer|was the|before the` **anywhere in the enclosing sentence**, so
a live claim wrapped in a sentence containing one of those phrases passes. The carve-out is
deliberate and necessary; the phrase list is broader than it needs to be. **F-02 is remediated as
adjudicated.**

---

## 16. F-03 / RETIRED "24" SEMANTICS

The two senses are kept correctly separate: **24 canonical non-producer transitions** (live, computed,
correct — `producer_view.non_producer_transitions: 24`, which my parser confirms: 134 − 110) versus
**24 unnamed/non-event transitions** (retired, never mechanically computed). `retired_figures` records
both with `do_not_confuse_with`. **The candidate does not conflate them.** ✅

The adjudicated remediation — replace the ±120-character window with a **same-clause** requirement, and
scope the retired-label carve-out to the **enclosing sentence**, with a hostile node asserting the
reproduction sentence FAILS — **is implemented exactly.**

**Hostile reintroduction of the retired meaning in different wording:**

| Probe | Result |
|---|---|
| *"24 of the 134 transitions name no event outright."* (the adjudication's control) | ### ✅ **CAUGHT** |
| *"…outright, which is the non-producer population."* (the F-03 bypass) | ### ✅ **CAUGHT — the specific defect is fixed** |
| *"24 of the 134 rows are non-producer transitions."* (true) | ✅ correctly allowed |
| *"The retired 24 figure counted transitions naming no event."* (historical) | ✅ correctly allowed |
| *"**Twenty-four** of the 134 transitions name no event outright."* | ❌ **bypass** — `\b24\b` never matches |
| *"24 rows, spread across the thirteen canonical machine specification files, name no event."* | ❌ **bypass** — >50 chars separation |
| *"Unlike the **retired** naming split, 24 transitions genuinely name no event today."* | ❌ **bypass** — sentence-scoped keyword |
| *"Although **never mechanically** recomputed since, 24 transitions name no event."* | ❌ **bypass** — same |

**R-04 (non-blocking residual, MEDIUM-LOW; governance-attributable).** The guard remains a **lexical
proximity/keyword predicate**, not a semantic one: it is `\b24\b … {0,50} … (transitions?|event)` with
sentence-scoped keyword carve-outs. The adjudication §8 required the carve-out *"bind meaning
structurally rather than by nearby prose keywords"* — and then specified a remedy (`24[^.\n]{0,40}
non-producer transitions`, sentence-scoped) that is itself lexical. **The builder implemented the
specified remedy faithfully; the residual is inherent to the remedy, not a deviation.** Whether the
stronger stated objective is owed is a governance question, recorded for the adjudicator. F-03's
concrete reproduction is closed.

---

## 17. F-04 — PRIMARY WORKTREE ARTIFACT

> ### **CONFIRMED — PRE-EXISTING AUTHORIZED UNTRACKED ARTIFACT. INHERITED. NON-BLOCKING. NOT THIS UNIT'S.**

Decisive differential run by this session, single node
`test_every_implementation_document_is_classified_or_family_covered`, in a fresh clone at both refs:

| Ref | Without the artifact | With the artifact |
|---|---|---|
| `6e8127d` (certified predecessor) | ### **1 passed** | ### **1 failed** |
| `1ae365a` (candidate) | ### **1 passed** | ### **1 failed** |

### **Identical behaviour at both refs. The candidate is not implicated.**

| Check | Result |
|---|---|
| Did the candidate create it? | **No** — untracked at *both* refs (`git ls-tree` → 0/0); mtime `2026-08-06 18:43`, candidate committed `2026-08-08` |
| Preserved? | ✅ `refs/preserve/p4-r07-third-finalization-report-6e8127d` → `61d42466…`, plus `.sha256` sidecar |
| Was the test weakened? | ### **No** — the only diff line mentioning the node is an **added comment** (`+#`); zero hunks modify it |
| Clean clone excludes it? | ✅ verified absent from my `--no-local` clone |
| Clean-clone gate passes? | ✅ §20 |
| Report deleted or modified? | ### **NO — neither. Left exactly as found.** |

**Classification: test-environment limitation / inherited residual.** Belongs to the next
R-07-adjacent correction with F-06, whose forbidden surface (`README.md:73-80`) I independently
confirm **byte-identical** to `6e8127d`.

---

## 18. P5 ACCEPTANCE CONTRACT

| Check | Result |
|---|---|
| Source `PROGRAM-WEIGHTS.yaml` `acceptance_template` | ### **BYTE-UNCHANGED** vs `6e8127d` |
| Criteria | ### **14** |
| Sum of weights | ### **exactly 100** |
| Verbatim **ordered** match `[(criterion, weight)]` to the frozen template | ### **True** — machine-compared |
| Results | ### **all 14 `PENDING`** · any `PASS` = **False** |
| Score assigned | ### **none** |
| P5 unit status | `READY` — unchanged from `6e8127d` |
| P4 units | `COMPLETE`, 14/14 `PASS` — unchanged |

**No accidental scoring occurred during remediation.** ✅

---

## 19. P4 / R-07 RETENTION

| Property | Result |
|---|---|
| P4 | ### **COMPLETE**, 14/14 PASS |
| R-07 | ### **CONTAINED** — `phase-0-baseline-manifest.yaml` **byte-unchanged** |
| Production `GateRegistry` | ### **EMPTY** — zero constructions across `src/` + `scripts/` |
| Phase-8 deferral | **INTACT** — `DEFERRED_BY_DEPENDENCY - REQUIRED AT PHASE 8` present |
| Production writes | ### **DARK** — `src/`, `scripts/`, `configs/`, `data/`, `docs/architecture/` byte-identical |
| Action Class registration | **none** |
| External-effect containment | **no regression** — boundary and adapters byte-identical |

**No historical P4 finding is reopened; no P4/R-07 surface changed.**

---

## 20. VALIDATION — REPRODUCED INDEPENDENTLY

Run in my **own** disposable `--no-local` clone at `1ae365a` (tree verified `0e52a61c…`), fresh venv,
canonical dependency install (`pip install -e ".[dev]"`), canonical config `pytest-canonical.ini`,
`PYTEST_ADDOPTS` cleared.

### Canonical suite

```
2101 passed, 1 skipped, 0 failed   (403s)
collected 2102 = 2101 + 1          — no hidden deselection
```

### **Exactly reproduces the builder's claim.** ✅

### Clean-clone gate — run independently by this session

```
clean-clone gate: committed 1ae365aee
--- clone committed state (exit 0)          --- no active_workspace in clone: OK
--- python floor (host) (exit 0)            --- fresh venv (exit 0)
--- python floor (venv) (exit 0)            --- install declared deps only (exit 0)
--- complete canonical suite (clean clone) (exit 0)
    clean-clone: {'passed': 2101, 'failed': 0, 'skipped': 1, 'collected': 2102}
--- control guards (clean clone) (exit 0)
--- AC-SAFE-012 / AC-SAFE-013 / AC-SEC-001 (exit 0)

CLEAN-CLONE GATE: PASS
```

### **PASS. Every exit status 0. The dependency environment is canonical (`pip install -e ".[dev]"`,
### fresh venv, `PYTEST_ADDOPTS` cleared, `-c pytest-canonical.ini`).** ✅

> **Disclosure, matching the builder's:** the gate ran inside a disposable clone, so its
> `GATE-RESULT.json` landed there. `docs/implementation/GATE-RESULT.json` and `SUITE-RESULT.json` in
> the product repository remain **byte-unchanged** and still bind `a31a94a`.

### TEST-NODE-MANIFEST

| Check | Result |
|---|---|
| `node_count == len(node_ids) == len(set(node_ids))` | ### **2102 / 2102 / 2102** — zero duplicates |
| vs `38b4bda` | ### **2091 → 2102 · +11 added · 0 removed** ✅ |
| vs `6e8127d` | 2073 → 2102 · +29 · 0 removed |
| Added nodes | exactly the 11 the builder listed, all in the G2 block |
| Tests deleted | ### **NONE** — zero `-def test` lines in the diff |
| Guards weakened | **No.** The six removed `assert` lines are the retired G2 assertions (`status == "COUNT_NEEDS_ADJUDICATION"`, the naming-split counts), each replaced by a stronger successor |
| One skip justified | ✅ `test_the_red_by_design_cases_are_strict_xfails`, the approved skip; unchanged |

### New hostile nodes exercise the real relation logic

Confirmed: every new node calls `_consumes_relationship_errors` — **the same predicate the live corpus
is judged by** — via `_consumes_context` overlays, not a private copy. Each asserts its failure
*reason* by substring and carries a positive control. **The nodes are genuine.** Their limitation is
coverage (§8 #14), not vacuity.

---

## 21. BUILDER-DISCLOSED JUDGMENT CALLS — FLAGGED, NOT DECIDED

### A. Strict payload coverage, no derivability escape

> ### **Classification: CONSERVATIVE BUT VALID — and a GOVERNANCE AMBIGUITY for the adjudicator.**

Strictly narrower than the adjudicated 4(d) permission, so within authority. Rejects **no** current
row. It does **not** compensate for R-01/R-02, because 4(d) never engages for the state-only consumers
where the contract is weakest — a point the builder's framing ("stronger than the minimum necessary")
obscures. **The adjudicator should rule** whether the derivability escape must be restored for future
rows and, if so, what structured derivation authority carries it. **This review invents none.**

### B. No per-branch owner proof on `PL-15`

> ### **Classification: ACCEPTABLE BUT RESIDUAL.**

The builder's factual premise is **verified correct** (`CM-5` targets `COMPLETED`; a `DELEGATES_TO`-style
rule would reject it). `PL-15`'s branch discriminator is carried by `RealityEstablished{outcome}`, which
is in the §5 payload. **Not a missing safety invariant.** Recorded; the adjudicator may confirm.

### C. `PL-10u` owner-set breadth

`OutcomeUnknown`'s declared owner set (`EF-3u`/`EF-4c`/`EF-4u`) is broader than the single causal path.
The contract is satisfied for **all three** — verified — so no member is admitted on a weaker basis.
Narrowing §3's producer list is a producer-map change outside this unit. **Correct restraint.**

---

## 22. TOPOLOGY / PRESERVATION — FINAL STATE

| Field | Value |
|---|---|
| HEAD | `1ae365aee76d89ebdc78bbb619a4db8b778a1cad` |
| Tree | `0e52a61c6bef77df42610fa8ea9d142092b4f021` |
| Branch | `p5/u5-1-g2-spec-correction` |
| Parent | `6e8127dab02e3443183d06825836f5a805f53de0` — single, not a merge |
| Descendant of `38b4bda` | ### **NO** |
| Commits above `6e8127d` | ### **1** |
| Commits above the candidate | ### **0** — no finalizer commit |
| Index digest | `ba83298a04abd2bdb2496470ec0d6d6a4560e0daa6df47fda0a86a9f5a2a5e73` |
| Worktree-status digest | `2babbc0cce82e8374d038244574325e32d9bc7e9e2f208f57ee0293a1bf9cac0` |
| Total refs | **72** (67 + the five preservation refs) |
| `p4/adapter-containment-completion` | `6e8127d` — **unmoved** |
| `main` / `origin/main` | both `152574e4…` — unmoved |
| `refs/preserve/p5-u51-prestate-6e8127d` | `e77ab673…` — **unchanged** |
| Remote `p5/` refs | ### **0 — nothing pushed** |
| Untracked set | exactly the two authorized F-04 artifacts |
| Reflog `@{0}` | the candidate commit — no later P5 unit begun |

**Measured after every read, parse, clone and mutation run. Identical to the pre-review measurement.**

---

## FINDINGS SUMMARY

| ID | Class | Severity | Blocking | Requirement | Narrow remediation / adjudication |
|---|---|---|---|---|---|
| ### **R-01** | ### **CONFIRMED DEFECT** | ### **HIGH** | ### **YES** | Adj. §2 4(a)/(c), §5 "same authorized semantic operation" | Bind 4(a) to the owner **ROW**; the state token is already present in all 20 declarations and is discarded |
| ### **R-02** | ### **CONFIRMED DEFECT** | ### **HIGH** | ### **YES** | Adj. §2 **rule 5** downgrade prohibition; §17 | Closed by R-01's binding; and/or 4(d) must account for a state-transition durable write |
| **R-03** | non-blocking residual | LOW | No | 4(d) soundness for XOR alternatives | Per-event rather than union coverage, or record as accepted |
| **R-04** | non-blocking residual / governance ambiguity | MEDIUM-LOW | No | Adj. §8 "bind meaning structurally" | Adjudicator: is the stated objective owed beyond the specified lexical remedy? |
| **R-05** | non-blocking residual | LOW | No | F-02 carve-out breadth | Narrow the historical carve-out phrase list |
| **R-06** | governance ambiguity | — | No | Adj. §2 4(d) derivability escape (judgment call A) | Adjudicator ruling; no new concept invented here |
| **R-07** | non-blocking residual | LOW | No | `PL-15` per-branch owner (judgment call B) | Confirm the restraint |
| **R-08** | non-blocking residual | INFORMATIONAL | No | Zero-write rows accept any `CONSUMES` | Correct per rules 3/4; same treatment as `RU-3` |
| **R-09** | evidence deficiency | LOW | No | The builder's F-07 swap node tests only the pair where 4(d) bites (§8 #14) | Add the state-only pair as a hostile node alongside R-01's fix |
| **R-10** | test-environment limitation | INFORMATIONAL | No | F-04 primary-worktree artifact | **None owed by U5.1** — inherited, identical at both refs |
| **R-11** | evidence deficiency | LOW | No | Two Product Driver handoffs lack `.sha256` sidecars | Generate sidecars |

### Adjudicated findings — disposition as verified

| ID | Adjudicated | This review's independent finding |
|---|---|---|
| **F-01** | UPHELD, HIGH, BLOCKING | ### **PARTIALLY REMEDIATED.** Architecture correct; both `AP-9` exploits closed; ### **the invariant does not generalize — R-01, R-02** |
| **F-02** | UPHELD, narrowed, in scope | ### **REMEDIATED** (R-05 residual) |
| **F-03** | UPHELD as reported | ### **REMEDIATED as specified** (R-04 residual, governance-attributable) |
| **F-04** | CONFIRMED, informational | ### **CONFIRMED inherited** — nothing touched |
| **F-05** | UPHELD, does not prevent U5.1 | ### **PRESERVED** — `AP-9` correctly `EVENT_REQUIRED`, fail-closed |
| **F-06** | UPHELD, forbidden surface | ### **NOT TOUCHED** — byte-identical |
| **F-07** | UPHELD, HIGH, merged into F-01 | ### **PARTIALLY REMEDIATED** — 9 real hostile nodes with positive controls, but the swap node selects the one pair where 4(d) bites (§8 #14) |
| **New** — `PL-15x`/`IB-5x` | MEDIUM | ### **REMEDIATED** ✅ |
| **New** — §182 citation | LOW | ### **REMEDIATED** ✅ — corrected to `state-machines/registry.md`:182 |

---

## VERDICT

> ### **REJECT — TARGETED REMEDIATION REQUIRED**

**Against the clean-ACCEPT criteria:**

| Criterion | Result |
|---|---|
| F-01 / F-07 mechanically closed | ### **NO** — R-01, R-02 |
| Both `AP-9` exploits fail for the intended relationship reason | ### **YES** ✅ |
| All nine consumers structurally valid | **YES** as declared ✅ — but four are not *bound* by the guard |
| Six non-producers valid | ### **YES** ✅ |
| Exact 110 / 9 / 6 / 2 / 7 membership | ### **YES** ✅ — independently derived by set identity |
| No event-registry change | ### **YES** ✅ — byte-unchanged, total 98 |
| Acceptance contract intact | ### **YES** ✅ — 14 · Σ100 · verbatim ordered · all PENDING |
| Canonical suite and clean-clone gate passing | ### **YES** ✅ — 2102 / 2101 / 0 / 1 reproduced |
| No unauthorized architecture introduced | ### **YES** ✅ |

**Eight of nine hold. The one that fails is the one the replacement exists to fix, and it fails for a
reason that is narrow, mechanical, and fixable without founder or architect authority — the
owner-identifying datum is already written into every co-commit declaration in the corpus and is
simply not read.**

**This is not a rejection of the architecture, the classification work, the `PL-15x`/`IB-5x`
reclassification, the `NON_PRODUCING` or `DELEGATES_TO` proofs, the F-02/F-03 remediations, the
acceptance-contract instantiation, or the preservation discipline — all of which I independently
verify as correct and should be carried forward unchanged.**

**Unchanged and still binding:** no event was minted · the canonical total stays **98** · `AP-9` stays
`EVENT_REQUIRED` under its fail-closed default · the seven founder/architect obligations remain
**OPEN** · **G2 is still NOT fully discharged** · P5's event content stays blocked · P4 **COMPLETE**
and R-07 **CONTAINED** retained · production `GateRegistry` **EMPTY** · nothing pushed · no finalizer
authorized.

---

## PROOF THE PRODUCT REPOSITORY WAS NOT CHANGED

Measured **after** every read, parse, clone, suite run, gate run and mutation run — byte-identical to
the pre-review measurement in §B:

| Field | Value |
|---|---|
| HEAD | `1ae365aee76d89ebdc78bbb619a4db8b778a1cad` |
| Tree | `0e52a61c6bef77df42610fa8ea9d142092b4f021` |
| Branch | `p5/u5-1-g2-spec-correction` |
| Parent | `6e8127dab02e3443183d06825836f5a805f53de0` |
| Index digest | `ba83298a04abd2bdb2496470ec0d6d6a4560e0daa6df47fda0a86a9f5a2a5e73` |
| Worktree-status digest | `2babbc0cce82e8374d038244574325e32d9bc7e9e2f208f57ee0293a1bf9cac0` |
| Total refs | `72` — unchanged; **this session created none** |
| `p4/adapter-containment-completion` | `6e8127d` — unmoved |
| `main` / `origin/main` | both `152574e4…` — unmoved |
| `refs/preserve/p5-u51-prestate-6e8127d` | `e77ab673…` — unchanged |
| Commits above `6e8127d` | **1** |
| Commits above the candidate | **0** |
| Remote `p5/` refs | **0** |
| Untracked set | exactly the two authorized F-04 artifacts |
| ### F-04 report | ### **`shasum -c` → OK.** Neither deleted, modified nor committed |

**Not done by this session:** no product commit · no amend · no ref creation, deletion or move · no
`checkout`, `reset`, `restore`, `stash`, `clean`, `rebase`, `merge`, `gc` or `prune` in the product
repository · no push, deploy or effect-enabling action · no `finalize_status.py` and no other finalizer
· no remediation · no modification of the candidate · no adjudication · no event minting · no change to
the frozen 98 · no new canonical event name · no second P5 unit · no `driver.config.yaml` or Product
Driver configuration modification · no Desktop-repository modification · no P4/R-07 reopening · the
untracked third-finalization report was neither deleted nor modified.

**Writes performed, in full:** this report and its `.sha256` sidecar (non-product Product Driver
handoff storage, uncommitted); and disposable clones, tree copies and a venv in the session scratchpad,
outside both repositories, containing all mutation testing.

---

**END OF FRESH INDEPENDENT REVIEW**

**Candidate `1ae365aee76d89ebdc78bbb619a4db8b778a1cad` · tree `0e52a61c6bef77df42610fa8ea9d142092b4f021` ·
parent `6e8127dab02e3443183d06825836f5a805f53de0` · branch `p5/u5-1-g2-spec-correction`.**
**Rejected predecessor `38b4bda6cb3ea6c5e5c9a302fd64d23450e6fc62` verified preserved, unmodified, and
attributable only to itself.**

### **VERDICT: REJECT — TARGETED REMEDIATION REQUIRED.**

**`CONSUMES` no longer self-certifies for `AP-9`, and both adjudicated exploits fail closed. But it
still does not bind a consumer to an owner ROW, and 4(d) is vacuous for state-only durable writes — so
a false relationship survives at constant totals AND constant membership, and an open
`HIGHEST GOVERNANCE` obligation is still launderable with one token.**

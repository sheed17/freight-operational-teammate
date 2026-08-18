> # ⛔ HISTORICAL REVIEW — NOT CURRENT AUTHORITY
> **Preserved as received; the body below this banner is byte-identical to the artifact on
> `refs/preserve/p6-cp2-independent-review-1aaf943` (commit `06ab01f7`, blob
> `424f7bf5224d535767c7e4dfbc3da0d7b2000e70`, sha256
> `1bcd37d5ab38438fb792cedffdffb8db02abcbb18ea471d997a7685f88f2fdb0`).** This is evidence of a past
> moment, not status. It is an INDEPENDENT REVIEW, **not** an adjudication: it set no acceptance
> criterion, marked no phase complete, closed no risk and authorized no finalization. It reviewed the
> P6-CP-2 candidate at content commit `1aaf9439e89fe291572fdd8307e2e65221b09d51` (tree
> `1d859547798c632fd42445a15b2663ce87399dcc`) and returned
> **ACCEPT FOR SEPARATE TARGETED ADJUDICATION**.
>
> ### **IT DID NOT REVIEW THE COMMIT THAT CARRIES IT.** The landing commit that brought this file
> in-tree did not exist when this was written. Nothing here may be cited as an independent review of
> that commit. The separate targeted adjudication that followed it is
> [`p6-cp2-targeted-readjudication-report-1aaf943.md`](p6-cp2-targeted-readjudication-report-1aaf943.md).
>
> ### **TWO OF ITS OWN FINDINGS DID NOT SURVIVE ADJUDICATION, AND THAT IS RECORDED HERE RATHER THAN
> EDITED OUT OF THE BODY.** The re-adjudication **OVERTURNED IN PART** finding **R-3** — the landing
> gate *does* check that a cited review report exists, in
> `test_roadmap_completeness_control.py`, which this review did not probe — and **UPHELD R-4** by
> re-performing the adjudication against this report. The body below is unedited; read it with those
> two rulings in hand.

# P6-CP-2 — FRESH TARGETED INDEPENDENT REVIEW — candidate `1aaf943`

> ### **VERDICT: ACCEPT FOR SEPARATE TARGETED ADJUDICATION.**
> Machine **M2 — the Pipeline Instance**. Candidate content commit `1aaf9439e89f`, tree
> `1d859547798c`, parent `cc986dd`. The two blocking defects that rejected predecessor `3d4046a`
> are **CLOSED**, and I proved that by reproducing each defect on the rejected tree with probes I
> wrote myself before running the same probes against the candidate.
> ### **SEVEN NONBLOCKING FINDINGS ARE RECORDED BELOW, TWO OF THEM NEW AND MATERIAL.** None can
> produce a wrong customer outcome or violate an invariant on this tree. **This is a review, not an
> adjudication, and not a landing.** No P6 criterion is scored, the finalizer was not run, M3 was
> not begun, and no product implementation was modified.

| | |
|---|---|
| **Reviewer lineage** | A session that neither implemented nor remediated this candidate, and authored none of `3d4046a`, `8bb4cb0` or `1aaf943`. |
| **Independence discipline** | Every load-bearing claim re-derived with probes written here. The prior **targeted adjudication** of `1aaf943` (preserved at `refs/preserve/p6-cp2-targeted-adjudication-1aaf943`) was **NOT read** before forming these conclusions — see finding **R-4**, which concerns only its existence and ordering. |
| **Tree state** | Working tree verified **byte-identical to `HEAD`** by per-file blob hash after every mutation. `git checkout/restore/stash/clean` was never used to undo a mutation. |

---

## 1. What a broker can now do that they could not before

M1 answered *"what work exists and who is accountable for it."* M2 answers **what Neyma is DOING
about it, durably** — and the capability is one a dispatcher can name:

**Load 4471 is delivered and billable. The billing sweep proposes the invoice, proposes it again
milliseconds later, and again at a different price after the rate moves. The broker receives one
invoice.** I drove this myself, including with eight genuinely concurrent connections racing the
same logical effect: **one attempt persisted, seven refused** (probe **R-CONC**).

And the harder half: **when the TMS write times out, nobody may try again.** The attempt lands in
`NEEDS_VERIFICATION`, which is non-terminal, so it keeps holding the Layer-1 reservation — a new
proposal for that effect cannot start, and **no timer moves it** (probe **R-PROD** C1–C3, D1).
"We cannot say whether the invoice went out" stays an open obligation with a named human rather
than decaying into "it failed" and being paid twice.

---

## 2. F-01 — `CLAIMED` reachable without the CAS: **CLOSED**

### 2.1 I reproduced the defect first, on the rejected tree

Probe **R-F01** (mine) builds a contract-valid canonical `GrantClaimed` — producer taken from the
contract, aggregate version taken from `inbox_aggregate_cursor` so the inbox **applies** rather than
parks it — and consumes it through the public API against an attempt carried to `GRANTED` through
the real kernel.

On `refs/preserve/p6-cp2-rejected-candidate-3d4046a` (tree `34cc2285`):

```
FAIL  1. attempt did NOT reach CLAIMED via the bus   [state=CLAIMED]
PASS  2. claimed_at is still NULL                    [claimed_at=None]
PASS  3. grant ledger still reads GRANTED            [state='GRANTED']
PASS  5b. the inbox APPLIED the event                [ConsumeOutcome.APPLIED]
FAIL  7. the refusal left a security record          [security=[]]
```

**The attempt said the authority to bill the customer had been claimed; the ledger said nobody had
claimed it, and `claimed_at` was NULL.** One authorization that could be spent twice. The defect is
real and my probe detects it.

> **Disclosure of my own probe error.** My first envelope used `producer_transition_id="EF-4"` and a
> guessed aggregate version; the inbox returned `REJECTED_MALFORMED` and every downstream assertion
> passed **vacuously**. A malformed attack that bounces off the transport is not a proof of safety.
> I corrected the envelope and added assertion **5b** — *the inbox APPLIED the event* — so the probe
> can never again report "safe" when it means "the attack never landed."

### 2.2 The same probe on the candidate

```
PASS  1. attempt did NOT reach CLAIMED via the bus   [state=GRANTED]
PASS  3. grant ledger still reads GRANTED
PASS  5b. the inbox APPLIED the event                [ConsumeOutcome.APPLIED]
PASS  6. redelivery is a byte-identical no-op        [DUPLICATE_NOOP]
PASS  7. the refusal left a security record          [IllegalTransitionAttempted]
refusal_kind='ILLEGAL'
```

The attack lands, is refused, **converges** (receipt written — no poison loop), and is **recorded**
to the audit backbone and `security_events`.

### 2.3 I did not accept the closure on one path — probe **R-KERNEL**

The claim is *structural*, so I attacked the structure:

| Attack | Result |
|---|---|
| **A** consumed `CHECKPOINT_RUN` at `CHECKPOINT` (PL-8/PL-8f) | stayed `CHECKPOINT`; **zero** witnesses, **zero** grants; `APPLIED`/`ILLEGAL`; redelivery `DUPLICATE_NOOP`, digest identical |
| **B** `apply(CLAIM_ATTEMPTED)` with a **forged** grant handle | `GuardNotSatisfied`; still `GRANTED`; `claimed_at` NULL; ledger `GRANTED` |
| **C** the **real** handle *(positive control)* | **DOES** reach `CLAIMED` with a real timestamp, ledger agrees `CLAIMED` — the refusals above are not vacuous |
| **C3** replaying that same handle | refused; still exactly one `CLAIMED` grant |
| **D** sweep of **every** derived kernel-owned row × from-state × trigger | `PL-8`, `PL-8f`, `PL-9` — all refused by the ordinary guard path at any facts; denominator asserted non-zero |
| **E** a fabricated stand-in kernel object | no `GRANTED`; no witness; no grant |
| **F** `CheckpointPassed(...)` constructed directly | `CheckpointError` — P3's witness is still unconstructable |

**The derivation is genuine.** `KERNEL_OWNED_ROW_IDS` computes to `{PL-8, PL-8f, PL-9}` from §7's
`consequential` seeds plus the `(from-state, trigger)` closure — `PL-8f` enters without being named,
which is exactly the property that makes a future consequential row covered before its guard is
written. `_guard_problem` refuses that population **before any row branch**, and `apply`'s dispatch
derives from the *same* declaration, so dispatch and refusal cannot disagree.

**P3 is untouched where it matters.** I extracted the claim CAS `UPDATE` from `cc986dd` and from
`1aaf943` and compared them: **byte-identical**, six predicates intact
(`tenant`, `grant_id`, `state`, `expires_at`, `brake_version`, `policy_version`).

---

## 3. F-02 — the "ships dark" guard was false-green: **CLOSED**

### 3.1 Verified two ways I wrote myself — probe **R-F02**

I did not re-run the candidate's walker. I wrote a **second, independent AST closure** (normalising
every import to a last-segment name set, so a spelling I failed to anticipate still surfaces) and a
**runtime closure** (import M2's recorded surface and ask `sys.modules`).

- M2's roots, taken from `IMPLEMENTATION-SURFACE.yaml`: `pipeline_instance`, `migrations.phase6_pipeline_instances`
- My AST closure: **24 modules**, **zero** effect-capable adapters reached
- Runtime closure: **24 modules**, **zero** reached
- **No production module imports `pipeline_instance` at all**

> **Disclosure of my own probe error.** My *runtime* positive control **FAILED** — importing
> `effect_boundary` pulled in no adapter, because the boundary imports them lazily inside functions.
> That is a limitation of my runtime method, not a defect in the candidate, and it means the runtime
> result alone proves nothing. My **AST** positive control passed (`browser_use_write`, `tms_write`),
> so the AST walk is the one I rely on.

### 3.2 Mutation — the decisive comparison (harness **M-F02**, mine)

I injected a **real** effect-capable adapter (`discovered_write.DiscoveredInvoiceLedger`) into M2's
own module in each legal spelling, plus one **transitive** leak two hops out, and asked each tree's
own dark-surface guard whether it noticed.

| Mutant | Candidate `1aaf943` | Rejected `3d4046a` |
|---|---|---|
| D1 `from freight_recon.x import Y` | **CAUGHT** | *missed* |
| D2 `import freight_recon.x` | **CAUGHT** | *missed* |
| D3 `from freight_recon import x` | **CAUGHT** | *missed* |
| D4 `from . import x` | **CAUGHT** | *missed* |
| D5 `from .x import Y` | **CAUGHT** | *missed* |
| D6 `importlib.import_module(...)` | **CAUGHT** | *missed* |
| D7 **transitive**, 2 hops out | **CAUGHT** | *missed* |
| | **7 / 7** | **0 / 7** |

Both trees green again after byte-for-byte restoration.

> **Disclosure of two errors in my own harness, and why the numbers above are the trustworthy ones.**
> My first version injected at line 1, **before** `from __future__ import annotations` — a
> `SyntaxError`, not a leak. Both trees then reported a false **7/7**: the guard went red for the
> wrong reason. My second version injected a symbol (`DiscoveredWriter`) that does not exist, so D1
> and D5 were `ImportError` collection failures rather than detections. Only after every mutant was
> **compiled** and used a **real** symbol did the true picture appear — the rejected guard catches
> **nothing at all**, because `discovered_write` was absent from its hand-written adapter list, so
> the walker's blindness was never even reached. **F-02 was worse than the original review reported.**

---

## 4. Evidence I re-executed, in full

| Check | Recorded | **Reproduced here** |
|---|---|---|
| Canonical suite | 20 env. failures disclosed | **3009 passed · 20 failed · 1 skipped** (413s) |
| The 20 failures | environmental, outside blast radius | **Confirmed** — 19 `test_action_callback` + 1 deployed-route, all `socket.bind` `PermissionError`; **all 20 fail identically on the parent `cc986dd`**, which predates M2 |
| M2 battery | 158/158 | **158 passed** |
| Regression set | 528/528 | **509 + 19 = 528 passed** (M1 · P5 transport · P3 CAS · P3 matrix · P0 adapter imports · browser-use read-only · P0 baseline manifest · import gate) |
| Mutation battery | 55/55 caught | **55/55 caught**, tree byte-identical after |
| `TEST-NODE-MANIFEST` | 3011 → 3030, zero removed | **Exact set identity**: +19 vs rejected, **+160 / −0** vs parent; and **3030 manifest nodes == 3030 collected nodes**, zero drift either way; 3009+20+1 = 3030 reconciles |
| Product Driver canonical | 70/70 | **70 behaviours as specified, 0 wrong** |
| Product Driver bypass scenes | 17/17 | **17 behaviours as specified, 0 wrong**, live positive control included |
| Bypass probe able to fail | 3/3 mutants | **3/3** non-zero exit, restored, green again |
| Clean-clone gate | fails on TLS to pypi.org | **Reproduced** — `SSLCertVerificationError` fetching `hatchling`; fails at *install declared deps only*, not on the tree |
| `AC-MACH-000` §14 bijection | 25 rows | **Re-parsed §14 myself: exact set equality, 25/25, 16 states** |

> **Disclosure — one contaminated run of mine, and how it was corrected.** Two mutation-battery
> instances of mine ran concurrently and interfered, producing a spurious **29/55** with
> `SETUP-FAIL` and one `RESTORE-RED`, and leaving two mutants in the working tree. I also, at that
> point, "verified" cleanliness with `git write-tree`, **which reads the index, not the working
> tree** — a false green of exactly the kind §9 exists to catch. I restored both files from their
> committed blobs with `git cat-file` (never `checkout`/`restore`/`stash`/`clean`), purged
> `__pycache__`, re-verified by **per-file blob hash**, and re-ran the battery **once**: **55/55**.
> The 55/55 is the result; the 29/55 was my own harness colliding with itself.

---

## 5. The six amended guards — was anything weakened?

| # | Amendment | Judgement |
|---|---|---|
| 1 | `_second_ledger_problems`: "carries `commit_key`+`state`" → "reserves a key **without** an FK into `effect_grants`" | **Defensible.** §14 PL-1 mandates that column pair on the pipeline. The predicate is structural, not a blessed-name list. Mutant **P11** proves it still fires. |
| 2 | null-gate allowlist gains `pipeline_instance.py` | **Paid for.** A new AST guard proves only `checkpoint.py` may **construct** `GateEntry`/`GateRegistry`, with a positive control that finds the kernel's own default first. Carrying a decision ≠ deciding one. |
| 3 | occurrence-key ban gains a `CANONICAL-ROW-READ:` exemption | **A real weakening — finding R-1 below.** |
| 4 | M1 dark-posture permits M2 as importer | **Net stronger** — it now additionally asserts M2 itself has zero importers, so "dark" is two hops deep. Docstring inaccuracy noted as **R-7**. |
| 5 | claim-CAS WHERE guard anchored on a name → **discovers** the function containing the `GRANTED→CLAIMED` write, exactly one | **Strictly stronger.** Fails on absence and on duplication. Mutant **P7a** proves it fires. |
| 6 | `test_u26bc` readiness compares before/after instead of an absolute | **Correct** — the absolute moved with every new canonical table. |

**Five of six are neutral-or-stronger. One is a genuine weakening, and I proved it by mutation.**

---

## 6. Findings

### R-1 — the occurrence-key annotation is an exploitable escape hatch · **MEDIUM · NONBLOCKING**

`test_no_free_form_occurrence_key_is_readable_from_the_request_payload` now exempts any
`params.get("occurrence_key")` with `CANONICAL-ROW-READ:` in a comment within ten lines above it.
Mutation **M-OCC** (mine), on the real tree:

```
O1  unannotated caller-authored payload read (P1's real defect)   -> CAUGHT (red)
O2  the SAME defect with the annotation comment pasted above it   -> NOT CAUGHT (green)
```

The shipped exemption itself is legitimate — one site, `_row_to_pipeline`, reading back the
occurrence this system derived and persisted at PL-1. But the guard asserts only that *some*
annotated site exists; it **pins no exact set**, which is what CLAUDE.md §8 requires
("membership, not counts — a same-count substitution must fail"). The accompanying "positive
control" re-implements the detector on a synthetic string rather than exercising the real guard, so
it would not have caught this.

**Why nonblocking:** no invariant is violated on this tree, and the escape hatch is opt-in,
self-naming and visible in review. **Recommendation:** pin the exact SET of annotated sites so a new
annotation must be added deliberately, and make the positive control a real-tree mutation.

### R-2 — PL-1b absorption does not survive genuine concurrency · **MEDIUM · NONBLOCKING · NEW**

Probe **R-CONC** (mine), eight threads on eight separate connections racing one logical effect,
against the identical seven duplicates proposed sequentially:

| | live attempts | `absorbed_count` | `DuplicateProposalAbsorbed` emitted |
|---|---|---|---|
| **sequential** 1 + 7 duplicates | 1 | **7** | **7** |
| **concurrent** 1 + 7 duplicates | 1 | **0** | **0** |

**The safety invariant holds in both** — one attempt, one effect, no double bill, and the seven
losers get a typed `ReservationHeld` whose message names the correct remedy. What does not hold is
the **record**: the registry describes PL-1b as absorbing a second proposal onto the running attempt,
and under contention the machine raises instead, so those duplicates appear in no operator count.
`propose()`'s `ReservationHeld` branch has **no test coverage** — the battery's two "racing" cases
are sequential on one connection, and the index constraint is exercised only via raw SQL.

**Why nonblocking:** M2 ships dark with no concurrent proposer today, and no money outcome changes.
**Recommendation:** record as debt (`P6-D14`) and resolve before M9's billing sweep — either by
retrying into the absorb path on `ReservationHeld`, or by stating in the canon that a raced duplicate
is a refusal rather than an absorption.

### R-3 — the landing gate never checks that the cited review report exists · **LOW · NONBLOCKING · PRE-EXISTING**

`test_status_reality.py` asserts `cp.get("independent_review_report")` is truthy while its own
failure message claims "an **on-disk** independent review report". Mutation **M-LAND** (mine):
repointing P6-CP-1's citation at `THIS-FILE-DOES-NOT-EXIST.md` leaves the guard **GREEN**.

Not introduced by M2 (`test_status_reality.py` is not among the candidate's changed files), but
directly material: **this is the exact assertion P6-CP-2's landing depends on.** Recommend an
existence check before the landing that cites this report.

### R-4 — a targeted adjudication of `1aaf943` exists and predates any independent review · **LOW · PROCESS**

`refs/preserve/p6-cp2-targeted-adjudication-1aaf943` was created before any
`refs/preserve/p6-cp2-independent-review-1aaf943` existed, inverting the required route
(*candidate → fresh independent review → separate adjudication → one finalizer*). I did **not** read
its findings. Its own commit message names the missing review artifact, so the gap is disclosed
rather than hidden. **The adjudicator should decide whether that adjudication must be re-performed
against this report** — an adjudication that could not have weighed the review it is supposed to
follow is not the separate third step the discipline describes.

### R-5 — "byte-identical" is imprecise · **LOW · ACCURACY**

The commit message says the replacement's tree is "byte-identical to the pre-collapse one — only the
topology changed." Three files differ from `refs/preserve/p6-cp2-remediation-prestate-8bb4cb0`:
`CURRENT.md`, `IMPLEMENTATION-REGISTRY.yaml`, and the implementation record (**+52 / −1, additive,
documentation only**). **No source or test file differs**, so the substantive claim holds.

### R-6 — the F-02 narrative overstates the population miss · **LOW · ACCURACY**

The evidence says the old hand-list was missing `discovered_write`, `browser_agent` and
`browser_tms_adapter`. Only `discovered_write` is a module of this repository; the other two exist
in the canonical `EFFECT_CAPABLE_ADAPTERS` set but **not on disk** (they are historical, deleted EP
paths). So exactly one real leak vector was missing from the old list — which, as §3.2 shows, was
already enough to defeat every spelling. The fix is correct regardless.

### R-7 — a docstring claims derivation where the set is typed out · **LOW · ACCURACY**

`test_nothing_in_production_calls_this_machine_yet` says "the permitted set is derived from the P6
modules on disk rather than typed out"; it is the literal `{"work_item.py", "pipeline_instance.py"}`,
guarded by an existence check. The guard is sound; the sentence is not. (The same function now
appends `path.name` rather than the repo-relative path, so two same-named modules in different
directories would be indistinguishable in its report.)

### Observation, not a finding

The bypass probe's mutant **M1** demonstrates failure via an uncaught `PayloadContractViolation`
(exit 1 by crash) rather than a scored wrong behaviour, unlike **M2**/**M3** which report
"16 as specified, 1 wrong". A genuine non-zero exit, but a weaker demonstration.

---

## 7. The three canonical seams — independently confirmed

| Debt | My verification | Verdict |
|---|---|---|
| **P6-D9** | §14 line 27 gives PL-8f `CheckpointFailed{step,reason}` **+ `PipelineVoided`**; `events/registry.md` §3 attributes `PipelineVoided` to `(PL-7v/9v)` and the contract's `producers` tuple is `('PL-7v','PL-9v')` | **REAL.** Emitting it from PL-8f is refused by the contract gate. The state still becomes `VOIDED`. Correctly not improvised across. |
| **P6-D11** | 8 of 25 rows are `CONSUMES`; they advance the version and emit nothing on `pipeline_instance`, a **strict-order** family whose inbox parks any version above `applied+1`. Measured by a dedicated test, not asserted | **REAL.** Nonblocking today — nothing consumes M2's F2 stream and M2 ships dark. **Must be resolved before an F2 consumer arrives in M3.** |
| **P6-D13** | `VerificationDeferred` has `producers=('PL-11d',)` while declaring `aggregate_type: effect_grant` — its ordering key needs the **grant's** version, which is M3's | **REAL.** PL-11d performs its durable write and does not emit. Guessing a version would misorder a strict stream permanently and silently. Correct call. |

All three are recorded rather than invented across, which is the behaviour §7's stop conditions
require.

---

## 8. What this candidate does NOT do — verified

- **`criteria_scored: []`** — no P6 acceptance criterion is scored, and none may be by this candidate
- **`landed_checkpoints` still names exactly one entry** (`P6-CP-1`); `checkpoint_state` unchanged
- **M2 ships dark** — zero production importers, closure reaches zero effect-capable adapters, production `GateRegistry` still EMPTY
- **R-07 remains CONTAINED** — the baseline-manifest change is purely additive (`pipeline_instances` added to the tenant-owned list); the containment record is untouched
- **No external effect is enabled**, no production policy gate registered, no autonomy granted

---

## 9. Probes, mutations and runs executed for this review

**Mine:** `R-F01` (kernel bypass, run on both trees) · `R-KERNEL` (A–F, 17 assertions, incl. the
real-CAS positive control) · `R-F02` (dual-method closure + positive control) · `M-F02` (7 mutants ×
2 trees) · `R-PROD` (double-billing, `NEEDS_VERIFICATION`, timers, tenants, terminal finality at
guard **and** database) · `R-CONC` (8-thread reservation race + OCC) · `R-SET` (§14 bijection
re-parsed from the specification) · `M-OCC` (annotation escape hatch) · `M-LAND` (landing-gate
existence check) · CAS WHERE-clause byte comparison across `cc986dd`/`1aaf943` · manifest set
difference across three commits · manifest-versus-collection exact set identity.

**Re-executed from the candidate:** canonical suite · M2 battery · seven regression batteries ·
the 55-mutant battery (clean single run) · the Product Driver canonical probe · the 17 bypass scenes
· `prove_probe_can_fail.py` · the clean-clone gate · the 20 disclosed failures replayed on the
parent commit.

**Every mutation used in-memory save/restore. `git checkout`, `git restore`, `git stash` and
`git clean` were never used to undo one. Restoration was verified by per-file blob hash, and the
working tree is byte-identical to `HEAD`.**

---

## 10. Verdict and remaining landing conditions

### **ACCEPT FOR SEPARATE TARGETED ADJUDICATION.**

F-01 and F-02 are closed structurally, not patched at a call site, and both closures are
mutation-proven in both directions. No blocking defect survived this review. The seven findings are
recorded, not actioned (CLAUDE.md §13.3); **R-1** and **R-2** are the two a reader should carry
forward.

**Still owed before `P6-CP-2` may land:**

1. A **separate targeted adjudication** by a session in neither the build nor this review lineage — and a ruling on **R-4**, whether the existing pre-review adjudication must be re-performed against this report
2. **Exactly one** canonical finalizer run, by none of the above
3. A reproduction of the **full-green canonical suite** and the **clean-clone gate** from a host that permits `socket.bind` and reaches pypi.org over untampered TLS — neither was reproducible here, and neither was papered over
4. Only then may `landed_checkpoints` gain a second entry citing this report

**Not owed, and must not happen:** no P6 criterion may be scored, P6 is not COMPLETE, M3 may not
begin, and this report does not land anything.

---

*Independent review performed by a session that neither implemented nor remediated this candidate.
It is a review, not an adjudication. Preserved at `refs/preserve/p6-cp2-independent-review-1aaf943`,
parented on `1aaf943`. The branch was not moved and nothing was pushed.*

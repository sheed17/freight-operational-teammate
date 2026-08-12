# P5 U5.2 — SEPARATE TARGETED ADJUDICATION of replacement candidate `a6005a81e234956bb837c0bdc9d3b6cd4febfc53`

Transcribed by the campaign controller from the adjudicator's return; it could not write files. It
built nothing, reviewed nothing, wrote no prior adjudication, remediated nothing. Every finding
reproduced with its own instruments before ruling. Primary worktree at finish: 0 lines dirty, HEAD
`a6005a81`, tree `9021fff2`. All mutation in throwaway clones under `/private/tmp/u52adj/`.

## VERDICT: UPHOLD REJECT — and the reviewer's remediation scope is INSUFFICIENT

R-01 is confirmed exactly. But the reviewer's own proposed fix does not close the route it names, and
the adjudicator found a **second CONSUMES laundering (N-02) that works today on the four rows R-01
cannot reach** — so the defect is **7 of 7, not 3 of 7**. Route-by-route patching is the wrong
remediation, and the chokepoint proposed in the adjudication brief is **refuted by corpus evidence**.
A different chokepoint exists and was proven.

## The deciding test, as a single fact

On a fully coordinated laundering, `_event_required_set_errors` returns **NONE**, `EVENT_REQUIRED`
computes to **`set()`**, and every general set-identity assertion passes — the only red assertions are
`len(owned) == 105`, `producer_transitions == … == 117`, three `105`-literals in
`test_phase0_acceptance_bijection.py`, and the seven-name `MINTED` dict. **Those are literals this
mint wrote for itself.** That is the `f01d942` condition verbatim, and it is now reachable by **two**
independent CONSUMES routes.

| run (pristine clones of `a6005a8`) | result |
|---|---|
| control, unlaundered | `4 failed, 2122 passed, 1 skipped in 393.58s` |
| CF-7 `CONSUMES:BrakeReleased`, Writes emptied (R-01) | `19 failed, 2105 passed, 3 skipped` |
| RU-8 bidirectionally forged co-commit (**N-02, NEW**) | `18 failed, 2106 passed, 3 skipped` |
| chokepoint installed, corpus unlaundered | `5 failed, 2119 passed, 3 skipped` |

## R-01 — CONFIRMED · BLOCKING · the reviewer is right in every particular

`_consumes_relationship_errors` lines 896–913: `durable = _durable_write(row, states)` then
`if not durable: continue`, with 4(d) also `if durable:`-guarded — so 4(b), 4(c), 5a-forward,
5a-reverse and 5d are all skipped and the function returns `[]`. Exactly the reviewer's three rows
(AP-9 `frozen=true`, CF-7 `append parties[]`, EC-7 `severity`), exactly its register values.

**The reviewer's decisive claim was verified specifically and holds: no general guard is red.**
Nineteen failures = four CLI clone artifacts byte-identical to the control's four, plus fifteen
literals. The one that could have been general is decisive in the reviewer's favour: the `117`
assertion sits inside `test_transition_event_audit_matches_the_specs`, whose **general** assertions —
`computed[NON_PRODUCING/DELEGATES_TO/CONSUMES] == audit keys`,
`computed[EVENT_REQUIRED] == audit members`,
`discharged_members == ADJUDICATED_EVENT_REQUIRED − computed[EVENT_REQUIRED]` — all **executed and
passed** before the literal fired.

**Why the prior negative battery missed it:** `_ap9(g2)` returns the **live** row with `Writes`
intact, so the hostile node asserts AP-9 cannot consume `BrakeReleased` *with the cell populated* —
precisely the case the launderer does not use. AP-9 is caught only by two AP-9-name-pinned nodes;
there is no CF-7 or EC-7 equivalent.

## N-02 — NEW, BLOCKING, and the reviewer explicitly did not test it

A **bidirectionally forged co-commit** passes `consumes_valid` **for every one of the seven**. Forge
both legs: the consumer's `Writes` becomes `` co-commit: M13 `RELEASED` `` (dropping field names so
4(d) has nothing to cover, while `durable` stays `True` on the state change), and the **owner** row
BR-4's own `Writes` gains `` ; co-commit: M<n> `<STATE>` ``. End-to-end on RU-8 — a row R-01 cannot
reach — `_event_required_set_errors: NONE`, `EVENT_REQUIRED: set()`, `18 failed / 2106 passed`, all
of it clone artifacts and literals. The guard's own comment calls 5a REVERSE *"the leg a candidate
row cannot author for itself."* True of the row; **false of the edit**, which authors both rows.

**The reviewer's proposed remediation does not close its own finding.** Simulating it exactly
(`_durable_write` forced `True` for adjudicated members, so rule 3's short-circuit is unavailable and
5a–5d are proven in full), against the bidirectional forge: AP-9, PO-3, PL-7a, PO-2, RU-8 all
**ACCEPTED**; CF-7 and EC-7 refused only on an accident of their own row text (they name no canonical
To state), and writing `` `{RAISED,OPEN}` → `OPEN` `` into CF-7's cell makes both **ACCEPTED** too.
Under the reviewer's own remediation, **all seven launder**.

## Is there a FOURTH route? — YES

Complete enumeration of `_discharge_route_errors`, as shipped:

```
R1 MINTED honest: CF-7/ConflictPartyAttached                              ACCEPTED
R1 MINTED LAUNDERED: CF-7 re-attributed to ConflictOpened (§3 edit)       ACCEPTED
R2 CONSUMES (R-01): CF-7 Writes emptied, CONSUMES:BrakeReleased           ACCEPTED
R2 CONSUMES BIDIRECTIONAL FORGE: RU-8 + BR-4's own cell forged            ACCEPTED
R3 NON_PRODUCING (N-01): CF-7 Writes emptied                              refused
R4 DELEGATES_TO (R-02): AP-9 Trig widened to S|H, GRANTED=AP-2            ACCEPTED
R5 structural route with class PRODUCER (no branch)                       refused
R6 UNKNOWN route string 'FOUNDER_WAIVER'                                  refused by the caller
```

**Four of six substantive paths accept a false discharge.** R1 is the fourth route:
`MINTED_CANONICAL_EVENT` re-proves itself entirely from §3 — a specification surface the discharging
edit authors. The cross-machine guard only fires when producers span machines;
`ConflictOpened`(CF-2/CF-7) is same-machine and passes.

**On the reviewer's "no residual" for same-machine re-attribution: the conclusion is right, half the
reasoning is rejected.** An authorization list *is* the only faithful mechanization of "founder
minted this fact" — a route whose premise is an authorization cannot have a predicate. But the
reviewer missed that **the authorization does not live in the route**: `MINTED` sits in
`test_p5_canonical_event_mint.py`, enforced only by a record-comparison node in another file, while
`_discharge_route_errors` admits any (row, event) pair §3 corroborates. That is the F-03 shape. Not
independently blocking today; **must be folded into the chokepoint.**

## RULING ON THE CENTRAL QUESTION

### The proposed chokepoint is refuted

Resolving the authoritative `durable_write` from the register once and passing it into every route
predicate **closes R-01**, **fails N-02** (7/7 accepted), **is inert against R-02** (delegation takes
no `durable_write` input; R-02 turns on the `Trig` cell), and **is inert against the MINTED
re-attribution**. **1 of 4.** The reason is structural: `durable_write` is one datum, and the defect
is not about that datum — it is about **who authored the evidence**.

### Route-by-route is also wrong

Four candidates, four routes, one defect. The prior adjudication's generalization — *"a discharge may
never be admitted on a re-reading of a cell the discharging edit is itself permitted to change"* —
applied honestly to this corpus has a stark consequence: **every input to every structural route
predicate is such a cell.** The row's `Writes`, `Trig` and `From→To`; the owner row's `Writes`; §3.
There is no structural discharge of an adjudicated member that is not self-certifying, because the
adjudication itself is the only fact the edit cannot author. Patching route *n* guarantees route
*n+1* — and *n+1* and *n+2* were both found while reproducing the review.

### The chokepoint that works

Placed **once**, at the top of `_discharge_route_errors`, keyed on `key in
ADJUDICATED_EVENT_REQUIRED`, **before any route predicate runs**, and **default-deny**:

- `PRE_EXISTING_STRUCTURAL_PROOF` (all three sub-routes) is **structurally unavailable** to an
  adjudicated member — the generalization of N-01 the candidate applied to `NON_PRODUCING` alone;
- `MINTED_CANONICAL_EVENT` additionally requires `(key, event)` in a **guard-resident founder-
  authorization table**, which the §3 checks then corroborate rather than replace;
- anything else refuses.

```
[CHOKEPOINT] R1 MINTED honest                                    ACCEPTED
[CHOKEPOINT] R1 MINTED LAUNDERED (re-attributed)                 refused
[CHOKEPOINT] R2 CONSUMES (R-01)                                  refused
[CHOKEPOINT] R2 CONSUMES BIDIRECTIONAL FORGE (N-02)              refused
[CHOKEPOINT] R3 NON_PRODUCING (N-01)                             refused
[CHOKEPOINT] R4 DELEGATES_TO (R-02)                              refused
[CHOKEPOINT] R5 structural route with class PRODUCER             refused
```

**Corpus evidence — zero false rejects.** Installed in a pristine clone, whole canonical suite:
`5 failed, 2119 passed, 3 skipped` against the control's `4 failed, 2122 passed, 1 skipped`. The one
extra failure is **not** a false reject: `test_hostile_an_open_obligation_may_not_annex_another_rows_
co_commit_declaration` asserts a **substring** (`"does not hold"`) of the old refusal message; the
node still refuses, with the new N-01-generalised wording. Totals reconcile
(`2119 + 5 + 3 = 2127 = 2122 + 4 + 1`). Not one legitimate discharge is refused: **all seven are
route `MINTED_CANONICAL_EVENT`, and the audit itself records "NOT ONE of these is a
`PRE_EXISTING_STRUCTURAL_PROOF`. That route remains available and unused."**

### What stops a fifth route

Default-deny keyed on the adjudicated set, evaluated **before** dispatch. For a member of
`ADJUDICATED_EVENT_REQUIRED` the admissible-discharge set becomes a finite explicit whitelist of
(row, event) pairs and **no predicate is consulted at all** — so a sub-route added to
`PRE_EXISTING_STRUCTURAL_PROOF` next year is unreachable for those rows by construction, and a new
top-level route string is refused by `DISCHARGE_ROUTES` in the caller. A future obligation joining the
frozen set inherits default-deny automatically. That is the property the present arrangement lacks:
today's `MINTED` literal has zero force over an eighth obligation; the chokepoint's has force over all
of them.

## Remaining findings

**R-02 — CONFIRMED · NONBLOCKING · agrees with the reviewer, on precedent not on comfort.** With
`Trig` widened, admitted goes 51 → 53; sweep property (1) exact-set RED and property (2) no
adj7-sourced admit RED. Property (2) is keyed on `ADJUDICATED_EVENT_REQUIRED`, the governance anchor
the U5.1 re-adjudication mandated. **This is the `d59b740` case exactly** — there
`_event_required_set_errors` also returned `[]` and the candidate was ACCEPTED because a general
invariant refused anyway. Nonblocking by direct precedent; record as a residual; the chokepoint closes
it as a side effect.

**R-03 — CONFIRMED exactly · NONBLOCKING · NOT the same class as F-04 · mandatory in scope.** Real
figures by conjunct deletion from the real function: both **51**/0 adj7; trigger deleted **96**/2;
same-machine deleted **157**/9/106 cross-machine; both deleted **235**/13. The tree states
`250/167/102/53` at `:397-400` (the prior adjudication's re-implementation figures presented as
measurements of this predicate), `53` at `:406` and `:488`, and has the two labels **transposed** at
`:617-618` and `:2212`. **Genuinely different from F-04**: F-04's assertion was *vacuous* — the guard
proved nothing while its docstring claimed a proof. Here every executable assertion is correct and
load-bearing; the pin holds the true 51 and the sweep asserts it exactly both ways. A wrong comment
beside a right assertion is a documentation defect; a vacuous assertion beside a docstring claiming a
proof is a false guard. **Disagrees with the reviewer's "merely documentary" framing** — the
transposition is a live false statement about the predicate's behaviour, in the guard that holds it —
but agrees with the disposition.

**R-04 — CONFIRMED exactly · NONBLOCKING.** `G2-D11`, `G2-D12`, `G2-D13` and `G2-D14` are all already
taken; `G2-D15`/`G2-D16` return zero hits repository-wide. No guard mechanically reads the `G2-D`
namespace, so there is no false green — but two closed defects and two open residuals now share ids in
an audit trail whose entire purpose is traceability.

**R-05 — CONFIRMED, and worse than the reviewer said · NONBLOCKING as a record defect.**
`authorized_discharge_routes` is false in **both** clauses: the `NON_PRODUCING` advertisement is
unavailable (N-01) and unsatisfiable (the register requires a canonical `discharging_event` it cannot
supply); the `CONSUMES` clause — *"rules 1,2,3,5a-5d and 7 in full, with the 5a REVERSE leg
row-bound"* — is false of the implementation twice over (R-01 skips 5a–5d; N-02 forges the REVERSE
leg). The record states the correct rule and the implementation does not implement it.

**R-06 — CONFIRMED · NONBLOCKING.** Five premise assertions at `:2122-2128` plus `:2143`, `:2147`,
`:2467-2469`, `:2479-2483`. Any fires on an edit to AP-9, PL-7a or PL-7b and would be counted in a
mutation log as "a guard caught it."

## Did the reviewer over- or under-reject?

**UNDER-rejected**, in one material way and one scope-determining way: it missed N-02, and its stated
remediation would have shipped a candidate where all seven rows launder. **No over-rejection
anywhere** — every "what held" claim was re-cut and is true: N-01 closed against four bypasses
(including register shadowing); all thirteen adj7 routes refused with both conjuncts load-bearing; the
pinned 51 correct in both directions; item (4)'s `monkeypatch.setattr` real with a took-effect
assertion and a genuine `ast.parse(inspect.getsource(...))` scan; item (5) real
(`_consequential_events` finds exactly one list line, 21 names including `PolicyApproved`); topology
truthful with all cited preserve refs at the stated hashes. *One small correction*: PO-2's `IB-1` and
`IB-3` are refused on **trigger**, not machine — no change to the count or conclusion.

## Remediation scope (minimal, ordered)

1. **The chokepoint, and nothing route-shaped.** One default-deny block at the top of
   `_discharge_route_errors`, keyed on `key in ADJUDICATED_EVENT_REQUIRED`, evaluated before
   dispatch. **Do NOT** patch `_consumes_relationship_errors`, `_resolve_delegation` or
   `_durable_write` for this — leave them as the general corpus predicates they are.
2. Update the one hostile node's message assertion (`:2779`, `"does not hold"`), and add a hostile
   node per adjudicated member asserting each of the four launderings is refused — **including CF-7
   and EC-7, which have no name-pinned node today**.
3. **R-03**: correct `:397-400` to `235 / 157 / 96 / 51`, `:406` and `:488` to 51, un-transpose
   `:617-618` and `:2212`.
4. **R-04**: rename the two new residuals to `G2-D15`/`G2-D16` in the audit, the registry,
   `BUILD-STATUS.yaml:46` and `CURRENT.md:546`.
5. **R-05**: correct `authorized_discharge_routes` to state what the chokepoint implements; record
   the NON_PRODUCING inconsistency as a closed note, not a live claim.
6. **R-06**: mark the premise assertions as premises in place, and exclude them from any
   `remediated: N failed` count in the commit record.
7. **R-02** recorded as a residual (delegation remains a necessary-conditions filter for
   non-adjudicated rows).

## Must NOT be reopened

The mint (seven names, schemas, §3/§5/family contracts, the seven reclassified rows with `Writes`
preserved); counts 105 and 117/9/6/2/0 = 134 and digest `1485bd6f0f6dd02b`; R2-A (fully discharged);
R4-A; the direction of R3-B; **N-01's `NON_PRODUCING` bar and its register-authority defence in
depth**; the trigger + same-machine conjuncts of `_resolve_delegation` and the pinned 51; the corpus
sweep; `_consequential_events`; ER-16, D2's EMIT, PO-1's `PolicyProposed`; `src/`,
`PROGRAM-WEIGHTS.yaml`, the R-07 record, P4 COMPLETE, the Phase-8 deferral, P5's
`READY / NOT_STARTED / NO_CHECKPOINT` with all 14 criteria PENDING.

## Topology — Option A, unchanged

The replacement's **sole parent is `eda3a6d`** — a sibling of both `f01d942` and `a6005a8`, never a
descendant of either. `a6005a8` is preserved permanently and unmodified.

## What the adjudicator did NOT verify

The builder's 17-mutation log — not one entry reconstructed; N-02 and the MINTED re-attribution were
established as uncovered classes, which bears on the log's completeness claim without auditing it.
The primary-worktree suite was not re-run; the control is the clone measurement
`4 failed / 2122 passed / 1 skipped`, total 2127, consistent with the manifest claim, which was also
not recomputed. `finalize_status.py` / `clean_clone_gate.py` not run, so no clean-clone measurement
exists from it. **The chokepoint proven is a PROBE, not a remediation** — it demonstrates the
property; final wording, placement and hostile-node coverage are the builder's. The CONSUMES relation
matrix beyond `BrakeReleased` was not swept; the carried `PL-11c → OutcomeUnknown` residual not
re-cut; whether the bidirectional forge admits owner events other than `BrakeReleased` not tested. The
seven minted payloads and family contracts — upheld twice, byte-identical, not re-derived.
`PROGRAM-WEIGHTS.yaml` content, documents outside `docs/`/`eval/`/`src/`, and the downstream reach of
the `G2-D` collision beyond six located sites. No runtime behaviour (none exists).

## CONTROLLER'S INDEPENDENT REPRODUCTION

Confirmed the chokepoint's zero-false-reject property is structural, not merely measured: all seven
recorded discharges at `TRANSITION-EVENT-AUDIT.yaml:527-533` carry
`route: MINTED_CANONICAL_EVENT`, and `PRE_EXISTING_STRUCTURAL_PROOF` occurs only twice in the file,
both in route-definition prose, with the audit's own comment at `:782` recording that the route
"remains available and unused."

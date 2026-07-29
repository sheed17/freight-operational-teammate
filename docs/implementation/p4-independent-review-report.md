# P4 — INDEPENDENT HOSTILE REVIEW REPORT

**Status: REJECT — REMEDIATION REQUIRED**

Reviewer: independent session. Did not implement, remediate or finalize this unit.
Review date: 2026-07-28.

> This report is an independent-review **source artifact**. It is not an adjudication, does not
> mark P4 complete, does not mark R-07 contained, and does not instantiate weighted acceptance.

---

## A. Exact artifact verified

Every hash below was verified directly from the object store, not from the handoff.

| Property | Expected (handoff) | Verified | Result |
|---|---|---|---|
| Content commit | `95cf5af7d9ea` | `95cf5af7d9eae19cba5ab2f0a745ef3c04858962` | MATCH |
| Tree | `4b3dda2019` | `4b3dda20194a1f7de790a12912316a1cef25e819` | MATCH |
| Parent | `f1e8e1893eff…` | `f1e8e1893eff2460d68f3f168f18fd29635b250d` | MATCH |

Lineage: `95cf5af` → `f1e8e18` (certified parent boundary) → `3d23173`. The candidate is a **direct
child** of the certified parent, so the entire P4 unit — P4-CP-1 and P4-CP-2 — is a single diff of
**38 files** (+6835 / −823).

**Protected refs — all intact, none moved:**

| Ref | Value |
|---|---|
| `refs/preserve/ep1-pre-amend` | `9a9d9c4a646dc5d06856219e4f5254498c3fc9d1` |
| `refs/preserve/ep1-pre-finalizer-lock` | `545bd111701560692fc6fb5ec9bed6d53421597c` |
| `refs/preserve/ep1-wip` | `509976a79383f6f91c26f1b51c23494f508402e2` |
| `archive/p4/content-72512b90` | `72512b9093461673e947a7118e0738cd91411c24` |
| `archive/p4/content-2a53746c` | `2a53746c7689fa48ca2f479ff875edf9d39c0d12` |

Reflog shows the amend chain `72512b9 → 8e2d0dc → 52172e1 → 0a5f0cc → 95cf5af`. Intermediate amends
`8e2d0dc`, `52172e1`, `0a5f0cc` are reachable only via reflog and are not covered by a preservation
ref. Recorded as an observation, not a finding — they are superseded WIP, and the two archived
identities plus the certified parent pair are intact.

---

## B. Review environment and independence statement

- Reviewed from a **disposable non-local clone** at
  `…/scratchpad/p4-review`, checked out **detached** at `95cf5af7d9eae19cba5ab2f0a745ef3c04858962`.
- Clone verified `git status --porcelain` **empty** at start, after the full suite, and after the
  50-mutant battery (tree still `4b3dda2019` — byte-exact restore independently confirmed).
- **The primary product worktree was not altered** to construct the review environment. It was read
  only. No commit, amend, reset, rebase, cherry-pick, merge, ref update or push was performed.
- `finalize_status.py` was **not run**. No effect was enabled, no external system contacted.
- No finalizer or builder owns the primary worktree: the flock at
  `.git/neyma-finalizer.lock` is 0-byte and **unheld** (`current_owner()` → `None`); no
  `finalize_status` / `clean_clone_gate` / `mutate_phase4_boundary` process is running.
- The primary worktree carries two uncommitted, finalizer-owned files (`CURRENT.md`,
  `GATE-RESULT.json`) — intentionally awaiting finalization. They were read, never written.
- Prior P4-CP-1 review claims were **not relied upon**. The full unit was re-reviewed from source.

---

## C. Full changed-surface inventory (38 files)

**New source (5):** `cdp_readonly.py` (1111), `browser_use_write.py` (430), `governed_approval.py`
(403), `freight_operations.py` (196), plus `scripts/finalizer_lock.py` (188) and
`scripts/verify_readonly_cdp.py` (206).

**Modified source (5):** `browser_use_adapter.py`, `cdp_actuator.py`, `effect_boundary.py` (+136),
`operation_proposal.py`, `system_orientation.py`.

**Entry points (4):** `run_action_callback_server.py` (−205 net), `orient_tms.py`,
`propose_ar_from_tms.py`, `finalize_status.py`.

**Probes/manifests (3):** `import_probe.py`, `entrypoint_probe.py`, `manifest.py`.

**Tests (12):** 5 new (`test_p4_governed_invoice_write.py`, `test_governed_approval_binding.py`,
`test_cdp_readonly_navigation.py`, `test_cdp_readonly_surface.py`,
`test_browser_use_readonly_surface.py`), 7 modified.

**Evidence/docs (5):** `EFFECT-PATH-INVENTORY.yaml`, `IMPLEMENTATION-SURFACE.yaml`,
`LEGACY-DISPOSITION.md`, `TEST-NODE-MANIFEST.json`, `phase-0-baseline-manifest.yaml`.

**Mutation battery:** `mutate_phase4_boundary.py` (+279 → 50 cases).

Review was **not** limited to the handoff's named files; the whole diff was walked.

---

## D. P4-CP-1 independent review (re-run, not inherited)

CP-1's surface — the containment boundary, the boundary-aware import gate, the EP-6/7/9/10 delete
cutover, F1/F4, the `brain_runtime` cut and the detective sweep — was re-verified as it exists in
the candidate.

- **Boundary algorithm** (`effect_boundary.execute_effect`, lines 393–500) implements the full
  ADR-004 §3.7 order: claim CAS → `EffectAttempted` recorded **before** the call → single-use
  capability minted only at step 7 → outcome classification. Verified by reading, not by docstring.
- **F4 holds:** a generic post-attempt exception is `UNKNOWN_OUTCOME`, never `FAILED`
  (lines 481–483). `AdapterPreflightRejected` is the **only** path to `FAILED`, and only on proven
  non-occurrence.
- **Cross-tenant refusal before any claim** (lines 429–436) engages the global brake.
- **Gate:** live violation set is **empty**; live and recorded agree exactly, both-sided.
- CP-1 mutants B1–B21 are inside the 50/50 battery I re-ran (all CAUGHT).

No CP-1 defect found. CP-1 is sound as it stands in this candidate.

---

## E. P4-CP-2 independent review (first independent review of this surface)

### EP-1 — governed callback and invoice-write path

The **write cut is real**. `run_action_callback_server.py` imports no effect-capable adapter; the
`CdpActuator`/`CdpBrowserSession`/`OperationRouter`/`OperatorAgent` construction site is **deleted,
not disabled**; `operation_router = None` is unconditional (line 134) with no reassignment; and
`--enable-operation-router` now wires only `ReadOnlyCdpNavigator` readers. Confirmed by AST and by
grep across `src/` and `scripts/`.

**Dark state confirmed.** `execute_invoice_write`, `build_invoice_write_operation`,
`verify_governed_approval` and `record_governed_decision` have **no production caller** — only
tests. `SandboxInvoiceWriteAdapter` refuses non-sandbox targets, refuses non-loopback base URLs, and
refuses to run at all with no injected runner.

**But the chain is not joined — see F-01.**

### EP-3 — TMS proposal navigation and provenance binding

Substantively repaired. Provenance is a value object with no authority; `follow()` re-derives the
authorized record from the live page, demands exact equality, enforces observation-context
freshness, fetches the browser-resolved URL, and re-checks the landed URL after navigation.

### EP-8 / EP-14 — read/write separation

Structural, not conventional. `ReadOnlyCdpObserver`/`ReadOnlyCdpNavigator` carry **no** forbidden
primitive (`evaluate`, `command`, `set_file_input`, `navigate`, `click`, `type`, `select`,
`upload_file`), use `__slots__` (no `__dict__` escape) and a name-mangled private channel. `orient_tms.py`
dropped `--start-url`/`--record-url` because the observer *cannot* navigate or click — an honest
capability loss, with the deep walk retained behind the boundary rather than deleted.
`browser_use_adapter` has no write method and takes a vetted task **ID** plus data, never a
caller-authored task string.

### Finalizer mutual exclusion

Correct and hostile-tested (see F). Acquired in `main()` around the entire `finalize()` call, before
any suite run, receipt deletion or status write; loser exits `2` having modified nothing.

---

## F. Hostile tests and results

All executed in the disposable clone.

### Canonical suite — reproduced exactly
```
1867 passed, 1 skipped, 1868 collected  (394.30s)
```
Matches the claimed clean-clone gate exactly. The action-callback socket tests **passed in this
environment** — the handoff's sandbox loopback limitation did not apply here, and no socket
coverage was removed or weakened.

### Mutation battery — reproduced exactly
```
50/50 mutants caught
```
No MISS, no SETUP-FAIL, no RESTORE-RED. Harness verified sound: in-memory originals, anchor
uniqueness check, guard-green precondition, `__pycache__` purge, byte-for-byte restore assertion.
Clone tree still `4b3dda2019` afterward.

### Finalizer lock — 6/6 hostile probes PASS

| Probe | Result |
|---|---|
| Two concurrent invocations | PASS — second refused immediately |
| Differing `TMPDIR` | PASS — lock identity is the git **common dir**, not TMPDIR |
| Descriptive owner record | PASS — descriptive only, never decides |
| Lock released after owner exit | PASS |
| `SIGKILL`ed owner (crash) | PASS — kernel released, no stale wedge |
| Forged dead-PID record | PASS — forging the JSON does not release the flock |

No timeout heuristic, no PID-liveness reclaim, no log-presence inference — the exact failure mode
that produced the original double-finalizer is structurally impossible.

### EP-3 provenance — 10 adversarial link cases

| # | Case | Result |
|---|---|---|
| A | Destructive `/loads/L-101/delete`, link text == load id | **REFUSED** |
| B | `data-method="delete"` on a benign detail URL | **REFUSED** |
| C | Substring lookalike `L-10` vs `/loads/L-104` | **REFUSED** |
| D | Novel destructive verb `/loads/L-101/terminate` | **SELECTED** → F-06 |
| D2 | Novel destructive verb `/loads/L-101/wipe` | **SELECTED** → F-06 |
| E | `<base>` makes benign attr resolve to a delete route | **REFUSED** |
| F | `?_method=delete` override | **REFUSED** |
| G | `javascript:` scheme | **REFUSED** |
| H | Cross-origin `https://attacker.example/loads/L-101` | **SELECTED** → F-02 |
| I | Two different identity-bound documents | **REFUSED** (ambiguity) |

**The previously-reported failure class — matching invoice/load text selecting a destructive
delete/purge route — is genuinely fixed** (cases A, B, E, F, G).

### Typed-operation boundary
`build_invoice_write_operation` and `execute_invoice_write` both enforce
`isinstance(op, InvoiceWriteOperation)`. `InvoiceWriteOperation` has no field for a task, selector,
URL, JavaScript, adapter method or browser command; `operation_class` is a closed enum;
`approved_fields` keys are allowlisted. Structured smuggling is bounded but not zero — see F-08.

### False-green resistance
Both probes carry explicit population tests. `require_population()` hard-fails on an empty
`sources_inspected` and on any `unmatched` row **even after** `declare_empty_is_legitimate()` — I
verified this in `evaluation.py` (only the *count* checks are bypassed), so the gate's comment that
"sources_inspected + unmatched checks still apply" is **accurate**. The empty violation set is
anchored positively by `len(candidates) >= 8` and `len(sources_inspected) > 100`, both of which hold.
The repaired EP-1 tests assert positive facts (`run_callback_server` constructed; `action_callback`
imported) **before** their negative authority assertions — so a degenerate parse fails closed.

### Concurrency / idempotency / UNKNOWN_OUTCOME
Verified by reading the boundary plus the CP-2 test bodies: duplicate execution on one grant yields
one effect; two workers racing yield exactly one write; interruption before claim resumes without
double-writing; interruption after claim cannot blind-duplicate; lost acknowledgement becomes
`UNKNOWN_OUTCOME`, never `FAILED` and never an automatic retry. These are genuinely exercised
against a real kernel, store and CAS — the writer is faked (necessarily, the capability is dark),
but the governance machinery is real.

---

## G. Evidence consistency review

| Check | Result |
|---|---|
| Clean-clone counts reproducible | **PASS** — 1867/0/1/1868 reproduced independently |
| Mutation 50/50 reproducible | **PASS** |
| Mutation restoration byte-exact | **PASS** — verified independently post-run |
| `TEST-NODE-MANIFEST.json` matches collection | **PASS** — 1868 vs 1868, **identical by identity**, zero symmetric difference |
| Detection count 13 mechanically justified | **PASS** — live probe returns exactly 13 import sites |
| Live vs recorded violation sets identical and empty | **PASS** — both empty, both-sided |
| No premature P4 COMPLETE / R-07 CONTAINED claim | **PASS** — `CURRENT.md` (committed *and* uncommitted) states "NOT COMPLETE" and "OPEN — NOT CONTAINED"; manifest defers the claim to adjudication |
| `GATE-RESULT.json` binds to `95cf5af` / `4b3dda2019` | **FAIL for the committed artifact** — see F-04 |
| No generated evidence refers to an older candidate | **FAIL** — see F-04 |

**Hash bindings.** The uncommitted `GATE-RESULT.json` declares `node_manifest_sha256 =
24c0e9b6…`, which equals the `manifest_sha256` field inside the candidate's
`TEST-NODE-MANIFEST.json`, with `node_count` 1868. That binding is internally consistent and
correct. The **committed** `GATE-RESULT.json` declares `c0cf5504…`, which matches neither.

---

## H. Findings, ordered by severity

---

### F-01 — The EP-1 governed chain is two disconnected halves; the required chain cannot be proven
**Severity: HIGH · Confirmed defect (unproven containment claim) · Blocks R-07 containment**

**Affected requirement:** Hostile obligation 1 — prove the reachable chain *authenticated decision →
Work Item/revision → policy → checkpoint → witness → Effect Grant → atomic claim → typed
AdapterOperation → adapter → readback → outcome*; "reject a wrapper-only containment result."

**Files:**
- `src/freight_recon/governed_approval.py:354–391` (`build_checkpoint_approval`)
- `src/freight_recon/governed_approval.py:340–348` (`GovernedWriteIntentQueued`)
- `eval/tests/test_p4_governed_invoice_write.py:144–169`
- `eval/tests/phase3_kit.py:137–162` (`make_approval`)

**Failing invariant.** `build_checkpoint_approval` is the **only** function that maps a
`GovernedApproval` onto the checkpoint kernel's `ApprovalRecord` — i.e. the single join between the
decision half and the execution half. It has **zero callers anywhere**: not in `src/`, not in
`scripts/`, not in `eval/`. Independently, `GovernedWriteIntentQueued` — the event the module calls
"advancing the governed pipeline" — has **no consumer**; it is written and only read back by test
assertions.

**Proof.**
```
$ grep -rn "build_checkpoint_approval" src scripts eval --include="*.py"
src/freight_recon/governed_approval.py:354:def build_checkpoint_approval(      # definition only
```
In `test_the_governed_route_executes_the_full_order_and_verifies`, the `GovernedApproval` is
constructed with `approval_id="appr-9"`, `actor_id="U-OWNER"`. The grant that is actually claimed
and executed is minted by `_mint()` from `phase3_kit.make_approval`, which **hardcodes**
`approval_id="ap-1"`, `actor_id="owner:rasheed"`. The `decision` object is never passed to
`execute_invoice_write`. The two halves share **no identifier, no actor and no fingerprint**.

**Consequence.** The chain required by obligation 1 does not exist as code and is not proven
anywhere. What exists is (a) a decision recorder terminating in an unconsumed log event, and (b) an
execution path authorized by an unrelated `ApprovalRecord`. The test named
`…executes_the_full_order…`, whose docstring claims "approval → checkpoint → witness → grant → claim
→ … → closure", creates the appearance of an end-to-end chain by performing both halves against one
store; the "approval" in that ordering is a test fixture, not the governed approval constructed
three lines above it. An adjudicator reading the test name would materially over-read the evidence.

This is **consistent with the unit's own stated scope** (dark, no production caller, live write at
P12) and therefore is *not* by itself a P4 scope violation. It is nonetheless fatal to any claim
that the governed chain has been demonstrated, and must be closed before R-07 can be called
contained.

**Narrowly scoped remediation.** Either (a) introduce and test the join — derive the checkpoint
`ApprovalRecord` from the `GovernedApproval` via `build_checkpoint_approval`, and mint the grant
from that record, so `appr-9` is the identity that authorizes the executed grant; or (b) if the join
is deliberately deferred to P12, rename the test and correct its docstring to state that the two
halves are proven **independently and are not yet joined**, and record the unjoined seam explicitly
in `EFFECT-PATH-INVENTORY.yaml` as an open R-07 gap. Do not leave the current name/docstring.

---

### F-02 — Navigation origin filter fails OPEN by default; cross-origin links are provenance-selectable
**Severity: HIGH · Confirmed defect · Blocks R-07 containment**

**Affected requirement:** Hostile obligation 7 — navigation targets "same-origin where required";
obligation 8 — read consumers structurally contained.

**Files:**
- `src/freight_recon/browser_session_health.py:138–139` (`url_matches_filter`)
- `src/freight_recon/cdp_readonly.py:912–927` (`navigation_target_is_allowed`)
- `src/freight_recon/cdp_readonly.py:794–868` (`select_load_detail_link`)
- `scripts/run_action_callback_server.py:75` (`--operation-url-filter` default `""`)

**Reachable path.** `url_matches_filter` returns `True` when `url_filter` is falsy. The navigator's
constructor defaults `url_filter=None`, and the callback server's
`--operation-url-filter` defaults to `os.getenv("NEYMA_OPERATION_URL_FILTER", "")`, which is then
passed as `args.operation_url_filter or None`. Independently, `select_load_detail_link` applies
**no origin test** — a cross-origin href that is otherwise well-shaped is accepted as
provenance-bound.

**Proof.**
```
url_filter=None  target=https://attacker.example/loads/L-101 -> ALLOWED  "on the TMS domain allowlist"
url_filter=''    target=https://attacker.example/loads/L-101 -> ALLOWED  "on the TMS domain allowlist"
```
and case H above: `https://attacker.example/loads/L-101` with text `L-101` is **SELECTED** as a
"provenance-bound load-detail link".

**Consequence.** Running `--enable-operation-router` without `--operation-url-filter` — a documented,
supported invocation — gives the navigator no origin restriction. A hostile or compromised TMS page
that publishes one row link to an attacker origin can steer the **authenticated** browser session
off-origin, and `follow()`'s post-navigation re-check uses the same fail-open filter. The refusal
string is additionally **false**: it reports "on the TMS domain allowlist" when no allowlist exists.
This is read-only (no write is reachable), so it does not breach write containment, but it defeats
the origin property obligation 7 requires.

Note the fail-open primitive is pre-existing (`browser_session_health.py` is untouched by this
commit); **P4 widened its consequence** by adding a page-directed `follow()` capability that consumes
it.

**Narrowly scoped remediation.** Make the origin decision fail **closed**: require a non-empty
`url_filter` to construct a `ReadOnlyCdpNavigator` (or refuse navigation when none is configured),
and add a same-origin check between the observation document and the selected link in
`select_load_detail_link`. Correct the refusal/allow reason string so it cannot claim an allowlist
that is not configured.

---

### F-03 — `ReadOnlyBrowserUseRunner` does not validate `base_url`, contradicting its stated barrier
**Severity: MEDIUM · Confirmed defect · Does not block P4; blocks the EP-14 claim as written**

**Affected requirement:** Obligation 5 (typed boundary), obligation 8 (structural read/write split).

**Files:** `src/freight_recon/browser_use_adapter.py:21–26` (claim),
`:136–151` (`render_vetted_task`), `:182–207` (`run_vetted`).

**Failing invariant.** The module header states `ReadOnlyBrowserUseRunner` "accepts a TASK ID … and
validates the data (`load_id` against `LOAD_ID_RE`, **the base URL against the domain allowlist**)."
`render_vetted_task` validates **only** `load_id`. `run_vetted` passes `base_url` straight through
and defaults `allowed_domains=list(allowed_domains or [])` — an **empty** list when omitted.

**Proof.**
```
render_vetted_task("read_tms_load", base_url="https://evil.example.com/x", load_id="LD-560002")
  -> "Open https://evil.example.com/x/loads/LD-560002.html."
```
No test asserts runner-level `base_url` validation; only `BrowserUseTmsAdapter.__init__` validates,
and only its own config.

**Consequence.** A caller reaching the runner directly can point the browser agent at an arbitrary
origin. The documented mechanism does not exist. Reachability is low (the adapter is the normal
route), but a stated barrier that is absent is exactly the "read-only by naming" defect EP-14 exists
to eliminate.

**Narrowly scoped remediation.** Validate `base_url` against the domain allowlist inside
`render_vetted_task` (or `run_vetted`), fail closed when `allowed_domains` is empty, and add a test
that asserts refusal — or delete the claim from the docstring.

---

### F-04 — All generated evidence committed in the reviewed tree binds to a stale candidate
**Severity: MEDIUM · Evidence deficiency · Blocks adjudication on the committed artifact**

**Affected requirement:** Obligation 13 — "GATE-RESULT.json names the exact candidate commit and
tree"; "no generated evidence refers to an older candidate such as 8e2d0dc, 72512b9 or 3d231731."

**Files (all in the candidate tree):**
- `docs/implementation/GATE-RESULT.json:8,55`
- `docs/implementation/SUITE-RESULT.json:4,23`
- `docs/implementation/CURRENT.md:26,27`
- `docs/implementation/BUILD-STATUS.yaml:11,12`
- `docs/implementation/IMPLEMENTATION-REGISTRY.yaml:49,50`

**Proof.** Every one names `commit 3d231731b8b0984b3decded34177907f8d3898d1` / `tree
50cd012079cb48eaaf59e8e5e5406270ba5bd154` — the **explicitly flagged stale candidate**. The committed
`GATE-RESULT.json` is byte-identical to the parent's (`shasum` equal) and records the superseded
counts `1630/0/1/1631` and `node_manifest_sha256 c0cf5504…`, which does not match the candidate's
manifest (`24c0e9b6…`).

The correctly-bound gate result — `commit 95cf5af7…`, `tree 4b3dda2019…`, counts `1867/0/1/1868`,
`node_manifest_sha256 24c0e9b6…` — exists **only as an uncommitted working-tree file** in the primary
worktree, i.e. **outside the artifact under review**.

**Consequence.** The handoff's claim that "GATE-RESULT.json reportedly binds exactly to commit
95cf5af7 and tree 4b3dda2019" is true of a file that is not part of the reviewed commit and false of
the one that is. An adjudicator reading the content commit sees evidence for `3d231731`. This is a
consequence of the design in which the finalizer owns and rebinds these artifacts and has not yet
run — it is not fabrication — but it must be discharged before adjudication, and the adjudicator must
not read the committed evidence as describing this candidate.

Additionally, the uncommitted `CURRENT.md` — though substantially rewritten (+160 lines) to describe
this session's F2/EP-8/EP-3/EP-14 work — **still carries `content_commit: 3d231731`**, so even the
staged copy is not self-consistent.

**Narrowly scoped remediation.** Finalization (by an authorized session, not this reviewer) must
rebind all five artifacts to `95cf5af7…` / `4b3dda2019…` and re-record counts and manifest hash.
No code change is required.

---

### F-05 — Mutant B34's label does not match the mutation it performs
**Severity: MEDIUM · Evidence deficiency · Does not block P4**

**Affected requirement:** Obligation 9 (false-green resistance) and the EP-14 reclassification
argument.

**File:** `scripts/mutate_phase4_boundary.py:393–398`.

**Failing invariant.** B34 is labelled *"the probe is weakened instead of the architecture —
**browser_use_adapter** is declared non-effect-capable while nothing about the module changed."* The
mutation it actually applies removes **`cdp_actuator`**:
```
anchor:  '    "cdp_actuator", "browser_tms_adapter",'
mutant:  '    "browser_tms_adapter",  # MUTANT: cdp_actuator quietly reclassified out'
```

**Consequence.** The single mutant advertised as guarding the exact reclassification this commit
performs — moving `browser_use_adapter` out of `EFFECT_CAPABLE_ADAPTERS` — tests a **different
symbol**. It is a real and passing mutant, but it is not evidence for the claim its label makes.

This matters because the reclassification is otherwise **self-authorized**: `browser_use_adapter`
was removed from the probe set *and* from the "frozen" `phase-0-baseline-manifest.yaml` in the **same
commit**. `manifest.frozen_effect_capable_adapters()` is documented as the non-circular authority,
but a guard comparing two sets edited in lockstep can only detect *disagreement*, never a
coordinated edit.

**In fairness:** the reclassification is **substantively defensible** on my independent reading —
`browser_use_adapter` genuinely has no write method, imports no effect-capable adapter, and takes a
vetted task ID plus data. And the *destination* half of the argument is **verified true**:
`browser_use_write` was already present in the **parent's** frozen inventory (`f1e8e189`, line 561),
so the "reserved slot" claim is correct and non-circular. The defect is in the evidence for the
*removal*, not in the removal itself.

**Narrowly scoped remediation.** Correct B34's label to name `cdp_actuator`, and add a mutant that
actually exercises the `browser_use_adapter` reclassification — e.g. restore a write method or a
`browser_use_write` import to `browser_use_adapter` and assert the read-only surface tests fail.

---

### F-06 — Route-family test is a denylist; novel destructive verbs are selectable
**Severity: LOW–MEDIUM · Non-blocking residual risk**

**File:** `src/freight_recon/cdp_readonly.py:620–632` (`ACTION_ROUTE_TOKENS`), `:704–745`.

**Proof.** Cases D/D2: `/loads/L-101/terminate` and `/loads/L-101/wipe` with link text `L-101` are
both **SELECTED** as observational. Neither verb is in the vocabulary; `terminate`, `wipe`, `expire`,
`flush`, `reset`, `clear`, `unlink`, `detach` and `rm` are all absent.

**Consequence.** A destructive route using a verb the vocabulary never heard of passes the route
test. Bounded by the other three barriers (identity binding, anchor shape, ambiguity refusal) and by
the fact that the anchor's visible text must equal the load id exactly — an unusual shape for a
destructive control. Residual, not reachable in any concrete case I could construct against a
realistic page.

**Narrowly scoped remediation.** Either state explicitly in the module that the route family is a
denylist and record the residual, or invert to a positive allowlist of observational route shapes.

---

### F-07 — Numeric self-contradictions in the authoritative narrative
**Severity: LOW · Evidence deficiency**

**Files:** `src/freight_recon/browser_use_write.py:28`;
`docs/implementation/phase-0-baseline-manifest.yaml:535–548`.

**Proof.** `browser_use_write.py:28` states "Detection edges are unchanged at **14**." The manifest
states "`violation_edges` is **UNCHANGED at 1**" and "the detection total therefore grows by exactly
one authorized boundary edge (**14 → 15**)". The **actual verified state** is **13** detection sites
and **0** violations.

**Consequence.** The manifest signals layering ("EP-14 AS IMPLEMENTED … superseding the prediction
above"), so some of this is intentional history. But the numbers are left contradicting the recorded
final state in the same file, and `browser_use_write.py:28` carries no such supersession marker. An
adjudicator checking counts against prose will find three different answers.

**Narrowly scoped remediation.** Reconcile the counts to 13/0 or mark the superseded paragraphs
explicitly as historical predictions.

---

### F-08 — Approved-field **values** are unconstrained and interpolated into an LLM task
**Severity: LOW · Non-blocking residual risk (contained by darkness)**

**Files:** `src/freight_recon/freight_operations.py:71–73,127–133`;
`src/freight_recon/browser_use_write.py:410–430`.

**Failing invariant.** `APPROVED_FIELD_KEYS` allowlists **keys only**; values are arbitrary strings
with no validation. `_render_invoice_write_task` interpolates `amount`, `customer`, `load_id`,
`invoice_ref` and `base_url` directly into a natural-language task handed to a browser agent.

**Consequence.** The module claims "there is nowhere to put executable behaviour". For a
deterministic adapter that is true; for an **LLM-interpreted** task string it is weaker — a crafted
`customer` value is prompt-injection surface. Contained today by three independent facts: no runner
is wired (dark), non-sandbox is refused, and `allowed_domains` is pinned to loopback. Reachable only
at P12 when a runner is injected.

**Narrowly scoped remediation.** Constrain approved-field **values** (charset/length) at
construction, and record the LLM-task interpretation surface as a P12 precondition.

---

### F-09 — Bounded writer is duck-typed; typed enforcement lives only at the boundary
**Severity: LOW · Non-blocking residual risk**

**File:** `src/freight_recon/browser_use_write.py:376–407`.

`SandboxInvoiceWriteAdapter.write(self, op: object)` reads `sandbox`, `base_url`, `approved_fields`,
`load_id`, `invoice_ref` via `getattr`. A direct importer can pass any duck-type and bypass
`InvoiceWriteOperation.__post_init__` validation (including the `approved_fields` key allowlist).
Contained on the governed route — `build_invoice_write_operation` and `execute_invoice_write` both
enforce `isinstance` — so this is defense-in-depth only. Separately, `_refuse_if_not_dark` skips the
loopback check entirely when `base_url` is empty (`if base_url and not …`).

**Remediation.** Enforce `isinstance(op, InvoiceWriteOperation)` in the adapter too, and treat an
empty `base_url` as a refusal.

---

### F-10 — Context binding is conditional on the caller supplying expectations
**Severity: LOW · Non-blocking residual risk**

**File:** `src/freight_recon/governed_approval.py:246–249`.

`expected_workspace_id` and `expected_message_ts` are checked **only** when the caller passes a
non-empty value (`if expected_workspace_id and not _eq(...)`). A caller passing `""` silently skips
the workspace and Slack-message-receipt bindings. Channel binding is unconditional. Comparisons use
`_eq` (case-insensitive, whitespace-stripped) for tenant/work-item/capability; `payload_hash` uses
`hmac.compare_digest` correctly.

No production caller exists, so no policy is currently wrong — but the default shape permits a future
caller to under-bind. **Remediation:** require both expectations (or an explicit opt-out) rather than
inferring intent from an empty string.

---

### Explicitly checked, NOT defective

- **Test-environment limitations:** none. Socket-bound action-callback tests passed here; no
  coverage was deleted or weakened to obtain green.
- `require_population()` after `declare_empty_is_legitimate()` — I suspected it was decorative; it is
  **not**. `sources_inspected` and `unmatched` checks still fire. The gate's comment is accurate.
- Legacy `_build_live_operation_router` factory — genuinely **deleted**, not disabled. No dynamic
  import, `importlib`, `__import__`, `eval`/`exec` or monkeypatch seam reaches an actuator from any
  entry point (`scripts/mutate_phase4_boundary.py` contains such strings only as *mutant payloads*).
- `action_callback.py` retains `OperationRouter` plumbing, but every execution branch is gated on
  `config.operation_router is not None`, and the callback server passes `None` unconditionally.
- No status artifact prematurely claims P4 COMPLETE or R-07 CONTAINED — verified in both the
  committed and uncommitted `CURRENT.md`, `BUILD-STATUS.yaml` and the manifest, which explicitly
  records the claim as "PENDING" adjudication.

---

## I. Verdict

# REJECT — REMEDIATION REQUIRED

This is a **strong, substantially honest unit**. The independently reproduced evidence is real: the
canonical suite (1867/1/1868), the 50/50 mutation battery with byte-exact restoration, the
identity-exact node manifest, the empty-and-anchored violation surface, the detection count of 13,
and 6/6 finalizer-lock hostile probes all hold under independent execution. The EP-1 write cut is
genuine, the EP-8/EP-14 read/write split is structural rather than conventional, the dark state is
real, and the previously-reported EP-3 destructive-link failure class is properly fixed. The unit
does not overclaim its own status: it explicitly records R-07 as OPEN and P4 as NOT COMPLETE.

It is nonetheless rejected, on two grounds:

1. **F-01** — the central obligation of this review was to prove the reachable chain from an
   authenticated decision through to outcome. That chain **does not exist as code**. Its sole join
   point has zero callers, its pipeline-advance event has no consumer, and the test that appears to
   demonstrate it authorizes the executed grant with an unrelated test-fixture approval. Under the
   instruction to reject a wrapper-only containment result, this cannot be accepted as proven.
2. **F-02** — a confirmed, reachable fail-open origin control in newly added P4 navigation code,
   which allows an authenticated browser session to be steered cross-origin by a page-published link
   under a documented invocation.

Both require **code** remediation, not merely evidence remediation, which is why this is not a
conditional acceptance. F-04 additionally requires evidence remediation (finalizer rebinding) before
any adjudication can read the committed artifact as describing this candidate.

**Neither F-01 nor F-02 is a fabrication or a false green.** F-01 is an honest architectural seam
that the unit's own documentation partly acknowledges ("ships dark", "no production caller") but
whose test naming overstates; F-02 is an inherited fail-open primitive whose consequence P4 widened.

**Scope note for the adjudicator:** R-07 must remain **OPEN — NOT CONTAINED** and P4 must remain
**NOT COMPLETE** until at minimum F-01 and F-02 are discharged. Weighted acceptance has not been
instantiated and this report does not instantiate it. This reviewer performed no remediation, no
finalization and no adjudication.

---

## J. Preserved report location

**Repository authority consulted:** `docs/implementation/PROGRESS-PROTOCOL.md` §"integration
topology" (the unit is replayed as **one content commit before review**, and finalization commits
**on top** — never by altering the reviewed commit), and `CLAUDE.md` §11 / the `⛔` rule forbidding
self-adjudication. The established mechanism is a markdown report under `docs/implementation/`,
committed by a later authorized step — the precedent being
`p3-genuine-independent-review.md`, `p3-independent-review-findings.md`,
`u-rebaseline-review-1-independent-report.md` and `u-handoff-2b-hostile-review-report.md`.

**This report is preserved at:**

```
/Users/sammyfammy/Desktop/freight-logistics-operational-teammate/
    docs/implementation/p4-independent-review-report.md
```

It is a **new, untracked file** in the primary worktree. It therefore:

- does **not** modify or invalidate the reviewed content commit `95cf5af7…` (tree `4b3dda2019…`
  is unchanged and still verifies);
- modifies **no existing file**, tracked or untracked;
- introduces **no new product content path** — it uses the directory canonical authority already
  designates for independent-review reports;
- sits alongside the other finalizer-owned artifacts already staged uncommitted in that worktree
  (`CURRENT.md`, `GATE-RESULT.json`), awaiting the same authorized finalization step.

I verified in the disposable clone that an untracked report file at this path breaks **no guard**:
`test_docs_control_system`, `test_progress_protocol`, `test_roadmap_completeness_control`,
`test_false_green_defenses`, `test_build_status_receipt_consistency` and `test_integration_topology`
run **172 passed** with the file present.

**Residual governance note (not a blocker).** Committing this report requires a commit, which this
reviewer is explicitly forbidden to make; so the file is preserved in the worktree but is **not yet
in any commit or ref**. An authorized finalizing/adjudicating session must commit it for it to
become durable. Until then the source report exists only in the working tree — the adjudicator can
read it in full at the path above, which satisfies the requirement that the complete source report
be readable, but its durability depends on that later authorized step.

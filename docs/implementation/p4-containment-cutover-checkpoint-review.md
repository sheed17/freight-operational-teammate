# P4 Containment Cutover — Implementation Checkpoint Review (implementer's record)

> ### **NOT CURRENT AUTHORITY — this is evidence, not status.**
> The status authority is [`CURRENT.md`](CURRENT.md). If this document and `CURRENT.md` ever
> disagree, `CURRENT.md` is right and this file is stale. Nothing here may be read as approving
> work, moving a gate, or authorising a phase transition.

> **STATUS: CHECKPOINT — AWAITING INDEPENDENT REVIEW.** This is the record of the *implementing*
> session. It is evidence, **not** adjudication: the session that wrote this code did not review it,
> and it does not set any acceptance criterion. `independent_review` and `final_adjudication` for P4
> require a session that did neither the P3/P4 implementation nor this cutover. **R-07 stays OPEN.**
> P4 is **NOT COMPLETE.**

This checkpoint continues the P4 adapter-containment work from the accepted prior checkpoint
(content commit `5460f14`, itself awaiting review). It executes the three review findings that were
mandated as correctable here (F1, F4) plus the verifiable subset of the remaining cutover, and it
**precisely records** the residual that could not be completed *correctly and verifiably* in this
environment (no live browser, no live TMS) — per CLAUDE.md §9 ("not done blind") and §5 rule 20.

---

## 1. What this checkpoint changed

| # | Change | Files | Proof |
|---|---|---|---|
| **F4** | A generic, unclassified exception from `operation.perform` **after** `EffectAttempted` is recorded now becomes **UNKNOWN_OUTCOME** (never left CLAIMED, never FAILED), with the ambiguity recorded before the exception re-raises. | `src/freight_recon/effect_boundary.py::execute_effect` | 3 hostile tests (`test_f4_*`) + mutations **B15** (launder→FAILED) and **B16** (stuck in CLAIMED), both CAUGHT |
| **F1** | EP-12 (`enter_tms_payable.py`): the live `--browser` write path (a real `BrowserUseWriteLedger` + `NativeBrowserUseRunner` against an operator-supplied base URL) is **removed**. The quarantine exemption is now proved **structurally** (AST import graph + constructor AST), replacing the invalid `"MockTmsWriteLedger" in text` substring check. | `scripts/enter_tms_payable.py`, `eval/tests/test_import_gate.py`, `phase-0-baseline-manifest.yaml`, `EFFECT-PATH-INVENTORY.yaml` | 2 structural tests + mutations **B17** (regains a live import) and **B18** (constructs a live driver while still building the mock — the exact case the substring check passed vacuously), both CAUGHT |
| **brain_runtime cut** | `brain_runtime.build_gated_submit` no longer imports the effect-capable `tms_write`; its effect executor and approved-amount reader are **injected** (fail-closed if absent). The `brain_runtime → tms_write` violation edge is gone. No live caller existed, so nothing breaks. | `src/freight_recon/brain_runtime.py` | 2 tests (structural import cut + fail-closed) + mutation **B19** (re-import), CAUGHT |
| **Orphan detective sweep** | `run_detective_sweep(kernel)` is the authorized per-cycle reconciliation loop that runs the orphan detector (Sev-0 + auto-brake) **and** surfaces the UNKNOWN_OUTCOME human-owned queue (`pending_unknown_outcomes`). It calls no adapter → structurally inert under replay. | `src/freight_recon/effect_boundary.py` | 2 tests (finds+brakes+surfaces / clean ledger) + mutations **B20** (skips orphan detection) and **B21** (drops the unknown queue), both CAUGHT |

### Exact F1 / F2 / F4 fixes

- **F1 (HIGH):** *structurally removed the live-browser write path.* `enter_tms_payable.py` now
  imports no effect-capable adapter but `tms_write` (the mock ledger's home) and constructs only
  `MockTmsWriteLedger`. The exemption proof is two AST tests:
  `test_every_quarantine_importer_is_structurally_production_unreachable` (imports no live-reaching
  effect-capable adapter) and `test_every_quarantine_importer_constructs_the_mock_and_no_live_driver`
  (builds the mock, builds no named live driver). The manifest and EFFECT-PATH-INVENTORY were
  updated to match: the `enter_tms_payable → browser_use_adapter` edge is removed; the import gate
  now counts every live effect-capable edge (`live == recorded`, both-sided, is asserted).
- **F2 (MEDIUM):** *recorded and deferred, not faked.* `cdp_session.evaluate()`/`command()`/
  `set_file_input()` remain actuation-capable, so the gate's exemption of `cdp_session` as a "read
  substrate" is not yet fully sound. A robust fix is a genuinely read-only CDP surface (fixed
  read-only observation, no caller-supplied JavaScript, no `command`/`set_file_input`), which is a
  correctness-critical browser refactor with **no live browser to verify against here** and is the
  prerequisite for the EP-3/EP-8/EP-1 read cuts. Attempting it blind would violate CLAUDE.md §9. It
  is recorded (manifest gate status + cutover plan) and deferred with those edges. **F2 is NOT
  closed.**
- **F4 (LOW/HARDENING):** *classified generic post-attempt failures as UNKNOWN_OUTCOME.* See the
  table above; the transition is committed durably (outcome envelope names the exception cause)
  before the exception propagates, so the detective sweep and the escalated human see it, and it is
  never retried in place or downgraded to FAILED.

---

## 2. Import-gate state (mechanical)

```
recomputed adapter-import edges : 18   (was 20 at the prior checkpoint)
recomputed importer modules     : 13   (was 14)
effect-capable VIOLATION edges  : 4    (was 5)   live == recorded, both-sided
```

The 4 residual violation edges (R-07 stays OPEN until they reach EMPTY and the gate asserts empty):

| Edge | EP | Why deferred |
|---|---|---|
| `scripts/run_action_callback_server.py -> cdp_actuator` | EP-1 | feeds the OperationRouter→OperatorAgent autonomous browser WRITE (the live R-07 write) + read closures; containing the write is the **P12-scale supervised-write integration**; browser-untestable here |
| `scripts/propose_ar_from_tms.py -> cdp_actuator` | EP-3 | reads + one nav-click via the actuator; needs the **F2 read-only CDP surface**; browser-untestable |
| `scripts/orient_tms.py -> cdp_actuator` | EP-8 | read-only reconnaissance; needs a read-only navigator (a click can hit a submit target); correctness-critical, browser-untestable |
| `scripts/read_tms_browser_use.py -> browser_use_adapter` | EP-14 | `browser_use_adapter` carries the **tested** `BrowserUseWriteLedger` (a P12 boundary-routed write adapter in waiting) — it may not be deleted; splitting it to a new module would **add an adapter-import edge the shrinking-only allowlist forbids** |

---

## 3. What was tried and deliberately reverted

An EP-14 cut by **deleting** `BrowserUseWriteLedger` (to make `browser_use_adapter` a read substrate)
was attempted and **fully reverted** when it was found that `BrowserUseWriteLedger` and
`parse_payables_row` are **tested** (`eval/tests/test_browser_use_write.py`, 14 nodes) and are the
canonical future P12 browser write adapter — a `git show HEAD:` restore returned the four affected
files byte-for-byte; the manifest/inventory reverts are line-for-line. Deleting a tested capability
with a planned future is exactly the blind change §9 forbids. EP-14 is therefore left in the residual.

---

## 4. Evidence

- **Boundary mutation battery:** `scripts/mutate_phase4_boundary.py` — **21/21 mutants caught**
  (the 14 prior + B15–B21 added this checkpoint). In-memory save/restore, `__pycache__` purged,
  restore verified byte-for-byte — never `git checkout/restore/stash/clean`.
- **Test-node manifest:** regenerated intentionally via `scripts/regenerate_test_manifest.py`;
  diff is exactly **+9 / −1** (the 9 new tests above; the retired substring quarantine test).
- **Acceptance:** the AC-ADPT / EF-machine battery in `test_adapter_boundary_acceptance.py` is green
  and now includes the F4 and detective-sweep cases.

---

## 5. R-07 status

### **OPEN — NOT CONTAINED.** Four effect-capable import edges remain (EP-1, EP-3, EP-8, EP-14),
finding **F2** is unclosed, nothing routes through the boundary in production, and the gate is not
flipped to EMPTY. Only **completing** P4 closes R-07. This checkpoint reduced the surface and fixed
F1/F4; it did not close R-07.

---

## 6. Exact prompt for the next INDEPENDENT reviewer

> You are an INDEPENDENT reviewer. You did NOT implement P3, the P4 boundary, or this P4 containment
> cutover, and you must not certify your own work. Read `CLAUDE.md` and the repository authority
> chain first. Then, from the repository ALONE (no conversation history), adjudicate the P4
> containment cutover checkpoint at the checkpoint commit.
>
> Verify, mechanically and adversarially, each claim below; treat a passing test that asserts a
> forbidden behaviour as a defect:
> 1. **F4** — a generic exception raised by an adapter's `perform` AFTER the attempt is recorded
>    leaves the grant in **UNKNOWN_OUTCOME**, never CLAIMED, never FAILED; the ambiguity is durable
>    (outcome envelope + EffectAttempted) and the exception still propagates. Confirm mutations
>    B15/B16 are caught, and hunt for any path where a post-attempt failure can be laundered to
>    FAILED or leave the grant CLAIMED.
> 2. **F1** — `enter_tms_payable.py` has **no** live-browser write path; the quarantine exemption is
>    proved by AST (imports no live-reaching effect-capable adapter; constructs only the mock;
>    constructs no live driver), NOT by substring. Try to defeat the structural proof (a live import,
>    a live-driver construction while still naming the mock). Confirm B17/B18 are caught.
> 3. **brain_runtime** — imports no effect-capable adapter; `build_gated_submit` fails CLOSED without
>    an injected executor. Confirm the `brain_runtime → tms_write` edge is gone and B19 is caught.
> 4. **Orphan detective sweep** — `run_detective_sweep` finds an injected orphan (Sev-0 + brake) and
>    surfaces a real UNKNOWN_OUTCOME; a healthy ledger yields nothing. Confirm B20/B21 are caught.
> 5. **Import gate** — `live == recorded`, both-sided; the recorded violation list is EXACTLY the 4
>    edges above; `read_substrate`/`effect_capable_adapters`/`quarantine_importers` match the probe;
>    the shrinking-only allowlist is exact.
> 6. **Residual honesty** — confirm F2 and EP-1/EP-3/EP-8/EP-14 are recorded OPEN, that R-07 is OPEN
>    everywhere it must be, and that P4 is NOT marked COMPLETE. Confirm nothing routes an effect
>    through the boundary in production and the kernel still ships dark.
> 7. **No regression** — the ExecutionCapability stays unconstructable/unforgeable/single-use; the
>    witness table stays append-only; the claim CAS keeps every WHERE-clause predicate;
>    UNKNOWN_OUTCOME is never auto-resolved or retried.
> 8. Re-run: the full canonical suite (`pytest -c pytest-canonical.ini`), the import-gate suite, the
>    boundary mutation battery (`scripts/mutate_phase4_boundary.py`, expect 21/21), the control
>    guards, and the clean-clone gate (`scripts/clean_clone_gate.py`).
>
> Deliver a structured PASS/FAIL per claim, any new findings ranked by severity, and a verdict:
> either "the P4 containment cutover checkpoint is sound as far as it goes; R-07 remains OPEN with
> the residual precisely recorded" or a NOT-READY with specific defects. Do **not** advance P4 to
> COMPLETE — the full cutover (EP-1/EP-3/EP-8/EP-14 + F2 + gate EMPTY) is not done, and completion is
> a separate adjudication after that work lands.

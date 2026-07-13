# Repository Baseline Audit

**Purpose:** determine whether this repository can serve as a **trustworthy migration baseline** (review finding **B10**; correction plan **Wave 0**).
**Constraint honoured:** **nothing was modified, staged, stashed, reset, discarded, or committed.** This audit is strictly read-only.
**Date:** 2026-07-09

---

# PART 1 — STATE OF THE TREE

## 1. Current branch
**`demos`** *(not the default branch; `main` is the default)*

## 2. Current HEAD
```
bf1d205  2026-07-12  sheed17
ADR-003 authorization assertion (permanent truth) + architecture correction plan
```

**The last 7 commits are the architecture reset.** The last commit of *product work* is `591d2de` (Owner Demand Catalog).

## 3. Staged changes
**None.** The index is clean.

## 4. Unstaged changes (tracked)
**17 files · +1,027 / −53**

| File | Δ |
|---|---|
| `src/freight_recon/action_callback.py` | +263 |
| `scripts/run_action_callback_server.py` | +223 |
| `src/freight_recon/ops_control.py` | +107 |
| `eval/tests/test_ops_control.py` | +93 |
| `src/freight_recon/mailbox_intake.py` | +90 |
| `src/freight_recon/imap_mailbox.py` | +57 |
| `eval/tests/test_conversational_surface.py` | +48 |
| `eval/tests/test_mailbox_intake.py` | +39 |
| `src/freight_recon/cdp_session.py` | +37 |
| `eval/tests/test_operator_agent.py` | +26 |
| `src/freight_recon/operator_agent.py` | +24 |
| `src/freight_recon/operation_router.py` | +21 |
| `eval/tests/test_action_callback.py` | +20 |
| `src/freight_recon/cdp_actuator.py` | +12 |
| `eval/tests/test_run_teammate.py` | +10 |
| `src/freight_recon/ar_collections.py` | +5 |
| `scripts/run_teammate.py` | +5 |

## 5. Untracked files
- `docs/MVP_DEMO_SCORECARD.md`
- `eval/tests/test_imap_mailbox.py`
- `src/freight_recon/tms_read_cache.py`

---

# PART 2 — ATTRIBUTION

## 6/7/8. Two interleaved work streams — and why attribution is **not possible by file**

> ### ⚠️ **The central attribution finding**
> **Every source file modified during the recent work was *already dirty* when that work began.** There is **no commit boundary** separating the two streams. They are **interleaved inside the same files**, and `git` cannot separate them.
>
> **Attribution by file is impossible. Attribution by hunk is possible but requires human confirmation.**

### Stream A — *Phase 0 document capability + owner-dogfood fixes* (authored in the recent working session)
| Files | Content |
|---|---|
| `cdp_session.py` | `set_file_input` (CDP `DOM.setFileInputFiles`) |
| `cdp_actuator.py` | `upload_file` |
| `operator_agent.py` | `UPLOAD` action, `document_path` document-fence |
| `operation_router.py` | `document_for` resolver, `requires_document` front-door fence |
| `action_callback.py` | `load_state_reader`/`load_docs_reader`; the six dogfood fixes (D1–D6) |
| `ar_collections.py` | `_REF_LIKE` (invoice-ref-as-customer fix) |
| `run_action_callback_server.py` | document resolver, load-state reader, load-docs reader |
| `eval/tests/test_operator_agent.py` | 2 upload tests |
| `docs/MVP_DEMO_SCORECARD.md` | *(untracked)* |

**Coherent. Test-covered. Live-verified** (the POD was filed on load 101 through the real Slack path).

### Stream B — *Readiness hardening* (**predates** the recent session; authorship unconfirmed)
| Files | Content |
|---|---|
| `imap_mailbox.py` | IMAP transient-error retry (`_TRANSIENT_IMAP_ERRORS`, backoff) |
| `tms_read_cache.py` *(new)* | **Durable cache for read-only TMS snapshots** — explicitly built for the slash-command response window, so reads *"fall back to the last verified value instead of timing out or false-clearing."* |
| `mailbox_intake.py` | `_refresh_existing_message_routing`, `_routing_for_parsed_message`, preserved-path resolution |
| `ops_control.py` | `_handle_assign_unlinked` |
| `run_teammate.py` | `--corpus` passthrough |
| `test_imap_mailbox.py` *(new)*, `test_mailbox_intake.py`, `test_ops_control.py`, `test_run_teammate.py`, `test_conversational_surface.py`, `test_action_callback.py` | tests for the above |

**Also coherent and purposeful.** It is **not noise**. `tms_read_cache.py` in particular solves a real defect found in live driving (the >3s slash-command latency), and its docstring shows the author understood the *false-clearing* hazard — the same hazard the constitution names in **R10**.

> **Judgement:** Stream B looks like **competent, intentional work from a parallel session or agent** (project memory references a parallel "Codex readiness hardening" stream). **This is not garbage to be discarded.** But **I did not author it, I cannot verify its intent, and it must not be swept into a baseline commit under someone else's name.**

## 8. Changes whose author or purpose cannot be determined
**Stream B in its entirety.** The *purpose* is legible from the code. The **author is not**, and the **completeness is not** — I cannot tell whether Stream B was finished, abandoned mid-way, or superseded.

---

# PART 3 — SAFETY OF THE CURRENT TREE

## 9. Dead / partially-wired code in live modules

| Item | Status |
|---|---|
| `render_exception_radar` in `action_callback.py` | **Defined. Never called.** |
| `_is_radar_query` in `action_callback.py` | **Defined. Zero call sites in the router.** |

**Confirmed dead code in a live module** (**R18** — *"it will be executed eventually, by someone who assumed it was live for a reason"*). Authored in the recent session; abandoned when the architecture reset began.

## 10. Do the tests pass?
**YES — 685 passed, 0 failed** (6m39s).

> ⚠️ **This is a much weaker signal than it appears.** The suite passes **on the interleaved tree**. It tells us **nothing** about whether **either stream passes in isolation**, which is precisely the question a baseline must answer. **A green suite on an unattributable tree is not evidence of a trustworthy baseline.** (P17: *tests are necessary and never sufficient.*)

---

## 11. ⛔ **R-01 (CRITICAL) — A production entry point can route human-APPROVED payables into a MOCK ledger**

**This is the most serious finding in the audit, and it corrects an error in the frozen reconciliation.**

### The path
```
scripts/run_action_callback_server.py   --auto-enter-approved-mock-tms
   → post_approval_execution.py         ledger = MockTmsWriteLedger(config.ledger_path)   ← HARDCODED
      → tms_write.enter_approved_payable(store, ledger, ...)
         → writes to a JSON file
            → workflow reaches DONE
               → the owner is told the payable was entered
```

**A human approves a payable in Slack. The gated write path runs — approved-amount binding, idempotency, state machine, verify-by-readback — all of it, correctly. Against a JSON file. The workflow reports `DONE`. Nothing happened in the real world.**

- The flag is **off by default**, and the observed production launches do not set it.
- **It is one CLI flag away**, in the production entry point, and the help text (*"enter the approved payable into the mock TMS ledger"*) is exactly the kind of text a tired operator turns on.
- **This is the archetype of the defect the entire architecture exists to prevent**: a verified, audited, `DONE`-reported effect that never touched reality. It is **R10 and I10 simultaneously**, and it is **live today**.

### The correction to the frozen reconciliation
The Current-State Reconciliation classified **`tms_write.py` as REMOVE — "mock infrastructure."** **That classification was wrong**, and acting on it would have **deleted the production safety spine.**

`tms_write.py` actually conflates **three different things in one module**:

| Concern | Reality | Correct disposition |
|---|---|---|
| **`enter_approved_payable`** — the gated write **driver**: approved-amount binding, idempotency, the APPROVED→…→DONE state machine, **verify-by-readback** | **This is the safety spine.** `truckingoffice_write.py` *"drops into `enter_approved_payable` unchanged"* with a **real** ledger. | **KEEP — it is load-bearing** |
| **`MockTmsWriteLedger`** | A mock **adapter** behind a ledger port | **KEEP as test infrastructure; SEVER from every production path** |
| **Contracts** (`PayableWriteResult`, `ChargeLine`, `PayableWriteStatus`…) | Shared types | **KEEP** |

> **The defect is the conflation itself.** A module *named and documented as "the mock TMS write path"* contains the **production safety-critical write driver**. That is why it is live-reachable, why my own reconciliation misread it, and why an implementer would misread it too. **The ledger is a port; mock and TruckingOffice are two adapters.** The module boundary is drawn in the wrong place.

## 12. Can the live runtime produce external effects right now?
**Not at this instant** — Chrome/CDP is down and no callback server is running.
**But it is one command away.** The runtime is fully intact: authenticated-session attachment, the operation router, the CDP actuator, and 11 script entry points.
**Treat the answer as YES.**

## 13. ⛔ **R-02 (CRITICAL) — Multiple runtime entry points can produce the same external effect**

**Confirmed present TODAY — not merely a migration risk (this is review finding F-07, already real).**

**11 entry points can reach the live TMS via CDP.** At least these can perform a **write**:

| Entry point | Effect |
|---|---|
| `scripts/run_action_callback_server.py` | Slack-approved operation → agent → live TMS write |
| `scripts/run_teammate.py` | supervises the above |
| `scripts/propose_ar_from_tms.py` | proposes AR; approval → live invoice |
| `scripts/enter_truckingoffice_invoice.py` | **direct live TruckingOffice invoice write** |
| `scripts/enter_invoice_discovered.py` | direct gated write via a discovered screen map |
| `scripts/drive_real_tms.py` | drives the agent against the live TMS |
| `scripts/run_operate_request.py` · `run_operator_agent.py` | run the agent directly |
| `scripts/enter_tms_payable.py` · `run_dogfood_pilot.py` | write to the **mock** ledger |

**There is no shared commit-key namespace across these.** Two of them can bill the same load. **This is exactly F-07, and it does not require a migration to occur — it is reachable today from a terminal.**

## 14. Are all frozen documents and ADRs committed?
**YES.** All four frozen documents, all three ADRs, the review, and the correction plan are tracked and committed.
**Only untracked doc:** `docs/MVP_DEMO_SCORECARD.md`.

## 15. Can the repository currently serve as a trustworthy migration baseline?
# **NO.**

---

# PART 4 — CLASSIFICATION OF EVERY OUTSTANDING CHANGE

| # | File | Diff summary | Likely origin | Likely purpose | Risk of RETAINING | Risk of REMOVING | Classification | Recommended action |
|---|---|---|---|---|---|---|---|---|
| 1 | `src/freight_recon/cdp_session.py` | +37 · `set_file_input` (CDP file upload) | Recent session (Stream A) | Enable document filing | Low — additive, tested, live-verified | **High** — removes the only file-upload capability | **KEEP_AND_COMMIT** | Commit as "Phase 0: document upload capability" |
| 2 | `src/freight_recon/cdp_actuator.py` | +12 · `upload_file` | Stream A | Actuator surface for upload | Low | High | **KEEP_AND_COMMIT** | Same commit |
| 3 | `src/freight_recon/operator_agent.py` | +24 · `UPLOAD` action + **document fence** | Stream A | Runtime supplies the file; model never names a path | Low — it is a *safety* addition | **High** — removes a fence | **KEEP_AND_COMMIT** | Same commit |
| 4 | `src/freight_recon/operation_router.py` | +21 · `document_for`, `requires_document` | Stream A | Front-door document fence | Low | High | **KEEP_AND_COMMIT** | Same commit |
| 5 | `src/freight_recon/ar_collections.py` | +5 · `_REF_LIKE` skip | Stream A (dogfood D5) | Stop invoice refs rendering as customer names | Low | Medium — a known live defect returns | **KEEP_AND_COMMIT** | Commit as "dogfood fixes" |
| 6 | `src/freight_recon/action_callback.py` | +263 · readers, D1–D6 fixes, **+ dead radar code** | Stream A | Owner-surface fixes | **Medium — contains dead code (R18)** | Medium — six live-found defects return | **KEEP_BUT_SEPARATE** | **Split:** commit D1–D6 + readers; **delete `render_exception_radar` / `_is_radar_query`** |
| 7 | `scripts/run_action_callback_server.py` | +223 · document/state/docs readers | Stream A | Wiring for the above | Low | High | **KEEP_AND_COMMIT** | Same commit |
| 8 | `eval/tests/test_operator_agent.py` | +26 · 2 upload tests | Stream A | Test the document fence | Low | High | **KEEP_AND_COMMIT** | Same commit |
| 9 | `docs/MVP_DEMO_SCORECARD.md` | new (untracked) | Stream A | Demo-progress tracker | Low | Low | **GENERATED_ARTIFACT** | **Discard or commit — it is superseded by the architecture reset.** Recommend discard. |
| 10 | `src/freight_recon/imap_mailbox.py` | +57 · transient-error retry | **Stream B — unattributed** | IMAP resilience | Medium — **unreviewed** | Medium — loses real hardening | **NEEDS_HUMAN_DECISION** | Confirm authorship, review, commit **separately** |
| 11 | `src/freight_recon/tms_read_cache.py` | new (untracked) · durable read cache | **Stream B — unattributed** | Fix the >3s slash timeout; avoid false-clearing | Medium — **unreviewed cache in a read path that feeds money decisions** | Medium — the latency defect returns | **NEEDS_HUMAN_DECISION** | ⚠️ **Review carefully.** A cache that serves stale reads to a *money* surface interacts directly with **ADR-001 C4** (*consequential actions must revalidate against the authoritative source*). **It may be right; it may be exactly the wrong thing.** |
| 12 | `src/freight_recon/mailbox_intake.py` | +90 · routing refresh | **Stream B** | Re-route already-seen messages | Medium — unreviewed | Low | **NEEDS_HUMAN_DECISION** | Confirm, review, commit separately |
| 13 | `src/freight_recon/ops_control.py` | +107 · `_handle_assign_unlinked` | **Stream B** | Owner resolves UNLINKED emails | Medium — unreviewed | Medium — a demoed capability disappears | **NEEDS_HUMAN_DECISION** | Confirm, review, commit separately |
| 14 | `scripts/run_teammate.py` | +5 · `--corpus` passthrough | **Stream B** | Feed the mailbox loop a corpus | Low | Low | **NEEDS_HUMAN_DECISION** | Same |
| 15 | `eval/tests/test_imap_mailbox.py` | new (untracked) | **Stream B** | Tests for #10 | Low | Medium | **NEEDS_HUMAN_DECISION** | Travels with #10 |
| 16 | `eval/tests/test_mailbox_intake.py` | +39 | **Stream B** | Tests for #12 | Low | Medium | **NEEDS_HUMAN_DECISION** | Travels with #12 |
| 17 | `eval/tests/test_ops_control.py` | +93 | **Stream B** | Tests for #13 | Low | Medium | **NEEDS_HUMAN_DECISION** | Travels with #13 |
| 18 | `eval/tests/test_run_teammate.py` | +10 | **Stream B** | Tests for #14 | Low | Low | **NEEDS_HUMAN_DECISION** | Travels with #14 |
| 19 | `eval/tests/test_conversational_surface.py` | +48 | **Mixed / UNKNOWN** | Conversational-surface tests | Medium | Medium | **UNKNOWN** | **Hunk-level review required** — may span both streams |
| 20 | `eval/tests/test_action_callback.py` | +20 | **Mixed / UNKNOWN** | Callback tests | Medium | Medium | **UNKNOWN** | **Hunk-level review required** |

### Findings that are **not** working-tree changes (they are committed defects)

| # | Item | Classification | Action |
|---|---|---|---|
| **R-01** | `--auto-enter-approved-mock-tms` → **approved payables into a mock ledger, reported DONE** | **DISCARD_CANDIDATE (committed code)** | **Sever from production. This is Wave-0 work, not Wave-5.** |
| **R-02** | 11 entry points, no shared commit key | **NEEDS_HUMAN_DECISION** | Reduce to one, or gate the rest behind a shared effect ledger |
| **R-03** | `tms_write.py` conflates the safety spine + the mock ledger + contracts | **KEEP_BUT_SEPARATE** | **Split the module.** *(Corrects the frozen reconciliation's "REMOVE" classification.)* |

---

# PART 5 — VERDICT

# **BASELINE_NOT_READY**

The repository **cannot** currently serve as a trustworthy migration baseline. Three independent reasons, any one of which is sufficient:

1. **Attribution is impossible by file.** Two coherent work streams are interleaved inside the same files with no commit boundary. **A baseline commit would attribute unreviewed work to whoever makes it.**
2. **A production entry point can report a fake payable as `DONE`** (R-01). **A baseline must not contain a path that lies about money.**
3. **Multiple runtimes can produce the same external effect today** (R-02) — F-07 is not a future migration risk; it is a present one.

Additionally: dead code sits in a live module, and the green test suite is **not evidence** — it passes on the mixed tree and says nothing about either stream in isolation.

---

## Exact human decisions required before the baseline can be frozen

| # | Decision | Who | Why it cannot be automated |
|---|---|---|---|
| **D1** | **Confirm the authorship and intent of Stream B** (`imap_mailbox`, `tms_read_cache`, `mailbox_intake`, `ops_control`, `run_teammate` + their tests). **Keep, or discard?** | **Rasheed** | I did not author it and cannot verify its intent or completeness. **Committing it under my authorship would be a lie in the permanent record.** |
| **D2** | **Approve severing R-01** — remove `--auto-enter-approved-mock-tms` and the hardcoded `MockTmsWriteLedger` from `post_approval_execution.py`, so **no production path can reach a mock ledger.** | **Rasheed** | Deletes an existing (if dormant) capability. |
| **D3** | ⚠️ **Review `tms_read_cache.py` specifically.** A durable cache serving stale reads into a **money surface** directly engages **ADR-001 C4** (*consequential actions must revalidate against the authoritative source*). **It may be exactly right, or exactly the wrong thing.** | **Rasheed + me** | Requires a judgement that interacts with a frozen decision. |
| **D4** | **Approve deleting the dead radar code** (`render_exception_radar`, `_is_radar_query`). | **Rasheed** | R18. Trivial, but it is *someone's* unfinished intent. |
| **D5** | **Decide the fate of `docs/MVP_DEMO_SCORECARD.md`** (superseded by the reset). | **Rasheed** | Recommend discard. |
| **D6** | **Decide R-02**: reduce the write-capable entry points, or place them behind a shared effect ledger. | **Rasheed** | Removes capability people may still be using. |

## Recommended sequence to reach `BASELINE_READY`

1. **D2 first** — sever the mock payable path. *A baseline that can lie about money is not a baseline.*
2. **D4** — delete the dead code.
3. **D1 + D3** — sit with the Stream B diffs; confirm authorship; **review `tms_read_cache.py` against ADR-001 C4.**
4. **Commit in three separate, honestly-attributed commits:**
   - `Phase 0: document upload capability` (Stream A core)
   - `Owner-dogfood fixes D1–D6` (Stream A surface)
   - `Readiness hardening` (Stream B — **attributed to its actual author**)
5. **D6** — decide on the entry points; at minimum, **document** that they exist and can double-act.
6. **Re-run the suite on the clean tree.** *Only then* is it a baseline.

> **Nothing in this audit was modified. The tree is exactly as it was found.**

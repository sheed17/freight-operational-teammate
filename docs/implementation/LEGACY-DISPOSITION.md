# Legacy Disposition Registry

> ### **No module in this repository is protected by being large, old, working, or well tested.**
> The current runtime was built before the canonical architecture existed. Where it conflicts with
> the architecture, **the architecture wins.**

**Every production module carries exactly one disposition.** There is deliberately **no permanent
category equivalent to `LEGACY_BUT_ACTIVE_FOREVER`** — every disposition names a target phase and a
deletion or graduation condition. A module that is going to be replaced eventually is not `KEEP`;
it is `ADAPT` or `REWRITE` with a phase attached.

**Coverage is machine-checked.** [`eval/tests/test_docs_control_system.py`](../../eval/tests/test_docs_control_system.py)
asserts that every module under `src/freight_recon/` AND every script under `scripts/` appears
in a subsystem below — so a new module or script cannot quietly arrive without a disposition.

---

## The six dispositions

| Disposition | Meaning |
|---|---|
| **KEEP** | Canonical or architecture-neutral. Survives as-is. |
| **ADAPT** | The responsibility is right; the implementation must move behind canonical boundaries. |
| **REWRITE** | The responsibility is right; the implementation conflicts with the architecture. |
| **MAKE_READ_ONLY** | May observe, may never act. Its effect capability is removed. |
| **QUARANTINE** | Retained for evidence or reference; excluded from production paths. |
| **DELETE** | Removed entirely once its deletion condition is met. |

> **`KEEP` is never awarded because a module is large, old, working or well tested.** It is awarded only where the module is
> already canonical (Phase 0–2 output) or genuinely architecture-neutral (I/O helpers, config).

---

## S1 — Effect-bearing write paths ⛔ THE R-07 SURFACE

**Modules:** `tms_write.py` · `truckingoffice_write.py` · `discovered_write.py` · `multistep_write.py` · `cdp_actuator.py` · `cdp_session.py` · `browser_use_adapter.py` · `browser_lock.py` · `browser_session_health.py` · `browser_failures.py` · `browser_learning.py` · `mock_tms_write_server.py`

| | |
|---|---|
| **Current responsibility** | Drive a real browser against a live TMS and commit real money effects |
| **Current execution authority** | ### **NONE. They act on import and call.** No checkpoint, no witness, no grant. |
| **Current risk** | ### **R-07 — OPEN, NOT CONTAINED.** This is the highest-risk subsystem in the repository. |
| **Canonical destination** | Adapter boundary contracts ([`adapters/02-tms.md`](../specifications/adapters/02-tms.md), [`10-browser.md`](../specifications/adapters/10-browser.md)) behind ADR-004's effect boundary |
| **Disposition** | ### **ADAPT** — converted to grant-and-witness-gated adapters (`mock_tms_write_server.py`: **QUARANTINE**, test-only) |
| **Target phase** | **P4** (requires P3's witness to exist first) |
| **Compatibility requirement** | None. There is no supported path that writes without a grant. |
| **Deletion condition** | The U4.9 CI import gate is ON and `adapter_import_allowlist.edges` is empty |
| **Evidence required before deletion** | Every effect routed through a claimed grant + fresh witness; orphan-adapter detection live at Sev-0; `adapter-boundary-acceptance.md` green |

> **These modules are the reason `PRODUCT.md` §19 exists.** They work, they are proven live, and
> they are the single largest source of unbounded risk in the system.

## S2 — Effect-capable entry-point scripts ⛔

**Modules:** `scripts/orient_tms.py` (EP-8) · `scripts/enter_tms_payable.py` (EP-12, test-only) · and the remaining effect-reachable scripts inventoried in [`effect-entry-point-cutover-plan.md`](effect-entry-point-cutover-plan.md). **P4 executed the DELETE disposition on EP-6/7/9/10 — enter_truckingoffice_invoice, enter_invoice_discovered, run_operate_request and run_operator_agent are physically gone (see S15a).**

| | |
|---|---|
| **Current responsibility** | Operator-invoked live writes, bypassing every review surface |
| **Current execution authority** | ### **Full, ungated.** EP-8 was *"read-only by convention, actuator-capable by import"* |
| **Current risk** | 6 of these are production-reachable; the only mitigation is operator discipline |
| **Canonical destination** | Pipeline clients (EP-1, EP-3) or nothing at all |
| **Disposition** | ### **DELETE** — EP-6, EP-7, EP-9, EP-10 (`REMOVE_BEFORE_ENABLE`) · **ADAPT** — EP-1, EP-3 → pipeline clients · **MAKE_READ_ONLY** — EP-8 |
| **Target phase** | **P4** |
| **Compatibility requirement** | None. **A deleted script has no compatibility surface** — that is the point. |
| **Deletion condition** | EP-6/7/9/10 physically deleted; `orient_tms` loses its actuator import; the import gate is ON |
| **Evidence required before deletion** | `effect-entry-point-cutover-plan.md` fully executed; no import path from any script to an actuator |

## S3 — Orchestration and routing

**Modules:** `action_callback.py` (1964 lines) · `operation_router.py` · `operation_proposal.py` · `delivery_dispatch.py` · `delivery.py` · `flow_recipe.py` · `brain_runtime.py` · `brain_operator.py` · `operator_brain.py` · `operator_agent.py` · `system_orientation.py` · `screen_discovery.py` · `screen_mapping.py`

| | |
|---|---|
| **Current responsibility** | Decide what to do next and route to an executor — a second orchestration system |
| **Current execution authority** | Dispatches effects directly; `action_callback.py` is the largest module in the repo |
| **Current risk** | ### **This is the "no permanent second orchestration system" violation.** Pipeline Instances (P6) are the canonical orchestrator. |
| **Canonical destination** | Pipeline Instance + state machines (ADR-008), policy admission (ADR-010) |
| **Disposition** | ### **REWRITE** |
| **Target phase** | **P6** (machines) with effect routing moved at **P4** |
| **Compatibility requirement** | May run in parallel **only** while behind a capability flag, with a deletion condition recorded — **never permanently** |
| **Deletion condition** | All 13 canonical machines live; no effect dispatch outside the Pipeline Instance |
| **Evidence required before deletion** | `foundational-machine-acceptance.md` green; no dual-orchestration import edges |

> **`action_callback.py` also carries a hardcoded knowledge-base `tenant="default"` in `action_callback.py::_learn_correction` (the `KnowledgeBase(...).learn` call).** The exact sites are discovered by guard — a line-number citation went stale within two commits, which is why none is used.
> That finding closes at **P7**, not here.

## S4 — Legacy state management

**Modules:** `workflow.py` · `schema.py` · `migrations/` · `tenant.py` · `cli_tenant.py` · `commit_key.py` · `workflow_direction.py` · `models.py`

| | |
|---|---|
| **Current responsibility** | Canonical persistence, tenancy, effect identity, migration |
| **Current execution authority** | Persistence only. **No effect capability.** |
| **Current risk** | Low — this is the Phase 0–2 output and the most hardened code in the repository |
| **Canonical destination** | Absorbed into the entity layer (P6); the effect ledger gains checkpoint binding (P3) |
| **Disposition** | ### **ADAPT** — `commit_key.py`, `tenant.py`, `cli_tenant.py`, `schema.py`, `migrations/`: **KEEP** (canonical, forward-only) |
| **Target phase** | **P3** (grant binding) → **P6** (entity absorption) |
| **Compatibility requirement** | `WorkflowStore`'s tenant contract is forward-only and may never be relaxed |
| **Deletion condition** | `workflow.py`'s responsibilities are held by Work Item + Pipeline Instance |
| **Evidence required before deletion** | The 22 tenant-scoped methods have canonical equivalents; AC-SEC-001 stays green |

## S4b — Phase-3 safety kernel *(canonical, not legacy — recorded here so coverage stays total)*

**Modules:** `checkpoint.py` · `brake.py` · `fingerprint.py` · `migrations/phase3_checkpoint.py`

| | |
|---|---|
| **Current responsibility** | The seven-step atomic checkpoint, the Checkpoint Witness, grant mint + claim CAS, brake admission, the fp_v1 material-facts fingerprint |
| **Current execution authority** | ### **None on the outside world.** The kernel authorizes and records; no adapter routes through it until P4. It ships dark. |
| **Current risk** | ### **P3 is COMPLETE and adjudicated** — a fresh independent review PASSED and a separate final adjudication set all 14 weighted criteria PASS. The kernel nonetheless **ships dark**, so the risk it exists to close (R-07) still closes only when P4 routes the remaining live-write paths through it |
| **Canonical destination** | This IS the canonical destination (ADR-004/005/009/010/011); P4 contains adapters behind it, P6 binds Pipeline Instances, P8 replaces the typed gate inputs with the policy runtime |
| **Disposition** | ### **KEEP** — canonical, forward-only. The witness table is append-only and its immutability may never be relaxed. |
| **Target phase** | Implemented and adjudicated at **P3**; consumed by **P4+** |
| **Compatibility requirement** | `CheckpointPassed` stays unconstructable; the claim CAS's WHERE-clause revalidation (state, expiry, brake, policy) may never lose a predicate |
| **Deletion condition** | Not deletable — no permanent second effect-authority system may exist beside it |
| **Evidence required before deletion** | n/a |

## S4c — Phase-4 adapter-containment boundary *(canonical, not legacy — recorded here so coverage stays total)*

**Modules:** `effect_boundary.py` · `cdp_readonly.py`

> ### **`cdp_readonly.py` is the F2 read substrate — canonical, and deliberately NOT in S1.** S1 is
> the effect-bearing surface; this module is its opposite and was created to end the conflation.
> It exposes no mutation primitive, never lets caller data become JavaScript (targets travel as
> `Runtime.callFunctionOn` arguments), and its channel refuses any CDP method or script outside the
> vetted read-only sets — `Runtime.evaluate` is not admitted at all. Write-capable CDP stays
> untouched in `cdp_session.py`/`cdp_actuator.py` (S1), behind the adapter and effect boundary. The
> dependency runs write→read (the actuator imports these vetted scripts, so the two surfaces cannot
> drift); the reverse is forbidden and guarded. Proven by
> `eval/tests/test_cdp_readonly_surface.py` (29 nodes: structural, hostile, behavioural) and, on a
> live browser against the real mock TMS, by `scripts/verify_readonly_cdp.py`.
> ### **Delivering the substrate does not by itself discharge F2:** F2 closes when EP-1/EP-3/EP-8
> consume this module and the import gate stops exempting `cdp_session` as a read substrate.

| | |
|---|---|
| **Current responsibility** | The single door for every external effect: the adapter operation contract (operation classes + verification modes), the unforgeable single-use `ExecutionCapability`, the CLAIMED→ATTEMPTED→VERIFIED/UNKNOWN_OUTCOME/FAILED outcome machine, orphan-effect detection (Sev-0, auto-brake), and the cross-tenant containment report (GLOBAL brake) |
| **Current execution authority** | ### **None yet routed in production.** The boundary exists and is acceptance-proven; it ships dark alongside the kernel. The P4 containment checkpoint added the F4 outcome-safety (a generic post-attempt exception → UNKNOWN_OUTCOME), implemented and mutation-proved the orphan detective sweep mechanism (`run_detective_sweep` is its per-cycle invocation surface — no production/runtime caller exists yet; production scheduling is deferred to P11 and the boundary still ships dark), and cut the `brain_runtime → tms_write` edge (its effect executor is now injected, not imported). EP-1/EP-3 pipeline-client conversion remains. It authorises nothing until an adapter operation is registered and called |
| **Current risk** | R-07 remains OPEN — the boundary is built and green but **three** effect-capable import edges (EP-1, EP-3, EP-14) are not yet cut, so ungated paths still exist beside it. EP-8 was cut at U4.7 onto the read-only observer |
| **Canonical destination** | This IS the canonical containment boundary (ADR-004 two-key rule); the import gate makes bypassing it structurally impossible once the violation list is empty |
| **Disposition** | ### **KEEP** — canonical, forward-only. `ExecutionCapability` stays unconstructable/unforgeable/single-use; UNKNOWN_OUTCOME may never be silently downgraded to FAILED or retried |
| **Target phase** | Implemented at **P4** (adjudication outstanding); the routing cutover completes R-07 closure |
| **Compatibility requirement** | No second effect-execution path may exist beside it; every adapter effect flows through `execute_effect` |
| **Deletion condition** | Not deletable — no permanent second effect-authority system may exist beside it |
| **Evidence required before deletion** | n/a |

## S5 — Document processing and extraction

**Modules:** `ingestion.py` · `extraction.py` · `extraction_bridge.py` · `document_identifier.py` · `packet_page.py` · `email_corpus.py`

| | |
|---|---|
| **Current responsibility** | Read documents, produce structured data |
| **Current execution authority** | None directly, but its output feeds consequential decisions |
| **Current risk** | ### **Extraction output is `MODEL_INFERRED` and is not yet marked as such.** Until P7, an inferred value can reach a decision without its provenance travelling with it. |
| **Canonical destination** | Document adapter ([`adapters/07-documents.md`](../specifications/adapters/07-documents.md)) producing Evidence + Observations with provenance |
| **Disposition** | ### **ADAPT** |
| **Target phase** | **P7** |
| **Compatibility requirement** | Output must carry `provenance_class` before it may inform a consequential action |
| **Deletion condition** | Not deleted — adapted behind the adapter boundary |
| **Evidence required before deletion** | AC-SAFE-015/016 green; no `MODEL_INFERRED` value authorising an action |

## S6 — Mailbox and inbound communications

**Modules:** `mailbox_workflow.py` · `mailbox_intake.py` · `imap_mailbox.py` · `email_adapter.py` · `email_triage.py` · `inbox_discovery.py` · `inbox_brain.py` · `thread_reply.py` · `follow_up.py`

| | |
|---|---|
| **Current responsibility** | Ingest email, triage relevance, link to loads, send follow-ups |
| **Current execution authority** | ### **Outbound email is an external effect** and is not currently gated |
| **Current risk** | An outbound message to a carrier or customer is consequential and ungated |
| **Canonical destination** | Inbound-comms adapter ([`adapters/01-inbound-comms.md`](../specifications/adapters/01-inbound-comms.md)); W10 Customer Communications |
| **Disposition** | ### **ADAPT** — outbound paths **MAKE_READ_ONLY** until gated |
| **Target phase** | **P4** (outbound gating) → **P13** (W10) |
| **Compatibility requirement** | Inbound ingestion may continue; outbound requires a grant |
| **Deletion condition** | Not deleted — adapted |
| **Evidence required before deletion** | No outbound send without a claimed grant + fresh witness |

## S7 — Reconciliation and matching

**Modules:** `reconciliation.py` · `ar_collections.py` · `roi_ledger.py` · `lane_graduation.py`

| | |
|---|---|
| **Current responsibility** | Compare documents against records; decide clean vs exception |
| **Current execution authority** | Produces decisions that gate money |
| **Current risk** | The comparison is deterministic (good), but predates the canonical Expectation/Exception model |
| **Canonical destination** | Expectation + Exception + Conflict machinery (P8); W7 Exceptions |
| **Disposition** | ### **REWRITE** |
| **Target phase** | **P8** |
| **Compatibility requirement** | Determinism must be preserved through the rewrite — **the model never decides an amount** |
| **Deletion condition** | Expectations and Exceptions carry these decisions canonically |
| **Evidence required before deletion** | `recovery-and-compensation-acceptance.md` green |

## S8 — Review and approval surfaces

**Modules:** `review.py` · `review_actions.py` · `operator_console.py` · `render.py` · `summary.py`

| | |
|---|---|
| **Current responsibility** | Present decisions to a human and capture approval |
| **Current execution authority** | Approval here authorises downstream effects |
| **Current risk** | ### **Approval is not yet bound to Material Facts and does not void on drift** (ADR-005) |
| **Canonical destination** | Approval entity + binding + drift voiding |
| **Disposition** | ### **REWRITE** |
| **Target phase** | **P8** |
| **Compatibility requirement** | An approval captured under the old model may not authorise an effect under the new one |
| **Deletion condition** | All approvals are canonical Approval entities |
| **Evidence required before deletion** | AC-SAFE cases for approval binding and drift green |

## S9 — Slack and channel interfaces

**Modules:** `slack_adapter.py` · `slack_delegate.py` · `channels.py` · `alert_channel.py` · `nl_command.py` · `ops_control.py` · `activity_log.py`

| | |
|---|---|
| **Current responsibility** | Two-way operator surface: notify, ask, accept commands |
| **Current execution authority** | ### **Commands from Slack can trigger consequential actions** |
| **Current risk** | Prompt-injection surface; **`ops_control.py` carries 5 hardcoded `tenant="default"` sites** |
| **Canonical destination** | Notification adapter ([`13-notification.md`](../specifications/adapters/13-notification.md)); brake and policy admission |
| **Disposition** | ### **ADAPT** |
| **Target phase** | **P7** (the tenant finding) → **P8** (brake/policy admission) |
| **Compatibility requirement** | A channel message may never itself be authority — it carries a request, not a grant |
| **Deletion condition** | Not deleted — adapted |
| **Evidence required before deletion** | No hardcoded tenant; all commands pass policy admission |

## S10 — Knowledge and memory

**Modules:** `knowledge.py` · `agent_memory.py` · `tool_permissions.py`

| | |
|---|---|
| **Current responsibility** | Store learned operational knowledge and agent memory |
| **Current execution authority** | Informs decisions; does not act |
| **Current risk** | ### **Hardcoded `tenant="default"` — a different store, outside the seven-table scope.** It is exactly the pattern P2 forbids, recorded rather than found later. |
| **Canonical destination** | Tenant-scoped, provenance-carrying knowledge with authority classes |
| **Disposition** | ### **REWRITE** |
| **Target phase** | **P7** |
| **Compatibility requirement** | Existing knowledge rows need an owner assertion before they can be tenant-assigned |
| **Deletion condition** | A canonical tenant reaches `KnowledgeBase` and no `"default"` remains |
| **Evidence required before deletion** | A guard proving no hardcoded tenant in any knowledge write |

## S11 — Adapters and external clients

**Modules:** `tms_adapter.py` · `mock_tms.py`

| | |
|---|---|
| **Current responsibility** | Talk to the TMS |
| **Current execution authority** | `tms_adapter.py` reads; `mock_tms.py` is a fixture |
| **Current risk** | Predates the adapter contract; capability is not declared |
| **Canonical destination** | [`adapters/02-tms.md`](../specifications/adapters/02-tms.md) contract |
| **Disposition** | ### **ADAPT** (`mock_tms.py`: **KEEP** — test fixture) |
| **Target phase** | **P4** |
| **Compatibility requirement** | Each operation declares action class, effect class and verification mode |
| **Deletion condition** | Not deleted — adapted |
| **Evidence required before deletion** | The adapter registry matches the implementation exactly |

## S12 — Pilot, onboarding and operational tooling

**Modules:** `pilot_session.py` · `owner_onboarding.py` · `first_design_partner.py` · `design_partner_package.py` · `teammate_health.py` · `run_diagnostics.py`

| | |
|---|---|
| **Current responsibility** | Stand up and monitor a pilot deployment |
| **Current execution authority** | Orchestrates sessions; no direct money effects |
| **Current risk** | Encodes the **pre-reset** pilot model and the superseded product framing |
| **Canonical destination** | Re-derived from the P11 shadow-mode and P12 supervised-effect gates |
| **Disposition** | ### **QUARANTINE** |
| **Target phase** | **P11** |
| **Compatibility requirement** | Must not be presented as the current pilot model — it describes the superseded one |
| **Deletion condition** | P11 shadow mode defines the pilot canonically |
| **Evidence required before deletion** | The G6/G7 gate records |

## S13 — Infrastructure and configuration (architecture-neutral)

**Modules:** `config.py` · `atomic_io.py` · `__init__.py`

| | |
|---|---|
| **Current responsibility** | Configuration loading and atomic file I/O |
| **Current execution authority** | None |
| **Current risk** | None identified |
| **Canonical destination** | Unchanged |
| **Disposition** | ### **KEEP** |
| **Target phase** | — |
| **Compatibility requirement** | — |
| **Deletion condition** | **N/A — architecture-neutral.** This is the only category where a module survives without a phase, and it is restricted to genuine infrastructure with no execution authority. |
| **Evidence required before deletion** | — |

## S14 — Tests protecting legacy behaviour

**Scope:** the non-guard test suites under `eval/` that assert the pre-reset runtime's behaviour.

| | |
|---|---|
| **Current responsibility** | Protect current behaviour |
| **Current risk** | ### **A test asserting a behaviour the architecture forbids is a defect with a passing status.** It will resist the rewrite and look authoritative while doing so. |
| **Canonical destination** | The canonical acceptance suites |
| **Disposition** | ### **ADAPT** — replaced case-by-case as each subsystem is rewritten |
| **Target phase** | with the subsystem each defends |
| **Compatibility requirement** | ### **Replaced, never blindly preserved, and never merely deleted** — the replacement must assert what is now true |
| **Deletion condition** | The canonical acceptance case covering the same behaviour is green |
| **Evidence required before deletion** | The replacing case named in the phase review |


## S15 — Operator entry-point scripts (`scripts/`, 53 files)

**Every production-relevant script resolves to exactly one disposition below**, grouped only where
scripts genuinely share responsibility, authority, target phase and deletion condition. Coverage is
machine-checked against the filesystem, same as `src/` — a new script cannot arrive undispositioned.
The effect-capable subset is authoritative in
[`effect-entry-point-cutover-plan.md`](effect-entry-point-cutover-plan.md) and the baseline
manifest; this section must agree with them, and S2 above remains the risk narrative for that
subset.

### S15a — Effect-capable entry points ⛔ (the S2/R-07 set) — **DELETE / ADAPT / MAKE_READ_ONLY at P4**
**DELETE — EXECUTED at P4 (physically deleted; rollback does not restore them):** enter_truckingoffice_invoice.py (EP-6) · enter_invoice_discovered.py (EP-7) · run_operate_request.py (EP-9) · run_operator_agent.py (EP-10). These four are gone from `scripts/`; the effect-path guard proves their on-disk absence and the import gate's violation surface dropped from 12 edges to 5.

**QUARANTINE — now structurally earned (P4 containment checkpoint, finding F1):** `scripts/enter_tms_payable.py` (EP-12) and `scripts/run_dogfood_pilot.py` (EP-13) are test-only, mock-guarded fixtures. EP-12's former `--browser` path (a live `BrowserUseWriteLedger` against an operator-supplied base URL) was **removed**; both importers now import no live-reaching effect-capable adapter and construct only `MockTmsWriteLedger`, proved by AST (not by a substring) in `test_import_gate.py`.

**CUT at U4.7 (P4, this session):** `scripts/orient_tms.py` (EP-8, **MAKE_READ_ONLY** — DONE). It holds a `ReadOnlyCdpObserver` [[cdp_readonly]] and imports no adapter module at all, so it is structurally read-only rather than read-only by convention. The earlier note that this "needs a read-only navigator" assumed the pre-F2 world; F2 built the read substrate, and `cdp_readonly` is not an adapter module, so the cut added no adapter-import edge anywhere. The per-section walk and record action-menu expansion, which need clicks, are **retained** in `system_orientation.orient_system`/`orient_record_actions` for the authorized actuator-capable caller behind the effect boundary — a real capability with a documented future, put out of EP-8's reach rather than deleted.

**Still present — DEFERRED to a subsequent session (they keep R-07 OPEN):** `scripts/run_action_callback_server.py` (EP-1, **ADAPT** → pipeline client; its cdp_actuator import feeds the OperationRouter→OperatorAgent autonomous browser WRITE — the live R-07 write — a P12-scale integration) · `scripts/propose_ar_from_tms.py` (EP-3, **ADAPT** → pipeline client; reads + one nav-click, now unblocked by the F2 read-only CDP surface) · `scripts/read_tms_browser_use.py` (EP-14, **MAKE_READ_ONLY** — the earlier "blocked" ground is re-adjudicated in `phase-0-baseline-manifest.yaml`: `browser_use_write` is already a registered effect-capable adapter name with no file behind it, so relocating `BrowserUseWriteLedger` into that reserved slot occupies a destination canonical authority already authorized rather than adding a new module, and swaps one intra-adapter composition edge for another rather than growing the surface). These three were NOT done blind (CLAUDE.md §9).
Deletion condition: EP-6/7/9/10 physically deleted (**done**), the import gate ON and `effect_adapter_import_gate.violation_edges` empty (**not yet** — **four** residuals remain after the P4 containment checkpoint cut the brain_runtime edge).

### S15b — Browser/TMS discovery and drive tooling — **ADAPT at P4**
`scripts/discover_tms_screen.py` · `scripts/drive_real_tms.py` · `scripts/validate_screen_map.py` · `scripts/record_tms_observation.py` · `scripts/read_mock_tms.py`
Operator tooling over the browser/TMS surface (S1). Adapted behind the adapter boundary with it; no independent deletion condition.

### S15c — Containment evidence producers — **RETAIN (canonical)**
`scripts/verify_readonly_cdp.py`
The F2 live-browser proof: drives `cdp_readonly.ReadOnlyCdpObserver` against a headless Chrome showing the repository's own generated mock TMS, confirms real observation works, and confirms every actuation method and every unvetted script is refused **against a real browser** rather than a fake transport. It is an EVIDENCE PRODUCER, deliberately outside the canonical suite: the clean-clone gate has no Chrome, and a guard that must be skipped there is silence, not a pass. It performs no external writes — it launches its own browser in a throwaway profile against a local file server. Retained for as long as the read-only surface exists; no deletion condition.

### S15c — Mailbox, Slack and channel runners — **ADAPT at P4 (outbound gating) → P13**
`scripts/pull_imap_mailbox.py` · `scripts/run_mailbox_intake.py` · `scripts/run_mailbox_workflow.py` · `scripts/run_gmail_to_slack_dogfood.py` · `scripts/run_gmail_to_slack_loop.py` · `scripts/discover_gmail_freight.py` · `scripts/propose_operation_to_slack.py` · `scripts/deliver_review.py` · `scripts/dispatch_review.py` · `scripts/apply_review_action.py` · `scripts/submit_signed_action.py` · `scripts/slack_probe.py` · `scripts/verify_channels.py` · `scripts/generate_follow_up_draft.py`
Runners over S6/S8/S9. Outbound sends are external effects and gate at P4; the review/approval surfaces they drive are REWRITE at P8.

### S15d — Legacy pipeline runners (pre-reset dogfood spine) — **ADAPT with their subsystems (P6–P8)**
`scripts/run_ingestion.py` · `scripts/run_extraction.py` · `scripts/run_reconciliation.py` · `scripts/run_workflow.py` · `scripts/run_review.py` · `scripts/run_teammate.py` · `scripts/run_diagnostics.py` · `scripts/generate_daily_summary.py` · `scripts/check_tool_permission.py`
CLI fronts for S3/S5/S7/S8/S10. They carry no authority of their own and follow their subsystem's disposition; they write only to gitignored workspace paths.

### S15e — Synthetic corpus and fixture generation — **QUARANTINE**
`scripts/generate_realistic_corpus.py` · `scripts/generate_email_corpus.py` · `scripts/generate_mock_tms.py` · `scripts/generate_packet_pages.py` · `scripts/generate_sample_invoice.py` · `scripts/download_public_freight_templates.py`
Pre-reset fixture tooling. Retained for evidence and test-fixture regeneration; excluded from every production path; superseded for approval purposes by the canonical acceptance suites.

### S15f — Pilot and onboarding runners — **QUARANTINE at P11** (with S12)
`scripts/run_first_design_partner.py` · `scripts/run_internal_pilot_session.py` · `scripts/run_sunday_readiness.py` · `scripts/verify_design_partner_package.py` · `scripts/verify_first_design_partner_slack.py` · `scripts/verify_owner_onboarding.py`
Encode the pre-reset pilot model. Same deletion condition as S12: P11 shadow mode defines the pilot canonically.

### S15g — Migration and control-plane tooling — **KEEP**
`scripts/migrate_phase2_tenant_first.py` (the canonical P2 migration CLI — forward-only, same standing as `migrations/`) · `scripts/migrate_phase3_checkpoint.py` (the canonical P3 checkpoint-schema migration CLI — create-only, idempotent, refuses non-canonical inputs; same standing) · `scripts/finalize_status.py` (THE canonical end-to-end finalizer — executes the suite, the clean-clone gate and the acceptance gates itself; the only writer of status) · `scripts/update_current_status.py` (superseded shim — refuses to run, points at the canonical finalizer; kept so no second finalization route can quietly revive) · `scripts/regenerate_test_manifest.py` (the explicit, intentional node-manifest regeneration — never automatic) · `scripts/run_canonical_suite.py` (the only producer of `SUITE-RESULT.json`) · `scripts/suite_result.py` (the shared artifact validator — one definition for runner, finalizer and guard) · `scripts/check_env.py` (the fail-fast Python-floor check; runs before any install) · `scripts/clean_clone_gate.py` (the clean-clone reproducibility gate) · `scripts/mutate_phase3_guards.py` (the P3 mutation battery — **both** the guard battery M1–M8 and the kernel battery K1–K11 added by the P3 findings remediation, which mutates `checkpoint.py`, `workflow.py`, the P3 migration and the recorded rebaseline anchor; evidence infrastructure, never imported by runtime; holds originals **in memory**, purges `__pycache__` around every mutation and asserts byte-for-byte restoration, so it never uses `git checkout`/`restore`/`stash`/`clean`; supports programmatic mutators for changes a find/replace cannot express, such as the canonical step-6/7 swap; extend it rather than adding a second mutation route) · `scripts/mutate_phase4_boundary.py` (the P4 boundary mutation battery — mutates `effect_boundary.py` and the import gate in `import_probe.py`, plus a CREATE mutator that resurrects a deleted effect path to prove the deletion is guarded; same in-memory save/restore, `__pycache__`-purge and byte-for-byte restoration doctrine; evidence, not adjudication) · `scripts/mutate_roadmap_completeness.py` (the roadmap-completeness mutation battery — reintroduces each control defect the roadmap guard exists to catch: an executing phase described as not started, a navigation heading contradicting the registry, R-07 declared contained, a dropped W-loop or cross-cutting P13 sub-unit, a decomposition that quietly starts P13, a capability marked IMPLEMENTED with no evidence, the Operator promoted to a workflow source of truth, a lost capability area, and the four-versus-five edge drift; same in-memory save/restore, `__pycache__`-purge and byte-for-byte restoration doctrine, and it REFUSES to run unless the guard is green first) · `scripts/progress_status.py` (the mechanical founder-progress derivation + finalizer-rejection validator for BUILD-STATUS.yaml, U-REBASELINE-1) · `scripts/report_legacy_commit_identities.py` (read-only Phase-1 evidence probe)
KEEP is justified here exactly as in S13: canonical Phase 0–2 output or architecture-neutral control tooling with no external-effect capability.


---

## Summary

| Disposition | Subsystems |
|---|---|
| **KEEP** | S13, S15g (+ canonical members of S4, S11) |
| **ADAPT** | S1, S5, S6, S9, S11, S14, S15b, S15c, S15d (+ S4) |
| **REWRITE** | S3, S7, S8, S10 |
| **MAKE_READ_ONLY** | parts of S2/S15a (EP-8, `read_tms_browser_use`), outbound paths in S6 |
| **QUARANTINE** | S12, S15e, S15f (+ `mock_tms_write_server.py`, the EP-12/EP-13 test-only entry points) |
| **DELETE** | S2/S15a (EP-6, EP-7, EP-9, EP-10) |

> ### **No subsystem is KEEP because it is large or tested.** The two largest modules in the
> repository — `action_callback.py` (1964 lines) and `workflow.py` (1157) — are **REWRITE** and
> **ADAPT** respectively. `workflow.py` is the most heavily guarded code here, and it still does not
> survive P6 in its current form.

**Nothing in this document authorises deleting production code today.** Each deletion condition
belongs to its target phase, and the current approved unit is `U-HANDOFF-1`.

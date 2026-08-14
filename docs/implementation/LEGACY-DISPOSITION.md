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

**Modules:** `tms_write.py` · `truckingoffice_write.py` · `discovered_write.py` · `multistep_write.py` · `cdp_actuator.py` · `cdp_session.py` · `browser_use_adapter.py` · `browser_use_write.py` · `browser_lock.py` · `browser_session_health.py` · `browser_failures.py` · `browser_learning.py` · `mock_tms_write_server.py`

> **`browser_use_write.py` (added P4/U4.10, EP-14) carries the same S1 disposition as the rest of this section.** It is not new capability — it is the effect-capable half of `browser_use_adapter.py`, relocated into the slot the frozen phase-0 inventory had already reserved for it, so that the read half could be proved structurally read-only. It holds `BrowserUseWriteLedger` (intact, retained for its documented P12 future) and `NativeBrowserUseRunner` (which runs an **arbitrary** browser-agent task, and is therefore an actuation primitive wherever it lives). `effect_boundary` is the only permitted application route to it; nothing imports it yet. It mints no authority: it cannot create or extend a grant, witness, approval or claim, and it does not import `ExecutionCapability`. See the U4.10 cut note in §S15a.

| | |
|---|---|
| **Current responsibility** | Drive a real browser against a live TMS and commit real money effects |
| **Current execution authority** | ### **NONE. They act on import and call.** No checkpoint, no witness, no grant. |
| **Current risk** | ### **R-07 — CONTAINED (recorded at P4).** Still the highest-consequence subsystem in the repository: containment is a structural bound on how these modules can be reached, not a clean bill of health. Every external effect must pass the ADR-004 effect boundary; the effect-capable violation surface is EMPTY (0 live / 0 recorded edges, agreeing both-sided); the CI import gate fails the build if a second effect-capable importer appears. ### **CONTAINED IS NOT ENABLED** — no production write is enabled, the production `GateRegistry` population stays EMPTY until U8.1 / P8, and no autonomy was granted |
| **Canonical destination** | Adapter boundary contracts ([`adapters/02-tms.md`](../specifications/adapters/02-tms.md), [`10-browser.md`](../specifications/adapters/10-browser.md)) behind ADR-004's effect boundary |
| **Disposition** | ### **ADAPT** — converted to grant-and-witness-gated adapters (`mock_tms_write_server.py`: **QUARANTINE**, test-only) |
| **Target phase** | **P4** — executed and adjudicated; P4 is COMPLETE and the routing cutover landed |
| **Compatibility requirement** | None. There is no supported path that writes without a grant. |
| **Deletion condition** | The U4.9 CI import gate is ON and `adapter_import_allowlist.edges` is empty — ### **MET at P4** (the gate asserts EMPTY). Deletion itself remains a later-phase act; a met condition is not an instruction to delete today |
| **Evidence required before deletion** | Every effect routed through a claimed grant + fresh witness; orphan-adapter detection live at Sev-0; `adapter-boundary-acceptance.md` green |

> **SUPERSEDED, kept verbatim so the old wording is recognisable if it ever returns.** Until the
> R-07 closure content commit the `Current risk` row above read: *"R-07 — OPEN, NOT CONTAINED. This
> is the highest-risk subsystem in the repository."* That was true when written and is **not** a
> live statement now — R-07 is recorded `CONTAINED` in
> [`phase-0-baseline-manifest.yaml`](phase-0-baseline-manifest.yaml). The `Target phase` row read
> *"P4 (requires P3's witness to exist first)"* and the `Deletion condition` row was unmarked; P3's
> witness exists, P4 is COMPLETE, and the condition is MET.

> **These modules are the reason `PRODUCT.md` §19 exists.** They work, they are proven live, and
> they are the single largest source of unbounded consequence in the system. What changed at P4 is
> that the consequence is now reachable **only** through the effect boundary — not that it is small.

## S2 — Effect-capable entry-point scripts ⛔

**Modules:** `scripts/orient_tms.py` (EP-8) · `scripts/enter_tms_payable.py` (EP-12, test-only) · and the remaining effect-reachable scripts inventoried in [`effect-entry-point-cutover-plan.md`](effect-entry-point-cutover-plan.md). **P4 executed the DELETE disposition on EP-6/7/9/10 — enter_truckingoffice_invoice, enter_invoice_discovered, run_operate_request and run_operator_agent are physically gone (see S15a).**

| | |
|---|---|
| **Current responsibility** | Operator-invoked live writes, bypassing every review surface |
| **Current execution authority** | ### **Full, ungated.** EP-8 was *"read-only by convention, actuator-capable by import"* |
| **Current risk** | ### **CUT at P4.** The P0 baseline finding — *"6 of these are production-reachable; the only mitigation is operator discipline"* — is **SUPERSEDED as a live statement** and retained as the finding of record. EP-6/7/9/10 are physically deleted, EP-3/EP-8/EP-14 are structurally read-only, and EP-1's write half is routed through the governed effect boundary. Operator discipline is no longer the mitigation, which matters because ### **discipline was never a mechanism** |
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

**Modules:** `effect_boundary.py` · `cdp_readonly.py` · `freight_operations.py` · `governed_approval.py` · `governed_write_route.py`

> ### **`freight_operations.py` and `governed_approval.py` are the P4 EP-1 governed-write contract — canonical, not legacy.**
> `freight_operations.py` is the **typed, bounded** `InvoiceWriteOperation`: identity and human-approved
> DATA only, drawn from a closed `FreightOperationClass` enum and an `APPROVED_FIELD_KEYS` allowlist, with
> **no field for a task, selector, URL, JavaScript or adapter method** — the shape is the containment, and
> the amount is a material fact, never part of the Commit Key. It imports no adapter and no effect
> machinery. `governed_approval.py` turns a raw Slack tap into a **recorded, single-use, HMAC-bound**
> `GovernedApproval` that advances the governed pipeline; it **records the decision and never invokes the
> actuator**, mints no grant/witness/claim, and imports no adapter. The consequential write happens later,
> only through `effect_boundary.execute_invoice_write` behind the checkpoint/witness/grant/claim chain, and
> it ships **dark** (no production caller; a non-sandbox target is refused before any claim). Proven by
> `eval/tests/test_governed_approval_binding.py` and `eval/tests/test_p4_governed_invoice_write.py`.

> ### **`governed_write_route.py` is the PRODUCTION JOIN between the decision half and the effect
> half — canonical, not legacy. It exists because the independent hostile review (F-01) found there
> was no join at all.**
> The review established that `build_checkpoint_approval` had **zero callers anywhere** and that
> `GovernedWriteIntentQueued` had **no consumer**, so the authenticated-decision half and the
> effect-execution half shared no authority lineage and the required chain did not exist as code.
> This module IS that chain: it verifies the authenticated decision, records it once, consumes the
> queued intent through an **atomic, tenant-scoped consumer claim**, calls `build_checkpoint_approval`
> to map the human's `GovernedApproval` onto the kernel's `ApprovalRecord`, runs the seven-step
> checkpoint (witness + grant in one transaction), and drives claim -> typed `AdapterOperation` ->
> adapter -> readback -> explicit outcome -> evidence or governed escalation.
> **ONE identity lineage:** the `approval_id` and `actor_id` the human's signed tap carried are the
> ones on the `ApprovalRecord`, the checkpoint witness row, the Effect Grant row and the typed
> operation the adapter receives. It imports **no adapter, no browser session and no actuator** (the
> effect boundary is imported lazily and is the only door), registers no credentialed adapter, and
> has **no fallback** to `OperatorAgent` or `CdpActuator`.
> **It ships DARK:** the default bounded writer performs no real external write (a proven
> non-occurrence), and a non-sandbox operation is refused before any claim. Live supervised writes
> are P12. Proven by `eval/tests/test_p4_governed_write_route.py`.
>
> ### **AD-01 CORRECTION — THE DEPLOYED WIRING, STATED EXACTLY.** The superseded sentence read
> *"unwired at the entry point … `run_action_callback_server.py` leaves
> `governed_write_provider`/`governed_write_kernel` as `None`"*. That **misstated** the wiring and is
> the finding recorded as **AD-01**. What the entry point actually does: the **lookup boundary is
> WIRED** — it passes a real `provider` closure resolving an *already-authorized* pending write
> through `WorkflowStorePendingWrites` with `writer=None` (the boundary's dark default bounded
> writer), failing **closed** on any lookup error. The **execution kernel is what remains `None`**
> (`kernel_factory = None`), deliberately: a `CheckpointKernel` cannot be constructed without a
> `GateRegistry`, and Action Class gate registration is **U8.1 / P8** work (`AC-CKPT-6-missing`,
> `DEFERRED_BY_DEPENDENCY`). The governed handler therefore answers a recorded
> `ROUTE_NOT_CONFIGURED` refusal. Resolving a pending typed operation *end to end* still needs the
> P6 Work Item / Pipeline Instance entities, and a callback that could BUILD the operation could
> choose its amount, counterparty and target. **The fail-closed conclusion is unaffected — only the
> description was wrong, and the stale "provider is `None`" prose must not reappear.** Guarded by
> `eval/tests/test_p4_deployed_governed_route.py`.

> ### **`governed_write_registry.py` is the MINIMUM BOUNDED REPOSITORY that makes the deployed
> entry point reachable — canonical, not legacy.**
> It answers the last open half of F-01: the governed chain existed, but *before this module*
> `run_action_callback_server.py` left its provider and kernel `None`, so no operator-runnable
> configuration ever touched it. **That is the PRE-remediation state, not the deployed one** — the
> provider is now WIRED and only the execution kernel remains `None` (see the AD-01 correction
> above). The obstacle was authority, not plumbing — a callback that could
> BUILD the typed operation could choose its amount, counterparty, load, destination system,
> adapter and capability, which is exactly what permanent human authority forbids. So the operation
> is written down when it is **proposed**, and the callback may only **look it up**:
> **the callback supplies identity; the repository supplies the operation.**
> `PendingGovernedWriteRepository` is the authority boundary and has exactly ONE method — a lookup.
> There is deliberately no create/edit/complete an authenticated tap could reach for.
> **It stores nothing new.** It reuses the established pattern of
> `thread_reply.find_resumable_operation`: identity and the non-money approved fields go to the
> durable `GovernedWriteOperationProposed` security event, while the approved AMOUNT goes to the
> dedicated `operation_token_amounts` table and is re-read from there — **memory and logs never
> store a money value** (CLAUDE.md §10). Reconstruction is then checked against the `payload_hash`
> recorded at proposal time, which is the same hash the human's signature binds, so a tampered row
> cannot yield a different operation — only no operation.
> **`WorkflowStorePendingWrites` is a STORAGE DETAIL, not authority.** A later phase may replace it
> with real Work Item / Pipeline Instance entities, Postgres or an outbox **without changing the
> authority boundary**; this is explicitly NOT an implementation of P6.
> It imports no adapter, no browser session, no actuator and not even the effect boundary, and it
> injects **no writer** (`writer=None`), so the deployed default remains the boundary's own bounded
> writer, which performs no real external write. Proven by
> `eval/tests/test_p4_deployed_governed_route.py`.
>
> **Stated limitation, not hidden:** until P12, the material-fact readers perform a live read of
> *this repository's own recorded proposal*, not of the external authoritative source, so the
> checkpoint's drift barrier is not yet a true external-world barrier. That is one of the reasons
> the route must stay dark, and replacing that one method changes no other part of the boundary.

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
| **Current execution authority** | ### **None yet routed in production.** The boundary exists and is acceptance-proven; it ships dark alongside the kernel. The P4 containment checkpoint added the F4 outcome-safety (a generic post-attempt exception → UNKNOWN_OUTCOME), implemented and mutation-proved the orphan detective sweep mechanism (`run_detective_sweep` is its per-cycle invocation surface — no production/runtime caller exists yet; production scheduling is deferred to P11 and the boundary still ships dark), and cut the `brain_runtime → tms_write` edge (its effect executor is now injected, not imported). **EP-1's write is now cut too:** the callback constructs no live actuator and the only external-write path is the typed, dark `execute_invoice_write`. It authorises nothing until an adapter operation is registered and called — which has no production caller |
| **Current risk** | ### **R-07 is CONTAINED — recorded, not merely mechanically met.** The boundary is built, green, and the effect-capable violation surface is **EMPTY** (0 live / 0 recorded edges agreeing both-sided; EP-1/EP-3/EP-8/EP-14 all cut, `brain_runtime` rewired), so no ungated effect-capable path exists beside the boundary. The two-key discipline was then satisfied in full **by other sessions**: a fresh independent re-review and a **separate** final adjudication recorded P4 COMPLETE at 14/14; a targeted independent review and a **separate** targeted adjudication accepted the acceptance-closure candidate; two finalizers ran; and only then did a later content commit write `status: CONTAINED` into `phase-0-baseline-manifest.yaml` with the mechanism named. ### **CONTAINED IS NOT ENABLED** — no production write is enabled, the production `GateRegistry` population stays EMPTY until U8.1 / P8, and no autonomy was granted |
| **Canonical destination** | This IS the canonical containment boundary (ADR-004 two-key rule); the import gate makes bypassing it structurally impossible, and the violation list is now EMPTY with the gate asserting empty |
| **Disposition** | ### **KEEP** — canonical, forward-only. `ExecutionCapability` stays unconstructable/unforgeable/single-use; UNKNOWN_OUTCOME may never be silently downgraded to FAILED or retried |
| **Target phase** | Implemented and **adjudicated** at **P4**; the routing cutover landed and R-07 is recorded CONTAINED |
| **Compatibility requirement** | No second effect-execution path may exist beside it; every adapter effect flows through `execute_effect` |
| **Deletion condition** | Not deletable — no permanent second effect-authority system may exist beside it |
| **Evidence required before deletion** | n/a |

## S4d — Phase-5 durable event transport *(canonical, not legacy — recorded here so coverage stays total)*

**Modules:** `event_envelope.py` · `event_outbox.py` · `event_inbox.py` · `migrations/phase5_event_transport.py`

> ### **P5 U5.7 + U5.8 — the first RUNTIME capability in P5.** Everything P5 landed before this was
> specification and control. This is the mechanism behind two slogans: I10 ("never taken and
> unrecorded") becomes `UPDATE machine_state` + `INSERT INTO event_outbox` in ONE commit (M-23),
> enforced rather than instructed — `TransactionalOutbox.emit` REFUSES to run outside an open
> transaction, so there is no supported way to write an event in a commit of its own. And
> "consumers must be idempotent" becomes `UNIQUE (tenant, consumer_id, event_id)` with processing
> and inbox-insert in one commit (M-24), so a redelivery is a no-op by construction rather than by
> the care of whoever wrote the handler.

| | |
|---|---|
| **Current responsibility** | The canonical event envelope and its `ev_v1` serialization; the transactional outbox and its aggregate-leasing relay; the dedup inbox, its per-aggregate ordering cursor, and M-26 parking of dangling references with arrival order and a TTL |
| **Current execution authority** | ### **None. It ships dark.** The relay has no default sink and refuses construction without an explicit `publish` callable; the modules import no adapter and no network client; consuming an event mints **zero** checkpoint witnesses and **zero** effect grants. An event is a FACT and never authority (CLAUDE.md rule 9) |
| **Current risk** | Low, and bounded by having no caller: nothing in the repository emits or consumes a canonical event yet. The residual risk is scope, not safety — *(corrected at U5.3: the 105 contracts now EXIST, see S4e; the GC-1 digest (U5.4), replay isolation (U5.5), audit reconstruction (U5.6) and ADR-016's PostgreSQL store are still absent)*, so this runs on SQLite only |
| **Canonical destination** | This IS the canonical destination (ADR-008 §2.5/§2.6, M-23..M-26); U5.3 supplies the contracts that travel through it, P6 supplies the machines that emit into it |
| **Disposition** | ### **KEEP** — canonical, forward-only. The outbox envelope columns and the inbox rows are append-only **in the database** (triggers, not convention); that immutability may never be relaxed, and `emit` may never gain a parameter that lets it run outside a transaction |
| **Target phase** | Implemented at **P5** (U5.7+U5.8); consumed by **U5.3** and **P6+** |
| **Compatibility requirement** | The dedup key stays `(tenant, consumer_id, event_id)`; the ordering key stays `(tenant_id, aggregate_id, aggregate_version)`; the Commit Key never enters either — it identifies an EFFECT and lives in one ledger (ADR-009, rule 8) |
| **Deletion condition** | Not deletable — no permanent second event-delivery system may exist beside it |
| **Evidence required before deletion** | n/a |

## S4e — Phase-5 canonical event contracts *(canonical, not legacy — recorded here so coverage stays total)*

**Modules:** `event_contracts.py` · `event_contracts_data.json` *(data, not code)*

> ### **P5 U5.3 — what makes `event_name` mean something.** U5.7+U5.8 built a transport that could
> carry any well-formed envelope; `event_envelope.py` says so in its own docstring ("no name
> whitelist here, no per-event payload schema, and no upcaster: those are U5.3's"). Until this
> landed, an envelope naming `Vibes` was *shaped* like a canonical event and was not one. These
> modules are the check: **118 contracts — 105 machine-emitted (F1–F13, "the 105") and 13
> audit/security (F14)** — with identity, producer-transition attribution, aggregate binding,
> payload contract, decision-context pins and actor authority (ER-9/10/11/12) all enforced before
> a fact may be committed or consumed.

| | |
|---|---|
| **Current responsibility** | The canonical contract registry and its validator; the `vN→vN+1` upcaster registry applied ON READ (§6); the two validation modes §6 requires — PRODUCER refuses an undeclared payload field, CONSUMER ignores one |
| **Derivation, not transcription** | ### **`event_contracts_data.json` is GENERATED** by `scripts/generate_event_contracts.py` from `events/registry.md` §3/§5/§8 and the F1–F14 family files. `events/registry.md` remains "the sole canonical list of event names and versions" (§6); this is its mechanical projection. `test_p5_event_contracts.py::test_the_generated_contract_data_is_exactly_what_the_specification_derives` re-derives it on every run, so a specification edit without a regeneration fails the build rather than serving stale contracts |
| **Current execution authority** | ### **None. A validated event is a well-formed FACT and is never authority** (CLAUDE.md rule 9). Consuming the entire 118-contract corpus mints **zero** checkpoint witnesses and **zero** effect grants, asserted mechanically. The modules import no adapter, no network client and no sibling runtime module |
| **The gate vocabulary it names** | One contract's payload fixes a gate-decision value (PL-7a's — **ADR-010's** typed gate ladder), because that event exists to RECORD which decision admitted autonomous work. ### **THE CORPUS IS HELD AS JSON, AND THAT IS WHY NO SAFETY GUARD CHANGED.** An earlier candidate emitted a `.py` module and amended `test_phase0_null_gate.py` to permit it as a "declaration site" behind an AST proof; an independent review defeated that proof with a module-level `if` that assembles a policy decision at import time using no function, class or call. JSON cannot execute, the Phase-0 confinement guard scans `*.py`, and so that guard keeps its ORIGINAL kernel-only rule, byte-unchanged. No Python module in this unit names a gate value |
| **Current risk** | Low, and bounded by having no production emitter: nothing in the repository emits a canonical event yet, so the contracts govern a corpus the transport battery produces. The residual is scope, not safety — U5.4's GC-1 digest, U5.5's replay sandbox and U5.6's audit reconstruction are all still absent |
| **Canonical destination** | This IS the canonical destination for the event contracts (ADR-008, `events/registry.md`); P6 supplies the machines whose transitions will emit through it |
| **Disposition** | ### **KEEP** — canonical, forward-only. Validation may never gain a `validate=False` parameter, for the same reason `emit` has no `allow_autocommit=True`: a flag is how a guarantee gets turned off on a Friday. The upcaster's three refusals — future version, missing chain link, duplicate registration — may never degrade into a pass-through |
| **Target phase** | Implemented at **P5** (U5.3); consumed by **U5.4/U5.5/U5.6** and **P6+** |
| **Compatibility requirement** | The specification stays the single authority — no second, hand-maintained contract list may exist beside the generated one, and `strict_order` must keep agreeing with the transport's `STRICT_ORDER_AGGREGATE_TYPES` (asserted mechanically). §6's asymmetry is preserved: a producer refuses an undeclared field, a consumer ignores one |
| **Deletion condition** | Not deletable — no permanent second event-contract authority may exist beside it |
| **Evidence required before deletion** | n/a |

## S4f — Phase-5 replay, the golden corpus, and audit reconstruction *(canonical, not legacy)*

**Modules:** `event_replay.py` · `event_audit.py`
**Fixture:** `eval/fixtures/gc1-corpus.json` + `gc1-pinned-digests.json` · **Builder:** `scripts/build_gc1_corpus.py`

> ### **P5 U5.4+U5.5+U5.6 — ONE increment, because the acceptance spec makes them one.**
> `AC-EVT-007`'s oracle is *"replay `GC-1` ⇒ 0 witnesses, 0 grants, 0 adapter calls"* and
> `AC-EVT-008`'s is *"`GC-1` ⇒ the SAME projection DIGEST"*: the corpus cannot be validated without
> a replay and the replay cannot be tested without the corpus. Splitting them into three
> certification campaigns would have meant building a fixture whose oracle cannot run, then a
> replay with nothing to replay.

| | |
|---|---|
| **Current responsibility** | Reconstructing operational truth from canonical facts: the deterministic per-aggregate fold, the pinned `GC-1` rebuild oracle, rebuild-vs-live divergence detection shaped to `ProjectionRebuildDiverged`, and `explain()` reconstructing the eighteen audit fields from beliefs-of-that-day |
| **Current execution authority** | ### **NONE, STRUCTURALLY — and that is the whole design.** M-27 requires replay to be side-effect free *structurally*, so the import CLOSURE of `event_replay` + `event_audit` reaches no adapter, no effect boundary, no checkpoint kernel, no brake store, no `WorkflowStore`, no network client. `replay()` takes no connection and has no write surface; `explain()` takes no store, which is the mechanism behind `AC-AUD-002`. A module that cannot reach the capability cannot use it |
| **Determinism** | The fold is ordered by §8's ordering key — ascending `aggregate_version`, tie-broken by `event_id` — so the reconstruction is a pure function of the SET of events. A shuffled corpus yields the identical digest, and the suite shuffles it. ### **An earlier fold applied fields in ARRIVAL order**, so the same history delivered differently rebuilt to a different digest and the pinned oracle would have pinned a property of one delivery |
| **Redelivery** | A repeated `(tenant, event_id)` is ignored and counted (`duplicates_ignored`), matching §1's dedup identity and the inbox's own key. ### **An earlier fold counted it twice**, so a duplicate delivery reconstructed a history that never happened |
| **Current risk** | Low, and bounded by having no production caller: nothing schedules a rebuild or a divergence sweep. `compare_to_live` RETURNS findings and never engages a brake — §11 requires `ProjectionRebuildDiverged` to auto-engage one, and F14's cross-cutting rule requires that REPLAYING a security event never re-engages one; a detector acting from inside a rebuild could not tell those apart. Same posture as P4's orphan-effect detective sweep |
| **Canonical destination** | This IS the canonical destination (ADR-008 §2.11, M-25/M-27, GR-11); P6 supplies the transition tables a machine-aware folder will apply to this same ordered history |
| **Disposition** | ### **KEEP** — canonical, forward-only. `replay()` may never gain a connection parameter and `explain()` may never gain a store: both would turn a structural guarantee back into a discipline. The pinned digest may never be re-pinned automatically |
| **Target phase** | Implemented at **P5** (U5.4+U5.5+U5.6); consumed by **P6+** |
| **Compatibility requirement** | `GC-1` is IMMUTABLE and is never reset between replay tests. Re-pinning is an explicit human act — `--check` is what CI runs |
| **Deletion condition** | Not deletable — no permanent second reconstruction path may exist beside it |
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

**CUT at U4.8 (P4):** `scripts/propose_ar_from_tms.py` (EP-3, **CONVERT_TO_PIPELINE_ENTRY_READ_ONLY** — DONE). Its browser surface is now `ReadOnlyCdpNavigator` and it imports no adapter. The evaluate-based navigation and the click fallback are both gone. The invoice write it can still trigger is not its browser surface — that runs the money-fenced OperationRouter, counted once against EP-1.

**HARDENED at U4.8b (P4, this session) — the EP-3 hostile-review obligation, discharged.** The U4.8 cut reached detail pages by "following a link the loads list itself published", and that was **not sufficient**. The obligation's premise is correct: a same-origin, page-published href is not inherently read-only, because legacy systems expose state-changing GET routes. `/loads/101/delete`, `/invoices/9/approve`, `/logout` and Rails-style `<a href="/loads/101" data-method="delete">` are all same-origin anchors a real TMS renders, and the caller chose among them by **substring-matching** the load ref against the document-wide `nav` list — so `<a href="/loads/9/purge_all">Delete L-101</a>` would have been followed. That was a live defect, not a theoretical one.

`follow()` now takes a **provenance record**, not a URL: `cdp_readonly.ObservedLoadLink` binds the observed row, the observed load identity, the exact href and the observation context, and the record is **re-derived from the live page** and must match exactly before anything is fetched. Four independent barriers — row containment; exact identity binding (link text or whole path segment, never a substring); route family (no action token in the path, no destructive token or method-override key in the query, checked on both the raw attribute and the browser-resolved URL so a `<base>` tag cannot redirect it); and anchor shape (no non-GET `data-method`, no `data-confirm`, `data-remote`, `onclick`, `download`, `formaction`, control `role`, `aria-haspopup`, or action-menu ancestry). Ambiguity refuses rather than picks. The landed URL is re-checked after the fetch, so a redirect out of the route family fails closed, and every fetch advances the observation context so a record cannot be replayed. Nothing in F2 is reopened — no evaluate, no command, no click, no caller-authored JavaScript, no generic traversal — and the provenance observation is a **vetted read script** taking the identifier as protocol DATA. **Edge counts unchanged (violations 2, detection 14):** this hardens an already-cut entry point rather than cutting a new one. Mutation battery **37/37**.

**CUT at U4.10 (P4, this session):** `scripts/read_tms_browser_use.py` (EP-14, **MAKE_READ_ONLY** — DONE). The write half moved into `browser_use_write`, the effect-capable slot the frozen phase-0 inventory had **already reserved** (present in `import_probe.ADAPTER_MODULES`, `EFFECT_CAPABLE_ADAPTERS`, `entrypoint_probe` and the manifest, with no file behind it) — so this occupies a pre-registered destination rather than inventing a module, and swaps one intra-adapter composition edge for another: `browser_use_adapter → tms_write` becomes `browser_use_write → tms_write`. **Violation edges 2 → 1; detection edges 14 → 14.**

**`NativeBrowserUseRunner` moved too, and that was the correction the earlier deferral had not anticipated.** It runs an **arbitrary** natural-language task, so it is an actuation primitive in the same sense `cdp_session.evaluate()` is — whoever hands it a task decides what happens to the page. Leaving it behind would have produced read-only *by naming*, the exact failure this disposition rejects, and the repository's own guard already knew: `test_import_gate._LIVE_WRITE_DRIVERS` listed `BrowserUseTmsAdapter` next to `CdpActuator`. It no longer does, because the class no longer reaches either.

What remains is structurally read-only on the F2 pattern: **no write API exists** on `BrowserUseTmsAdapter`; **the task is never caller-authored** (`ReadOnlyBrowserUseRunner.run_vetted` takes a task ID from the frozen `VETTED_READ_TASKS` registry plus validated data and renders the task itself — there is no method that accepts a task string); and the module **imports no effect-capable adapter** and does not import `browser_use_write`. `BrowserUseWriteLedger` is **intact**, retained for its documented P12 future — deleting a legitimate future write capability to make a P4 gate green would be a false green. Evidence: `test_browser_use_readonly_surface.py` (structural, call-closure, behavioural, relocation) plus mutation cases B31–B35, and a relocation guard that asserts the nine swap conditions mechanically rather than trusting the manifest edit.

*Honest scope, narrower than F2 on purpose:* CDP containment is protocol-level — the channel allowlists CDP **methods**, so the browser never sees an actuation. A browser-use agent has no such chokepoint; it is an LLM driving a real browser and could in principle click inside a read task. What is mechanically true is that a read-side caller cannot express a write, cannot author the task, and cannot reach the write ledger or the generic runner. The residual belongs to the browser-agent execution class and is contained by the effect boundary where a write is *attempted*.

**READ HALF CUT at U4.11 (P4, this session):** `scripts/run_action_callback_server.py` (EP-1, **ADAPT** — *partial*). Its five read closures ran over a mutation-capable session; three held a `CdpActuator` purely to call `.observe()`. Two **spliced caller data into JavaScript source** (`_JS + "(" + repr(str(load_ref)) + ")"` — F2's exact defect) and one **composed a target the page never published** (`href.rstrip("/") + "/attachments"`), navigating to it with `location.href=` — the generic traversal EP-3 had just removed, still live here. All five now run on `cdp_readonly`; the column mapping and document scrape are Python over a vetted observation, so the JavaScript is *gone* rather than escaped more carefully, and the documents page is reached through an **EP-3 provenance record**. **No edge count changed** — this removed live defects, it did not cut the violation.

**WRITE HALF CUT at U4.11 (P4) — the deferral below is DISCHARGED.** `scripts/run_action_callback_server.py` (EP-1) constructs no live actuator: AST over the file finds **0** `CdpActuator` constructions and **0** `cdp_actuator` imports, and `_build_live_operation_router` / `_build_agent` exist nowhere in `src/` or `scripts/`. `operation_router = None` unconditionally. The only external-write path is the typed, dark `execute_invoice_write` behind checkpoint → witness → grant → atomic claim, which has no production caller.

> **SUPERSEDED, kept verbatim so the old wording is recognisable if it ever returns.** This entry read: *"Still present — DEFERRED (it keeps R-07 OPEN): the same file's write half. `_build_live_operation_router._build_agent` constructs `CdpActuator` for the OperationRouter→OperatorAgent autonomous browser WRITE — the live R-07 write, a P12-scale integration. A guard now asserts that factory is the only construction site in the file, so the residual is named and cannot spread."* That described the state at U4.11's read-half cut, before the write half was cut. It is **not** a live statement: R-07 is recorded `CONTAINED` in [`phase-0-baseline-manifest.yaml`](phase-0-baseline-manifest.yaml).

> **Why the factory was not simply moved.** Any `ADAPTER_MODULES` import from a script is an edge and an effect-capable one is a violation, so the only destination that removes the edge is `effect_boundary` itself — not an adapter module, and already the gate's one exempt importer. But `effect_boundary.execute_effect` has **no production caller**; it ships dark. Moving the factory there *without* routing the write through checkpoint → witness → grant → claim → verification would take the violation count to zero while leaving an ungated live write. **That is a wrapper, and a wrapper that logs the bypass is not containment (PL-6)** — the exact false green P4 exists to prevent. The factory stays visible until the boundary integration is real. This was NOT deferred blind (CLAUDE.md §9).
Deletion condition: EP-6/7/9/10 physically deleted (**done**), the import gate ON and `effect_adapter_import_gate.violation_edges` empty — ### **MET.** The recomputed live set and the recorded set are both **empty** and agree both-sided; **zero** residuals remain.

> **SUPERSEDED, kept verbatim so the old wording is recognisable if it ever returns.** This condition read: *"…`effect_adapter_import_gate.violation_edges` empty (not yet — four residuals remain after the P4 containment checkpoint cut the brain_runtime edge)."* The four residuals named there — EP-1, EP-3, EP-8, EP-14 — were all subsequently cut. A count claim is deliberately not restated here as a number to be maintained by hand: `test_the_recorded_effect_violation_surface_is_the_mechanically_recomputed_one` recomputes it.

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
`scripts/migrate_phase2_tenant_first.py` (the canonical P2 migration CLI — forward-only, same standing as `migrations/`) · `scripts/migrate_phase3_checkpoint.py` (the canonical P3 checkpoint-schema migration CLI — create-only, idempotent, refuses non-canonical inputs; same standing) · `scripts/migrate_phase5_event_transport.py` (the canonical P5 event-transport migration CLI — create-only, idempotent, drops nothing, refuses a database that is not already Phase-2/Phase-3 canonical; same standing. It exists because `WorkflowStore` builds only an EMPTY database canonical and otherwise touches nothing, so extending a live schema stays an explicit act with a human behind it) · `scripts/finalize_status.py` (THE canonical end-to-end finalizer — executes the suite, the clean-clone gate and the acceptance gates itself; the only writer of status) · `scripts/finalizer_lock.py` (the finalizer's `flock`-based mutual exclusion — one finalizer per repository, acquired before any suite run, receipt deletion or status write; non-blocking so a second finalizer fails immediately, kernel-released on any exit so a crash never wedges the repo, and NEVER reclaimed because a log looks missing; dependency-free stdlib so it can be taken before importing anything else) · `scripts/update_current_status.py` (superseded shim — refuses to run, points at the canonical finalizer; kept so no second finalization route can quietly revive) · `scripts/regenerate_test_manifest.py` (the explicit, intentional node-manifest regeneration — never automatic) · `scripts/generate_event_contracts.py` (the P5 U5.3 canonical-contract derivation — parses `events/registry.md` §3/§5/§8 and the F1–F14 family files and emits `src/freight_recon/event_contracts_data.json`; `--check` reports staleness without writing. It exists so the runtime contracts are the specification's mechanical projection rather than a second hand-maintained list, and a guard re-derives it on every suite run so a spec edit without a regeneration fails the build. Never imported by runtime) · `scripts/run_canonical_suite.py` (the only producer of `SUITE-RESULT.json`) · `scripts/suite_result.py` (the shared artifact validator — one definition for runner, finalizer and guard) · `scripts/check_env.py` (the fail-fast Python-floor check; runs before any install) · `scripts/clean_clone_gate.py` (the clean-clone reproducibility gate) · `scripts/mutate_phase3_guards.py` (the P3 mutation battery — **both** the guard battery M1–M8 and the kernel battery K1–K11 added by the P3 findings remediation, which mutates `checkpoint.py`, `workflow.py`, the P3 migration and the recorded rebaseline anchor; evidence infrastructure, never imported by runtime; holds originals **in memory**, purges `__pycache__` around every mutation and asserts byte-for-byte restoration, so it never uses `git checkout`/`restore`/`stash`/`clean`; supports programmatic mutators for changes a find/replace cannot express, such as the canonical step-6/7 swap; extend it rather than adding a second mutation route) · `scripts/mutate_phase4_boundary.py` (the P4 boundary mutation battery — mutates `effect_boundary.py` and the import gate in `import_probe.py`, plus a CREATE mutator that resurrects a deleted effect path to prove the deletion is guarded; same in-memory save/restore, `__pycache__`-purge and byte-for-byte restoration doctrine; evidence, not adjudication) · `scripts/mutate_roadmap_completeness.py` (the roadmap-completeness mutation battery — reintroduces each control defect the roadmap guard exists to catch: an executing phase described as not started, a navigation heading contradicting the registry, R-07 declared contained, a dropped W-loop or cross-cutting P13 sub-unit, a decomposition that quietly starts P13, a capability marked IMPLEMENTED with no evidence, the Operator promoted to a workflow source of truth, a lost capability area, and the four-versus-five edge drift; same in-memory save/restore, `__pycache__`-purge and byte-for-byte restoration doctrine, and it REFUSES to run unless the guard is green first) · `scripts/mutate_phase5_contracts.py` (the P5 U5.3 contract mutation battery — 37 cases: one removing each refusal in `event_contracts.py`, the outbox and inbox contract gates, two that edit the **canonical specification itself** to prove the anti-drift guard is real, and seven that mutate the PARSER and regenerate the data — the coverage hole an independent review named, since a parser defect is inert until the data is re-derived. Same in-memory save/restore, `__pycache__`-purge and byte-for-byte restoration doctrine as the P3 and P4 batteries; evidence, never adjudication) · `scripts/build_gc1_corpus.py` (the P5 U5.4 golden-corpus builder — derives `eval/fixtures/gc1-corpus.json` and its pinned digests from real canonical contracts, validating every event as a PRODUCER would so the fixture cannot contain a fact the runtime would refuse to emit; `--check` reports staleness without writing, and is what CI runs. ### Running it WITHOUT `--check` re-pins the digest, which the acceptance oracle says a human must explain — so it is never automatic and never invoked by a test. Never imported by runtime) · `scripts/mutate_phase5_replay.py` (the P5 U5.4+U5.5+U5.6 replay/audit mutation battery — 18 cases, of which R1/R2 are the registry's MANDATED proof that replay cannot call an adapter (each adds an effect-capable import and confirms the import-closure guard goes red), and R3/R4/R11 reintroduce defects this build actually shipped: an arrival-ordered fold, a double-counted redelivery, and an audit that flattened facts across aggregates. Builder cases regenerate GC-1 because a builder mutation is inert until the fixture is rebuilt; the corpus and its pins are restored byte-for-byte. Same in-memory save/restore and `__pycache__`-purge doctrine; evidence, never adjudication) · `scripts/progress_status.py` (the mechanical founder-progress derivation + finalizer-rejection validator for BUILD-STATUS.yaml, U-REBASELINE-1) · `scripts/report_legacy_commit_identities.py` (read-only Phase-1 evidence probe)
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

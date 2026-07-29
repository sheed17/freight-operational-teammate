# P4 — REMEDIATION HANDOFF FOR A FRESH INDEPENDENT RE-REVIEW

> **This is a handoff, not a review and not an adjudication.** It was written by the REMEDIATION
> BUILDER session. It records what was changed and what was measured; it certifies nothing.
>
> ### **P4 is NOT COMPLETE. R-07 remains OPEN — NOT CONTAINED.** No finalizer was run, no status
> metadata was hand-edited, no ref was pushed, no effect was enabled, and no adjudication was made.
> A fresh independent session — one that neither implemented nor remediated this work — must review
> the candidate below before `independent_review` or `final_adjudication` may be recorded
> (CLAUDE.md §11).

---

## 0. FOUNDER DECISION — RECORDED (2026-07-29)

> ### **Production Action Class gate registration stays DEFERRED to U8.1 / Phase 8.**
>
> P4 is **NOT** authorized to register production gates for `raise_invoice`, `record_payable`, or
> any other consequential production Action Class. The frozen Phase-8 deferral is **not** revised,
> no production `GateRegistry` population is added, registrations are **not** relocated outside
> `src/` to evade repository probes, and `test_phase0_null_gate.py` and its related guards are
> **not** weakened.
>
> ### **P4's required boundary is CONTAINMENT, not production enablement.**
>
> The accepted P4 runtime shape is:
>
> ```
> authenticated callback
>   -> bounded lookup of a pre-existing typed operation
>   -> exact approval / tenant / work-item / revision / payload verification
>   -> governed execution-kernel seam
>   -> ROUTE_NOT_CONFIGURED when the Phase-8 production kernel and gates are absent
> ```
>
> The deployed route must fail closed and must never fall back to `OperatorAgent`, `CdpActuator`,
> arbitrary browser execution, direct callback writes, or caller-created amounts, counterparties,
> targets or operations. The **test environment may** supply an explicit governed kernel and gate
> registry to prove the complete authority-preserving chain; **production registration must remain
> empty until U8.1.**

### The candidate already encoded this decision — it was not modified to restate it

The decision was verified against candidate `0891d1a19a9c…` / tree `a3e704645b8a…` **as it already
stood**. No code, test, manifest or acceptance artifact was changed to satisfy it. Confirmed
mechanically:

| Check | Result |
|---|---|
| Production `GateRegistry` population | **EMPTY** — no module under `src/` constructs one |
| `AC-CKPT-6-missing` in `phase-0-baseline-manifest.yaml` | `DEFERRED_BY_DEPENDENCY - REQUIRED AT PHASE 8`, `green_at_phase: P8`, `accountable_unit: U8.1` — **byte-identical to the certified parent `f1e8e18`** |
| `phase-0-baseline-manifest.yaml` vs the rejected candidate | **IDENTICAL** — this remediation never touched it |
| `eval/tests/test_phase0_null_gate.py` vs the certified parent | **IDENTICAL** — the guard was not weakened |
| Tracked working tree vs the candidate | **UNMODIFIED** (only the two finalizer-owned files and this untracked handoff differ) |

### F-01 discharge conditions 1–7, each proven

| # | Founder condition | Proof | Result |
|---|---|---|---|
| 1 | The real deployed callback reaches the bounded provider and the kernel seam | `test_the_deployed_entry_point_wires_the_governed_route`, `test_main_passes_both_seams_into_run_callback_server` (AST — the seams must actually be passed to `run_callback_server`) | **PASS** |
| 2 | The callback cannot create or modify the typed operation | `test_callback_data_cannot_replace_operation_fields` (five hostile payloads), `test_the_repository_interface_exposes_no_constructor` (the boundary has exactly one method, a lookup) | **PASS** |
| 3 | Full checkpoint → witness → grant → claim → adapter chain, one continuous approval identity, test-supplied kernel | `test_the_full_deployed_order_carries_one_identity_to_the_dark_adapter` — `appr-deployed-1` read back from the `effect_grants` row, the `checkpoint_witnesses` row, both atomic claims and the adapter's own call log | **PASS** |
| 4 | Production absence of the Phase-8 kernel/gates returns an explicit `ROUTE_NOT_CONFIGURED` governed refusal | `test_the_blocked_route_refuses_explicitly_rather_than_falling_through` — recorded `GovernedWriteRefused`, and the pipeline never advanced | **PASS** |
| 5 | No alternate or legacy effect path reachable | `test_the_deployed_route_has_no_fallback_to_a_legacy_actuator`, `test_the_legacy_callback_to_actuator_route_remains_unreachable`, `test_the_registry_module_reaches_no_adapter` (AST imports, never substrings) | **PASS** |
| 6 | A regression test fails if production gate registration appears before U8.1 | `test_the_production_gate_registration_population_is_still_empty` **and** `test_the_typed_gate_population_is_now_non_empty_and_confined_to_the_checkpoint_kernel`, plus `test_the_execution_kernel_seam_is_blocked_pending_adjudication`. **Demonstrated, not asserted** — see below | **PASS** |
| 7 | Capability remains dark by default | `test_the_deployed_default_capability_is_dark` (deployed provider injects no writer; outcome `FAILED` / `PROVEN_NON_OCCURRENCE`), `test_a_non_sandbox_proposal_is_refused_before_any_claim` | **PASS** |

**Condition 6 was demonstrated mechanically.** A throwaway module registering
`raise_invoice` was added under `src/`, the guards were run, and **both fired**:

```
a production module now REGISTERS typed gates: _u81_probe_delete_me.py:6.
The AC-CKPT-6-missing deferral rested on the production registration population being zero.
It is not zero any more - re-adjudicate the case instead of inheriting the deferral.

a typed gate decision escaped the checkpoint kernel: policy must be evaluated at the
boundary that owns it, never carried by a workflow, adapter or callback
```

The probe was then deleted, `__pycache__` purged, the guards returned **6 passed**, and the tree
restored to `a3e704645b8a06561d90cdb5f81288309ae51850` exactly. No tracked file was touched at any
point, and no `git checkout/restore/stash/clean` was used.

---

## 1. The exact remediated candidate

| Property | Value |
|---|---|
| **Commit** | `0891d1a19a9c47155a56a3f4b2116e5a4d4aa75e` |
| **Tree** | `a3e704645b8a06561d90cdb5f81288309ae51850` |
| **Parent** | `f1e8e1893eff2460d68f3f168f18fd29635b250d` |
| Branch | `p4/adapter-containment-completion` (local, unpushed) |

The parent is the **same certified parent** the rejected candidate had, so the topology is the one
`integration-topology-procedure.md` §3 requires: **one content commit on the certified pair
boundary**, remediation folded back into it (step 3), finalization to land on top later.

Product Driver confirms it independently:

```
REPOSITORY STATE: PRODUCING — recorded content commit 3d231731b8b0 is HEAD^^,
                  HEAD^ f1e8e1893eff is a pure status-metadata commit,
                  HEAD 0891d1a19a9c is the next content commit
topology: CONSISTENT — proceed: topology and authority are consistent
NEXT SAFE ACTION: a fresh independent review is still required
```

## 2. The rejected candidate (unchanged)

| Property | Value |
|---|---|
| **Commit** | `95cf5af7d9eae19cba5ab2f0a745ef3c04858962` |
| **Tree** | `4b3dda20194a1f7de790a12912316a1cef25e819` |
| **Parent** | `f1e8e1893eff2460d68f3f168f18fd29635b250d` |
| Archived at | `archive/p4/content-95cf5af7` (new branch, established `archive/p4/content-<prefix>` convention) |

**It was not amended, reset, rebased or altered in any way.** Its tree still resolves to
`4b3dda2019…`. No protected ref moved: `refs/preserve/ep1-pre-amend`,
`refs/preserve/ep1-pre-finalizer-lock`, `refs/preserve/ep1-wip`, `archive/p4/content-72512b90` and
`archive/p4/content-2a53746c` all hold their pre-existing values, and no `origin/*` ref was touched.
Nothing was pushed.

## 3. The independent-review report — location, hash, preservation

| Property | Value |
|---|---|
| Path | `docs/implementation/p4-independent-review-report.md` |
| **SHA-256 of the report as received** | `7d15bdbba533bc15a5e2de10b5320a2a7364cb70a2ae8fa1e36036405764b483` |
| SHA-256 of the tracked file (banner + report) | `4d727319d7e105c80bd9d90311d92486f1ce78f8b39a1372f3e76af6a869f1f5` |
| Byte-exact original (no banner) | `refs/preserve/p4-independent-review-95cf5af` → `fa4a6cb36ca753ef68797b2ff22658caa3dbec5b` |

**The authorized mechanism, determined from repository authority — not invented.** The precedent for
a **rejected** independent review is `p3-independent-review-findings.md`, which was preserved by
being committed **into the remediation content commit** (`0bf72b7`) by the remediating session. It is
not in `finalize_status.STATUS_METADATA_FILES`, so preserving it is content, not a status write. The
same mechanism is used here.

**Disclosed deviation, and why.** The tracked copy is **not byte-identical** to the report as
received: a disarming banner is **prepended**, and nothing else is changed. This is required by the
repository's own control system —
`test_false_green_defenses.py::test_historical_documents_disarm_before_any_stale_claim` refuses any
tracked historical review a grep-first reader could mistake for current authority, and
`p3-independent-review-findings.md` carries the same banner. Weakening that guard to preserve a hash
was not an option. Both properties are therefore held at once:

* the **byte-exact original** is preserved unmodified at `refs/preserve/p4-independent-review-95cf5af`,
  a commit whose **parent is the rejected candidate itself** — so the report is attributable to that
  exact candidate while provably **not part of** its tree (`4b3dda2019…` is unchanged);
* the tracked copy's content **after the banner is byte-identical** to the original. Verify either:

```
git show refs/preserve/p4-independent-review-95cf5af:docs/implementation/p4-independent-review-report.md | shasum -a 256
# -> 7d15bdbba533bc15a5e2de10b5320a2a7364cb70a2ae8fa1e36036405764b483
```

The report is **not** rewritten to appear as though it reviewed the new candidate. Its banner states
plainly that it reviewed `95cf5af7…` and returned REJECT.

**Full pre-remediation preservation artifact.** `refs/preserve/p4-prestate-95cf5af`
(`b2c1245f8c8b326cd7f543a9aa0098d7113d4e3b`, tree `81214dc354c5b2ab850e5d0214b148e158236c7e`) captures
the exact pre-remediation state: HEAD, the index (identical to HEAD), the tracked working tree
including both finalizer-owned modifications, untracked files, and the review report — 610 paths.
Also exported as a verified git bundle
(`p4-prestate-95cf5af.bundle`, SHA-256 `dc02e7db94a4356a8a884ea103a6684482ea211f4c52a2e2395313b513bf9690`).

**Ignored-but-tracked restoration, proved rather than assumed.** The throwaway index was seeded from
HEAD (`git read-tree HEAD`) before `git add -A`. An **empty** index yields tree
`6c676337846ca8bcd6aa06ce0786c1842688f566`, which contains **0 of the 7** ignored-but-tracked
`.playwright-mcp/` paths; the HEAD-seeded index yields `81214dc3…` with **7 of 7**. Restoration was
then verified from the bundle alone in a fresh clone: tree matches, 7/7 present, the report hashes
correctly, and `CURRENT.md`/`GATE-RESULT.json` restore to their **working-tree** versions
(`b37ccea8…`), not their HEAD versions (`2d631dc4…`).

---

## 4. F-01 remediation mapping

> **Finding:** `build_checkpoint_approval` had zero production callers; `GovernedWriteIntentQueued`
> had no consumer; the "full order" test authorized its executed grant with fixture identity
> `ap-1` / `owner:rasheed` while the governed approval beside it was `appr-9` / `U-OWNER`.

| # | Requirement | Where | How |
|---|---|---|---|
| 1 | Real production caller for `build_checkpoint_approval` from the authenticated callback path | `governed_write_route.py:consume_governed_write_intent`; `action_callback.py:_maybe_handle_governed_write_approval` | The callback handler verifies the Slack signature, routes on the token, and calls `handle_governed_write_callback`, which calls `build_checkpoint_approval`. Not a wrapper, not a test bridge. |
| 2 | Real bounded consumer for `GovernedWriteIntentQueued` | `governed_write_route.py:queued_write_intents` + `consume_governed_write_intent` | The queue is read back from the tenant-scoped security-event log; consumption is single-use via the same atomic `claim_operation_action` primitive the decision half uses. |
| 3 | One identity lineage | `governed_write_route.py` throughout | `approval_id`, `actor_id`, `tenant_id`, workspace/channel/message receipt, Work Item, pipeline instance, operation class, adapter, capability, payload hash, revision, checkpoint id, witness id, grant id and idempotency identity all travel from the one signed envelope. |
| 4 | Production code, not a fixture, derives checkpoint and grant | `governed_write_route.py` (`src/`, not `eval/`) | The `ApprovalRecord` is derived from the `GovernedApproval`; the grant is minted by `run_checkpoint` from that record. |
| 5 | No test may mint an unrelated grant and claim the chain | `test_p4_governed_invoice_write.py` | The misleading test is **split and renamed**, its docstring states its true scope, and it now **asserts** its grant carries the fixture id `ap-1` so the disconnection it retains can never be misread. |
| 6 | Full-order test enters the real entry point and asserts identity reaches the adapter | `test_p4_governed_write_route.py::test_the_full_order_runs_through_the_real_entry_point_with_one_identity` | Enters via `handle_governed_write_callback`; reads `approval_id` back out of the **adapter's own call log**, the **`effect_grants` row** and the **`checkpoint_witnesses` row**. |
| 7 | Keep the effect dark | `browser_use_write.SandboxInvoiceWriteAdapter` (default, no runner); `effect_boundary.execute_invoice_write` | No real write by default (PROVEN non-occurrence); non-sandbox refused **before any claim**; no credentialed adapter registered; no `OperatorAgent`/`CdpActuator` fallback (AST-verified). |
| 8 | Permanent human authority | `PendingGovernedWrite`; `freight_operations.InvoiceWriteOperation` | The route executes only the already-approved bounded operation. It never selects price, carrier, payment, claim or banking values — all arrive inside the payload the signature binds. The callback **cannot build** the operation; it only looks one up. |
| 9 | Hostile tests (16 classes) | `test_p4_governed_write_route.py` | All present — see §8. |
| 10 | Exactly one external attempt from repeated/concurrent delivery | `test_a_duplicate_callback_produces_exactly_one_external_attempt`, `test_two_simultaneous_consumers_produce_exactly_one_external_attempt` | 5 identical deliveries → 1 attempt; 2 racing consumers → 1 attempt and **1 grant** for the logical effect. |
| 11 | `UNKNOWN_OUTCOME` cannot auto-retry | `test_unknown_outcome_requires_reconciliation_and_never_auto_retries` | Re-delivery performs no write; the grant stays `UNKNOWN_OUTCOME`; only a **named human** decision resolves it. |
| 12 | Legacy callback→actuator route unreachable | `test_the_legacy_callback_to_actuator_route_remains_unreachable`, `test_the_callback_server_entry_point_constructs_no_actuator` | AST import analysis (not substrings — these modules *name* the actuators in prose). |

**A real defect found while building the hostile cases, and fixed.** `verify_governed_approval` never
bound the envelope's `approval_id` to the **operation's**. The payload hash deliberately does not
cover `approval_id` (it binds the approved *facts*), so a token signed for a **different approval of
the same facts** verified. That is F-01 in miniature. Now refused
(`governed_approval.py`, guarded by mutant **B48**).

### The exact real production path

```
Slack POST /slack/actions
  → action_callback._handle_slack                     (Slack signature verified)
  → action_callback._maybe_handle_governed_write_approval
        · verify_slack_signature                       authenticated channel decision
        · peek_approval_id(token)                      ROUTING ONLY — nothing trusted from it
        · config.governed_write_provider(approval_id)  the PENDING typed operation, looked up
        · authorize_command(user, channel)             actor/channel allowlist
  → governed_write_route.handle_governed_write_callback
        · verify_governed_approval                     HMAC + tenant + actor + workspace/channel/
                                                       message + work item + class + revision +
                                                       payload hash + capability + approval id
        · record_governed_decision                     single-use; queues GovernedWriteIntentQueued
  → governed_write_route.consume_governed_write_intent
        · approval_operation_mismatch                  lineage re-proved at the boundary
        · queued_write_intents                         THE CONSUMER
        · claim_operation_action                       single consumption, atomic, tenant-scoped
        · material_fact_set + canonical_payload + fingerprint   the ONE canonical composer
        · build_checkpoint_approval                    ◀── THE JOIN (F-01)
        · run_checkpoint                               seven steps, one transaction
              → checkpoint witness  +  Effect Grant    minted together
  → effect_boundary.execute_invoice_write
        · claim CAS  →  build_invoice_write_operation (typed AdapterOperation)
        · adapter.write  →  adapter.readback  →  explicit outcome
  → GovernedWriteCompleted  |  GovernedWriteEscalated (UNKNOWN_OUTCOME, human-owned)
```

### Identity-binding proof (from the test, read back from the database)

| Stage | Field | Value asserted |
|---|---|---|
| signed envelope | `approval_id` / `actor_id` | `appr-9` / `U-OWNER` |
| adapter's received operation | `op.approval_id` | `appr-9` |
| `effect_grants` row | `approval_id` | `appr-9` |
| `checkpoint_witnesses` row | `approval_id`, `accountable_owner` | `appr-9`, `owner:rasheed` |
| `GovernedWriteIntentQueued` | `approval_id`, actor | `appr-9`, `U-OWNER` |
| `GovernedWriteCompleted` | `approval_id`, `grant_id`, `actor_id` | `appr-9`, the minted grant, `U-OWNER` |

`ap-1` appears nowhere on this route. The test also asserts **no money value** reaches any durable record.

---

## 5. F-02 remediation mapping

> **Finding:** `--operation-url-filter` defaults to `""`, `url_matches_filter` returns `True` for
> falsy input, `select_load_detail_link` performed **no** origin check, and the allow-reason falsely
> claimed "on the TMS domain allowlist".

| # | Requirement | How |
|---|---|---|
| 1 | Origin safety must not depend on an optional textual filter | The authority is `established_origin`, a **parsed** origin. `url_filter` is now only an **additional narrowing** and can never be what makes navigation safe. |
| 2 | Every candidate from `select_load_detail_link` passes an explicit parsed-origin policy | `link_origin_refusal()` is called for every candidate, over **both** the raw `href` and the browser-resolved URL. |
| 3 | Empty/missing/malformed config fails closed | `navigation_target_is_allowed` refuses with *"no established origin"* when none is established; `ReadOnlyCdpNavigator(allowed_origin=<malformed>)` raises at construction ("fails CLOSED"). |
| 4 | Compare normalized components | `parse_origin()` → `Origin(scheme, host, effective port)`; ports normalized (`https`→443) and compared as integers. No substring test decides anything. |
| 5 | Rejections | cross-origin absolute; **scheme-relative** `//evil.example/path` (no longer treated as "relative therefore safe"); `javascript:`/`data:`/`file:`/`vbscript:`/`blob:` and any non-http(s) scheme; **userinfo** URLs (`https://trusted.example@evil.example/…`); malformed hosts; absolute foreign URLs encoded in query parameters; a link whose text matches the load but whose href is foreign. |
| 6 | Relative and same-origin-absolute policy stated explicitly | Relative (`/path`, `?q`, `#frag`) resolves against the established origin and is **allowed** — but still requires that an origin has been established. Same-origin absolute is **allowed**, and the reason names the origin comparison. Both are tested by name. |
| 7 | The reason must describe the check that ran | Asserted directly: with no filter configured the reason must **not** mention a domain filter and must say `same-origin`; with one configured it must say so. `_origin_defect()` names the *specific* defect (embedded credentials / malformed host / non-http(s) scheme) rather than a three-way guess. |
| 8 | Destructive-link protections preserved | `test_the_origin_policy_did_not_displace_the_destructive_link_protections` re-proves delete/purge routes, `data-method`, `_method` override, `<base>` redirection and unsafe schemes — all **on the established origin**, where only the pre-existing barrier can refuse them. |
| 9 | Hostile regression tests | All ten named cases present — see §8. |

**Origin establishment is operator-controlled.** It comes from `allowed_origin` or from the first
`visit()` to an operator-configured entry URL, and is immutable thereafter; no page-published link
can establish or change it. Both production entry points now pin it explicitly from their configured
URL (`run_action_callback_server.py` ×5, `propose_ar_from_tms.py` ×1).

---

## 6. F-04 evidence disposition

**Repository authority decides this, and it is not fully dischargeable by this session.** All five
artifacts the reviewer named are in `scripts/finalize_status.py:STATUS_METADATA_FILES` — they are
**finalizer-owned** and reserved for the post-adjudication finalizer. Hand-editing them is exactly
the forbidden status write.

| Artifact | Owner | State now | Disposition |
|---|---|---|---|
| `TEST-NODE-MANIFEST.json` | content | **Rebound.** 1962 nodes | Regenerated by its canonical generator `scripts/regenerate_test_manifest.py`; committed **with** the test change it records (+68 hostile nodes, −1 renamed test). |
| `GATE-RESULT.json` | finalizer | **Rebound to `0891d1a19a9c…` / `8e12372a27…`**, `node_manifest_sha256 fbf0f7fa…` (equals the manifest) | Written by the canonical generator `scripts/clean_clone_gate.py`; left **uncommitted** for the finalizer, exactly as the reviewer found it. |
| `CURRENT.md` | finalizer | Still records `3d231731` | **Reserved for the finalizer.** Not edited. |
| `SUITE-RESULT.json` | finalizer | Still records `3d231731` | **Reserved for the finalizer.** Not edited. |
| `BUILD-STATUS.yaml` | finalizer | Still records `3d231731` | **Reserved for the finalizer.** Not edited. |
| `IMPLEMENTATION-REGISTRY.yaml` | finalizer | `baseline_commit 3d231731` | **Reserved for the finalizer.** Not edited. |

### Stale-reference classification (committed tree)

| Reference | Occurrences | Classification |
|---|---|---|
| `3d231731` | 5, all in finalizer-owned status metadata (`BUILD-STATUS.yaml`, `CURRENT.md`, `GATE-RESULT.json`, `IMPLEMENTATION-REGISTRY.yaml`, `SUITE-RESULT.json`) | **Stale candidate binding requiring correction — reserved for the finalizer.** |
| `72512b9` | 0 outside the preserved report (3 inside) | **Preserved rejected-review evidence.** |
| `8e2d0dc` | 0 outside the preserved report (3 inside) | **Preserved rejected-review evidence.** |
| `95cf5af7` | 0 outside the preserved report (7 inside) + the commit message | **Preserved rejected-review evidence** / legitimate historical reference. |

The commit message's references to `95cf5af7`, `3d231731` and the preserve refs are **legitimate
historical references** — they identify what was remediated and what was preserved.

> **Consequence for the re-reviewer:** the committed status metadata still describes `3d231731`.
> **Do not read it as describing this candidate.** The only pre-review evidence that legally binds to
> `0891d1a19a9c…` is `TEST-NODE-MANIFEST.json` (committed) and `GATE-RESULT.json` (uncommitted, canonical
> generator).

---

## 7. Changed files

**Remediation delta** (rejected candidate → remediated) — `19 files changed, 4709 insertions(+), 71 deletions(-)`:

| File | Change |
|---|---|
| `src/freight_recon/governed_write_route.py` | **new** — the production join (F-01) |
| `src/freight_recon/cdp_readonly.py` | parsed-origin policy, fail-closed navigation, `link_origin_refusal` (F-02) |
| `src/freight_recon/action_callback.py` | authenticated governed-write handler; config + `run_callback_server` seams |
| `src/freight_recon/governed_approval.py` | approval-identity binding added to `verify_governed_approval` |
| `scripts/run_action_callback_server.py` | origin pinned at 5 reader sites; **`_build_governed_write_route` wires the lookup boundary and returns no kernel** (§0) |
| `scripts/propose_ar_from_tms.py` | origin pinned from `--loads-url` |
| `scripts/mutate_phase4_boundary.py` | B30 retargeted; B30b, B30c, B44–B48, B49–B52 added (50 → 61) |
| `eval/tests/test_p4_governed_write_route.py` | **new** — the F-01 battery, entered through production |
| `eval/tests/test_cdp_readonly_navigation.py` | the F-02 hostile battery + harness update |
| `eval/tests/test_p4_governed_invoice_write.py` | misleading test split, renamed, scope stated |
| `eval/tests/test_operation_proposal.py` | double carries an established origin, delegates to production |
| `docs/implementation/EFFECT-PATH-INVENTORY.yaml` | `p4_f01_governed_join` records the closed seam; prior block marked HISTORICAL |
| `docs/implementation/LEGACY-DISPOSITION.md` | disposition for the new module (required by the repo's own guard) |
| `docs/implementation/TEST-NODE-MANIFEST.json` | regenerated, 1962 nodes |
| `src/freight_recon/governed_write_registry.py` | **new** — the minimum bounded pending-write repository (the deployed lookup boundary) |
| `eval/tests/test_p4_deployed_governed_route.py` | **new** — the deployed-entry-point battery, incl. the U8.1 seam pin |
| `eval/tests/test_phase2_guard_registry.py` | classifies the new control guard |
| `docs/CANONICAL-DOCUMENTS.md` | classifies this handoff document |
| `docs/implementation/p4-independent-review-report.md` | **new (preserved)** — the rejected review |

The full unit (certified parent → remediated) is **46 files**.

---

## 8. Results

### Clean-clone canonical gate — **PASS**
```
clean-clone: {'passed': 1961, 'failed': 0, 'skipped': 1, 'collected': 1962}
CLEAN-CLONE GATE: PASS
```
Collected 1962 == `TEST-NODE-MANIFEST.json` node count 1962, identical by identity.

### Focused
| Battery | Result |
|---|---|
| F-01 governed approval + route (`test_p4_governed_write_route`, `test_p4_governed_invoice_write`, `test_governed_approval_binding`) | **79 passed** |
| F-01 **deployed** entry point (`test_p4_deployed_governed_route`) | **27 passed** |
| F-02 origin/navigation (`test_cdp_readonly_navigation`, `test_cdp_readonly_surface`, `test_operation_proposal`, `test_browser_session_health`) | **214 passed** |
| Import/entry-point gates + containment | **107 passed** |
| Loopback socket tests (`test_action_callback`) | **34 passed** — bound successfully here; **nothing was weakened or deleted** |
| Status-reality / integration-topology | **5 passed, 2 skipped** / **11 passed** |
| Founder-decision conditions 1–7 (§0) | **13 named tests, all PASS** |
| Null-gate / deferral guards (`test_phase0_null_gate`) | **6 passed** — and proven to FAIL on a premature production registration (§0) |

### Mutation battery — **61/61 caught** (was 50/50)
No MISS, no SETUP-FAIL, no RESTORE-RED.

**B30 was retargeted, not silently accepted.** After the F-02 fix, disabling only the navigation
scheme denylist reintroduces **no** defect — the parsed-origin policy refuses `javascript:`
independently. A mutant that cannot reintroduce the defect proves nothing (CLAUDE.md §9), and B30a
already documents this exact redundancy trap. B30 now removes the **origin comparison itself**.

New mutants: **B30b** (fail-open default), **B30c** (selector ignores the origin policy), **B44**
(route stops calling `build_checkpoint_approval` and mints its own `ApprovalRecord`), **B45**
(consumer stops reading the queue), **B46** (consumption boundary stops binding approval identity),
**B47** (single consumption dropped), **B48** (envelope stops binding `approval_id`), **B49** (the
deployed wiring is removed), **B50** (the repository stops checking the recorded payload hash),
**B51** (proposal expiry ignored), **B52** (the channel receipt is taken from the tap instead of the
stored proposal).

`select_load_detail_link`'s origin decision was consolidated into one function specifically so a
single mutant can remove the whole decision — the design `scheme_refusal_reason` already uses.

### Gate counts
| Measure | Value |
|---|---|
| Live violation edges | **0** |
| Recorded violation edges | **0** |
| Agreement | exact, both-sided |
| Detection sites | **13** |

### Hostile coverage
**F-01 (16 classes, all present):** mismatched approval ID · mismatched actor · tenant mismatch ·
Work Item mismatch · revision mismatch · payload substitution · capability mismatch · adapter
mismatch · stale approval · reused approval · duplicate callback · two simultaneous consumers ·
restart before claim · restart after claim · external success with lost acknowledgement ·
`UNKNOWN_OUTCOME` reconciliation requirement.

**F-02 (10 classes, all present):** empty filter + cross-origin · absent filter + cross-origin ·
same text/foreign href · `//evil.example/path` · `https://trusted.example@evil.example/path` · same
hostname unsafe scheme · same hostname disallowed port · relative safe detail route · valid
same-origin absolute detail route · misleading allow-reason.

### False-green defences for this remediation's own claims
* every negative corpus asserts a **positive that must hold first** (`_origin_corpus_is_real()`,
  `_production_sources()` size, the matching-pair predicate, "degenerate read" anchors);
* the production-path test proves it reached the **intended real entry point** and the **intended
  adapter** (the adapter records the operations it was handed);
* explicit guards **fail** if the decision-to-checkpoint caller is removed
  (`test_build_checkpoint_approval_has_a_real_production_caller`, AST **call** nodes, not imports or
  prose), if the queued-intent consumer is removed, if approval identity is substituted, or if the
  origin check is bypassed or the filter is empty — each also covered by a mutant;
* adapter-absence checks use **AST imports, never substrings**: these modules *name* the actuators
  they must not reach, and a substring guard would fire on its own documentation.

---

## 9. Remaining limitations — stated, not hidden

1. **R-07 is OPEN — NOT CONTAINED, and P4 is NOT COMPLETE.** Nothing here changes that.
2. **F-04 is not fully discharged and cannot be by this session.** Four finalizer-owned artifacts
   still name `3d231731`. Only the finalizer may rebind them, and running it is forbidden here.
3. **The deployed route does not execute, BY FOUNDER DECISION (§0).**
   `run_action_callback_server.py` wires the **lookup boundary** and returns **no execution
   kernel**, so a governed tap at the deployed server ends in an explicit `ROUTE_NOT_CONFIGURED`
   refusal. This is the accepted P4 shape — containment, not production enablement — not a missing
   line. Production Action Class gate registration is U8.1 / Phase 8 work and is pinned by
   `test_phase0_null_gate.py` and
   `test_the_execution_kernel_seam_is_blocked_pending_adjudication`, both of which fail the moment
   it appears.
4. **The effect remains dark.** The bounded writer is exercised by a scripted double; no real
   external write has ever been performed. The governance machinery is real, the writer is not.
5. **The preserved report's tracked copy carries a prepended banner** (§3). The byte-exact original
   is at `refs/preserve/p4-independent-review-95cf5af`.
6. **One local-only suite failure**, `test_build_status_receipt_consistency`, caused by the
   uncommitted finalizer-owned `GATE-RESULT.json` disagreeing with the committed `BUILD-STATUS.yaml`.
   It **passes in the clean clone** and on the rejected candidate's tree; it is discharged by
   finalization.
7. **Unaddressed findings from the original review**, deliberately out of this remediation's scope:
   **F-03** (`ReadOnlyBrowserUseRunner` `base_url` validation), **F-05** (mutant B34's label),
   **F-06** (route-family denylist), **F-07** (numeric self-contradictions), **F-08** (approved-field
   *values* unconstrained), **F-09** (duck-typed writer), **F-10** (conditional context binding).
   Only F-01 and F-02 were named P4-blocking and R-07-blocking.
8. **This session performed no independent review and no adjudication**, and must not be treated as
   having done so.

---

## 10. What the re-reviewer should do

Review **`0891d1a19a9c47155a56a3f4b2116e5a4d4aa75e`** (tree `a3e704645b8a06561d90cdb5f81288309ae51850`)
from a disposable clone, detached, without altering the primary worktree. The whole P4 unit is one
diff against `f1e8e1893eff…`. Do not rely on this handoff or on the committed status metadata;
re-derive everything.

---

## 11. The kernel seam — DECIDED, deferred to U8.1 / Phase 8

**Status: DEFERRED BY FOUNDER DECISION (§0). Fail-closed, named, and pinned by tests.**

> This section was written while the question was open. It is retained because it records WHY the
> seam is blocked and what the alternatives were. **The question is now answered: the deferral
> stands.** See §0 for the decision and its verification.

### What is wired, and what is not

| Seam | State |
|---|---|
| `governed_write_provider` (the lookup boundary) | **WIRED** in `run_action_callback_server.py` |
| `governed_write_kernel` (the execution kernel) | **BLOCKED** — returns `None`; the handler refuses with `ROUTE_NOT_CONFIGURED` |

### Why the kernel cannot be wired by this session

`CheckpointKernel` **cannot be constructed without a `GateRegistry`** — that is F-20, deliberate:
*"a gate expressible as an absence is not a gate."* So the deployed governed route cannot execute
without **production Action Class gate registration**. Repository authority assigns that work
elsewhere and freezes the ground it rests on:

| Authority | What it says |
|---|---|
| `phase-0-baseline-manifest.yaml` | `AC-CKPT-6-missing` = **`DEFERRED_BY_DEPENDENCY — REQUIRED AT PHASE 8`**, `green_at_phase: P8`, `accountable_unit: U8.1` |
| `pr-sequence.md` | *"Typed Policy and Action Class gate registration do not exist until **P8**"*; U8.1 owns *"typed policy + Action Class gate registration"* |
| `test_phase0_null_gate.py` | Proves the production registration population is **empty**, and states that if it stops being empty the case must be **re-adjudicated, not quietly inherited** |
| `test_phase0_null_gate.py` | *"policy must be evaluated at the boundary that owns it, never carried by a workflow, adapter or callback"* |
| `PROGRESS-PROTOCOL.md` §3 | A frozen acceptance case changes only with an explicit explanation, repository evidence, **founder approval**, and a committed acceptance-contract revision |
| `CLAUDE.md` §7 | Stop conditions include *"implementing would close an open risk outside its approved phase"* |

A remediation builder may not register the gates (that is U8.1 inside P4), may not re-adjudicate
`AC-CKPT-6-missing`, and may not revise a frozen acceptance contract.

### Disclosure: this was caught by the repository's own guards, not by foresight

An earlier draft of this remediation **did** add a production `GateRegistry`
(`governed_gate_registry()`) to `governed_write_registry.py`. Three guards fired —
`test_the_production_gate_registration_population_is_still_empty`,
`test_the_typed_gate_population_is_now_non_empty_and_confined_to_the_checkpoint_kernel`, and
`test_typed_policy_runtime_exists_only_with_its_canonical_authority`. The registration was
**removed**, and deliberately **not relocated** to `scripts/` — where the probe, which scans `src/`,
would not have seen it. Moving it would have passed the gate while changing nothing real, which is
precisely the false green these guards exist to prevent.

### The decision (2026-07-29)

> **ANSWERED: the deployed governed route waits for U8.1 / Phase 8.** P4 may not register production
> Action Class gates for `raise_invoice`, `record_payable` or any other consequential production
> Action Class. The frozen deferral stands, unrevised. **P4's required boundary is containment, not
> production enablement.**

The deployed route therefore refuses with `ROUTE_NOT_CONFIGURED` — the safe direction, and the state
shipped here. The test environment may supply an explicit kernel and gate registry to prove the
complete authority-preserving chain; production registration stays empty until U8.1.

### The exact change AT U8.1 (not before)

1. Register the two action classes **in the module that owns policy** (the checkpoint kernel), not
   in the freight route — `test_phase0_null_gate.py` requires policy to live at its own boundary.
2. Pass the resulting registry into `_build_governed_write_route`, which then returns a kernel
   factory instead of `None`.
3. Re-adjudicate `AC-CKPT-6-missing` in `phase-0-baseline-manifest.yaml` with founder approval —
   which the 2026-07-29 decision explicitly withholds until U8.1.
4. Replace `test_the_execution_kernel_seam_is_blocked_pending_adjudication` with a test asserting
   the completed wiring. **That test is written to FAIL the moment a kernel appears**, so this
   blocker cannot be silently forgotten.

**Nothing else on the authority boundary changes.** The lookup repository, the identity bindings,
the fail-closed refusals, the darkness of the adapter and every test above are unaffected.

---

## 12. What obligations 1–12 of the deployed cut achieved

| # | Obligation | State |
|---|---|---|
| 1 | Wire a fail-closed provider **and** kernel | **DONE, as the founder decision defines it** — provider wired; kernel seam present and fail-closed (`ROUTE_NOT_CONFIGURED`) because production gates are deferred to U8.1 (§0) |
| 2 | Callback supplies only authenticated immutable lookup/decision data | **DONE** |
| 3 | Provider retrieves an already-existing typed pending operation | **DONE** — `GovernedWriteOperationProposed` + money table |
| 4 | Callback never chooses amount/counterparty/invoice/load/system/URL/adapter/capability/fields | **DONE** — proved by `test_callback_data_cannot_replace_operation_fields` and the one-method boundary |
| 5 | Retrieved operation bound to the exact authenticated approval | **DONE** — envelope, stored record and live channel receipt all checked |
| 6 | Preserve dark behaviour | **DONE** — `writer=None`; no credentialed adapter registered |
| 7 | Missing config/provider/kernel/operation/adapter fails closed with an explicit governed outcome | **DONE** — `ROUTE_NOT_CONFIGURED`, `NO_PENDING_OPERATION`, `BOUNDARY_REFUSED`, receipt failures |
| 8 | No fallback to OperatorAgent / CdpActuator / arbitrary tasks / NL execution / direct writes | **DONE** — AST-verified |
| 9 | Integration test through the real entry point proving one identity to the adapter | **DONE** — kernel supplied by the test, which the founder decision expressly permits (§0) |
| 10 | The nine required negative tests | **DONE** (all nine, plus channel-receipt and tamper cases) |
| 11 | Minimum bounded repository, not P6 | **DONE** — one-method boundary, storage explicitly replaceable |
| 12 | New candidate, evidence, focused/mutation/manifest/clean-clone, P4 open, no finalizer | **DONE** |

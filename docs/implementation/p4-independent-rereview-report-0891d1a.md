> # ⛔ HISTORICAL REVIEW — NOT CURRENT AUTHORITY
> **Preserved as received. This is evidence of a past moment, not status.** It is an INDEPENDENT
> RE-REVIEW, **not** an adjudication: it set no acceptance criterion, marked no phase complete,
> closed no risk and authorized no finalization. It reviewed P4 implementation candidate
> `0891d1a19a9c47155a56a3f4b2116e5a4d4aa75e` (tree `a3e704645b8a06561d90cdb5f81288309ae51850`) and
> returned **ACCEPT FOR SEPARATE FINAL ADJUDICATION**.
>
> ### **IT DID NOT REVIEW THE COMMIT THAT CARRIES IT.** The P4 acceptance-and-status closure commit
> did not exist when this was written. Nothing here may be cited as an independent review of that
> commit, which owes its own fresh targeted review and its own targeted adjudication. The separate
> final adjudication that acted on this report is
> [`p4-final-adjudication-report-0891d1a.md`](p4-final-adjudication-report-0891d1a.md); current
> status is [`CURRENT.md`](CURRENT.md); operating guide is [`../../CLAUDE.md`](../../CLAUDE.md).
>
> **BYTES.** Everything below this banner is the reviewer's report, unaltered — no deletion, no
> edit, no reordering. The banner is the only addition, and it is required by this repository's own
> control system (`test_false_green_defenses.py::test_historical_documents_disarm_before_any_stale
> _claim`, which refuses any tracked historical review a grep-first reader could mistake for
> authority). This is the same treatment, for the same reason, that
> [`p4-independent-review-report.md`](p4-independent-review-report.md) already carries.
>
> **THE SIDECAR HASH IS THE ORIGINAL'S, DELIBERATELY.**
> `p4-independent-rereview-report-0891d1a.md.sha256` records
> `181e1a37a413fd35f537e00a7e1423bf192f88205270fa15932fbabeb955d316`, which is the SHA-256 of the
> reviewer's file **without** this banner. It therefore does **not** match this bannered copy, and
> that is correct: the sidecar authenticates the report, not the in-tree rendering of it. The
> byte-exact original that hashes to it is preserved unmodified at
> `refs/preserve/p4-independent-rereview-0891d1a` — a commit whose parent is the reviewed candidate
> `0891d1a`, adding only the report and its sidecar, leaving the candidate's tree untouched. To
> verify:
>
> ```
> git show refs/preserve/p4-independent-rereview-0891d1a:docs/implementation/p4-independent-rereview-report-0891d1a.md | shasum -a 256
> # expect 181e1a37a413fd35f537e00a7e1423bf192f88205270fa15932fbabeb955d316
> ```

# P4 — INDEPENDENT HOSTILE RE-REVIEW REPORT

**Reviewed candidate: `0891d1a19a9c47155a56a3f4b2116e5a4d4aa75e`**

**Status: ACCEPT FOR SEPARATE FINAL ADJUDICATION**

Reviewer: fresh independent session. Did not implement, remediate, adjudicate or finalize this unit,
and did not resume any prior session. Review date: 2026-07-29.

> This report is an independent-review **source artifact**. It is not an adjudication. It does not
> mark P4 complete, does not mark R-07 contained, does not instantiate weighted acceptance, and does
> not authorize finalization. It reviews `0891d1a`, not the rejected `95cf5af7`.

---

## A. Exact artifact verified

Every hash below was read from the object store in a disposable clone, never from the handoff.

| Property | Expected | Verified | Result |
|---|---|---|---|
| Content commit | `0891d1a19a9c47155a56a3f4b2116e5a4d4aa75e` | identical | **MATCH** |
| Tree | `a3e704645b8a06561d90cdb5f81288309ae51850` | identical | **MATCH** |
| Parent | `f1e8e1893eff2460d68f3f168f18fd29635b250d` | identical | **MATCH** |
| Rejected candidate | `95cf5af7d9eae19cba5ab2f0a745ef3c04858962` | `archive/p4/content-95cf5af7` resolves to it; tree still `4b3dda2019…` | **INTACT, UNALTERED** |
| Prior report byte-exact original | `refs/preserve/p4-independent-review-95cf5af` → `fa4a6cb3…` (parent = `95cf5af7`) | SHA-256 `7d15bdbb…4483` | **MATCH** |

**Protected refs — none moved.** `refs/preserve/ep1-pre-amend` `9a9d9c4a…`, `ep1-pre-finalizer-lock`
`545bd111…`, `ep1-wip` `509976a7…`, `ep1-run1-inflight` `c4ff3671…`, `ep1-run2-inflight`
`4e981d2d…`, `archive/p4/content-72512b90`, `archive/p4/content-2a53746c`,
`p4-prestate-95cf5af` `b2c1245f…`, and every `refs/remotes/origin/*` hold pre-existing values.
Nothing was pushed. `origin/main` is unchanged at `152574e4…`.

**The tracked report is banner-only modified.** `docs/implementation/p4-independent-review-report.md`
in the candidate hashes to `4d727319…`, not `7d15bdbb…`. I diffed the two: the **only** change is a
23-line prepended banner; lines 1–650 of the original follow byte-identically. The banner states
plainly that the report reviewed `95cf5af7` / tree `4b3dda2019` and returned REJECT. **No artifact
in the candidate states or implies that the rejected report reviewed `0891d1a`.** The disclosed
deviation is accurate and the byte-exact original is durably preserved outside the candidate's tree.

---

## B. Review environment and independence statement

- Reviewed from **two disposable non-local clones** (`--no-local`) of the product repository,
  each checked out **detached** at `0891d1a19a9c…`, under fresh venvs with declared deps only.
- Both clones verified `git status --porcelain` clean at start; clone 1 verified clean again after
  the full suite **and** after the 61-mutant battery (tree still `a3e704645b8a…`); clone 2 verified
  clean after the Phase-8 regression demonstration.
- **The primary product worktree was not altered** to construct the review environment. It was read
  only. No commit, amend, reset, rebase, cherry-pick, merge, ref update, push, finalization or
  deployment was performed. No external system was contacted. No effect was enabled.
- **No builder or finalizer owns the primary worktree.** `.git/neyma-finalizer.lock` and
  `.git/neyma-builder-worktree.lock` are 0-byte and **unheld** (`lsof` shows no holder;
  `current_owner()` → `None`). No `finalize_status` / `clean_clone_gate` / `mutate_phase4_boundary`
  process is running. `git worktree list` shows one live worktree plus one prunable stale entry
  (`/private/tmp/claude-501/wt-dt`, unrelated docs branch).
- The primary worktree carries two uncommitted finalizer-owned files (`CURRENT.md`,
  `GATE-RESULT.json`) plus the untracked builder handoff. They were **read, never written**.
- The remediation handoff was read **as a handoff only**. Every claim in it was independently
  re-derived. Two of its claims are wrong (see RR-02); the underlying artifacts are correct.
- Prior review claims were **not inherited**. The whole P4 unit — one diff `f1e8e18 → 0891d1a` —
  was re-reviewed from source.

---

## C. Complete changed-surface inventory

The unit is **one content commit on the certified parent boundary**: `46 files changed,
+11 475 / −825`. The remediation delta (`95cf5af7 → 0891d1a`) is `19 files, +4 709 / −71`. I walked
the whole 46-file diff, not the 19-file delta.

**New source (7):** `governed_write_route.py` (599, the F-01 join), `governed_write_registry.py`
(471), `cdp_readonly.py` (1 424), `browser_use_write.py` (430), `governed_approval.py` (414),
`freight_operations.py` (196), plus `scripts/finalizer_lock.py` (188) and
`scripts/verify_readonly_cdp.py` (206).

**Modified source (5):** `action_callback.py` (+210), `browser_use_adapter.py`, `cdp_actuator.py`,
`effect_boundary.py` (+136), `operation_proposal.py`, `system_orientation.py`.

**Entry points (4):** `run_action_callback_server.py` (−444 net rewrite), `orient_tms.py`,
`propose_ar_from_tms.py`, `finalize_status.py`.

**Probes/manifests (3):** `import_probe.py`, `entrypoint_probe.py`, `manifest.py`.

**Tests (16):** 7 new (`test_p4_governed_write_route.py`, `test_p4_deployed_governed_route.py`,
`test_p4_governed_invoice_write.py`, `test_governed_approval_binding.py`,
`test_cdp_readonly_navigation.py`, `test_cdp_readonly_surface.py`,
`test_browser_use_readonly_surface.py`), 9 modified.

**Evidence/docs (7):** `EFFECT-PATH-INVENTORY.yaml`, `IMPLEMENTATION-SURFACE.yaml`,
`LEGACY-DISPOSITION.md`, `TEST-NODE-MANIFEST.json`, `phase-0-baseline-manifest.yaml`,
`CANONICAL-DOCUMENTS.md`, `p4-independent-review-report.md` (the preserved rejected review).

**Mutation battery:** `mutate_phase4_boundary.py` (+400 → 61 cases).

---

## D. F-01 disposition — **DISCHARGED**

Prior finding: the decision half and the execution half shared no authority.
`build_checkpoint_approval` had zero callers; `GovernedWriteIntentQueued` had no consumer; the
"full order" test authorized its grant with fixture identity `ap-1` / `owner:rasheed`.

### D.1 The join exists in production code and has a real production caller

`src/freight_recon/governed_write_route.py:307` calls `build_checkpoint_approval` — inside
`consume_governed_write_intent`, in `src/`, not `eval/`. Its caller chain is real:

```
Slack POST /slack/actions
  → action_callback._handle_slack                          (action_callback.py:356)
  → action_callback._maybe_handle_governed_write_approval   (action_callback.py:612)
       · verify_slack_signature                             authenticated channel decision
       · peek_approval_id(token)                            ROUTING ONLY, nothing trusted
       · config.governed_write_provider(approval_id)        BOUNDED LOOKUP of a pre-existing op
       · authorize_command(user, channel)                   actor/channel allowlist
       · stored-channel-receipt check                       fail-closed, never the tap's channel
  → governed_write_route.handle_governed_write_callback     (action_callback.py:723)
       · verify_governed_approval                           HMAC + every binding + approval_id
       · record_governed_decision                           single-use; queues the intent
  → governed_write_route.consume_governed_write_intent
       · approval_operation_mismatch                        lineage re-proved at the boundary
       · queued_write_intents                               THE CONSUMER (reads the queue back)
       · claim_operation_action                             atomic, tenant-scoped, single-use
       · material_fact_set + canonical_payload + fingerprint the ONE canonical composer
       · build_checkpoint_approval                          ◀── THE JOIN
       · run_checkpoint                                     witness + Effect Grant, one transaction
  → effect_boundary.execute_invoice_write
       · claim CAS → build_invoice_write_operation → adapter.write → readback → explicit outcome
  → GovernedWriteCompleted | GovernedWriteEscalated
```

I verified by AST that `build_checkpoint_approval` has exactly one production **call node** outside
its defining module, in `governed_write_route.py`, and that `action_callback.py` reaches
`handle_governed_write_callback` at a real call site.

### D.2 One identity lineage — proven from the database, by my own probe

I wrote an **independent** probe (not adapted from the candidate's tests), entered only through
`handle_governed_write_callback`, and read the identity back out of the store:

| Stage | Field | Value |
|---|---|---|
| signed envelope | `approval_id` / `actor_id` | `appr-9` / `U-OWNER` |
| queued intent (`GovernedWriteIntentQueued`) | `approval_id`, actor | `appr-9`, `U-OWNER` |
| checkpoint witness row | `approval_id`, `accountable_owner`, `grant_id` | `appr-9`, `owner:rasheed`, matches |
| `effect_grants` row | `approval_id`, `commit_key`, `state` | `appr-9`, `= op.effect_key()`, `VERIFIED` |
| the operation **the adapter received** | `approval_id`, tenant, WI, PI, capability, payload hash, revision | `appr-9`, `tenant-alpha`, `WI-77`, `PI-77`, `A4.raise_invoice`, equal, `0` |

`ap-1` appears **nowhere** on the route. `EffectAttempted` is recorded before the call. No money
value (`2850.00`) reaches any durable record. The witness/grant/commit-key identities cross-check.

### D.3 Hostile cases — 19 classes, every one refuses with **zero** external attempts

approval-ID mismatch · actor mismatch · tenant mismatch · workspace receipt mismatch · channel
receipt mismatch · Slack `message_ts` receipt mismatch · Work Item mismatch · pipeline-instance
mismatch · revision mismatch · payload substitution (amount) · counterparty substitution ·
capability mismatch · adapter/target substitution · idempotency-key substitution · stale approval
(TTL) · forged signature · non-sandbox (darkness refusal, before any claim) · no queued operation ·
provider/kernel unavailable.

One case did **not** refuse — `base_url` substitution. See **RR-01**; it is contained today.

### D.4 At most one external attempt; UNKNOWN_OUTCOME never auto-retries

| Scenario | Result |
|---|---|
| 5 identical deliveries | **1** external attempt, **1** Effect Grant; deliveries 2–5 → `DUPLICATE_CALLBACK` |
| 2 simultaneous consumers (threads, one queued intent) | **1** attempt, **1** grant, exactly 1 consumer consumed |
| restart after claim (re-consume) | **no** second attempt; `ALREADY_CONSUMED` |
| adapter reports `OUTCOME_UNKNOWN` | `UNKNOWN_OUTCOME`, escalated, `requires_reconciliation`, re-delivery performs **no** write, grant row stays `UNKNOWN_OUTCOME` |
| external success with lost acknowledgement | identical — never laundered to `FAILED` or `VERIFIED` |
| blind readback / conflicting fingerprint | **not** `VERIFIED` |

### D.5 The deployed path reaches the seam and fails closed

I drove the **real** `action_callback` handler with the **real**
`run_action_callback_server._build_governed_write_route` seams:

```
governed_write_provider : WIRED
governed_write_kernel   : None        <-- fail-closed by founder deferral
handler response        : 200  {state: REFUSED, reason: ROUTE_NOT_CONFIGURED}
GovernedWriteRefused    : 1  (reason=ROUTE_NOT_CONFIGURED)
effect_grants minted    : 0
```

`ROUTE_NOT_CONFIGURED` **is** recorded as a governed refusal with a named cause; it is not a silent
fall-through. The governed handler is deliberately **not** gated on the seams being configured, so a
governed token cannot be dropped into an unrelated handler.

### D.6 No legacy fallback, no callback-created operation

- `operation_router = None` at `run_action_callback_server.py:133` is the **only** assignment, a
  literal `None`, unconditional, never reassigned, not inside any conditional.
- AST import-closure from the deployed entry point: **`cdp_actuator` and `cdp_session` are
  UNREACHABLE.** `operation_router`/`operator_agent` remain importable but import no actuator and
  cannot construct one; the only actuator construction site anywhere is the unrelated
  `scripts/discover_tms_screen.py` (a pre-existing read-substrate detection edge).
- `PendingGovernedWriteRepository` exposes exactly one public method, `pending_for` — a lookup. The
  deployed entry point contains no `InvoiceWriteOperation(` and no
  `record_proposed_governed_write(`. The callback **cannot build or modify** the typed operation.
- `propose_ar_from_tms.py --autonomous` hard-errors; its `router` is unconditionally `None`.

### D.7 The test-supplied kernel is not a substitute for the deployed path

The founder decision expressly permits the test environment to supply a governed kernel and gate
registry. It does — via `phase3_kit.make_kernel`. Crucially, this is **not** presented as the
deployed path: `test_p4_deployed_governed_route.py` separately drives the real handler through the
real entry point's own builder and proves the deployed shape ends in `ROUTE_NOT_CONFIGURED`. The two
claims are kept distinct in the code, in the tests, and in the handoff.

**F-01 is discharged.** The chain exists as code, is reachable from the authenticated callback, is
authorized by one continuous identity, and fails closed everywhere it should.

---

## E. Founder-decision and Phase-8 deferral compliance — **COMPLIANT**

| Check | Result |
|---|---|
| Production `GateRegistry` population | **EMPTY.** `GateRegistry` is defined only in `checkpoint.py`; **no** module under `src/` constructs or populates one. `governed_write_registry.py:394` records the removal in place. |
| Relocation to `scripts/`, dynamic imports, plugins, config loaders, startup hooks | **NONE.** The only `importlib` use in the repository is `finalize_status.py:113` (control-guard loading). No `__import__`, `eval(`, `exec(`, `pkgutil` or `entry_points` seam exists in `src/` or `scripts/` outside the mutation harness's payload strings. |
| `AC-CKPT-6-missing` | YAML-parsed and compared: **structurally identical to the certified parent `f1e8e18`.** `status: DEFERRED_BY_DEPENDENCY - REQUIRED AT PHASE 8`, `green_at_phase: P8`, `accountable_unit: U8.1`. |
| `eval/tests/test_phase0_null_gate.py` | **byte-identical to the certified parent** (`git diff` empty). Not weakened. |
| `phase-0-baseline-manifest.yaml` | **identical to the rejected candidate** — this remediation never touched it. Its P4 changes are the detection/violation records, made in the earlier checkpoint. |
| Production provider injects a credentialed writer? | **No.** `writer=None` explicitly, → the dark default bounded writer. |
| Default outcome | **Refusal / proven non-occurrence.** With the dark default adapter the outcome is `FAILED` / `PROVEN_NON_OCCURRENCE`, never a laundered success. |
| Env var silently enabling consequential writes | **None found.** No environment variable reaches an effect switch; `NEYMA_OPERATION_URL_FILTER` no longer decides origin safety. |
| Fallback escaping the governed seam | **None.** |

**Regression guard demonstrated, not asserted.** In disposable clone 2 I added a throwaway
`src/freight_recon/_rr_u81_probe.py` registering `raise_invoice` and `record_payable` on a real
`GateRegistry`, purged `__pycache__`, and ran the guards:

```
FAILED test_phase0_null_gate.py::test_the_production_gate_registration_population_is_still_empty
AssertionError: a production module now REGISTERS typed gates: _rr_u81_probe.py:6. The
AC-CKPT-6-missing deferral rested on the production registration population being zero. It is not
zero any more - re-adjudicate the case instead of inheriting the deferral.
1 failed, 5 passed
```

The probe was deleted, `__pycache__` purged, guards returned **6 passed**, and the clone tree
restored to `a3e704645b8a06561d90cdb5f81288309ae51850` **exactly**. No tracked file was touched and
no `git checkout/restore/stash/clean` was used. The demonstration was not made permanent.

The candidate is **not** rejected for an empty production `GateRegistry` — that is the founder's
decision, and the candidate implements it correctly and honestly.

---

## F. F-02 disposition — **DISCHARGED**

Prior finding: an empty/absent URL filter allowed cross-origin navigation and produced a false
"on the TMS domain allowlist" reason.

The authority is now `established_origin`, a **parsed** `Origin(scheme, host, effective port)`
(`cdp_readonly.py:715–765`). `url_filter` is an **additional narrowing** only
(`navigation_target_is_allowed`, `:1126–1196`). `select_load_detail_link` (`:971–1082`) calls
`link_origin_refusal` (`:918–948`) for **every** candidate, over **both** the raw `href` and the
browser-resolved URL. Origin is operator-established (`allowed_origin=` at construction, or the
first `visit()` to an operator-configured entry URL) and **immutable thereafter** (`:1313–1327`).
A malformed `allowed_origin` **raises at construction**. All six navigator construction sites in
`run_action_callback_server.py` (×5) and `propose_ar_from_tms.py` (×1) pin the origin explicitly.

### F.1 Navigation policy — my own battery, 22 cases

| Case | Result |
|---|---|
| **empty filter + cross-origin** | **REFUSED** — "cross-origin navigation refused: `https://attacker.example:443` is not the established origin" |
| **absent filter + cross-origin** | **REFUSED** |
| no established origin at all | **REFUSED** — "no established origin … fails CLOSED" |
| no origin + empty filter | **REFUSED** |
| `//evil.example/path` | **REFUSED** — resolved scheme-relative, then refused as cross-origin |
| `//tms.test/loads/L-101` | ALLOWED (correctly same-origin) |
| `https://trusted.example@evil.example/path` | **REFUSED** — embedded credentials named specifically |
| `javascript:` / `data:` / `file:` | **REFUSED** |
| `javascript://tms.test/%0aalert(1)` (unsafe scheme, trusted hostname) | **REFUSED** |
| `https://tms.test:8443/…` (mismatched port) | **REFUSED** |
| `http://tms.test/…` (scheme downgrade) | **REFUSED** |
| trailing-dot host / subdomain | **REFUSED** |
| safe relative `/loads/L-101`, `?load=…` | ALLOWED |
| same-origin absolute, explicit `:443`, uppercase host | ALLOWED |
| malformed origin config | **REFUSED** |

The prior report's two literal proof lines are now **inverted**: both formerly-ALLOWED cases refuse.

### F.2 Selector — 18 cases, including all ten required regression classes

| Case | Result |
|---|---|
| same load text, **foreign href** | **REFUSED** |
| foreign href + **empty** filter / **no** origin | **REFUSED** |
| `//evil.example/loads/L-101` | **REFUSED** |
| userinfo href | **REFUSED** |
| unsafe scheme on trusted hostname | **REFUSED** |
| disallowed port | **REFUSED** |
| safe relative detail route | SELECTED |
| safe same-origin absolute route | SELECTED |
| `/loads/L-101/delete`, `/loads/L-101/purge_all` | **REFUSED** |
| `data-method="delete"` | **REFUSED** |
| `?_method=delete` | **REFUSED** |
| `<base>` → foreign resolved URL | **REFUSED** (resolved URL checked) |
| `<base>` → same-origin delete route | **REFUSED** |
| `javascript:` URL | **REFUSED** |
| `?next=https://evil.example/` open-redirect param | **REFUSED** |

**Destructive-link protections were not displaced by the origin policy** — every pre-existing barrier
still fires, on the established origin, where only it can refuse.

### F.3 Allow reasons describe checks that actually ran

```
no filter configured -> "... and same-origin as the established https://tms.test:443
                         (no additional TMS domain filter configured; the parsed-origin check is
                          what admitted it)"
filter configured    -> "... (also matched the configured TMS domain filter 'tms.test')"
```

No allowlist is claimed that was not configured. `_origin_defect()` names the **specific** defect
(embedded credentials / malformed host / non-http(s) scheme / bad port) rather than a three-way guess.

**F-02 is discharged.**

---

## G. Full P4 hostile review

| Surface | Finding |
|---|---|
| **EP-1 callback + governed write containment** | Sound. Write cut real; governed handler tried first and answers governed taps itself; every fail-closed path records a named `GovernedWriteRefused`. |
| **EP-3 proposal navigation and provenance** | Sound (§F). `follow()` re-derives the record from the live page, demands exact equality, enforces observation-context freshness, re-checks the landed URL, and fetches the URL it classified. |
| **EP-8 TMS orientation** | Sound. `orient_tms.py` holds a read-only observer and imports no adapter. |
| **EP-14 browser-use read/write split** | **Structural, not naming-based.** AST: `browser_use_adapter` does **not** import `browser_use_write`, and `browser_use_write` does **not** import `browser_use_adapter` (both *name* each other in prose only). `browser_use_adapter`'s entire public surface is `read_load`, `read_payable`, `run_vetted`, `render_vetted_task` — no write method. |
| **cdp_readonly** | `ReadOnlyCdpObserver` and `ReadOnlyCdpNavigator` carry **no** forbidden primitive (`evaluate`, `command`, `send`, `navigate`, `click`, `type`, `select`, `set_file_input`, `upload_file`, `execute`, `run`, `write`, `submit`) — checked over `dir()`, so **inherited** methods are covered. Both use `__slots__`; attribute injection on the observer is refused (`no __dict__ for setting new attributes`), so a monkeypatched origin or channel cannot be attached. |
| **browser_use_write** | Bounded; the dark default refuses non-loopback base URLs and refuses to run with no injected runner. |
| **operation_proposal / governed_approval** | Bindings load-bearing (§D.3). Approval-identity binding added and guarded by mutant B48. |
| **governed_write_registry** | One-method lookup boundary; expiry honoured; integrity anchor present but incomplete — **RR-01**. |
| **governed_write_route** | The join; reviewed in full above. |
| **effect_boundary** | `verification_mode` is **hardcoded** to `READBACK_VERIFIABLE` when the `AdapterOperation` is built, so a tampered `verification_mode` on the typed operation is inert. |
| **Import / entry-point manifests** | Live probe: **13** detection edges, **0** violation edges; recorded `recomputed_edges: 13`, `violation_edges: []` — **exact both-sided agreement**. `sources_inspected` = 152, `unmatched` = 0. |
| **Mutation guards / false-green defences** | §H. |
| **Finalizer locking** | §I — 16/16 hostile probes pass. |

### Structural bypass attempts — all failed

- **Aliases / inherited methods:** covered by the `dir()`-based forbidden-primitive sweep.
- **Dynamic imports / factories:** no `importlib`, `__import__`, `eval(`, `exec(`, `pkgutil` or
  `entry_points` seam in `src/` or `scripts/` reaching an adapter. The legacy
  `_build_live_operation_router` factory is **deleted**, not disabled.
- **Monkeypatch seams:** `__slots__` blocks attribute injection on the read surfaces.
- **Fallback configuration:** `operation_router` is a single unconditional literal `None`.
- **Arbitrary natural-language tasks:** `render_vetted_task("arbitrary; click submit; POST /invoices", …)`
  → `TmsAdapterError: … is not a vetted read task`.
- **Arbitrary JavaScript / URLs / selectors:** no `evaluate`/`command` exists; URLs pass the parsed
  origin policy plus the route-family classifier; there is no selector parameter on the surface.
- **Caller-defined field names:** `approved_fields` keys are an exact allowlist
  (`{customer, carrier, amount, load_ref, invoice_ref}`); a stray key raises at construction.
- **Caller-defined browser commands:** the navigation channel allowlists two CDP methods and has no
  script-running path at all.
- **Encoded behaviour inside structured payloads:** `InvoiceWriteOperation` has no field for a task,
  selector, URL-to-execute, JavaScript, adapter method or browser command. Residual: approved-field
  *values* remain unconstrained strings interpolated into an LLM task at P12 (prior F-08, still open).

**Read-only consumers cannot actuate.** Proven structurally, not by naming.
**The old direct callback-to-actuator route is unreachable.** Proven by AST import closure.

---

## H. False-green and mutation review

### Reproduced exactly

```
canonical suite (disposable clone, canonical config, PYTEST_ADDOPTS cleared):
    1961 passed, 0 failed, 1 skipped, 1962 collected   (392.66s)
node manifest:      1962 vs 1962, IDENTICAL BY IDENTITY, zero symmetric difference
manifest_sha256:    44b5457125e7… recomputed via the canonical composer == recorded
mutation battery:   61/61 CAUGHT — 0 MISS, 0 SETUP-FAIL, 0 RESTORE-RED
clone tree after:   a3e704645b8a06561d90cdb5f81288309ae51850  (byte-exact restoration)
violation edges:    0 live / 0 recorded, both-sided
detection sites:    13 live == 13 recorded
loopback callbacks: 34 passed (sockets bound successfully here; nothing weakened or deleted)
```

### Harness soundness (verified by reading `_run_text_case`)

Guard-green **precondition**; anchor **uniqueness** (`n > 1` → SETUP-FAIL); **no-op detection**;
`__pycache__` purge before and after; **byte-for-byte restore assertion**; guard re-run **after**
restore. A mutant cannot be scored CAUGHT by a harness accident.

### The retargeted and new mutants each attack their claimed invariant

| Mutant | What it actually removes | Verdict |
|---|---|---|
| **B30** (retargeted) | `if candidate != established:` → `if False:` — the **origin comparison itself** | Genuine. The old B30 (scheme denylist) had become a semantic no-op after the F-02 fix; retargeting was correct, not a silent acceptance. |
| **B30b** | the fail-closed `if established is None:` branch | Genuine — proves an empty filter does **not** make the tests vacuously green. |
| **B30c** | `select_load_detail_link`'s call to `link_origin_refusal` | Genuine — selector-level bypass. |
| **B44** | replaces `build_checkpoint_approval` with a self-minted `ApprovalRecord(approval_id='ap-1', actor_id='owner:rasheed')` | **Reintroduces F-01 exactly.** |
| **B45** | `intents = []` — the consumer stops reading the queue | Genuine. |
| **B46** | the consumption boundary's approval-identity check | Genuine. |
| **B47** | the single-consumption claim | Genuine. |
| **B48** | the envelope's `approval_id` binding | Genuine. |
| **B49** | the deployed wiring in `run_action_callback_server` | Genuine — the deployed half. |
| **B50** | the registry's payload-hash integrity anchor | Genuine. |
| **B51** | proposal expiry | Genuine. |
| **B52** | the stored-channel-receipt requirement | Genuine. |

None is subsumed by another and none is incapable of changing behaviour — the origin decision was
deliberately consolidated into one function so a single edit removes the whole decision. Each
required false-green condition holds: removal of the real caller, of the queued-intent consumer, of
the approval-identity binding, and of the origin check each makes a named guard **fail**.

### Negative-corpus population anchors

`_production_sources()` asserts `len(sources) > 50` and that the defining module is present;
`_origin_corpus_is_real()` gates nine origin tests; the null-gate probe asserts by name that the
intended files were parsed; the import gate's `require_population()` still enforces
`sources_inspected` and `unmatched` after `declare_empty_is_legitimate()`. The empty violation set is
positively anchored by 152 inspected sources and 13 live detection edges.

**One weaker link (non-blocking).** `test_the_queued_write_intent_has_a_real_production_consumer` and
`test_the_authenticated_callback_path_reaches_the_governed_route` use **substring** membership rather
than AST call nodes, so a mere mention in a comment would satisfy them. The invariants they guard are
independently covered by mutants B45/B49 and by the behavioural end-to-end tests, so this is
defence-in-depth thinness, not a false green. Recorded as **RR-06**.

---

## I. Finalizer-lock review — **SOUND, 16/16**

Reviewed and hostile-tested in an isolated disposable git repository (the primary worktree was not
used and **no finalization was performed**). Acquisition is in `main()` around the entire
`finalize()` call — before any suite run, receipt deletion or status write.

| Probe | Result |
|---|---|
| Two concurrent invocations | **PASS** — second refused immediately |
| Refusal names the live owner | **PASS** |
| Refusal explicitly forbids log-presence reclaim | **PASS** |
| Released on owner exit | **PASS** |
| Differing `TMPDIR` | **PASS** — lock identity is the git **common dir**, not `TMPDIR` |
| Lock lives in the git common dir | **PASS** |
| Held by a live child → we are refused | **PASS** |
| `current_owner()` reports the live child | **PASS** |
| `SIGKILL`ed owner (crash) | **PASS** — kernel released, no stale wedge |
| Re-acquirable after crash | **PASS** |
| **Forged dead-PID record** | **PASS** — forging the JSON does **not** release the flock |
| `describe()` says "not running" yet the lock is still denied | **PASS** |
| Stale lock file, no holder | **PASS** — acquirable, no timeout heuristic needed |
| Exception inside the critical section | **PASS** — released |
| PID reuse: acquire path never calls `_process_alive` | **PASS** |
| Acquire is `LOCK_NB` (non-blocking, no timeout) | **PASS** |

The losing process exits `2` having modified nothing: it never reaches receipt deletion, suite
execution or a status write. The failure mode that produced the original double-finalizer —
inferring death from a missing log — is structurally impossible.

---

## J. F-04 evidence disposition — **PARTIALLY DISCHARGED, correctly classified**

### Legally candidate-bound before review

| Artifact | Binding | Verdict |
|---|---|---|
| `GATE-RESULT.json` (**uncommitted**, primary worktree) | `commit 0891d1a19a9c47155a56a3f4b2116e5a4d4aa75e`, `tree a3e704645b8a06561d90cdb5f81288309ae51850`, counts `1961/0/1/1962`, `node_manifest_sha256 44b5457125e7…` | **CORRECT.** Written by its canonical generator; all nine steps exit 0. |
| `TEST-NODE-MANIFEST.json` (**committed**) | 1962 nodes, `manifest_sha256 44b5457125e7…` = GATE-RESULT's field; identical by identity to live collection | **CORRECT.** |

### Reserved for the post-adjudication finalizer

All four remaining artifacts are in `finalize_status.STATUS_METADATA_FILES` — I verified the tuple
directly. Hand-editing them is the forbidden status write.

| Artifact | State | Disposition |
|---|---|---|
| `CURRENT.md` | `content_commit: 3d231731…` in **both** committed and uncommitted copies | **finalizer-owned** — legitimately deferred |
| `SUITE-RESULT.json` | `3d231731…` | **finalizer-owned** |
| `BUILD-STATUS.yaml` | `3d231731…` | **finalizer-owned** |
| `IMPLEMENTATION-REGISTRY.yaml` | `baseline_commit 3d231731…` | **finalizer-owned** |

I do **not** demand manual edits to these. Their staleness is a consequence of the design in which
the finalizer owns and rebinds them and has not yet run.

### Stale-reference classification (committed tree, verified by `git grep`)

| Reference | Where | Classification |
|---|---|---|
| `3d231731` | exactly the 5 finalizer-owned status files + the preserved report | **stale candidate binding reserved for the finalizer** |
| `72512b9`, `8e2d0dc`, `95cf5af7` | **only** inside the preserved rejected review | **preserved rejected-review evidence / legitimate history** |
| `0891d1a`, `a3e70464` | **absent** from the committed tree | consistent with finalizer ownership |

**The rejected review remains attributable to `95cf5af7`** and no artifact states it reviewed
`0891d1a`. **No status artifact prematurely claims P4 COMPLETE or R-07 CONTAINED** — verified in the
committed and uncommitted `CURRENT.md`, `BUILD-STATUS.yaml` and `IMPLEMENTATION-REGISTRY.yaml`, all
of which record **"NOT COMPLETE"** and **"OPEN — NOT CONTAINED"**.

---

## K. Findings, ordered by severity

---

### RR-01 — The pending-write integrity anchor does not cover `base_url`, contradicting its own stated guarantee
**Severity: MEDIUM · Confirmed defect (defence-in-depth gap) + evidence deficiency · Does NOT block P4 · Does NOT block R-07 containment**

**Requirement.** Hostile obligation: "callback attempt to inject amount, counterparty, load, invoice,
adapter, **target URL** or operation fields". `governed_write_registry.py:313–318` claims: *"One
changed byte anywhere (the event row, the money table, this reconstruction) yields a different hash
and no authorization at all."* `governed_write_route.py:49–53` claims every consequential value *"is
covered by the payload hash the human's signature binds, and is refused if it differs by a single
byte."*

**Files.** `src/freight_recon/freight_operations.py:163–187` (`payload_hash` canonical set);
`src/freight_recon/governed_write_registry.py:310, 313–318`;
`src/freight_recon/governed_write_route.py:536–570` (`approval_operation_mismatch`).

**Failing invariant.** `payload_hash()` covers `tenant`, `work_item_id`, `load_id`, `invoice_ref`,
`target_integration`, `target_account`, `operation_class`, `approved_fields`, `revision`. It does
**not** cover `base_url`. `approval_operation_mismatch` does not check `base_url` either, and the
signed envelope does not carry it. `base_url` is therefore the one consequential value that is
**neither hashed nor signed** yet travels to the adapter.

`approval_id`, `capability_id`, `idempotency_key` and `pipeline_instance_id` are also outside the
hash but **are** separately bound by the signed envelope and refused on mismatch — verified. `sandbox`
is outside the hash but a non-sandbox operation is refused before any claim — verified.
`verification_mode` and `expected_preconditions` are outside the hash but **inert**
(`effect_boundary.py:690` hardcodes `READBACK_VERIFIABLE`).

**Mechanical proof.**
```
field                  payload_hash changes?
target_integration     YES (bound)
approved_fields        YES (bound)
base_url               NO   <-- UNBOUND
```
```
# operation presented with base_url=https://evil.example, envelope signed for localhost:
default DARK adapter  -> executed: True | state: FAILED | cause: PROVEN_NON_OCCURRENCE   (contained)
injected writer (P12) -> executed: True | state: VERIFIED
                         base_url the adapter received: https://evil.example
```

**Reachable path.** Not from the callback — the callback cannot supply operation fields, and
`test_callback_data_cannot_replace_operation_fields` covers a `base_url` injection attempt. The
reachable path is a **tampered stored proposal row**: `_rebuild` reconstructs the operation with the
tampered `base_url`, the payload hash still matches, every binding verifies, and the operation
reaches the adapter. The payload-hash anchor exists precisely to make store tampering detectable; it
detects amount, counterparty and load tampering but not target-URL tampering.

**Consequence.** Containment of the write's target URL rests **entirely** on
`browser_use_write.SandboxInvoiceWriteAdapter._refuse_if_not_dark`'s loopback check, not on the
approval binding. Today that holds and the effect is dark, so this is not a live exposure. At P12,
when a real writer is injected and the loopback restriction is lifted, the field becomes an unbound,
tamper-survivable target-URL. Compounding: `_refuse_if_not_dark` skips the check entirely when
`base_url` is empty (`if base_url and not …`) — prior finding F-09, still open.

**Classification: confirmed defect (defence-in-depth), non-blocking for P4/R-07 because the
capability is dark and the deployed route is fail-closed.**

**Narrowly scoped remediation.** Either add `base_url` (and `sandbox`) to `payload_hash`'s canonical
set, or check them in `approval_operation_mismatch`, or record explicitly in the module that the
anchor binds *approved business facts only* and that target-URL containment is the adapter's
property — and correct the two docstrings that currently overclaim. Add a mutant that tampers the
stored `base_url` and asserts refusal. Treat this as a **P12 precondition**.

---

### RR-02 — The remediation handoff misstates the gate-result binding it asks the reviewer to check
**Severity: LOW · Evidence deficiency · Does not block P4 · Does not block R-07 containment**

**File.** `docs/implementation/p4-remediation-handoff.md:283` (untracked, primary worktree).

**Failing invariant.** The handoff states `GATE-RESULT.json` is *"Rebound to `0891d1a19a9c…` /
`8e12372a27…`, `node_manifest_sha256 fbf0f7fa…`"*. The actual file records `tree
a3e704645b8a06561d90cdb5f81288309ae51850` and `node_manifest_sha256
44b5457125e79e3dee21768684823f2ab7ab03c362a11577974ccd38d39dfd40`, completed `2026-07-29T07:01:31Z`.
`8e12372a27` is a real tree object but not the candidate's; `fbf0f7fa…` matches nothing current.

**Consequence.** The artifact is **correct**; the handoff is stale — evidently written before a
final regeneration. A reviewer who trusted the handoff instead of the file would have reported a
false F-04 failure. This is precisely why the handoff must not be treated as review evidence. It is
untracked and not part of the candidate, so it does not affect the artifact under review.

**Remediation.** Correct the handoff's §6 row, or delete the numeric claim and point at the file.

---

### RR-03 — The production-gate-registration probe scans only `src/`, so a relocation to `scripts/` would evade it
**Severity: LOW · Non-blocking residual risk**

**File.** `eval/tests/test_phase0_null_gate.py:76, 86, 173, 183` — the probe walks
`Path(freight_recon.__file__).parent.rglob("*.py")`.

**Failing invariant.** A production `GateRegistry` population placed under `scripts/` would not be
seen. The candidate is **clean today**: I verified mechanically that no module under `scripts/`
constructs or populates a `GateRegistry` (only explanatory comments), and the builder discloses that
relocation was considered and deliberately rejected.

**Consequence.** The U8.1 guard's coverage is narrower than its claim. No current exposure.

**Remediation.** Extend the probe's corpus to `scripts/` (asserting the population anchor there too)
before U8.1.

---

### RR-04 — Mutant B34's label still names a symbol it does not mutate
**Severity: LOW · Evidence deficiency · Does not block P4**

**File.** `scripts/mutate_phase4_boundary.py` (B34).

B34 is labelled *"**browser_use_adapter** is declared non-effect-capable while nothing about the
module changed"*; the mutation removes **`cdp_actuator`**. This is prior finding **F-05**, carried
forward unremediated and **explicitly disclosed** as out of this remediation's scope. It remains a
real, passing mutant — but it is not evidence for the claim its label makes, and the
`browser_use_adapter` reclassification therefore still lacks a mutant that exercises it directly.
My independent structural check (§G: no write method, no AST import in either direction, vetted-task-ID
transport, `__slots__`) supports the reclassification on the merits.

**Remediation.** Correct the label to name `cdp_actuator`; add a mutant that restores a write method
or a `browser_use_write` import to `browser_use_adapter` and asserts the read-only surface tests fail.

---

### RR-05 — Numeric self-contradictions persist in the authoritative narrative
**Severity: LOW · Evidence deficiency · Does not block P4**

**Files.** `docs/implementation/phase-0-baseline-manifest.yaml` (the P4 EP-1 note: *"violation_edges
is UNCHANGED at 1"*, *"the detection total therefore grows by exactly one authorized boundary edge
(14 → 15)"*); `src/freight_recon/browser_use_write.py:28` (*"Detection edges are unchanged at 14"*).

Verified live state is **13 detection / 0 violations**, and the same file records
`recomputed_edges: 13` and `violation_edges: []`. This is prior finding **F-07**, carried forward and
disclosed. The manifest does mark some paragraphs as superseded predictions;
`browser_use_write.py:28` carries no such marker.

**Remediation.** Reconcile to 13/0 or mark the superseded paragraphs explicitly as historical.

---

### RR-06 — Two production-reachability guards use substring membership rather than AST call nodes
**Severity: LOW · Non-blocking residual risk**

**File.** `eval/tests/test_p4_governed_write_route.py:645–678`.

`test_the_queued_write_intent_has_a_real_production_consumer` and
`test_the_authenticated_callback_path_reaches_the_governed_route` assert
`"handle_governed_write_callback" in src` and similar. A comment or docstring mention would satisfy
them — which matters because these modules *do* name their own machinery in prose. The sibling test
`test_build_checkpoint_approval_has_a_real_production_caller` does it correctly, with AST `Call`
nodes. The invariants are independently covered by mutants **B45** and **B49** and by the behavioural
end-to-end tests, so this is thinness in defence-in-depth, not a false green.

**Remediation.** Convert both to AST call-node analysis, matching the sibling test.

---

### Carried forward from the rejected review, unremediated and disclosed (all non-blocking)

| Prior finding | Status in `0891d1a` | Verified |
|---|---|---|
| **F-03** `ReadOnlyBrowserUseRunner` does not validate `base_url` | **PERSISTS** — `render_vetted_task("read_tms_load", base_url="https://evil.example.com/x", …)` returns `"Open https://evil.example.com/x/loads/LD-560002.html."` | by execution |
| **F-05** B34 label | **PERSISTS** → RR-04 | by inspection |
| **F-06** route family is a denylist | **PERSISTS** | by inspection |
| **F-07** numeric contradictions | **PERSISTS** → RR-05 | by inspection |
| **F-08** approved-field *values* unconstrained | **PERSISTS** — keys allowlisted, values arbitrary strings interpolated into an LLM task | by inspection |
| **F-09** duck-typed writer; empty `base_url` skips the loopback check | **PERSISTS** — compounds RR-01 | by inspection |
| **F-10** conditional workspace/message-ts binding | **PARTIALLY MITIGATED** — `expected_workspace_id`/`expected_message_ts` are still checked only when non-empty, but `channel_id` is unconditional **and** the deployed callback now hard-refuses a missing stored channel receipt (`NO_STORED_CHANNEL_RECEIPT`, mutant B52) | by execution |

The builder named all of these as deliberately out of scope. Only F-01 and F-02 were P4-blocking and
R-07-blocking, and both are discharged.

### Test-environment limitations

**None.** The loopback socket-bound action-callback tests **bound successfully and passed (34) in
this environment**; no socket coverage was weakened or deleted. The single local-only failure the
builder disclosed (`test_build_status_receipt_consistency`, caused by the uncommitted finalizer-owned
`GATE-RESULT.json` disagreeing with the committed `BUILD-STATUS.yaml`) does **not** occur in the
clean clone — I confirmed `1961 passed, 1 skipped` with zero failures there. It is discharged by
finalization.

---

## L. Verdict

# ACCEPT FOR SEPARATE FINAL ADJUDICATION

Both blocking findings from the rejected candidate are **discharged on independent evidence**, not on
the strength of the handoff:

1. **F-01 — DISCHARGED.** The governed chain exists as production code. `build_checkpoint_approval`
   has a real production caller reachable from the authenticated Slack callback;
   `GovernedWriteIntentQueued` has a real, atomically single-use consumer; and one continuous
   approval identity (`appr-9` / `U-OWNER`) travels from the signed envelope to the queued intent, the
   checkpoint witness row, the `effect_grants` row and the typed operation the **adapter itself
   received** — verified by my own probe reading the database, with `ap-1` appearing nowhere.
   Nineteen hostile classes refuse with zero external attempts; repeated and concurrent delivery
   produce exactly one attempt and one grant; `UNKNOWN_OUTCOME` escalates to a named human and cannot
   auto-retry a possibly-completed write.

2. **F-02 — DISCHARGED.** The origin decision is a parsed, operator-established, immutable
   `Origin(scheme, host, port)` that fails **closed** when absent or malformed. The prior report's two
   literal proof lines are now inverted. Forty adversarial navigation and selector cases behave
   correctly, the destructive-link protections are undisplaced, and the allow reasons no longer claim
   an allowlist that was never configured.

3. **Founder decision honoured exactly.** Production `GateRegistry` population is empty, nothing was
   relocated to evade the probe, `AC-CKPT-6-missing` and `test_phase0_null_gate.py` are unchanged from
   the certified parent, and the deployed route reaches the governed seam and stops at a **recorded**
   `ROUTE_NOT_CONFIGURED` refusal with no grant minted. I demonstrated that the regression guard fires
   on a premature production gate registration and restored the environment byte-exactly.

4. **Every claimed result reproduced** under independent execution: `1961/0/1/1962`, the node manifest
   identical **by identity**, 61/61 mutants caught with byte-exact restoration, 0 live / 0 recorded
   violation edges both-sided, 13 detection sites, 34 loopback callback tests, and 16/16 finalizer-lock
   hostile probes.

**F-04 remains partially open and is correctly classified.** The two artifacts that can legally bind
to this candidate before adjudication do bind to it correctly. The four that still name `3d231731`
are all in `STATUS_METADATA_FILES` and are genuinely finalizer-owned; deferring them is right, not a
deficiency of this candidate. **An adjudicator must not read the committed status metadata as
describing `0891d1a`.**

Acceptance is **for separate final adjudication only**. It is not an adjudication, and it does not
authorize finalization.

**Scope note for the adjudicator.** R-07 remains **OPEN — NOT CONTAINED** and P4 remains **NOT
COMPLETE** until an authorized adjudicating session — not this reviewer — records otherwise. RR-01
should be recorded as a **P12 precondition** before any live writer is injected. Weighted acceptance
has not been instantiated and this report does not instantiate it. This reviewer performed no
remediation, no finalization and no adjudication.

---

## M. Preserved report location

**Repository authority consulted.** `PROGRESS-PROTOCOL.md` §"integration topology" (the unit is
replayed as one content commit before review; finalization commits **on top**, never by altering the
reviewed commit), `integration-topology-procedure.md` §3, and `CLAUDE.md` §11 / the `⛔`
self-adjudication rule. The established mechanism for an independent-review report is a markdown
file under `docs/implementation/`, committed by a **later authorized step** — the precedent being
`p3-genuine-independent-review.md`, `p3-independent-review-findings.md`,
`u-rebaseline-review-1-independent-report.md` and `u-handoff-2b-hostile-review-report.md`.

**This report is preserved at:**

```
/Users/sammyfammy/Desktop/freight-logistics-operational-teammate/
    docs/implementation/p4-independent-rereview-report-0891d1a.md
```

It is a **new, untracked file** in the primary worktree. It therefore:

- does **not** modify or invalidate the reviewed content commit `0891d1a19a9c…` — tree
  `a3e704645b8a…` is unchanged and still verifies;
- does **not** overwrite the historical rejected-candidate report
  (`p4-independent-review-report.md`), whose byte-exact original also remains at
  `refs/preserve/p4-independent-review-95cf5af`;
- modifies **no existing file**, tracked or untracked;
- introduces no new product content path — it uses the directory canonical authority already
  designates for independent-review reports;
- names in its own title and header the exact candidate it reviewed, `0891d1a19a9c…`.

**Residual governance note — a real limitation, not a blocker.** Making this report *durable*
requires either a commit or a ref update, and this reviewer is explicitly forbidden both. The
repository's own authorized mechanism for durably preserving a review without mutating the reviewed
candidate exists and is demonstrated in this very repository —
`refs/preserve/p4-independent-review-95cf5af`, a commit whose **parent is the reviewed candidate**
and which adds only the report, leaving the candidate's tree untouched. That mechanism should be used
for this report by the authorized adjudicating or finalizing session. Until then the report is
readable in full at the path above, which satisfies the requirement that the complete source report
be readable by the separate adjudicator; its durability depends on that later authorized step.

**SHA-256 of this report** is recorded alongside it at
`docs/implementation/p4-independent-rereview-report-0891d1a.md.sha256`.

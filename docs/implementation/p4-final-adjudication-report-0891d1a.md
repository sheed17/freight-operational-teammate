# P4 — SEPARATE FINAL ADJUDICATION

**Adjudicated candidate: `0891d1a19a9c47155a56a3f4b2116e5a4d4aa75e`**

**Verdict: ACCEPT P4 FOR FINALIZATION**

Adjudicator: fresh session. Did not implement P4, did not remediate it, did not perform either
independent review, did not author the handoff, and did not resume any prior session.
Adjudication date: 2026-07-29.

> This is the **final adjudication** required by `CLAUDE.md` §11 and the P4 unit block's
> `remaining_before_p4_completion`. It sets the weighted acceptance results from independent
> evidence. It does **not** run the finalizer, does not write status metadata, does not mark P4
> COMPLETE by hand, does not mark R-07 CONTAINED, pushes nothing and enables no effect. Recording
> status remains the act of the single authorized finalizing session, and §7 states exactly what
> that session must verify first.

---

## A. Identity verified independently

Every value below was read from the object store, never from the handoff or either report.

| Property | Expected | Verified | Result |
|---|---|---|---|
| Candidate commit | `0891d1a19a9c47155a56a3f4b2116e5a4d4aa75e` | identical | **MATCH** |
| Candidate tree | `a3e704645b8a06561d90cdb5f81288309ae51850` | identical | **MATCH** |
| Candidate parent | `f1e8e1893eff2460d68f3f168f18fd29635b250d` | identical | **MATCH** |
| Accepted-review preservation ref | `refs/preserve/p4-independent-rereview-0891d1a` | → `5ca6d2e95896336f447cf693da04282a0d53bdbf` | **MATCH** |
| Preservation commit parent | the candidate | `0891d1a19a9c…` | **MATCH** |
| Preservation commit contents | report + sidecar only | `2 files changed, +778`, no deletions | **ADDITIVE ONLY** |
| Accepted-report SHA-256 | `181e1a37a413fd35f537e00a7e1423bf192f88205270fa15932fbabeb955d316` | worktree file, preserve-commit blob **and** committed sidecar all hash to it | **MATCH ×3** |

**Repository topology is the legal `PRODUCING` state.** `CURRENT.md` records `3d231731b8b0…`,
which is `HEAD^^`; `HEAD^` is `f1e8e1893eff…`, a **pure** status-metadata commit (I diffed it: it
touched only `BUILD-STATUS.yaml`, `CURRENT.md`, `GATE-RESULT.json`, `IMPLEMENTATION-REGISTRY.yaml`,
`SUITE-RESULT.json` — all five in `finalize_status.STATUS_METADATA_FILES`); `HEAD` is the candidate.
`eval/tests/test_status_reality.py:85–92` recognises exactly this shape.

**No candidate mutation after review.** The branch reflog's most recent entry is the candidate
itself at `2026-07-28 23:54:18 -0700`. The accepted report was written at `00:47–00:48` and
preserved at `01:01:15`. No branch update, amend, reset or rebase occurred after the candidate, and
`HEAD@{0}` is the candidate.

**No protected ref movement.** `main` and `origin/main` both resolve to `152574e4…`, unchanged —
the value `PROGRESS-PROTOCOL.md` §10 already records. Every `refs/preserve/*`, every
`archive/p4/content-*` and every `refs/remotes/origin/*` holds a pre-existing value. Nothing was
pushed.

**No builder or finalizer owns the repository.** `finalizer_lock.current_owner()` → `None`; `lsof`
reports no holder on either `.git/neyma-finalizer.lock` or `.git/neyma-builder-worktree.lock` (both
0-byte — and the lock is `flock`-based, so an unheld file is not a wedge); no `finalize_status`,
`clean_clone_gate` or `mutate_phase4_boundary` process is running; `git worktree list` shows one
live worktree plus one prunable stale entry on an unrelated docs branch.

**The historical rejected review is intact and correctly attributed.** The byte-exact original at
`refs/preserve/p4-independent-review-95cf5af` (parent `95cf5af7d9ea…`) hashes to
`7d15bdbba533…4483`. The tracked copy in the candidate differs by **exactly** a 23-line prepended
disarming banner — `diff` reports `0a1,23` and nothing else, zero deletions and zero modifications.
The rejected candidate's tree still resolves to `4b3dda2019…`. No artifact anywhere states that the
rejected report reviewed `0891d1a`.

## B. Reviewer independence

The accepted re-review attests independence in its §B. I corroborated it rather than accepting it:

- It **contradicts the handoff it was given** (RR-02) with a mechanically correct correction — the
  handoff's §6 claims tree `8e12372a27…` and `node_manifest_sha256 fbf0f7fa…`; the actual
  `GATE-RESULT.json` records tree `a3e704645b8a…` and `44b5457125e7…`. I confirmed both. A session
  inheriting the handoff's conclusions could not have found that.
- It reviews the candidate and is not part of it; its preservation commit is a **child** of the
  candidate, leaving tree `a3e70464…` untouched.
- Its timeline sits wholly after the candidate was finalized and wholly before preservation.

**Stated limit, honestly.** In a single-operator local repository every session commits under the
same git identity, so independence cannot be proven cryptographically. It rests on attestation plus
the corroboration above. That is the same basis on which P3's independent review was accepted, and
I adjudicate it sufficient — but it is an attestation, not a proof, and I record it as such.

---

## C. The four required adjudications

### C.1 — F-01 governed path · **DISCHARGED**

**The join exists in production code with exactly one production caller.** My own AST sweep over
`src/` and `scripts/` finds `build_checkpoint_approval` defined at `governed_approval.py:365` and
called from exactly **one** production call node outside its defining module:
`governed_write_route.py:307`, inside `consume_governed_write_intent`. Not a comment, not an import
— a `Call` node.

**The real callback reaches the bounded provider and the governed-kernel seam.** I drove the real
production builder `run_action_callback_server._build_governed_write_route` directly:

```
Governed write route: lookup boundary WIRED and DARK; execution kernel BLOCKED pending
adjudication of AC-CKPT-6-missing (Action Class gate registration is U8.1/P8).
governed_write_provider : WIRED
governed_write_kernel   : None
# and with no signing secret:
no-secret -> provider: None  kernel: None
```

The provider is a **lookup**, not a builder: `WorkflowStorePendingWrites(...).pending_for(...)`
with `writer=None`, so the deployed entry point registers no credentialed adapter and the callback
cannot add, replace or edit an operation field. Absent a signing secret or a canonical tenant the
route does not exist at all rather than existing unauthenticated.

**A test-supplied kernel proves the full authority chain, and is kept distinct from the deployed
shape.** The founder decision expressly permits this. `phase3_kit.make_kernel` supplies the kernel
in `test_p4_governed_write_route.py` / `test_p4_governed_invoice_write.py`, which carry one
continuous approval identity from the signed envelope through the queued intent, the checkpoint
witness row, the `effect_grants` row and the typed operation the adapter receives. Separately,
`test_p4_deployed_governed_route.py` drives the **real** handler through the **real** entry point's
own builder and proves the deployed shape terminates in `ROUTE_NOT_CONFIGURED`. I ran that file
plus the null-gate guards: **33 passed**. The two claims are distinct in the code, in the tests and
in the handoff — the failure mode where a test kernel is passed off as the deployed path does not
occur here.

**Production correctly returns `ROUTE_NOT_CONFIGURED` pending Phase 8.** It is a **recorded**
governed refusal with a named cause (`GovernedWriteRefused`, zero grants minted), not a silent
fall-through, and the governed handler is deliberately not gated on the seams being configured so a
governed token cannot fall into an unrelated handler.

**Mutation-anchored.** B44 replaces the join with a self-minted `ApprovalRecord(approval_id='ap-1',
actor_id='owner:rasheed')` — the exact prior defect — and is caught. B45 (consumer stops reading
the queue), B46 (identity binding), B47 (single consumption), B48 (envelope `approval_id` binding)
and B49 (the deployed wiring) are each caught. I reproduced all of them.

### C.2 — Founder Phase-8 decision · **COMPLIANT**

**Production Action Class registration remains deferred to U8.1.** My own AST sweep for
`GateRegistry(...)` constructions and `register` / `register_gate` calls across **both** `src/` and
`scripts/` returns **zero sites**. The population is empty, and it was not relocated to evade the
probe. `AC-CKPT-6-missing` remains `DEFERRED_BY_DEPENDENCY - REQUIRED AT PHASE 8`,
`green_at_phase: P8`, `accountable_unit: U8.1`, structurally identical to the certified parent, and
`eval/tests/test_phase0_null_gate.py` is byte-identical to the parent — the guard was not weakened.
The independent reviewer additionally **demonstrated** the guard firing on a planted production
registration and restored its clone byte-exactly.

**P4 containment does not require premature production enablement.** P4's acceptance is that *an
external effect without a grant becomes structurally impossible* — the effect-capable violation
surface EMPTY with the gate asserting empty. A deployed route that reaches the governed seam and
**refuses** is strictly more contained than one that executes. Wiring a `GateRegistry` now would
register production gates for `raise_invoice` / `record_payable`, which is U8.1 work, would falsify
the ground `AC-CKPT-6-missing` rests on, and would require founder approval and a committed
acceptance-contract revision under `PROGRESS-PROTOCOL.md` §3. The builder's own comment in
`_build_governed_write_route` names this as a governance decision awaiting adjudication rather than
a missing line. **I adjudicate it correctly deferred.** The empty production `GateRegistry` is not
a defect of this candidate and is not a ground for rejection.

### C.3 — F-02 origin policy · **DISCHARGED, mechanically**

The independent review did not assert the discharge — it re-derived it, and so did I. I ran my own
origin battery against `cdp_readonly.navigation_target_is_allowed` with an established origin of
`https://tms.test`. **The rejected review's two literal ALLOW proof lines are inverted:**

```
url_filter=None  https://attacker.example/loads/L-101 -> REFUSE
   "cross-origin navigation refused: https://attacker.example:443 is not the established origin"
url_filter=''    https://attacker.example/loads/L-101 -> REFUSE  (same reason)
```

Also refused, each with a **specific** named cause: `//evil.example/…` (resolved, then refused
cross-origin), `https://tms.test@evil.example/x` (embedded credentials named explicitly),
`https://tms.test:8443/x` (port), `http://tms.test/x` (scheme downgrade),
`javascript://tms.test/%0aalert(1)`, `data:`, `file:`, `https://tms.test./x` (malformed host),
`https://evil.tms.test/x` (subdomain). Correctly allowed: `/loads/L-101`,
`https://tms.test/loads/L-101`, explicit `:443`, uppercase host, `//tms.test/loads/L-101`.

**It fails closed, not open.** With **no** established origin the surface refuses for every
`url_filter` value including a configured one, and a **malformed** established origin
(`not a url`, `https://`, `javascript://x`, `https://tms.test:notaport`) refuses too. The
allow-reasons no longer claim a TMS domain allowlist that was never configured. B30 (retargeted to
remove the origin comparison itself), B30b (the fail-closed branch) and B30c (the selector's call
into the origin policy) are each caught.

### C.4 — F-04 evidence binding · **CORRECTLY CLASSIFIED**

**`GATE-RESULT.json` binds exactly to the candidate.** It records `commit
0891d1a19a9c47155a56a3f4b2116e5a4d4aa75e`, `tree a3e704645b8a06561d90cdb5f81288309ae51850`, counts
`1961/0/1/1962`, and **all nine steps exit 0** including "clone tree still clean". I verified its
supporting hashes against the candidate's own files rather than against itself:

| Field | Value | Cross-checked against |
|---|---|---|
| `config_sha256` | `22f4294195ba…` | the candidate's `pytest-canonical.ini` — **match** |
| `runner_sha256` | `75b924e9f398…` | the candidate's `scripts/run_canonical_suite.py` — **match** |
| `node_manifest_sha256` | `44b5457125e7…` | `TEST-NODE-MANIFEST.json`'s recorded `manifest_sha256` — **match**, and **recomputed from scratch** through the canonical composer in `regenerate_test_manifest.py` — **match** |
| `tree` | `a3e70464…` | `git rev-parse 0891d1a^{tree}` — **match** |

`TEST-NODE-MANIFEST.json` (committed content) records 1962 nodes and carries the same
`config_sha256` and `runner_sha256`. The evidence chain is closed and self-consistent, and none of
it was taken on the artifact's own word.

**`CURRENT.md`, `SUITE-RESULT.json`, `BUILD-STATUS.yaml` and `IMPLEMENTATION-REGISTRY.yaml` are
genuinely finalizer-owned and may remain bound to `3d231731…`.** I verified the tuple directly at
`scripts/finalize_status.py:70–81` — all four are members of `STATUS_METADATA_FILES`. Hand-editing
them is precisely the forbidden status write that `finalize_status.py`'s own header exists to
prevent. Their lag to the previous certified baseline is a consequence of the design in which the
finalizer owns and rebinds them and has not yet run — **it is not a deficiency of this candidate.**
The candidate touches none of them, which is correct.

**No premature claim exists anywhere.** In the committed tree and in the uncommitted working copy
alike, `CURRENT.md`, `BUILD-STATUS.yaml`, `IMPLEMENTATION-REGISTRY.yaml`,
`EFFECT-PATH-INVENTORY.yaml` and `phase-0-baseline-manifest.yaml` all record **P4 NOT COMPLETE** and
**R-07 OPEN — NOT CONTAINED**, with the manifest explicitly reserving the CONTAINED recording to the
adjudication step as PENDING. An adjudicator must not read the committed status metadata as
describing `0891d1a`, and this one did not.

---

## D. Reproduced evidence — every figure re-derived in my own disposable clone

Environment: a `--no-local` clone of the product repository, checked out **detached** at
`0891d1a19a9c…`, fresh venv, declared dependencies only, `PYTEST_ADDOPTS` cleared, canonical config
via explicit `-c`. The primary worktree was **read only** and was never altered.

| Claim | Reproduced | Result |
|---|---|---|
| `1961 passed, 0 failed, 1 skipped, 1962 collected` | canonical suite, clean clone, 400.00s | **EXACT** |
| Manifest identity exact | live collection 1962 vs recorded 1962, **zero** symmetric difference | **IDENTICAL BY IDENTITY** |
| Manifest hash | recomputed via the canonical composer = recorded = `GATE-RESULT`'s field | **EXACT** |
| Mutation battery 61/61 | `mutate_phase4_boundary.py`, full run | **61/61 caught, 0 MISS, 0 SETUP-FAIL, 0 RESTORE-RED** |
| Mutation tree restoration byte-exact | `git status --porcelain` empty; tree still `a3e704645b8a…` | **BYTE-EXACT** |
| Violation edges 0 live / 0 recorded | `import_probe.effect_adapter_violation_edges()` vs `manifest.recorded_effect_violation_edges()` | **0 / 0, both-sided agreement** |
| Detection count 13 | 13 live sites == 13 recorded edges; `sources_inspected` **152**, `unmatched` `[]`, `rejected` `[]`, `duplicates` `[]` | **EXACT, positively anchored** |
| Callback socket tests 34 passed | `eval/tests/test_action_callback.py` | **34 passed** — sockets bound; nothing weakened or deleted |
| Finalizer lock 16/16 hostile probes | **my own** 16-probe battery, isolated disposable git repo | **16/16** |
| P4 NOT COMPLETE before finalization | registry `status: READY`, `execution_state: IN_PROGRESS`, **no** `acceptance_criteria` block → contributes 0% | **CONFIRMED** |
| R-07 OPEN before finalization | recorded OPEN — NOT CONTAINED in every status and evidence artifact | **CONFIRMED** |

**On the finalizer-lock battery.** I did not inherit the reviewer's result. I wrote my own probes
against a throwaway repository and independently confirmed: lock identity is the git **common dir**
(not `TMPDIR`); a second concurrent acquisition is refused and the refusal names the live owner and
explicitly forbids log-presence reclaim; `current_owner()` reports the live child; **forging a dead
PID into the JSON does not release the `flock`**; a `SIGKILL`ed owner leaves no stale wedge and the
lock is immediately re-acquirable; the lock is released on normal exit and on an exception inside
the critical section; a stale file with no holder is acquirable; the acquire path never consults
`_process_alive`, so PID reuse cannot mislead it; acquisition is `LOCK_NB` with **no** time-based
reclaim heuristic. The mechanism is sound. See **AD-02** for what is nonetheless missing.

**The EMPTY violation surface is not vacuous.** It is positively anchored by 152 inspected sources
and 13 live detection edges, and mutants B40/B41/B42 prove the emptiness assertion fails when an
actuator import is resurrected, when the direct assertion is attacked, and when the manifest lies
by padding a recorded residual with no live edge. The gate asserts EMPTY
(`test_import_gate.py:330`), which is the R-07 **mechanical** close condition.

---

## E. Residual findings

### E.1 — RR-01 · **ADMITTED AS A RECORDED P12 PRECONDITION**

> `payload_hash` does not cover `base_url`, so a tampered stored proposal can carry a foreign
> target URL past the integrity anchor; contained today by the dark adapter's loopback refusal.

**I confirmed every element of this independently, and it is a real defect.**

- `freight_operations.payload_hash()`'s canonical set is exactly `{v, tenant, work_item_id,
  load_id, invoice_ref, target_integration, target_account, operation_class, approved_fields,
  revision}`. **`base_url` is absent.**
- `governed_write_route.approval_operation_mismatch` does not mention `base_url` at all — verified
  over the function's source.
- `governed_write_registry._rebuild` reconstructs the operation with
  `base_url=str(record.get("base_url", ""))`, read straight from the stored row, and the integrity
  anchor immediately below it claims *"One changed byte anywhere (the event row, the money table,
  this reconstruction) yields a different hash and no authorization at all."* **That claim is false
  for `base_url`.** `governed_write_route.py`'s module docstring makes the same overclaim about
  every consequential value being "covered by the payload hash the human's signature binds".
- Containment today rests **entirely** on
  `browser_use_write.SandboxInvoiceWriteAdapter._refuse_if_not_dark`, and that check reads
  `if base_url and not _is_loopback_base_url(base_url)` — **an empty `base_url` skips it
  entirely**, which is prior finding F-09 compounding exactly as the reviewer said.

**Repository authority permits this as a recorded P12 precondition, and I so admit it.** P4's
acceptance contract is containment: the effect-capable violation surface EMPTY with the gate
asserting empty, the capability dark, the deployed route fail-closed. RR-01 cannot produce an
external effect under any of those conditions — the reachable path requires a tampered stored
proposal row **and** an injected live writer, and no live writer exists or may exist before P12.
`IMPLEMENTATION-REGISTRY.yaml`'s P4 block scopes P12 as the supervised-write integration, and
`browser_use_write`'s own refusal names the P12 approved-sandbox gate as the missing control.

**It is not discharged and must not be discarded.** It is carried forward as a **binding P12
precondition** and must appear in the final status/risk record produced by the finalizing session.
Required before any live writer is injected: add `base_url` (and `sandbox`) to `payload_hash`'s
canonical set **or** check them in `approval_operation_mismatch`; correct the two docstrings that
currently overclaim; remove the empty-`base_url` bypass in `_refuse_if_not_dark`; and add a mutant
that tampers the stored `base_url` and asserts refusal.

### E.2 — RR-02 … RR-06 and the carried-forward findings · **NON-BLOCKING, individually and cumulatively**

| Finding | Severity | My disposition |
|---|---|---|
| **RR-02** handoff misstates the gate-result binding | LOW | Confirmed: handoff §6 says tree `8e12372a27…` / `fbf0f7fa…`; the file says `a3e70464…` / `44b5457125e7…`. The **artifact is correct**; the handoff is stale and untracked, outside the candidate. Correct or delete the numeric claim. |
| **RR-03** null-gate probe scans only `src/` | LOW | Confirmed clean today — my own sweep found no `GateRegistry` population under `scripts/` either. Extend the probe's corpus before U8.1. |
| **RR-04** mutant B34's label names a symbol it does not mutate | LOW | Confirmed (prior F-05, disclosed). B34 passes and is real; its label is wrong. The `browser_use_adapter` reclassification is independently supported structurally. |
| **RR-05** numeric self-contradictions in the narrative | LOW | Confirmed (prior F-07, disclosed). Live state is 13 detection / 0 violations and the same files record `recomputed_edges: 13`, `violation_edges: []`. Superseded paragraphs sit behind a `HISTORY:` marker in the manifest; `browser_use_write.py:28` carries no marker. |
| **RR-06** two guards use substring rather than AST membership | LOW | Confirmed. Independently covered by mutants B45/B49 and by the behavioural end-to-end tests. Defence-in-depth thinness, not a false green. Convert to AST call nodes. |
| **F-03** `ReadOnlyBrowserUseRunner` `base_url` unvalidated | MEDIUM | Persists, disclosed. Read-side only; no write reachable. |
| **F-06** route family is a denylist | MEDIUM | Persists, disclosed. Ambiguity refuses; four independent barriers remain. |
| **F-08** approved-field *values* unconstrained | MEDIUM | Persists, disclosed. Keys are an exact allowlist; values are interpolated into an LLM task **at P12**. P12 precondition alongside RR-01. |
| **F-09** duck-typed writer; empty `base_url` skips the loopback check | MEDIUM | Persists, disclosed. **Compounds RR-01** — carried into the same P12 precondition. |
| **F-10** conditional workspace / message-ts binding | LOW | Partially mitigated: `channel_id` is unconditional and a missing stored channel receipt now hard-refuses (`NO_STORED_CHANNEL_RECEIPT`, mutant B52). |

**Cumulative assessment — does any become blocking together?** No. They fall into two families and
neither family crosses the containment boundary:

1. **Narrative accuracy** (RR-02, RR-04, RR-05, AD-01, F-07): claims in prose or labels that
   overstate or misdescribe what a check does. Every underlying mechanical fact I tested was
   correct; the defects are in the descriptions, not the code. They degrade future readability, not
   present containment.
2. **Deferred-scope hardening** (RR-01, RR-03, RR-06, F-03, F-06, F-08, F-09, AD-02): gaps whose
   exploitation requires a capability that does not exist yet — a live writer, a production gate
   registration, or a regression in a module that currently behaves correctly.

Family 2's members compound one another only **at P12**, and they compound into a single coherent
obligation — bind the target URL and the approved-field values to the human's signature before any
live writer is injected — which I record as a binding precondition rather than dissolve. Nothing in
either family can produce an external effect while the violation surface is EMPTY, the capability
is dark, and the deployed route returns `ROUTE_NOT_CONFIGURED`.

### E.3 — New findings from this adjudication

The accepted review did not record these. Neither is blocking; both must be carried forward.

#### AD-01 — Two committed evidence artifacts misstate the deployed wiring · LOW–MEDIUM

`docs/implementation/EFFECT-PATH-INVENTORY.yaml:86` and
`docs/implementation/LEGACY-DISPOSITION.md:156` — both **committed in the candidate tree** — state
that `run_action_callback_server.py` *"leaves `governed_write_provider`/`governed_write_kernel` as
`None`"*.

That is **mechanically false for the provider.** Driving the real builder returns a **WIRED**
provider and a `None` kernel, and the module's own console line says so
(*"lookup boundary WIRED and DARK; execution kernel BLOCKED"*). Both the handoff (§11: "**WIRED**")
and the accepted re-review (§D.5: `governed_write_provider : WIRED`) record it correctly — these
two evidence artifacts do not.

**The operative conclusion is nevertheless true and independently verified**: the route is
unreachable from the deployed server, because the *kernel* seam is `None` and the handler returns a
recorded `ROUTE_NOT_CONFIGURED`. The defect is that the stated **mechanism** overstates containment
— a future reader would believe the deployed server performs no `pending_for` lookup on a governed
tap, when it does (bounded, `writer=None`, no adapter registered). Same family as F-07/RR-05, but
not covered by them, which name different files.

**Remediation:** correct both sentences to *"wires the lookup boundary and returns no execution
kernel"*. No code change.

#### AD-02 — `scripts/finalizer_lock.py` has zero committed test coverage · MEDIUM

`finalizer_lock.py` is a **new 188-line safety-critical module** introduced by this candidate. It
has **no test coverage at all**: zero references anywhere under `eval/`, zero nodes in
`TEST-NODE-MANIFEST.json`, and no mutant in the 61-case battery targets it. Its only verification
is the independent reviewer's ad-hoc battery, which was run in a disposable repository and **was
not preserved as a repository artifact**.

I independently reproduced 16/16 of its substantive properties (§D), so **the mechanism is sound
today**. But nothing committed would catch a regression in the one module that exists to prevent
the double-finalizer defect this repository actually shipped — and by `CLAUDE.md` §9's own doctrine,
a guard never seen to fail is a decoration.

**Not blocking for P4 or R-07**: the lock protects status-record integrity, not effect containment,
and P4's acceptance is adapter containment. **But it is directly load-bearing for the very next
act**, which is running the finalizer. I record it as a **named prerequisite** (§7) and as a
required follow-on: commit a hostile test battery for `finalizer_lock.py` and regenerate the node
manifest.

---

## F. Weighted acceptance — instantiated and adjudicated

P4 had **no** `acceptance_criteria` block; `IMPLEMENTATION-REGISTRY.yaml`'s
`remaining_before_p4_completion` names instantiating one from the `PROGRAM-WEIGHTS.yaml`
`acceptance_template` as a remaining item, and the registry comments that without it P4 contributes
0%. The template is **frozen** (14 criteria, weights totalling exactly 100), so instantiation is
mechanical and carries no discretion — the only adjudicative act is setting the results, which is
this session's role and follows the P3 precedent exactly (`p3-final-adjudication-review.md`).

**I set the following results from independent evidence.** A later authorized session must
transcribe them into the registry; this document is their source.

| # | Criterion | Weight | Result | Basis |
|---|---|---|---|---|
| 1 | `accepted_scope_and_design` | 6 | **PASS** | Within P4's `allowed_scope`; nothing from `prohibited_scope` (events, entities, freight workflows) touched. |
| 2 | `required_tests` | 8 | **PASS** | 1962 nodes, identical by identity; F-01 and F-02 batteries entered through production entry points. *Qualified by AD-02.* |
| 3 | `core_implementation` | 20 | **PASS** | Violation surface EMPTY with the gate asserting empty; EP-1/EP-3/EP-8/EP-14 cut; the governed join is production code with a real caller. |
| 4 | `failure_handling` | 8 | **PASS** | `UNKNOWN_OUTCOME` escalates, never auto-resolves and never launders to `FAILED` or `VERIFIED`; blind readback is not `VERIFIED`. |
| 5 | `concurrency_handling` | 8 | **PASS** | Two simultaneous consumers of one queued intent → 1 attempt, 1 grant; atomic single-use claim; `finalizer_lock` mutual exclusion verified 16/16. |
| 6 | `authorization_and_security` | 10 | **PASS** | One continuous approval identity end to end; 19 hostile classes refuse with zero external attempts; origin policy fails closed. RR-01 is a contained defence-in-depth gap carried to P12, not an authorization failure. |
| 7 | `migrations_and_persistence` | 6 | **PASS** | `migration_requirements: none` in the P4 registry block; the pending-write repository is a bounded lookup over the existing store. |
| 8 | `observability_and_operational_behavior` | 6 | **PASS** | Every fail-closed path records a named `GovernedWriteRefused`; `ROUTE_NOT_CONFIGURED` is recorded with its cause; orphan detection at Sev-0. |
| 9 | `mutation_or_hostile_cases` | 8 | **PASS** | 61/61 caught, 0 MISS / 0 SETUP-FAIL / 0 RESTORE-RED, byte-exact restoration — reproduced by me. |
| 10 | `full_test_suite` | 5 | **PASS** | 1961 passed / 0 failed / 1 skipped / 1962 collected — reproduced by me. |
| 11 | `canonical_finalizer` | 3 | ### **PENDING** | **The finalizer has not run on this candidate.** This criterion cannot pass before finalization and legitimately completes last. |
| 12 | `clean_clone_execution` | 3 | **PASS** | `GATE-RESULT.json` `passed: true`, nine steps exit 0, bound to `0891d1a` / `a3e70464`; independently reproduced. |
| 13 | `independent_review` | 5 | **PASS** | `refs/preserve/p4-independent-rereview-0891d1a`, report SHA-256 `181e1a37…316`, verdict ACCEPT FOR SEPARATE FINAL ADJUDICATION. Supplied by a session that did not implement P4. |
| 14 | `final_adjudication` | 4 | **PASS** | This document, by a session that did not implement, remediate or review P4. |

**P4 computes to 97/100 now, and to 100/100 the moment `canonical_finalizer` passes** — that is, on
a successful finalizer run against `0891d1a`. This is self-consistent with `PROGRESS-PROTOCOL.md`
§8, which forbids a phase reaching 100% before `independent_review` **and** `final_adjudication`
are PASS: both now are.

---

## G. Verdict

# ACCEPT P4 FOR FINALIZATION

The accepted independent re-review **does** support finalization of this exact candidate. Both
blocking findings are discharged on evidence I re-derived rather than inherited; every headline
figure reproduces exactly; identity, preservation, non-mutation, ref stability and clean-clone
binding all verify; and no residual — alone or cumulatively — reaches the containment boundary.

### G.1 Exact candidate

```
commit  0891d1a19a9c47155a56a3f4b2116e5a4d4aa75e
tree    a3e704645b8a06561d90cdb5f81288309ae51850
parent  f1e8e1893eff2460d68f3f168f18fd29635b250d
branch  p4/adapter-containment-completion (local, unpushed)
```

### G.2 Exact accepted review

```
preservation ref  refs/preserve/p4-independent-rereview-0891d1a
preservation commit  5ca6d2e95896336f447cf693da04282a0d53bdbf  (parent = the candidate)
report  docs/implementation/p4-independent-rereview-report-0891d1a.md
sha256  181e1a37a413fd35f537e00a7e1423bf192f88205270fa15932fbabeb955d316
verdict ACCEPT FOR SEPARATE FINAL ADJUDICATION
```

### G.3 Exact canonical evidence accepted

- Canonical suite **1961 passed / 0 failed / 1 skipped / 1962 collected**
- `TEST-NODE-MANIFEST.json` — 1962 nodes, `manifest_sha256 44b5457125e79e3dee21768684823f2ab7ab03c362a11577974ccd38d39dfd40`, identical by identity, hash recomputed through the canonical composer
- `GATE-RESULT.json` (uncommitted, canonical generator) — `passed: true`, nine steps exit 0, bound to `0891d1a` / `a3e70464`, `config_sha256 22f4294195ba…`, `runner_sha256 75b924e9f398…`
- Boundary mutation battery **61/61 caught**, 0 MISS / 0 SETUP-FAIL / 0 RESTORE-RED, tree restored byte-exactly to `a3e70464…`
- Effect-capable violation edges **0 live / 0 recorded**, both-sided; detection edges **13 live == 13 recorded**; `sources_inspected` 152, `unmatched` 0
- Loopback socket-bound callback tests **34 passed**; deployed-route + null-gate guards **33 passed**
- Finalizer-lock hostile probes **16/16** (independently re-derived)

### G.4 Residual risks carried forward

**Binding P12 preconditions** (must be discharged before any live writer is injected):
**RR-01** (`base_url` outside the payload hash and outside `approval_operation_mismatch`, with two
docstrings overclaiming), compounded by **F-09** (empty `base_url` skips the loopback refusal) and
**F-08** (approved-field values unconstrained and interpolated into an LLM task).

**Recorded non-blocking residuals:** RR-02, RR-03, RR-04, RR-05, RR-06, F-03, F-06, F-07, F-10,
and the two findings this adjudication adds — **AD-01** (two committed evidence artifacts misstate
the deployed provider wiring) and **AD-02** (`finalizer_lock.py` has zero committed test coverage).

None of these may be silently discarded. All must appear in the status/risk record the finalizing
session produces.

### G.5 May R-07 become CONTAINED after the finalizer mechanically updates status?

### **No — not by the finalizer's mechanical update, and not in one step.** State this plainly rather than assuming it.

The finalizer's **entire** write set is: `CURRENT.md`'s fenced status-block; the registry's
`baseline_commit`, `validated_tree` and `suite` lines; `SUITE-RESULT.json`; `GATE-RESULT.json`;
`BUILD-STATUS.yaml`'s derived-block; and placeholder substitution in five named review documents.
**Phase status, R-07 status and `acceptance_criteria` results are not in it** —
`scripts/progress_status.py` only *reads* `acceptance_criteria`; nothing writes them.

Two further, separate acts are required:

1. **A status-recording act inside the metadata commit.** The P4 `acceptance_criteria` block (§F),
   P4 `status: COMPLETE`, and the R-07 lines in `CURRENT.md` and `BUILD-STATUS.yaml` are all in
   `STATUS_METADATA_FILES`, so they may legally land in the one metadata commit — but they must be
   authored, not derived.
2. **A subsequent content commit.** P4's own `completion_evidence` requires *"R-07 marked CONTAINED
   with the mechanism named, in `phase-0-baseline-manifest.yaml`"*. That file is **not** in
   `STATUS_METADATA_FILES`, and `test_status_reality.py:78–83` fails any metadata commit that
   touches a non-status file. **R-07 therefore cannot be fully closed within the commit that
   finalizes this candidate.** It requires one further content commit afterwards.

Until both occur, **R-07 remains OPEN — NOT CONTAINED**, and this adjudication does not change that.
What it establishes is that the **mechanical** close condition is met and independently verified,
and that the adjudication gate the manifest names as PENDING is now discharged.

### G.6 May P5 become the sole READY phase after successful finalization?

**Yes — conditionally, and by an authored registry edit, not by derivation.** P5's `dependencies`
and `unlocked_by` are `[P4]` and P4 `blocks: [P5]`; P4's `next_units_unlocked` is `[P5]`. Once P4 is
recorded COMPLETE at 100/100, P5 becomes eligible to move `BLOCKED → READY`, and P4 must leave
`READY` in the same commit so that exactly one READY unit exists — five guards assert
`ready == ["P4"]` today and will need to assert `ready == ["P5"]`.

**Two cautions the finalizing session owns.** First, `CLAUDE.md` §11 forbids beginning P5 until
`CURRENT.md` says otherwise — finalization authorizes the *status transition*, not the start of P5
work, and `PROGRESS-PROTOCOL.md` §9 requires stopping at the control boundary rather than rolling
on. Second, `IMPLEMENTATION-REGISTRY.yaml` records P5 as also blocked on the **G2**
transition/event adjudication (13 of 134 transitions name no event); that is independent of P4 and
this adjudication does not discharge it.

### G.7 Exact prerequisites the one finalizer must verify

Before it runs:

1. **`HEAD` is exactly `0891d1a19a9c47155a56a3f4b2116e5a4d4aa75e`**, tree `a3e704645b8a…`, on
   `p4/adapter-containment-completion`, and the `PRODUCING` topology still holds
   (`3d231731…` == `HEAD^^`, `f1e8e18…` == `HEAD^` and pure).
2. **The working tree is clean.** `finalize_status.py:97–101` aborts on **any** dirty tracked file,
   *before* it deletes receipts. Two tracked files are dirty today:
   - `GATE-RESULT.json` — safe to discard; the finalizer deletes and regenerates it (steps 6 and 8).
   - `CURRENT.md` — **167 lines of hand-authored prose that the finalizer does not generate.** It
     rewrites only the fenced status-block. This prose must be preserved **out of band** (copy the
     file aside), and ### **never with `git checkout` / `restore` / `stash` / `clean`** — `CLAUDE.md`
     §9 records that doing so once destroyed unrecoverable work here.
3. **It holds `finalizer_lock` exclusively.** Verify `current_owner()` is `None` first. Note
   **AD-02**: this lock has no committed test coverage; treat a refusal as authoritative and never
   reclaim it because a log file is missing.
4. **No builder owns the worktree** (`.git/neyma-builder-worktree.lock` unheld) and no
   `mutate_phase4_boundary` run is in flight.
5. **The candidate has not moved** since this adjudication — re-verify the commit, the tree, and
   that `refs/preserve/p4-independent-rereview-0891d1a` and
   `refs/preserve/p4-final-adjudication-0891d1a` still resolve to commits whose parent is the
   candidate.
6. **`main` is untouched** at `152574e4…`; nothing is pushed. Integration to `main` is
   fast-forward-only under R-21 and is a **separate** founder-authorized act, not part of
   finalization.

After it runs, and before committing:

7. **The metadata commit contains only `STATUS_METADATA_FILES`** — `test_status_reality.py:78–83`
   fails otherwise. `phase-0-baseline-manifest.yaml` **must not** be in it (§G.5).
8. **The P4 `acceptance_criteria` block is present with the fourteen results of §F**, with
   `canonical_finalizer` moved to `PASS` on the strength of the run that just completed. Because
   `BUILD-STATUS.yaml`'s derived percentages are computed from those results, the derived block must
   be regenerated **after** they are in place, or it will record P4 at 0%.
9. **The recorded percentages are evidence-supported.** `progress_status.py:192–200` refuses a phase
   at 100% without `independent_review` and `final_adjudication` PASS; both are PASS (§F).
10. **The residual register carries RR-01 (with F-08/F-09), RR-02…RR-06, F-03, F-06, F-07, F-10,
    AD-01 and AD-02** — §G.4. RR-01 must be recorded as a binding P12 precondition.
11. **The full `NEYMA BUILD STATUS` block is printed** and the session **stops at the control
    boundary** (`PROGRESS-PROTOCOL.md` §9). It must not begin P5.

---

## H. Scope of this document

This is an adjudication and nothing else. It ran no finalizer, wrote no status metadata, marked no
phase complete, marked R-07 neither contained nor closed, modified no product code, remediated no
finding, amended no candidate, moved no protected ref, pushed nothing, contacted no external system
and enabled no effect. The candidate's tree `a3e704645b8a06561d90cdb5f81288309ae51850` is unchanged
and still verifies.

Preserved by the mechanism this repository already demonstrates twice — a commit whose **parent is
the adjudicated candidate**, adding only this report, exposed through `refs/preserve/*`, leaving the
candidate's tree untouched:

```
refs/preserve/p4-final-adjudication-0891d1a
```

SHA-256 of this report is recorded alongside it at
`docs/implementation/p4-final-adjudication-report-0891d1a.md.sha256`.

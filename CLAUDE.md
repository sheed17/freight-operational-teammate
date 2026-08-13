# CLAUDE.md — Operating Guide for Coding Agents

> **You are probably starting with no conversation history. That is the expected case.**
> This repository is designed to replace conversation memory. Everything you need to work correctly
> is written down. **If it is not written down, it is not decided — and you must stop and ask rather
> than choose.**

**This file outranks every other instruction file in this repository**, including `AGENTS.md`,
`README.md`, and every agent definition under `.claude/agents/` and `.codex/agents/`.

---

## ⛔ READ THIS FIRST: what you will get wrong if you skip ahead

This repository contains a working runtime that does carrier-invoice reconciliation, document
extraction, Slack review and browser-driven TMS writes. **If you infer the product from that code,
you will build the wrong product.**

Neyma is the **AI-native operating platform and system of action for small and medium freight
and logistics companies** (ADR-012), operating across
**eleven** operational loops. The invoice work is the first implemented surface, not the product.
**See [`PRODUCT.md`](PRODUCT.md) §12 for the explicit list of things Neyma is not.**

You will also find guidance files describing an **8-stage roadmap** ("Stage 1 — IN PROGRESS",
"Stage 5 Human Review"). **That roadmap is historical and superseded.** The current program is
**Implementation Phases P0–P14** with gates **G0–G10**. See
[`docs/implementation/PHASE-OUTPUTS.md`](docs/implementation/PHASE-OUTPUTS.md).

---

## 1. Required reading order

Read in this order. Do not skip 1–5.

| # | Document | Why |
|---|---|---|
| 1 | **`CLAUDE.md`** (this file) | how to work here |
| 2 | [`PRODUCT.md`](PRODUCT.md) | what is being built, and what it is not |
| 3 | [`ARCHITECTURE.md`](ARCHITECTURE.md) | the canonical architecture in one pass |
| 4 | [`docs/CANONICAL-DOCUMENTS.md`](docs/CANONICAL-DOCUMENTS.md) | which documents may authorise decisions |
| 5 | [`docs/implementation/CURRENT.md`](docs/implementation/CURRENT.md) | **the single short-form status authority** |
| 6 | [`docs/implementation/IMPLEMENTATION-REGISTRY.yaml`](docs/implementation/IMPLEMENTATION-REGISTRY.yaml) | the work units, their status and dependencies |
| 7 | the acceptance registry for your selected unit | [`docs/specifications/acceptance/registry.md`](docs/specifications/acceptance/registry.md) |
| 8 | the relevant ADRs, entity, event, state-machine and workflow specs | the binding detail |
| 9 | [`docs/implementation/LEGACY-DISPOSITION.md`](docs/implementation/LEGACY-DISPOSITION.md) | the disposition of every module you are about to touch |
| 10 | [`docs/implementation/TOOL-ACCESS-POLICY.md`](docs/implementation/TOOL-ACCESS-POLICY.md) | what you may research and what research can never authorise |

## 2. Project identity

**Neyma is the AI-native operating platform and system of action for small and medium freight
and logistics companies** ([`ADR-012`](docs/architecture/decisions/ADR-012-product-identity-and-strategy.md)).
It connects to the systems the company already uses, maintains coherent operational state across
them, owns open operational obligations, coordinates authorized execution, and remains
responsible until the relevant business outcome is closed. The initial ICP is small and medium
US freight brokerages; the wedge hypothesis is **Delivered Load Closure** (PRODUCT.md §15 —
`NEEDS VALIDATION`). Neyma may become authoritative for individual workflows only through the
customer-authorized migration model of ADR-013 — integrate-first, migration-capable, no
artificial ceilings and no assumed rip-and-replace.

> ### **Neyma is NOT an invoice processor, an AP reconciliation tool, a document-extraction service,
> a TMS chatbot, a Slack interface over old workflows, or a browser-automation wrapper.**
> Any document, comment or agent definition that says otherwise is stale. Report it; do not follow it.

## 3. Current status

| | |
|---|---|
| **Phase 0** | ✅ COMPLETE — baseline + anti-false-green infrastructure |
| **Phase 1** | ✅ COMPLETE — correct effect identity (amount out of the Commit Key) |
| **Phase 2** | ✅ COMPLETE — tenant-safe persistence |
| **Phase 3** | ✅ **COMPLETE — ADJUDICATED.** The checkpoint kernel: seven-step atomic checkpoint, unconstructable Checkpoint Witness, grant mint + claim CAS, brake admission. **Ships dark — nothing routes through it.** The first INDEPENDENT review returned 9 findings (60/100, `NOT READY`) and P3 **did not pass it**; all nine were **remediated**; a **FRESH INDEPENDENT** review of the remediated, finalized tree then **PASSED** (zero new defects, 13/13 hostile probes); and a **separate FINAL ADJUDICATION** set all 14 weighted criteria `PASS` and recorded P3 COMPLETE ([adjudication](docs/implementation/p3-final-adjudication-review.md)). Completing P3 did **not** close R-07 — the kernel is dark until P4 routes effects through it. |
| **Phase 4** | ✅ **COMPLETE — ADJUDICATED.** Adapter containment: the governed write route, the two-key rule at the effect boundary, and the CI import gate asserting the effect-capable violation surface is EMPTY. **Ships dark — the deployed route answers a recorded `ROUTE_NOT_CONFIGURED` refusal.** Its first INDEPENDENT review **REJECTED** candidate `95cf5af7` (blocking findings F-01, F-02); a separate session remediated it into `0891d1a`; a **FRESH INDEPENDENT re-review** returned ACCEPT FOR SEPARATE FINAL ADJUDICATION; a **separate FINAL ADJUDICATION** set thirteen of the fourteen weighted criteria `PASS` ([adjudication](docs/implementation/p4-final-adjudication-report-0891d1a.md)); and `canonical_finalizer` became `PASS` on the one finalizer run that executed. ### **Completing it did NOT close R-07** — a separate, later content commit did; see the row below. |
| **R-07** | ### **CONTAINED.** The containment MECHANISM is built and independently verified, and the CONTAINED **record** is now written in [`phase-0-baseline-manifest.yaml`](docs/implementation/phase-0-baseline-manifest.yaml) (`expected_legacy_paths.status: CONTAINED`) with the mechanism named. It could not ride in a status-metadata commit, so it took a **separate content commit after both P4 finalization passes** — and that commit, not P4's completion, is what closed it. ### **CONTAINED ≠ ENABLED:** external-effect paths are structurally forced through the governed boundary or fail closed; no production write is enabled, the production `GateRegistry` population stays EMPTY until U8.1/P8, and no autonomy was granted. |
| Live-write paths | P0 baseline was **6 production-reachable** paths (EP-1, EP-3, EP-6, EP-7, EP-9, EP-10). All six are now cut: EP-6/7/9/10 physically DELETED, EP-3/EP-8/EP-14 cut to structurally read-only surfaces, and EP-1's write half routed through the governed write route and the checkpoint kernel. The R-07 record now says CONTAINED. |
| Adapter imports | P0 baseline was **31 direct adapter-import edges** across 18 importer modules. The boundary-aware gate's effect-capable violation surface is now **EMPTY** — 0 live and 0 recorded violation edges agreeing both-sided, positively anchored by 152 inspected sources and 13 authorized detection edges. EMPTY was the R-07 **mechanical** close condition; the record was the separate act that followed it. |
| Transition/event completeness | ### **G2 ADJUDICATED — ITS SEVEN EVENT OBLIGATIONS ARE DISCHARGED.** The predicate is settled and mechanised: a *producer transition* is one declared in `events/registry.md` §3 (117 of the 134 rows; the remaining 17 are non-producer transitions), and completeness is GR-2 over durable writes. All 134 rows carry structured classification, never prose (117 PRODUCER · 9 CONSUMES · 6 NON_PRODUCING · 2 DELEGATES_TO · 0 EVENT_REQUIRED). ### **A structured marker is not a proof either.** A durable-writing `CONSUMES` row must satisfy `CONSUMES-VALID`: a co-commit declared in **both** rows' `Writes` cells, a **different machine**, **not mutually exclusive** with the owner, and every persisted field carried by a consumed event's `state-machines/registry.md` §5 payload — undecidable **fails the build**. A `DELEGATES_TO` row must additionally share a **trigger type** with each target: `PL-7a → PL-7b` reaches the same state but is `S` against `H`, so the autonomous path cannot borrow the human path's event. ### **The seven durable writes that named no event — `PL-7a`, `AP-9`, `CF-7`, `EC-7`, `PO-2`, `PO-3`, `RU-8` — were given seven MINTED canonical events under founder/architect authority (2026-08-12), taking the registry 98 → 105.** Each discharge is re-proven mechanically on every run, and each obligation is **retained** in the audit rather than deleted. Still OPEN there: the G2 residuals `G2-D4`, `G2-D6`, `G2-D8`, `G2-D9`, `G2-D10`. Exact members and proofs: [`TRANSITION-EVENT-AUDIT.yaml`](docs/implementation/TRANSITION-EVENT-AUDIT.yaml). The old "24-name-no-event" figure and the "121/13" split were never correct and are both retired |
| Knowledge base | hardcoded **`tenant="default"`** remains (`ops_control.py` ×5, `action_callback.py::_learn_correction` (the `KnowledgeBase(...).learn` call)) — sites verified by guard, never by line number |
| **Durable handoff readiness** | ### **COMPLETE — the gate is CLOSED.** The second independent rehearsal PASSED 13/13; the hostile review's findings were corrected and mutation-proved by U-HANDOFF-1C; the SECOND HOSTILE review (**U-HANDOFF-2B**, independent) then defended its attack battery, and **U-HANDOFF-1D adjudicated all 13 criteria PASS** from that evidence ([`u-handoff-2b-hostile-review-report.md`](docs/implementation/u-handoff-2b-hostile-review-report.md)). |
| **Product/production rebaseline** | ### **`U-REBASELINE-1` COMPLETE — RB-01..RB-24 ALL PASS**, adjudicated by U-REBASELINE-1A from the INDEPENDENT U-REBASELINE-REVIEW-1 ([preserved report](docs/implementation/u-rebaseline-review-1-independent-report.md) · [adjudication](docs/implementation/u-rebaseline-1a-founder-adjudication-review.md)). |
| **Next approved unit** | ### **`P5` — Canonical events, outbox/inbox, replay isolation and production persistence. THE ONE AND ONLY READY UNIT — NOW IN PROGRESS, AND IT IS NOT COMPLETE.** Its `execution_state` is `IN_PROGRESS`, its `checkpoint_state` is `CHECKPOINT_ACCEPTED_FOR_CONTINUATION`, and it records one landed checkpoint, `P5-CP-1`: U5.7+U5.8 landed the transactional outbox and the dedup inbox — durable, atomic event emission and idempotent consumption. That is a **continuation** checkpoint, not phase acceptance. Still unbuilt: the 105 event contracts (U5.3), the GC-1 corpus (U5.4), the replay sandbox (U5.5), audit reconstruction (U5.6), and production-grade persistence (PostgreSQL, schema migrations, durable timers and scheduler per ADR-016) — the landed transport is SQLite only. ### **Its own blocker — G2's seven founder-gated event obligations — is DISCHARGED (2026-08-12):** the seven canonical events were minted under founder/architect authority, so the specification no longer blocks P5's event content. ### **NOTHING IS SCORED.** All 14 P5 acceptance criteria are `PENDING`, and the G2 residuals `G2-D4`/`D6`/`D8`/`D9`/`D10` stay open. `P6`–`P14` stay BLOCKED behind P5. |

**The authoritative, updatable version of this table is
[`docs/implementation/CURRENT.md`](docs/implementation/CURRENT.md).** If it disagrees with this
section, `CURRENT.md` wins and this section is stale — fix it.

## 4. Canonical terminology

Use these words precisely. Using them loosely is how two systems end up claiming one authority.

| Term | Meaning |
|---|---|
| **Tenant** | One brokerage. First in every key. Never `default`, never inferred. |
| **Work Item** | The unit of accountable work. Exactly one accountable human owner. |
| **Pipeline Instance** | The durable execution of a workflow for a Work Item; also the reservation. |
| **Expectation** | What should happen by when. The mechanism that makes a **missing** event observable. |
| **Obligation** | An unresolved thing owed. Always has one accountable human. |
| **Evidence** | Content-addressed support for a fact. |
| **Provenance** | Where a fact came from and how much it can bear (`OWNER_ASSERTED`, `MODEL_INFERRED`, …). |
| **Commit Key** | The identity of the **effect**. **The amount is not in it.** |
| **Material Facts** | The **content** of the decision — the approved values. Drift voids the approval. |
| **Effect Grant** | Authority to perform one external effect. 8 states. One canonical ledger. |
| **External Effect** | A consequential action on the outside world. |
| **Checkpoint Witness** | Proof the seven checks passed **moments ago**. Freshness. |
| **Approval** | A human authorisation bound to Material Facts and an authority. Expires; revocable. |
| **Policy** | Typed, compiled rules governing admission. *A prompt string is not a policy.* |
| **Brake** | Human admission control. **Controls whether new work starts — not termination.** |
| **Adapter** | A boundary to an external system. **A boundary, not a brain.** |
| **Replay** | Reconstructing state from history. **Structurally inert.** |
| **Reconciliation** | Comparing projection against authoritative external state. |
| **Unknown Outcome** | We cannot establish whether the effect happened. **Never auto-resolves.** |

## 5. Non-negotiable engineering rules

1. **LLM output is never canonical truth.**
2. **`MODEL_INFERRED` facts cannot independently authorise consequential actions.**
3. **`OWNER_ASSERTED` facts cannot be silently overwritten.**
4. **Every extracted or inferred fact preserves provenance.**
5. **Consequential actions require deterministic validation.**
6. **Financial and carrier-assignment actions require deterministic validation.** The model never
   chooses an amount.
7. **External effects require authorisation and idempotency.**
8. **Commit Key and Material Facts are different concepts** and may not be merged.
9. **Events cannot grant execution authority.**
10. **Replay cannot mint witnesses or grants.**
11. **Replay cannot call adapters.**
12. **Timeout alone never becomes `FAILED`.**
13. **Every open operational obligation has one accountable human owner.**
14. **Do not create a new agent when a deterministic service or workflow is sufficient.**
15. **Compatibility paths require explicit deletion conditions.**
16. **No permanent dual orchestration systems.**
17. **No permanent dual effect-authority systems.**
18. **Unresolved freight rules must be marked `NEEDS VALIDATION`** — never guessed.
19. **Existing code may be rewritten or deleted when it conflicts with canonical architecture.**
20. **Tests protecting unsafe or obsolete behaviour must be REPLACED, not preserved.** A green test
    asserting a forbidden behaviour is a defect with a passing status.

## 6. Work-unit protocol

Every implementation session follows this, in order:

1. **Read the repository status** — [`CURRENT.md`](docs/implementation/CURRENT.md).
2. **Identify exactly ONE `READY` work unit** from
   [`IMPLEMENTATION-REGISTRY.yaml`](docs/implementation/IMPLEMENTATION-REGISTRY.yaml). One. Not two.
3. **Verify its dependencies** are `COMPLETE`.
4. **Read its acceptance contract.**
5. **Inspect the legacy dispositions** of every module you will touch.
6. **Implement only that unit** — its `allowed_scope`, never its `prohibited_scope`.
7. **Run the required hostile and acceptance cases.**
8. **Run mutations where the unit requires them.**
9. **Update status and evidence.**
10. **Commit a clean, truthful result.**
11. **Stop** on any contradiction or blocking validation requirement.

## 7. Stop conditions

**Stop and ask. Do not invent.** You must stop when:

- canonical documents disagree with each other
- a required product decision is missing
- design-partner validation is explicitly required
- ownership of a Work Item or obligation is ambiguous
- the authority for a consequential action is unclear
- acceptance criteria are incomplete
- two systems claim canonical authority
- implementing would close an open risk outside its approved phase
- the selected work unit is `BLOCKED`
- the repository cannot identify the next approved unit

> **A plausible guess in this codebase becomes a permanent, invisible decision.** The failure mode
> is not "the agent asked too many questions"; it is a freight rule nobody chose being enforced on
> real money six months later.

## 8. Definition of done

A unit is done only when **all** of these are true:

- [ ] code complete
- [ ] tests complete
- [ ] exact-set guards complete (membership, not counts — a same-count substitution must fail)
- [ ] acceptance complete
- [ ] concurrency complete **where required by the unit**
- [ ] mutation complete **where required by the unit**
- [ ] migration posture complete
- [ ] rollback or disablement documented
- [ ] legacy dispositions updated
- [ ] documentation and status updated
- [ ] **final-tree validation run LAST, on the final tree**
- [ ] clean commit
- [ ] **no post-validation tree changes**

## 9. Verification discipline — learned the hard way

These are not style preferences. Each one is a defect this repository actually shipped.

- **Run validation LAST, on the final tree.** A green suite that predates the commit is not evidence
  about the commit. Phase 0 shipped red because of exactly this.
- **Verify mechanically, not by reading.** Check your own output with scripts that print their
  **denominator**. A green check that parsed nothing is worse than no check.
- **A negative assertion needs a proven population.** `assert X not in results` passes vacuously over
  an empty set. Use a `require_population()`-style guard.
- **Mutate to prove a guard works.** A guard never seen to fail is a decoration. Mutate the real
  tree, confirm the guard fails, restore. **A mutation that does not reintroduce the real defect
  proves nothing** — verify the mutant actually misbehaves before believing a "MISS".
- **Never enumerate filenames in a guard.** Discover them. This repository has produced the same
  filename-enumeration blind spot **four separate times**.
- **Use whole-token or AST matching, not substrings.** Substring guards fire on their own assertion
  text and on unrelated words.
- **Restoring a `.py` is not restoring behaviour** — purge `__pycache__`, or a same-length mutation
  restored within one mtime tick leaves poisoned bytecode and a false green.
- **Use the safe in-memory save/restore harness for mutation.**
  ### **Never use `git checkout`, `git restore`, `git stash` or `git clean` to undo a mutation.**
  Doing so once destroyed unrecoverable uncommitted work in this repository.
- **A defect and its defending test arrive together.** When fixing a defect, grep the suite for its
  symbols — the test that asserts the broken behaviour passes, so it hides.

## 10. Repository conventions

- Secrets live in `.env` (gitignored). **Never commit them.**
- **Never push without an explicit go-ahead.**
- Credentials: Neyma **minimizes handling of employees' raw personal credentials and prefers
  dedicated, scoped machine identities** (ADR-014). It may securely possess customer-authorized
  authentication material under ADR-014's governance; `human_established_session_only` remains a
  supported per-tenant fallback, not a universal rule. **Authentication never creates action
  authority.** No credential implementation exists yet — it lands with P4/P11, never earlier.
- Memory and logs must **never** store money values.
- Commit trailer: `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`
- Bootstrap: `python3 scripts/check_env.py` **before** creating the venv and again inside it
  **before** `pip install -e ".[dev]"` — it enforces pyproject's `requires-python` fail-fast.
- Run the suite with: `.venv/bin/python -m pytest eval/ -q`
- Prove clean-clone reproducibility with: `.venv/bin/python scripts/clean_clone_gate.py`
- **Progress reporting is mandatory, not conversational.** Every session ends by running the
  finalizer (which derives [`docs/implementation/BUILD-STATUS.yaml`](docs/implementation/BUILD-STATUS.yaml)
  from evidence and refuses inflated numbers) and **printing the full `NEYMA BUILD STATUS` block**,
  then stopping at the next approved control boundary. Percentages are mechanically derived from
  [`PROGRAM-WEIGHTS.yaml`](docs/implementation/PROGRAM-WEIGHTS.yaml), never estimated. The protocol
  is [`docs/implementation/PROGRESS-PROTOCOL.md`](docs/implementation/PROGRESS-PROTOCOL.md).
- **Tool access is intentionally broad so missing technical context is investigated rather than
  guessed. Tool access expands evidence retrieval, not canonical decision authority.** Search
  aggressively; infer cautiously; execute according to authority — the full policy, including the
  mandatory missing-context classification, is
  [`docs/implementation/TOOL-ACCESS-POLICY.md`](docs/implementation/TOOL-ACCESS-POLICY.md).

## 11. What you must NOT begin

Until [`CURRENT.md`](docs/implementation/CURRENT.md) says otherwise:

- ⛔ **Do not begin Implementation Phase 6** (foundational entities and state machines) — its
  dependency `P5` is **IN_PROGRESS, not complete**. **`P5` (events, outbox/inbox, replay isolation,
  PostgreSQL) is the sole READY unit**; it is no longer forbidden here. `P5-CP-1` landed the
  transactional outbox and the dedup inbox as a **continuation** checkpoint; the event contracts,
  the replay sandbox, audit reconstruction and PostgreSQL are not built, and all 14 P5 acceptance
  criteria are still `PENDING`.
- ⛔ **Do not adjudicate any phase COMPLETE from within the session that implemented or remediated
  it.** `independent_review` and `final_adjudication` require a session that did neither; certifying
  your own fixes is self-adjudication, a defect with a passing status (section 5, rule 20). This is
  how P3 and P4 were completed — reviewer and adjudicator were sessions separate from the
  implementer, and P4's first independent review returned REJECT.
- ⛔ **R-07 is now CONTAINED — do not read that as enablement.** The record was written where it
  belongs, `docs/implementation/phase-0-baseline-manifest.yaml`, by a **separate content commit made
  after both P4 finalization passes**; that commit, not P4's completion and not any finalizer, is
  what closed R-07. **Containment means external-effect paths are structurally forced through the
  governed boundary or fail closed.** It does **not** enable a production write, does **not**
  register a production policy gate, and grants **no autonomy of any kind**. Do not weaken the
  record: it stands only while every mechanical condition behind it holds (0 live / 0 recorded
  violation edges agreeing both-sided, an EMPTY production `GateRegistry`, no direct
  callback-to-actuator route, and the full evidence chain intact), and a guard fails the build the
  moment one stops.
- ⛔ Do not enable any external effect on live traffic. The capability ships dark and the deployed
  governed route answers a recorded `ROUTE_NOT_CONFIGURED` refusal; enabling it is a separate,
  later, founder-authorized decision, not a consequence of P4's acceptance.
- ⛔ Do not weaken the kernel: `CheckpointPassed` stays unconstructable, the witness table stays
  append-only, and the claim CAS's WHERE-clause revalidation may never lose a predicate.
- ⛔ Do not implement freight workflows.
- ⛔ Do not delete legacy production code outside the deletion conditions in
  `docs/implementation/LEGACY-DISPOSITION.md`.
- ⛔ Do not invent design-partner observations.
- ⛔ Do not promote the Delivered Load Closure wedge to validated.

**The next approved program is
[P5 — CANONICAL EVENTS, OUTBOX/INBOX, REPLAY ISOLATION AND PRODUCTION PERSISTENCE](docs/implementation/CURRENT.md)**
— the one and only `READY` unit, and now **IN_PROGRESS**: `P5-CP-1` landed the transactional outbox
and the dedup inbox as a **continuation** checkpoint. `READY` is a **selection** and a landed
checkpoint is not acceptance — no P5 criterion is scored, all 14 stay `PENDING`, and P5 is **NOT
COMPLETE**. P4 (adapter containment) is now **adjudicated COMPLETE**: its
first INDEPENDENT review **rejected** candidate `95cf5af7`, a separate session remediated it, a
**FRESH** INDEPENDENT re-review of candidate `0891d1a` returned ACCEPT FOR SEPARATE FINAL
ADJUDICATION, a **separate FINAL ADJUDICATION** set thirteen of the fourteen weighted criteria
`PASS` ([`p4-final-adjudication-report-0891d1a.md`](docs/implementation/p4-final-adjudication-report-0891d1a.md)),
and `canonical_finalizer` became `PASS` on the one finalizer run that executed
([`p4-first-finalization-pass-report-86306d5.md`](docs/implementation/p4-first-finalization-pass-report-86306d5.md)).
P3 (the checkpoint kernel) was completed the same way, one phase earlier
([`p3-final-adjudication-review.md`](docs/implementation/p3-final-adjudication-review.md)).
**P4 built the mechanism that makes an ungated external effect structurally impossible — and R-07
did NOT close there.** The CONTAINED record is a **separate content commit**, made after both P4
finalization passes, and it is what actually closed R-07. **R-07 is CONTAINED; containment is not
enablement, and the capability still ships dark.**

## 12. Other instruction files

| File | Standing |
|---|---|
| **`CLAUDE.md`** (this) | **AUTHORITATIVE** |
| [`AGENTS.md`](AGENTS.md) | compatibility entry point; must defer to this file |
| [`README.md`](README.md) | orientation only; not an authority on status or product |
| `.claude/agents/*`, `.codex/agents/*` | task lenses. **Their embedded status blocks and the 8-stage roadmap are historical.** See [`docs/implementation/AUTO-LOADED-GUIDANCE-REVIEW.md`](docs/implementation/AUTO-LOADED-GUIDANCE-REVIEW.md). |
| `docs/` root pre-reset files (every one now carries an in-file supersession banner) | **HISTORICAL.** Evidence of what was built and learned. **Not authority.** |

> **If any of them tells you the product is invoice processing, that the project is at "Stage 1" or
> "Stage 5", or that you should preserve legacy architecture by default — it is stale.
> This file wins.**

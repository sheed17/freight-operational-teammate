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

Neyma is an **operational execution layer for small and medium freight brokerages** across
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

**Neyma is an operational execution layer for small and medium freight brokerages.** It maintains
canonical operational state across fragmented systems, coordinates bounded actions, identifies
missing events, manages exceptions, and helps accountable humans close operational loops.

> ### **Neyma is NOT an invoice processor, an AP reconciliation tool, a document-extraction service,
> a TMS chatbot, a Slack interface over old workflows, or a browser-automation wrapper.**
> Any document, comment or agent definition that says otherwise is stale. Report it; do not follow it.

## 3. Current status

| | |
|---|---|
| **Phase 0** | ✅ COMPLETE — baseline + anti-false-green infrastructure |
| **Phase 1** | ✅ COMPLETE — correct effect identity (amount out of the Commit Key) |
| **Phase 2** | ✅ COMPLETE — tenant-safe persistence |
| **Phase 3** | ⛔ **NOT STARTED** |
| **R-07** | ### **OPEN — NOT CONTAINED** |
| Live-write paths | **6 production-reachable** paths remain (EP-1, EP-3, EP-6, EP-7, EP-9, EP-10) |
| Adapter imports | **31 direct adapter-import edges** remain across 18 importer modules |
| Event-less transitions | **24 of 134** transitions cite no event — a G2 question, unsettled |
| Knowledge base | hardcoded **`tenant="default"`** remains (`ops_control.py` ×5, `action_callback.py:1639`) |
| **Durable handoff readiness** | ### **NOT complete.** A non-independent rehearsal ran and returned NOT READY; its findings are corrected, and ### **the INDEPENDENT rehearsal has not been run.** |

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
- Neyma never handles a customer's TMS credentials — the human logs in and Neyma attaches
  (`human_established_session_only`).
- Memory and logs must **never** store money values.
- Commit trailer: `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`
- Run the suite with: `.venv/bin/python -m pytest eval/ -q`
- **Tool access is intentionally broad so missing technical context is investigated rather than
  guessed. Tool access expands evidence retrieval, not canonical decision authority.** Search
  aggressively; infer cautiously; execute according to authority — the full policy, including the
  mandatory missing-context classification, is
  [`docs/implementation/TOOL-ACCESS-POLICY.md`](docs/implementation/TOOL-ACCESS-POLICY.md).

## 11. What you must NOT begin

Until [`CURRENT.md`](docs/implementation/CURRENT.md) says otherwise:

- ⛔ **Do not begin Implementation Phase 3.**
- ⛔ Do not implement the Checkpoint Witness, the seven-step checkpoint, or the claim CAS.
- ⛔ Do not contain adapters.
- ⛔ **Do not close R-07.**
- ⛔ Do not implement freight workflows.
- ⛔ Do not delete legacy production code.
- ⛔ Do not invent design-partner observations.
- ⛔ Do not promote the W6→W8 slice to validated.

**The next approved program is the
[ZERO-CONTEXT CLI HANDOFF REHEARSAL AND HOSTILE READINESS REVIEW](docs/implementation/CURRENT.md).**
Phase 3 becomes available only after that review passes and an independent repository inspection
agrees.

## 12. Other instruction files

| File | Standing |
|---|---|
| **`CLAUDE.md`** (this) | **AUTHORITATIVE** |
| [`AGENTS.md`](AGENTS.md) | compatibility entry point; must defer to this file |
| [`README.md`](README.md) | orientation only; not an authority on status or product |
| `.claude/agents/*`, `.codex/agents/*` | task lenses. **Their embedded status blocks and the 8-stage roadmap are historical.** See [`docs/implementation/AUTO-LOADED-GUIDANCE-REVIEW.md`](docs/implementation/AUTO-LOADED-GUIDANCE-REVIEW.md). |
| `docs/` root (23 pre-reset files) | **HISTORICAL.** Evidence of what was built and learned. **Not authority.** |

> **If any of them tells you the product is invoice processing, that the project is at "Stage 1" or
> "Stage 5", or that you should preserve legacy architecture by default — it is stale.
> This file wins.**

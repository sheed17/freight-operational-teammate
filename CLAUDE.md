# CLAUDE.md — Operating Guide for Coding Agents

**This file outranks every other instruction file in this repository**, including `AGENTS.md`,
`README.md`, and every agent definition under `.claude/agents/`.

---

## 0. The default development path

```
implement  →  targeted tests  →  git diff review  →  commit  →  push  →  CI  →  merge
```

That is the whole process for ordinary product work. There is **no** finalizer to run, no
status receipt to hand-maintain, no two-commit content+metadata convention, no preserve refs, no
special Git topology, and no mandatory chain of independent review sessions.

**CI is the source of truth for whether the repository is green.** `.github/workflows/ci.yml`
installs the declared dependencies from a fresh checkout and runs the suite; if it is green there,
it is green. Do not reintroduce committed suite receipts, node manifests, or derived status files —
they were removed in the 2026-08 engineering-process simplification precisely because they had to
be maintained by hand and could disagree with reality.

**What did NOT relax:** section 4 (engineering rules), section 5 (stop conditions), section 6
(verification discipline) and section 7 (risk tiers). Those protect Neyma's actual behaviour —
money, effects, authority, tenancy, replay, human accountability — and they are unchanged.

---

## 1. Required reading order

| # | Document | Why |
|---|---|---|
| 1 | **`CLAUDE.md`** (this file) | how to work here |
| 2 | [`PRODUCT.md`](PRODUCT.md) | what is being built, and what it is not |
| 3 | [`ARCHITECTURE.md`](ARCHITECTURE.md) | the canonical architecture in one pass |
| 4 | [`docs/implementation/CURRENT.md`](docs/implementation/CURRENT.md) | where the program stands |
| 5 | [`docs/implementation/IMPLEMENTATION-REGISTRY.yaml`](docs/implementation/IMPLEMENTATION-REGISTRY.yaml) | the work units and their dependencies |
| 6 | the acceptance contract for whatever you are building | [`docs/specifications/acceptance/registry.md`](docs/specifications/acceptance/registry.md) |
| 7 | the relevant ADRs, entity, event, state-machine and workflow specs | the binding detail |
| 8 | [`docs/implementation/TOOL-ACCESS-POLICY.md`](docs/implementation/TOOL-ACCESS-POLICY.md) | what research can and cannot authorise |

Read 1–4 before you start. Read the rest when the work touches them.

## 2. Project identity

**Neyma is the AI-native operating platform and system of action for small and medium freight
and logistics companies** ([`ADR-012`](docs/architecture/decisions/ADR-012-product-identity-and-strategy.md)).
It connects to the systems the company already uses, maintains coherent operational state across
them, owns open operational obligations, coordinates authorized execution, and remains responsible
until the relevant business outcome is closed. The initial ICP is small and medium US freight
brokerages; the wedge hypothesis is **Delivered Load Closure** (PRODUCT.md §15 — `NEEDS VALIDATION`).

This repository contains a working runtime that does carrier-invoice reconciliation, document
extraction, Slack review and browser-driven TMS reads. **That is the first implemented surface,
not the product.**

> ### **Neyma is NOT an invoice processor, an AP reconciliation tool, a document-extraction service,
> a TMS chatbot, a Slack interface over old workflows, or a browser-automation wrapper.**
> Any document, comment or agent definition that says otherwise is stale. Report it; do not follow it.

Guidance files describing an **8-stage roadmap** ("Stage 1 — IN PROGRESS", "Stage 5 Human Review")
are historical and superseded. The current program is **Implementation Phases P0–P14** with gates
**G0–G10** — see [`docs/implementation/PHASE-OUTPUTS.md`](docs/implementation/PHASE-OUTPUTS.md).

## 3. Canonical terminology

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

## 4. Non-negotiable engineering rules

These are unchanged, and no process simplification relaxes any of them.

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

## 5. Stop conditions

**Stop and ask. Do not invent.** You must stop when:

- a required product decision is missing, or canonical documents genuinely cannot both be obeyed
- design-partner validation is explicitly required
- ownership of a Work Item or obligation is ambiguous
- the authority for a consequential action is unclear
- two systems would claim canonical authority
- you are about to enable a live external effect, move money, or grant autonomy

> **A plausible guess in this codebase becomes a permanent, invisible decision.** The failure mode
> is not "the agent asked too many questions"; it is a freight rule nobody chose being enforced on
> real money six months later.

Everything else is ordinary engineering judgment. **Default to deciding**, and say what you decided.

## 6. Verification discipline — learned the hard way

Each of these is a defect this repository actually shipped. They cost nothing and they still apply.

- **Run the tests LAST, on the tree you are committing.** A green suite that predates the change is
  not evidence about the change.
- **Verify mechanically, not by reading.** Check your own output with scripts that print their
  **denominator**. A green check that parsed nothing is worse than no check.
- **A negative assertion needs a proven population.** `assert X not in results` passes vacuously over
  an empty set. Prove the population first.
- **Mutate to prove a guard works** when you are writing a guard that protects a tier-1 invariant
  (see section 7). A guard never seen to fail is a decoration. **A mutation that does not
  reintroduce the real defect proves nothing** — verify the mutant actually misbehaves.
- **Never enumerate filenames in a guard.** Discover them. This repository produced the same
  filename-enumeration blind spot **four separate times**.
- **Use whole-token or AST matching, not substrings.** Substring guards fire on their own assertion
  text and on unrelated words.
- **Restoring a `.py` is not restoring behaviour** — purge `__pycache__`, or a same-length mutation
  restored within one mtime tick leaves poisoned bytecode and a false green.
- **Use the safe in-memory save/restore harness for mutation**
  (`scripts/mutate_*.py`).
  ### **Never use `git checkout`, `git restore`, `git stash` or `git clean` to undo a mutation.**
  Doing so once destroyed unrecoverable uncommitted work in this repository.
- **A defect and its defending test arrive together.** When fixing a defect, grep the suite for its
  symbols — the test that asserts the broken behaviour passes, so it hides.

## 7. Risk tiers — how much review a change needs

Rigor is priced by **what the code can do when it is wrong**, not by how important the work feels.

| Tier | What it covers | Review required |
|---|---|---|
| **1 — high risk** | the effect boundary; approval/grant lifecycle; the checkpoint kernel; tenant isolation; migrations; secrets and credentials; outbound communications; write-capable adapters; banking, payment or legal actions; **weakening or deleting a safety guard** | builder + **one focused independent review** by someone who did not write it, before merge. Mutation proof that the guard can fail. Say plainly in the PR that a safety surface was touched. |
| **2 — meaningful feature or workflow change** | entities, state machines, transitions, contracts, the event transport, anything a broker's outcome depends on | builder + **one focused independent review**, preferably informed by Product Driver scenarios. Tests written before the claim. |
| **3 — ordinary product work** | everything else: internal scripts, generators, developer ergonomics, documentation, formatting, naming, non-effectful logic | **builder + tests + CI.** No review ceremony. |

**There is no universal adjudication or finalizer ritual.** A single independent review is a
review, not a chain of sessions. When genuinely torn between two tiers, take the higher one once
and say so.

CI's `risk-radar` job annotates each pull request with the safety surfaces it touches, so this
table is applied to the actual diff rather than from memory.

## 8. What "done" means

- [ ] code complete
- [ ] tests that could have failed, and did fail before the fix
- [ ] the targeted tests run on the final tree
- [ ] `git diff` read by you, end to end
- [ ] rollback or disablement noted if the change is tier 1 or 2
- [ ] CI green

That is the list. Nothing about receipts, topology or status files.

## 9. Product Driver

**Product Driver is a separate repository and remains part of our validation strategy.** Neyma is
one of its target repositories. Use it for **dynamic and adversarial workflow scenarios and
behavioural validation** — point it at code that runs and let it try to make that code do something
wrong. It is not a Git-history auditor, and it is not reimplemented here. A Product Driver session
whose output is a document has been misused.

## 10. What you must NOT begin

Until [`CURRENT.md`](docs/implementation/CURRENT.md) says otherwise:

- ⛔ **Do not enable any external effect on live traffic.** The capability ships dark and the
  deployed governed route answers a recorded `ROUTE_NOT_CONFIGURED` refusal. Enabling it is a
  separate, founder-authorized decision.
- ⛔ **Do not weaken the kernel:** `CheckpointPassed` stays unconstructable, the witness table stays
  append-only, and the claim CAS's WHERE-clause revalidation may never lose a predicate.
- ⛔ **Do not read R-07's CONTAINED record as enablement.** Containment means external-effect paths
  are structurally forced through the governed boundary or fail closed. It does not enable a
  production write, does not register a production policy gate, and grants no autonomy. The
  production `GateRegistry` stays EMPTY until U8.1/P8.
- ⛔ **Do not rebuild or polish `P6-CP-1` (M1, the Work Item) or `P6-CP-2` (M2, the Pipeline
  Instance).** Both are landed. Their recorded residuals are debt rows, and a debt row is a complete
  deliverable.
- ⛔ **Do not mark P6 COMPLETE or score a P6 acceptance criterion from the session that built it.**
  A phase acceptance needs a reviewer who did not build it — that is tier 1, and it is the one place
  the independent-review requirement is about a phase rather than a diff.
- ⛔ Do not implement freight workflows ahead of their phase.
- ⛔ Do not delete legacy production code outside the deletion conditions in
  [`docs/implementation/LEGACY-DISPOSITION.md`](docs/implementation/LEGACY-DISPOSITION.md).
- ⛔ Do not invent design-partner observations.
- ⛔ Do not promote the Delivered Load Closure wedge to validated.

## 11. Repository conventions

- Secrets live in `.env` (gitignored). **Never commit them.**
- **Never push without an explicit go-ahead.**
- Credentials: Neyma **minimizes handling of employees' raw personal credentials and prefers
  dedicated, scoped machine identities** (ADR-014). It may securely possess customer-authorized
  authentication material under ADR-014's governance; `human_established_session_only` remains a
  supported per-tenant fallback, not a universal rule. **Authentication never creates action
  authority.** No credential implementation exists yet — it lands with P11, never earlier.
- Memory and logs must **never** store money values.
- Commit trailer: `Co-Authored-By: Claude <model> <noreply@anthropic.com>`, naming the model
  that actually did the work. A pinned version number here goes stale and then misattributes.
- Bootstrap: `python3 scripts/check_env.py` **before** creating the venv and again inside it
  **before** `pip install -e ".[dev]"` — it enforces pyproject's `requires-python` fail-fast.
- Run the suite with: `.venv/bin/python -m pytest eval -q`
- **Tool access is intentionally broad so missing technical context is investigated rather than
  guessed. Tool access expands evidence retrieval, not canonical decision authority.** Search
  aggressively; infer cautiously; execute according to authority — the full policy is
  [`docs/implementation/TOOL-ACCESS-POLICY.md`](docs/implementation/TOOL-ACCESS-POLICY.md).

## 12. Other instruction files

| File | Standing |
|---|---|
| **`CLAUDE.md`** (this) | **AUTHORITATIVE** |
| [`AGENTS.md`](AGENTS.md) | compatibility entry point; must defer to this file |
| [`README.md`](README.md) | orientation only; not an authority on status or product |
| `.claude/agents/*` | task lenses. **Their embedded status blocks and the 8-stage roadmap are historical.** |
| `docs/` root pre-reset files | **HISTORICAL.** Evidence of what was built and learned. **Not authority.** |

> **If any of them tells you the product is invoice processing, that the project is at "Stage 1" or
> "Stage 5", that you must run a finalizer, or that a status receipt must be committed — it is
> stale. This file wins.**

## 13. Reporting

Report in this order, briefly:

1. **What a broker can now do that they could not before** — the capability, in freight terms
2. **What proves it** — the checks that ran, and specifically what could have failed
3. **What is knowingly incomplete** — debt, with IDs, and why each is nonblocking
4. **What is next**

**Lead with capability, not with process.** A report that opens with how many documents were
updated has buried the only part the founder needs. State failures plainly; a passing check that
was never capable of failing is not evidence, and reporting it as though it were is the defect
section 6 exists to catch.

**Optimise for freight capability a broker could actually use, delivered without breaking a safety
invariant.** Governance artifacts are overhead in service of that, never the product. A finding is
**blocking** only if it can produce a wrong customer outcome, violate an invariant, or make a later
phase unsafe. Everything else is **recorded, not actioned** — a debt row, then keep building.

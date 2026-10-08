# Career notes

Material for a resume, interviews and LinkedIn, drawn only from what this repository can support.
Every number is in [`METRICS.md`](METRICS.md) with the command that produced it.

## Describing your role accurately

Read this before using anything below.

- **417 of the 434 commits carry an AI co-author trailer.** The code was written with AI coding
  agents (mostly Claude Code) under your direction. An interviewer who opens the git log will see
  that in ten seconds, so say it first. Stated well, it is a strength: you designed the
  architecture, set the invariants, decided what was acceptable, and built the review discipline
  that caught the agents' mistakes.
- **Choose verbs you can defend line by line.** "Designed", "architected", "specified",
  "directed", "led the build of" and "built with AI coding agents" are supported by the record.
  "Hand-wrote" is not, and nothing below says it. If you personally wrote specific modules, name
  those and say so.
- **"Independent review" was separate AI-agent sessions**, not human colleagues or auditors. Call
  it "review by a separate session that had not written the code".
- **The repository supports no customer, production or business impact claim.** It records no
  users, no deployment, no savings, no revenue and no accuracy on real data. The bullets below
  contain none. Add one only if you can evidence it from outside this repository; an unsupported
  one is the fastest way to lose a technical interviewer.

Edit the bullets to match what you actually did. They are written to be true as they stand for
someone who designed and directed this work.

## Resume bullets — software engineering

- Designed and led the build of a multi-tenant operational state engine for freight brokerage
  workflows (Python, ~81k LOC, 13 state machines, 118 event contracts) in which canonical state is
  a deterministic projection over immutable observations, making replay, restart and duplicate
  delivery side-effect free by construction; verified by 4,373 automated tests.
- Architected an effect-authorization kernel — a seven-check atomic checkpoint, an unforgeable
  freshness witness, and one-time grants claimed by compare-and-set — with a transactional outbox,
  de-duplicating inbox and durable timers on SQLite and PostgreSQL, enforced by a CI import gate so
  no code path can reach an external system around it.
- Root-caused a silent-failure defect in which a terminal state in a deadline state machine
  dropped a delivery obligation after a human correction; reproduced it on demand, fixed it
  without mutating history, and grew that module's suite from 30 to 83 tests backed by a 102-mutant
  battery in which every reintroduced defect is caught.

## Resume bullets — AI engineering / forward-deployed

- Designed an LLM inference boundary that exposes five typed tasks instead of a prompt API: strict
  structured outputs, verbatim-quote grounding that discards unsupported extractions, per-run token
  budgets, bounded retries, and record/replay so model evaluations run in CI at zero cost.
- Enforced model-output provenance at runtime — the system, never the model, labels how much a fact
  can bear, and a model-inferred value raises if a consequential gate reads it — so interpretation
  can inform a decision and can never authorize one; in a synthetic evaluation 176 of 286 decisions
  were settled deterministically with no model call.
- Translated messy freight-operations reality (contradictory tracking, missed appointments,
  unsigned PODs, disputed invoices, identifier collisions across tenants) into 65 executable
  synthetic load histories with labeled outcomes and 393 adversarial variants, giving a regression
  harness for domain behaviour before any customer data existed.

Optional additions if they are true for you, in your own words: what you learned in customer
discovery and why you paused; any specific modules you wrote by hand; any work with real brokerage
staff.

## The interview explanation

**Thirty seconds.**

> Neyma was an attempt at an AI operations teammate for freight brokerages. Freight runs on
> messages that contradict each other, and the costly failures are things that silently don't
> happen. So I confined the model to reading language into typed, quoted claims, and made
> everything that decides or acts deterministic: a canonical record with field-level provenance,
> deadlines that fire on silence, conflicts only a named human can resolve, and an authorization
> kernel for external actions that the model cannot reach. It runs on synthetic data in shadow
> mode. I paused the product after customer discovery; the engineering is what I'm showing.

**Two minutes — add:**

> It was built with AI coding agents, which made verification the real work. The rule was that a
> check which has never been seen to fail is decoration. So guards are proven with mutation tests
> that put the real defect back, an independent oracle re-derives "is this load falsely quiet?" on
> every evaluation, and anything touching a safety surface is reviewed by a session that didn't
> write it.
>
> That process caught the bug I'd point to. A driver says delivered, tracking disagrees, a human
> overrules the driver — and the load went quiet while the truck missed its appointment. The
> driver's claim had already discharged the delivery watch, discharged is a terminal state, and
> watch ids are derived from their cause for idempotency, so the system couldn't re-raise it. My
> tests were green, and the gap had even been written down as low-risk, because a tracking
> cadence would catch it — but that cadence is optional configuration. The fix keeps the terminal state terminal and
> raises a new generation of the watch whenever nothing standing answers it. Nothing in the
> history is rewritten.

**If asked what you would do differently:** talk to customers before building the safety kernel.
The engineering order was defensible; the product order was not.

## Technical skills demonstrably used

| Skill | Where to point |
|---|---|
| Python system design: typed domain models, state machines, pure projections | `src/freight_recon/freight_domain/`, the thirteen machine modules |
| Event-driven architecture: transactional outbox, idempotent inbox, durable timers, replay | `event_outbox.py`, `event_inbox.py`, `event_timers.py`, `event_replay.py` |
| Concurrency control and idempotency: compare-and-set claims, effect identity | `checkpoint.py`, `commit_key.py`, `effect_boundary.py` |
| Multi-tenant data isolation and migrations (SQLite, PostgreSQL) | `tenant.py`, `persistence.py`, `migrations/` |
| LLM application engineering: structured outputs, grounding, budgets, record/replay, eval harness | `inference/`, `freight_domain/interpretation.py`, `scripts/run_freight_interpretation_eval.py` |
| Prompt-injection and authority containment | `inference/prompts.py`, `provenance.py`, `proposal.py` |
| Test engineering: mutation testing, independent oracles, adversarial input generation, anti-vacuity guards | `scripts/mutate_*.py`, `eval/freight_corpus/work_attack.py`, `eval/tests/` |
| Static guards: AST and import-graph checks in CI | `eval/tests/test_import_gate.py`, `eval/tests/test_ac_sec_001_registry.py` |
| CI design: deterministic sharding with a proof that shards are disjoint and total | `.github/workflows/ci.yml` |
| Architecture decision records and specification writing | `docs/architecture/decisions/` (19 ADRs), `docs/specifications/` |
| Directing AI coding agents with review, acceptance criteria and risk tiers | `CLAUDE.md`, `docs/implementation/` |
| Freight-domain modelling: loads, stops, appointments, PODs, rate confirmations, carrier invoices | `freight_domain/model.py`, `eval/freight_corpus/` |

Earlier work in the same repository also touched document extraction from PDFs, Slack review flows
and read-only browser automation against a TMS. Describe those as the first prototype surface.

## Three LinkedIn story angles

**1. The bug that passed every test.**
A human corrected the system, and the system went silent. Tell it in freight terms — a driver says
delivered, tracking disagrees, a dispatcher overrules him, and the load stops being watched while
the truck misses its appointment. The hook is that every test was green and you had written the
risk down as acceptable, on an argument that depended on an optional setting. The takeaway: a
safety argument that rests on configuration is not a safety argument, and the identity of an
obligation is not the identity of the database row that recorded it.

**2. The model reads. It decides nothing.**
Everyone is wiring LLMs to tools. Describe the opposite bet: five typed tasks and no prompt API,
every extracted fact forced to quote its source or be dropped, provenance assigned by the system,
and a message that says "this charge is approved" treated as a fraud signal rather than an
instruction. The concrete detail that makes it land: most decisions in the evaluation never
reached a model at all.

**3. 417 of 434 commits were co-written by an AI. Here is what kept it honest.**
Not a productivity story — a verification story. Agents produce confident, plausible code and
confident, plausible tests, so the scarce skill becomes proving a check can fail. Mutation
batteries that reintroduce real defects, review by a session that did not write the code, reviews
that rejected the work, and a written rule that a guard never seen to fail is a decoration.
Mention that you later cut process that had grown past its value; it makes the rest believable.

A fourth, if you want the reflective one: **I built the vault before I knew what went in it** —
months of safety infrastructure, shipped dark, then customer discovery paused the product. Only
you can write that one, because only you know what discovery showed.

## What not to say

- That it was used by, piloted with or deployed to a brokerage — unless you can evidence it. The
  repository does not.
- Any saving, accuracy, throughput or revenue figure.
- That the "human touches per load" figure from the demo corpus is a measured labor reduction. It
  describes how the fixtures were written.
- That the model evaluation shows production accuracy. It is a small synthetic corpus, replayed.
- That the work was independently audited. It was reviewed by separate AI-agent sessions.
- That the freight workflow is validated. The repository records the opposite.

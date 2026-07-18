# Neyma

**An operational execution layer for small and medium freight brokerages.**

Neyma observes fragmented freight work across the systems a brokerage actually runs on — email,
PDFs and freight documents, TMS platforms, carrier and customer portals, SMS and calls,
spreadsheets, accounting systems, load boards, and human approval channels. It maintains canonical
operational state, coordinates bounded actions, identifies missing events, manages exceptions, and
helps accountable humans close operational loops.

The unit of value is a **closed loop**, not a processed document.

> ### ⚠️ If you are an AI coding agent, read [`CLAUDE.md`](CLAUDE.md) before anything else.
> This repository is designed to replace conversation memory, and it contains a working runtime
> that will mislead you about the product if you infer the product from the code.

---

## What Neyma is not

Not a carrier-invoice processor, a document-extraction service, a TMS chatbot, a collection of
disconnected agents, a Slack interface over old workflows, a browser-automation wrapper, or an AP
reconciliation tool.

**The repository currently contains all of those things.** They are the first implemented surfaces
of the product — **not the product.** See [`PRODUCT.md`](PRODUCT.md) §12.

## Documentation entry points

| Read this | For |
|---|---|
| ### [`CLAUDE.md`](CLAUDE.md) | ### **How to work in this repository. Agents start here.** |
| [`PRODUCT.md`](PRODUCT.md) | What Neyma is, who it is for, and what it is not |
| [`ARCHITECTURE.md`](ARCHITECTURE.md) | The canonical architecture in one pass |
| [`docs/CANONICAL-DOCUMENTS.md`](docs/CANONICAL-DOCUMENTS.md) | Which documents may authorise decisions |
| ### [`docs/implementation/CURRENT.md`](docs/implementation/CURRENT.md) | ### **The single status authority** |
| [`docs/implementation/IMPLEMENTATION-REGISTRY.yaml`](docs/implementation/IMPLEMENTATION-REGISTRY.yaml) | Work units, status, dependencies |
| [`docs/implementation/PHASE-OUTPUTS.md`](docs/implementation/PHASE-OUTPUTS.md) | What each phase buys |
| [`docs/implementation/LEGACY-DISPOSITION.md`](docs/implementation/LEGACY-DISPOSITION.md) | What happens to every existing subsystem |

## Current implementation status

| | |
|---|---|
| **Implementation Phase 0** | ✅ COMPLETE — baseline and anti-false-green infrastructure |
| **Implementation Phase 1** | ✅ COMPLETE — correct effect identity (the amount is out of the Commit Key) |
| **Implementation Phase 2** | ✅ COMPLETE — tenant-safe persistence |
| **Implementation Phase 3** | ⛔ **NOT STARTED** |
| **Suite** | **1073 passed · 0 failed · 1 conditionally justified skip** |
| **Next approved work** | **Zero-context CLI handoff rehearsal and hostile readiness review** |

**Phases are `P0`–`P14` with gates `G0`–`G10`.** Older documents refer to an 8-stage roadmap
("Stage 1"…"Stage 8") — **that roadmap is superseded.** See
[`PHASE-OUTPUTS.md`](docs/implementation/PHASE-OUTPUTS.md).

## ⛔ Current open safety findings

| Finding | Status |
|---|---|
| **R-07 — ungated live-write paths** | ### **OPEN — NOT CONTAINED** |
| **6 production-reachable live-write paths** | OPEN — close at **P4** |
| **31 direct adapter-import edges** | OPEN — close at **P4** |
| **24 of 134 transitions cite no event** | OPEN — must be settled before **P5** |
| Hardcoded knowledge-base `tenant="default"` | OPEN — closes at **P7** |
| No firsthand design-partner observation | OPEN |

> ### **Phase 2 made tenant ownership real at persistence boundaries. It did NOT make consequential
> external effects safe.** Six paths can still execute real external effects with no checkpoint, no
> witness and no grant. The only mitigation today is the operator's one-writer-at-a-time
> discipline — **which is discipline, not a mechanism, and is never to be recorded as containment.**

## The current runtime is not the final product

The runtime in `src/freight_recon/` was built before the canonical architecture existed. It works,
parts of it are proven live, and **it is under controlled replacement.** Every major subsystem
carries an explicit disposition — KEEP, ADAPT, REWRITE, MAKE_READ_ONLY, QUARANTINE or DELETE —
with a target phase and a deletion condition.

**No module is protected by being large, old, working or well tested.** The two largest modules in
the repository are marked REWRITE and ADAPT.

## Running the tests

```bash
.venv/bin/python -m pytest eval/ -q          # the full suite: 1073 passed, 1 skipped
```

Targeted runs:

```bash
.venv/bin/python -m pytest eval/tests/test_phase2_integrated_acceptance.py -q   # Phase-2 acceptance
.venv/bin/python -m pytest eval/tests/test_docs_control_system.py -q            # documentation guards
.venv/bin/python -m pytest eval/ -q -k "ac_safe_012 or ac_safe_013 or ac_sec_001"
```

**Verification discipline** (each rule below is a defect this repository actually shipped):
run validation **last, on the final tree**; verify mechanically with scripts that print their
denominator; never let a negative assertion run over an empty set; and mutate the tree to prove a
guard can fail. See [`CLAUDE.md`](CLAUDE.md) §9.

## Finding the next work unit

1. Read [`docs/implementation/CURRENT.md`](docs/implementation/CURRENT.md).
2. Open [`docs/implementation/IMPLEMENTATION-REGISTRY.yaml`](docs/implementation/IMPLEMENTATION-REGISTRY.yaml).
3. Find the unit with `status: READY`. **There is exactly one, and a guard enforces that.**
4. Verify its dependencies are `COMPLETE`, read its acceptance contract, and check the legacy
   dispositions of every module it touches.

Statuses are exactly `BLOCKED`, `READY`, `IN_PROGRESS`, `COMPLETE`. There is no "mostly done".

## Repository layout

| Path | Contains |
|---|---|
| `src/freight_recon/` | The runtime (77 modules) — under controlled replacement |
| `scripts/` | Operator entry points (52) — **several are effect-capable; see R-07** |
| `eval/` | The test suite, guards and probes |
| `docs/architecture/` | Engineering principles, semantic model, **ADR-001…ADR-011**, target spec |
| `docs/specifications/` | Entities, state machines, events, adapters, workflows, acceptance |
| `docs/product/` | Operating model, freight discovery, open validation items |
| `docs/implementation/` | Roadmap, registries, phase reviews, baseline manifest |
| `docs/*.md` (23 files) | ### **Pre-reset. Historical evidence, not authority.** |

## Setup

```bash
python3 -m venv .venv && .venv/bin/pip install -e ".[dev]"
cp .env.example .env       # secrets live here; .env is gitignored and must never be committed
```

Neyma **never handles a customer's TMS credentials** — the human establishes the session and Neyma
attaches to it (`human_established_session_only`).

---

*The previous README described Neyma as a carrier-invoice reconciliation engine on an 8-stage
roadmap with ~515 tests. That description was accurate before the architectural reset and is
preserved in git history. It is not accurate now.*

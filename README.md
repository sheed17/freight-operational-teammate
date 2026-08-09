# Neyma

**The AI-native operating platform and system of action for small and medium freight and
logistics companies.** (Initial ICP: small and medium US freight brokerages — ADR-012.)

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
| [`docs/implementation/TOOL-ACCESS-POLICY.md`](docs/implementation/TOOL-ACCESS-POLICY.md) | Broad tool access for formal sessions — and why it is not action authority |

## Current implementation status

| | |
|---|---|
| **Implementation Phase 0** | ✅ COMPLETE — baseline and anti-false-green infrastructure |
| **Implementation Phase 1** | ✅ COMPLETE — correct effect identity (the amount is out of the Commit Key) |
| **Implementation Phase 2** | ✅ COMPLETE — tenant-safe persistence |
| **Implementation Phase 3** | ✅ COMPLETE — **ADJUDICATED.** The checkpoint kernel (seven-step checkpoint, Checkpoint Witness, claim CAS, brake admission) **ships dark**. A FRESH independent review PASSED and a separate final adjudication set all 14 weighted criteria PASS. Completing P3 did not close R-07. |
| **Implementation Phase 4** | ✅ COMPLETE — **ADJUDICATED.** Adapter containment: every external effect now runs through the governed write route, the checkpoint kernel and the two-key rule, and the CI import gate asserts the effect-capable violation surface is **EMPTY**. It **ships dark** — the deployed route answers a recorded `ROUTE_NOT_CONFIGURED` refusal with zero grants minted. Its first independent review **REJECTED** it; after remediation a fresh independent re-review accepted it and a separate final adjudication set all 14 weighted criteria PASS. **Completing it did not close R-07.** |
| **Suite** | green — ### **exact counts live ONLY in [`CURRENT.md`](docs/implementation/CURRENT.md)'s machine-maintained status block** |
| **Next approved work** | **`P5` — canonical events, outbox/inbox, replay isolation and production persistence** — the sole `READY` unit. ### **`READY` is a selection: it has not begun and is NOT COMPLETE.** Its event content additionally waits on **G2**, which is now adjudicated but only **partially discharged**: seven transitions still perform durable writes that no canonical event records, and naming those events is founder/architect authority. |

**Phases are `P0`–`P14` with gates `G0`–`G10`.** Older documents refer to an 8-stage roadmap
("Stage 1"…"Stage 8") — **that roadmap is superseded.** See
[`PHASE-OUTPUTS.md`](docs/implementation/PHASE-OUTPUTS.md).

## ⛔ Current open safety findings

| Finding | Status |
|---|---|
| **R-07 — ungated live-write paths** | ### **CONTAINED** — the mechanism is built and independently verified, and the CONTAINED **record** is now written in [`phase-0-baseline-manifest.yaml`](docs/implementation/phase-0-baseline-manifest.yaml) with the mechanism named. It took a **separate content commit after both P4 finalization passes** — not P4's completion — to close it. ### **CONTAINED ≠ ENABLED:** external-effect paths are structurally forced through the governed boundary or fail closed; no production write is enabled, the production `GateRegistry` stays EMPTY until U8.1/P8, and no autonomy was granted |
| **6 production-reachable live-write paths** | ### **CUT AND RECORDED** — EP-6/7/9/10 deleted, EP-3/EP-8/EP-14 cut to structurally read-only, EP-1's write half routed through the governed write route |
| **31 direct adapter-import edges** | ### **RESOLVED AND RECORDED** — 0 effect-capable violation edges remain (13 authorized detection edges) |
| **RR-01 — `base_url` outside the payload hash and outside the approval mismatch check** | OPEN — a **binding P12 precondition**, compounded by F-08 and F-09; must be discharged before any live writer is injected |
| **AD-02 — `finalizer_lock.py` has zero committed test coverage** | OPEN — safety-critical and load-bearing for the next finalizer run; a committed hostile battery is owed |
| **Transition/event completeness** — G2 is adjudicated and the contract is mechanised, but **7 transitions perform durable writes and name no event outright** (`PL-7a`, `AP-9`, `CF-7`, `EC-7`, `PO-2`, `PO-3`, `RU-8`). The earlier "24-name-no-event" figure and the "121/13" split were never correct and are both retired | ### **PARTIALLY DISCHARGED** — naming those seven events is **founder/architect authority**, so **P5**'s event content stays blocked ([audit](docs/implementation/TRANSITION-EVENT-AUDIT.yaml)) |
| **Production Action Class gate registration** | ### **DEFERRED BY FOUNDER DECISION to U8.1 / P8** — the production `GateRegistry` population is EMPTY and must stay empty |
| Hardcoded knowledge-base `tenant="default"` | OPEN — closes at **P7** |
| No firsthand design-partner observation | OPEN |

> ### **Phase 2 made tenant ownership real at persistence boundaries. It did NOT make consequential
> external effects safe. Phase 4 built the mechanism that does — and the record still says
> `OPEN — NOT CONTAINED`.** An external effect without a grant is now structurally impossible: the
> governed write runs through approval, checkpoint, witness, grant and atomic claim, and the import
> gate asserts nothing is left outside that path. What has **not** happened is the recording of
> R-07 as contained, which is a separate commit. Until then the only recorded mitigation remains
> the operator's one-writer-at-a-time discipline — **which is discipline, not a mechanism, and is
> never to be recorded as containment.**

## The current runtime is not the final product

The runtime in `src/freight_recon/` was built before the canonical architecture existed. It works,
parts of it are proven live, and **it is under controlled replacement.** Every major subsystem
carries an explicit disposition — KEEP, ADAPT, REWRITE, MAKE_READ_ONLY, QUARANTINE or DELETE —
with a target phase and a deletion condition.

**No module is protected by being large, old, working or well tested.** The two largest modules in
the repository are marked REWRITE and ADAPT.

## Running the tests

```bash
.venv/bin/python -m pytest eval/ -q          # the full suite; current counts: docs/implementation/CURRENT.md
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
| `src/freight_recon/` | The runtime — under controlled replacement |
| `scripts/` | Operator entry points — **several are effect-capable; the exact adjudication is [`EFFECT-PATH-INVENTORY.yaml`](docs/implementation/EFFECT-PATH-INVENTORY.yaml) (R-07)** |
| `eval/` | The test suite, guards and probes |
| `docs/architecture/` | Engineering principles, semantic model, **ADR-001…ADR-011**, target spec |
| `docs/specifications/` | Entities, state machines, events, adapters, workflows, acceptance |
| `docs/product/` | Operating model, freight discovery, open validation items |
| `docs/implementation/` | Roadmap, registries, phase reviews, baseline manifest |
| `docs/*.md` (23 files) | ### **Pre-reset. Historical evidence, not authority.** |

## Setup

```bash
python3 scripts/check_env.py                       # fail-fast: requires the Python in pyproject.toml (>=3.11)
python3 -m venv .venv
.venv/bin/python scripts/check_env.py              # verify the venv's interpreter too, BEFORE installing
.venv/bin/pip install -e ".[dev]"
cp .env.example .env       # secrets live here; .env is gitignored and must never be committed
```

If `check_env.py` fails, create the venv with a newer interpreter (e.g. `python3.12 -m venv .venv`).
Do not let pip start resolving on a non-compliant Python — the resolver error arrives twenty
minutes later and says nothing useful. A true clean-clone verification (fresh directory, fresh
venv, full suite) is one command: `.venv/bin/python scripts/clean_clone_gate.py`.

Neyma **minimizes handling of employees' raw personal credentials and prefers dedicated, scoped
machine identities** ([`ADR-014`](docs/architecture/decisions/ADR-014-credential-and-machine-identity.md)).
It may securely possess customer-authorized authentication material under ADR-014's governance;
human-established session attachment (`human_established_session_only`) remains a supported
per-tenant fallback. **Authentication never creates action authority.**

---

*The previous README described Neyma as a carrier-invoice reconciliation engine on an 8-stage
roadmap, with a much smaller suite. That description was accurate before the architectural reset
and is preserved in git history. It is not accurate now.*

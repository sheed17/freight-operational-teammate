# AGENTS.md — Compatibility Entry Point

> ### ⛔ **THIS FILE IS NOT THE OPERATING GUIDE.**
> ### **The operating guide is [`CLAUDE.md`](CLAUDE.md). Read it. It outranks this file.**
>
> This file exists so that agents which auto-load `AGENTS.md` (Codex and others) are routed to the
> canonical control system instead of a stale one. It deliberately holds **no status, no roadmap,
> and no product definition of its own** — because this repository previously maintained status in
> four places and all four disagreed with each other and with reality.

---

## Read these, in this order

| # | Document | For |
|---|---|---|
| 1 | ### [`CLAUDE.md`](CLAUDE.md) | ### **How to work here. Non-negotiable rules, work-unit protocol, stop conditions.** |
| 2 | [`PRODUCT.md`](PRODUCT.md) | What Neyma is and is not |
| 3 | [`ARCHITECTURE.md`](ARCHITECTURE.md) | The canonical architecture |
| 4 | [`docs/CANONICAL-DOCUMENTS.md`](docs/CANONICAL-DOCUMENTS.md) | Which documents may authorise decisions |
| 5 | ### [`docs/implementation/CURRENT.md`](docs/implementation/CURRENT.md) | ### **The ONLY status authority** |
| 6 | [`docs/implementation/IMPLEMENTATION-REGISTRY.yaml`](docs/implementation/IMPLEMENTATION-REGISTRY.yaml) | The work units |

## Product identity, in one line

**Neyma is the AI-native operating platform and system of action for small and medium freight
and logistics companies** (ADR-012; initial ICP: US freight brokerages), spanning
eleven canonical operational loops (W1–W11).

> ### **It is NOT an invoice processor, an AP reconciliation tool, a document-extraction service,
> a TMS chatbot, or a Slack interface over old workflows.** The repository contains code doing all
> of those; that code is the first implemented surface, not the product.

## Status

**Do not read status from this file, and do not add it here.**
[`docs/implementation/CURRENT.md`](docs/implementation/CURRENT.md) is the single authority.

At the time of writing it records: Implementation **Phases P0/P1/P2/P3 COMPLETE, P4 the sole READY
unit (adapter containment) — not begun, R-07 OPEN — NOT CONTAINED** (P3's checkpoint kernel is
adjudicated COMPLETE and ships dark; only completing P4 closes R-07). If this line and `CURRENT.md`
ever disagree, **`CURRENT.md` is right and this line is stale.**

## Roadmap

Implementation phases **P0–P14**, gates **G0–G10** —
[`docs/implementation/PHASE-OUTPUTS.md`](docs/implementation/PHASE-OUTPUTS.md).

> ### **The 8-stage roadmap ("Stage 1 … Stage 8") in `docs/PRODUCT_ROADMAP.md` is SUPERSEDED.**
> Any file telling you the project is at "Stage 1" or "Stage 5" is describing a state from before
> the architectural reset.

## Non-negotiable rules

They live in [`CLAUDE.md`](CLAUDE.md) §5 and are not duplicated here — a duplicated rule set drifts,
and then two files both claim to be the rules. The load-bearing ones:

- LLM output is never canonical truth; the model never chooses an amount.
- `MODEL_INFERRED` cannot authorise a consequential action; `OWNER_ASSERTED` cannot be silently
  overwritten.
- Commit Key ≠ Material Facts. Events are facts, never authority. Replay cannot call adapters.
- Timeout alone never means `FAILED`.
- Every open obligation has one accountable human owner.
- No permanent dual orchestration or dual effect-authority systems.
- Tests protecting unsafe or obsolete behaviour are **replaced**, not preserved.

## Work-unit protocol

Read the status → pick the **one** `READY` unit → verify dependencies → read its acceptance
contract → check legacy dispositions → implement only that unit → run the required acceptance,
concurrency and mutation cases → update status → commit clean. **Stop on any contradiction.**
Full protocol: [`CLAUDE.md`](CLAUDE.md) §6, stop conditions §7, definition of done §8.

## Verification

```bash
.venv/bin/python -m pytest eval/ -q                                  # full suite
.venv/bin/python -m pytest eval/tests/test_docs_control_system.py -q  # documentation guards
```

Run validation **last, on the final tree**. See [`CLAUDE.md`](CLAUDE.md) §9 for the verification
discipline — every rule there is a defect this repository actually shipped.

**End every session by printing the `NEYMA BUILD STATUS` block** — the mandatory, evidence-based
progress report defined in
[`docs/implementation/PROGRESS-PROTOCOL.md`](docs/implementation/PROGRESS-PROTOCOL.md). Its
percentages come from [`BUILD-STATUS.yaml`](docs/implementation/BUILD-STATUS.yaml), which the
canonical finalizer derives from [`PROGRAM-WEIGHTS.yaml`](docs/implementation/PROGRAM-WEIGHTS.yaml)
and refuses to let anyone inflate. Progress reporting is part of the control system, not optional.

## Agent definitions

`.claude/agents/*` and `.codex/agents/*` are **task lenses**, not authorities. Each now carries a
supersession banner. Their embedded status blocks and stage roadmaps are historical — see
[`docs/implementation/AUTO-LOADED-GUIDANCE-REVIEW.md`](docs/implementation/AUTO-LOADED-GUIDANCE-REVIEW.md).

---

*This file previously carried a "Current Phase" block naming a stage of the superseded
8-stage roadmap, a 40-command
verification list targeting the pre-reset suites, a 12-item feature-expansion plan, and links to two
documents that do not exist. All of it predated the architectural reset. It is preserved in git
history and has been replaced here by pointers to the canonical control system.*

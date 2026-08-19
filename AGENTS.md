# AGENTS.md — Compatibility Entry Point

> ### ⛔ **THIS FILE IS NOT THE OPERATING GUIDE.**
> ### **The operating guide is [`CLAUDE.md`](CLAUDE.md). Read it. It outranks this file.**
>
> This file exists so that agents which auto-load `AGENTS.md` are routed to the canonical control
> system instead of a stale one. It deliberately holds **no status, no roadmap, and no product
> definition of its own** — because this repository previously maintained status in four places and
> all four disagreed with each other and with reality.

---

## Read these, in this order

| # | Document | For |
|---|---|---|
| 1 | ### [`CLAUDE.md`](CLAUDE.md) | ### **How to work here: the default development path, the non-negotiable rules, the risk tiers, the stop conditions.** |
| 2 | [`PRODUCT.md`](PRODUCT.md) | What Neyma is and is not |
| 3 | [`ARCHITECTURE.md`](ARCHITECTURE.md) | The canonical architecture |
| 4 | [`docs/implementation/CURRENT.md`](docs/implementation/CURRENT.md) | Where the program stands |
| 5 | [`docs/implementation/IMPLEMENTATION-REGISTRY.yaml`](docs/implementation/IMPLEMENTATION-REGISTRY.yaml) | The work units |

## Product identity, in one line

**Neyma is the AI-native operating platform and system of action for small and medium freight
and logistics companies** (ADR-012; initial ICP: US freight brokerages), spanning eleven canonical
operational loops (W1–W11).

> ### **It is NOT an invoice processor, an AP reconciliation tool, a document-extraction service,
> a TMS chatbot, or a Slack interface over old workflows.** The repository contains code doing all
> of those; that code is the first implemented surface, not the product.

## How work gets done

```
implement  →  targeted tests  →  git diff review  →  commit  →  push  →  CI  →  merge
```

**CI is the source of truth for green.** There is no finalizer, no committed suite receipt, no
two-commit metadata convention, no preserve refs, and no mandatory review chain for ordinary work.
Review scales with risk — see [`CLAUDE.md`](CLAUDE.md) §7. High-risk surfaces (effect boundary,
approvals, tenant isolation, migrations, secrets, outbound communications, write-capable adapters,
money/legal actions, weakening a safety guard) get one focused independent review before merge.

## Status

**Do not read status from this file, and do not add it here.**
[`docs/implementation/CURRENT.md`](docs/implementation/CURRENT.md) is the single authority. If this
file and `CURRENT.md` ever disagree, **`CURRENT.md` is right and this file is stale.**

**R-07 is CONTAINED, and CONTAINED is not ENABLED.** External-effect paths are structurally forced
through the governed boundary or they fail closed. No production write is enabled, the production
`GateRegistry` population is EMPTY until U8.1 / P8, and no autonomy of any kind was granted.

## Roadmap

Implementation phases **P0–P14**, gates **G0–G10** —
[`docs/implementation/PHASE-OUTPUTS.md`](docs/implementation/PHASE-OUTPUTS.md).

> ### **The 8-stage roadmap ("Stage 1 … Stage 8") in `docs/PRODUCT_ROADMAP.md` is SUPERSEDED.**
> Any file telling you the project is at "Stage 1" or "Stage 5" is describing a state from before
> the architectural reset.

## Non-negotiable rules

They live in [`CLAUDE.md`](CLAUDE.md) §4 and are not duplicated here — a duplicated rule set drifts,
and then two files both claim to be the rules. The load-bearing ones:

- LLM output is never canonical truth; the model never chooses an amount.
- `MODEL_INFERRED` cannot authorise a consequential action; `OWNER_ASSERTED` cannot be silently
  overwritten.
- Commit Key ≠ Material Facts. Events are facts, never authority. Replay cannot call adapters.
- Timeout alone never means `FAILED`.
- Every open obligation has one accountable human owner.
- No permanent dual orchestration or dual effect-authority systems.
- Tests protecting unsafe or obsolete behaviour are **replaced**, not preserved.

## Verification

```bash
python3 scripts/check_env.py            # before creating the venv, and again inside it
.venv/bin/python -m pytest eval -q      # the whole suite
```

Run the tests **last, on the tree you are committing**. See [`CLAUDE.md`](CLAUDE.md) §6 for the
verification discipline — every rule there is a defect this repository actually shipped.

## Product Driver

Product Driver is a **separate repository**, and Neyma is one of its target repositories. Use it for
dynamic and adversarial workflow scenarios and behavioural validation. Do not reimplement it here.

## Agent definitions

`.claude/agents/*` are **task lenses**, not authorities. Their embedded status blocks and stage
roadmaps are historical.

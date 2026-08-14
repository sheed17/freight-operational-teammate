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

At the time of writing it records: Implementation **Phases P0/P1/P2/P3/P4/P5 COMPLETE; `P6`
(foundational entities and state machines) is the sole selected unit and has NOT STARTED; P7–P14
BLOCKED; R-07 CONTAINED.** P5 was adjudicated COMPLETE at 14/14 after a fresh independent review
found zero material blocking defects; **P6 may not begin until the P5 closure commit is finalized.** If this line and `CURRENT.md` ever disagree,
**`CURRENT.md` is right and this line is stale.**

> ### **HOW R-07 ACTUALLY CLOSED — corrected, because the wording here was wrong.**
> This section used to say *"only completing P4 closes R-07"*. That is **not** what happened, and
> reading it that way is exactly the P4-COMPLETE ⇒ R-07-closed conflation the repository spent four
> documents and a guard assertion preventing. The real sequence was **four separate acts**:
>
> 1. **P4 implementation and acceptance completed.** Its first INDEPENDENT review REJECTED candidate
>    `95cf5af7`; a separate session remediated it into `0891d1a`; a FRESH INDEPENDENT re-review
>    accepted it; a **separate FINAL ADJUDICATION** set all 14 weighted criteria PASS, and P4 became
>    COMPLETE at 100/100. ### **That did NOT close R-07.**
> 2. **R-07 required its own separate, evidence-backed closure cycle.** The CONTAINED record lives in
>    [`docs/implementation/phase-0-baseline-manifest.yaml`](docs/implementation/phase-0-baseline-manifest.yaml),
>    which is **not** a status-metadata file, so it could ride in neither finalizer's commit.
> 3. **Both P4 finalization passes ran** — the first on implementation candidate `0891d1a`, the
>    second on the separately reviewed and separately adjudicated acceptance-closure candidate.
> 4. ### **Only then** did a later content commit write the canonical containment record, with the
>    mechanism named and the whole review / adjudication / finalizer evidence chain bound to it.
>    **That record is what closed R-07 — not the completion of P4.**
>
> ### **CONTAINED IS NOT ENABLED.** External-effect paths are structurally forced through the
> governed boundary or they fail closed. No production write is enabled, the production
> `GateRegistry` population is EMPTY until U8.1 / P8, and no autonomy of any kind was granted.

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

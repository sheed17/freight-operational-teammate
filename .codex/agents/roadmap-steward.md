> ### COMPATIBILITY SURFACE — NOT THE CANONICAL AGENT DEFINITION
> **The canonical surface is [`.claude/agents/roadmap-steward.md`](../../.claude/agents/roadmap-steward.md)**
> (decision recorded by U-HANDOFF-1A: the formal CLI environment is Claude Code, so
> `.claude/agents/` is canonical and this file is compatibility-only). Corrections land
> there first; if this file and its canonical counterpart disagree, the counterpart wins.


> ## ⛔ SUPERSEDED STATUS — READ `CLAUDE.md` FIRST
>
> **This file is a TASK LENS, not an authority on product, status or roadmap.**
>
> - **Product identity:** [`PRODUCT.md`](../../PRODUCT.md) — Neyma is an **operational execution
>   layer** for freight brokerages across **eleven** loops. **Not** an invoice processor.
> - **Current status:** [`docs/implementation/CURRENT.md`](../../docs/implementation/CURRENT.md) —
>   Implementation **Phases P0/P1/P2 COMPLETE, P3 NOT STARTED, R-07 OPEN — NOT CONTAINED**.
> - **Roadmap:** [`docs/implementation/PHASE-OUTPUTS.md`](../../docs/implementation/PHASE-OUTPUTS.md)
>   — phases **P0–P14**, gates G0–G10.
>
> ### **Any "Stage 1–8" roadmap, "Current Phase" or "Current status" block below is HISTORICAL and
> must not be followed.** The 8-stage roadmap is superseded. Where this file and `CLAUDE.md`
> disagree, **`CLAUDE.md` wins.**
>
> Full audit: [`docs/implementation/AUTO-LOADED-GUIDANCE-REVIEW.md`](../../docs/implementation/AUTO-LOADED-GUIDANCE-REVIEW.md)

# Codex Roadmap Steward

Use this as the Codex planning and gatekeeping lens for the Neyma Freight Ops Agentic
Workflow Engine. The old narrow framing was "freight invoice reconciliation"; that remains
Workflow 1, not the whole company.

Primary roadmap docs:

- `docs/NEYMA_VISION.md`
- `docs/PRODUCT_ROADMAP.md`
- `docs/AGENTIC_ARCHITECTURE.md`

## Required Questions

Every status assessment should answer:

1. Where are we?
2. Is the current stage exit gate met?
3. What exactly is next?

Read the repo and run what is relevant before answering.

## Legacy Technical Roadmap For Workflow 1

1. **Stage 1 — Extraction proof.** PDF render, one vision extraction call, Pydantic,
   Instructor, field confidence, eval against real invoices. No matching, DB, Slack, TMS,
   or browser automation.
2. **Stage 2 — Config system + reconciliation matching.** YAML-driven extraction plus
   deterministic matching against rate-con fixtures. No real TMS.
3. **Stage 3 — State machine + orchestrator + DB.** SQLite, lifecycle states, polling loop,
   idempotency, stub entry.
4. **Stage 4 — Slack HITL gateway.** Block Kit review cards and signed Slack webhooks.
   Entry remains stubbed.
5. **Stage 5 — TMS READ agent.** First browser/TMS work. Mock TMS first, then sandbox.
6. **Stage 6 — TMS WRITE agent.** Approved entry only, verify-by-readback, mock-first.
7. **Stage 7 — Full loop + deployment.** Real end-to-end supervised pilot, Docker/host,
   email trigger, session setup, unhappy-path verification.
8. **Stage 8 — Hardening.** Fix observed production failures, tighten prompts, thresholds,
   retries, observability, and client-specific slices.

Browser/TMS automation starts at Stage 5, not before.

For the broader Neyma product roadmap, use `docs/PRODUCT_ROADMAP.md`, which starts at
Stage 0 discovery and continues through pilot deployment, workflow pack expansion, and
production hardening.

## ⛔ Current Verified Status — SUPERSEDED

### **Superseded by [`docs/implementation/CURRENT.md`](../../docs/implementation/CURRENT.md)**
(P0/P1/P2 COMPLETE, P3 NOT STARTED, R-07 OPEN). The snapshot below predates the reset.

<details><summary>Historical snapshot — not authoritative</summary>

As of this repo snapshot:

- Stage 1 is **in progress**.
- The extraction runtime and eval harness exist.
- The eval golden set contains 3 synthetic documents.
- Offline harness tests pass when run with `.venv/bin/python -m pytest eval/tests -q`.
- Render-only demo works with `.venv/bin/python scripts/run_extraction.py --render-only`.
- Mock v1 intentionally fails the gate; mock v2 passes the synthetic mock gate.
- The old real-doc dependency has been replaced for development by the realistic synthetic
  freight corpus. Real/customer docs remain a later validation gate before unsupervised
  production use.
- The broader agentic workflow architecture is now documented, but not yet implemented.

</details>

## ⛔ Next Actions To Advance Stage 1 — SUPERSEDED

### **The next approved unit is whatever [`docs/implementation/CURRENT.md`](../../docs/implementation/CURRENT.md) names — never this file.** The steps below target a gate passed long ago. *(U-REBASELINE-1B: this disarming line previously named a specific unit and went stale the moment that unit completed; a pointer cannot rot.)*

<details><summary>Historical</summary>

1. Generate the realistic synthetic corpus:

   ```bash
   .venv/bin/python scripts/generate_realistic_corpus.py --loads 18 --seed 42
   ```

2. Wire generated carrier invoice truth into the eval path for clean and dirty variants.
3. Put `ANTHROPIC_API_KEY` in `.env` and run corpus extraction evals.
4. Review overconfidence and field failures, especially required fields.
5. Tune prompts/configs, save new runs, and compare.
6. Only start the next workflow slice once the realistic corpus gate passes.

If real/client-approved docs arrive later, add them as a separate validation slice:

   ```bash
   .venv/bin/python eval/add_to_golden_set.py path/to/real_invoice.pdf
   ```

## Production Improvements To Fold In Now

- Treat the real golden set as a ratchet: every corrected real invoice becomes future eval data.
- Align `load_or_pro` vs `load_or_pro_number` naming before matching starts.
- Keep money as decimal values in production code and preserve exact tolerance rules.
- Track overconfidence separately from raw accuracy because confident wrong money fields are
  the dangerous failure mode.

</details>

> # ⛔ HISTORICAL REVIEW — NOT CURRENT AUTHORITY
> **This document is evidence of a past moment, accurate as of its own commit and possibly stale
> since.** It must not direct current implementation. Verdicts, statuses, counts and "READY"
> declarations below describe the state THEN — several are known-superseded (including any
> "24 of 134" transition figure, retired by U-HANDOFF-1B, and any suite count). Current status:
> [`CURRENT.md`](CURRENT.md) · authority map: [`../CANONICAL-DOCUMENTS.md`](../CANONICAL-DOCUMENTS.md)
> · operating guide: [`../../CLAUDE.md`](../../CLAUDE.md).

# Auto-Loaded Guidance Audit

> **Every file a coding agent auto-loads or treats as implementation guidance, audited and given
> exactly one disposition.**

## ⛔ The finding that motivated this audit

A mechanical search for `ADR-`, `docs/architecture`, `docs/implementation`, `docs/specifications`,
`implementation-roadmap`, `target-system-spec` and `Implementation Phase` across **all 13
auto-loaded files returned ZERO hits.**

> ### **The entire architectural reset programme — 11 ADRs, the target specification, six
> specification layers, the acceptance corpus, and three completed implementation phases — was
> invisible to every file an agent loads automatically.**

A zero-context agent landing on this branch would have been told by **every single guidance file**
that the project was at *"Stage 5 Human Review"* or *"Stage 1 — IN PROGRESS"* of a completely
different 8-stage roadmap.

### Three mutually inconsistent "where are we" claims existed simultaneously

| Source | Claimed |
|---|---|
| `AGENTS.md` | Stage 5 Human Review — channel-neutral delivery adapter |
| `README.md` | Engine built and green (~515 tests); one fix round from a supervised pilot |
| `roadmap-steward` (both copies) | **Stage 1 in progress; Stages 2–8 not started; broader engine not implemented** |
| **Reality** | **P0/P1/P2 complete, P3 not started, R-07 open, 1073 tests passing** |

**No file was correct, and none referenced the reset programme at all.**

---

## Dispositions

| File | Lines | Disposition | Action taken |
|---|---|---|---|
| `README.md` | 410 | ### **REPLACE** | Rewritten as repository orientation. Product identity corrected; status replaced with a pointer to `CURRENT.md`; open safety findings surfaced; the "expand by stage, not by rewrite" instruction removed |
| `AGENTS.md` | 366 | ### **REPLACE** | Rewritten as a thin compatibility entry point holding **no status, no roadmap and no product definition of its own** |
| `.claude/agents/roadmap-steward.md` | 133 | ### **UPDATE + QUARANTINE (status block)** | Banner added; the Stage-1 status block wrapped as historical; ### **the "guard against browser automation early" instruction disarmed** |
| `.codex/agents/roadmap-steward.md` | 88 | **UPDATE + QUARANTINE** | Banner added; "Current Verified Status" and "Next Actions To Advance Stage 1" wrapped as historical |
| `.claude/agents/build-supervisor.md` | 106 | **UPDATE** | Banner added. Its 12 safety rules survive the reset; its legacy state machine does not |
| `.codex/agents/build-supervisor.md` | 75 | **UPDATE** | Banner added |
| `.claude/agents/intent-mapper.md` | 129 | **UPDATE** | Banner added. Sourced ground truth from `AGENTS.md`, laundering the Stage-5 claim into every spec it produced |
| `.codex/agents/intent-mapper.md` | 98 | **UPDATE** | Banner added |
| `.claude/agents/owner-operator-reviewer.md` | 111 | **RETAIN + banner** | The safest files audited. No legacy preservation, no acceptance bypass |
| `.codex/agents/owner-operator-reviewer.md` | 105 | **RETAIN + banner** | As above |
| `.claude/agents/phase-code-reviewer.md` | 110 | **UPDATE** | Banner added. Its 9 hardcoded verification commands target the pre-reset suites only |
| `.codex/agents/phase-code-reviewer.md` | 128 | **UPDATE** | Banner added |
| `.codex/agents/principal-architect-supervisor.md` | 80 | **UPDATE** | Banner added. Its LangGraph/LangChain guidance conflicts with ADR-008 and ADR-002 |
| **`CLAUDE.md`** | — | ### **CREATED** | ### **Did not exist.** The single highest-value gap in the repository |

## What was disarmed, specifically

### 1. The browser-automation instruction ⛔

`.claude/agents/roadmap-steward.md` instructed:

> *"The common mistake to guard against: building the browser automation early… If you see effort
> going into Browser Use before extraction and matching are proven, call it out."*

> ### **An agent following this would flag the repository's most mature, live-proven subsystem as
> premature work to be halted.** The browser/TMS path has committed real money writes against a live
> TMS. Its actual disposition is **ADAPT at P4**.

**Action:** replaced in place with an explicit "HISTORICAL — DO NOT APPLY" block naming the real
disposition.

### 2. Four stale status blocks

`AGENTS.md` "Current Phase", `README.md` "Current Focus", and both `roadmap-steward` "Current
status" sections. **Action:** removed from the two root files entirely and wrapped as collapsed
historical detail in the agent files. **Status is now maintained in exactly one place.**

### 3. The "expand by stage, not by rewrite" instruction

`README.md` said *"The project should expand into those pieces by stage, not by one giant rewrite."*
A zero-context agent reads this as an explicit prohibition on the architectural reset currently in
flight. **Action:** removed; replaced with the controlled-replacement posture and a pointer to the
legacy disposition registry.

### 4. Two broken documentation links

`AGENTS.md` referenced `docs/MODEL_STRATEGY.md` and `docs/ASCENDTMS_MAPPING.md`, **neither of which
exists** — and made the first a *gate* (*"Use docs/MODEL_STRATEGY.md before changing model defaults
or claiming production extraction readiness"*). **A gate pointing at a missing file cannot be
satisfied.** **Action:** both references removed with the rewrite.

## Findings recorded at U-DOC-1 — dispositions updated by U-HANDOFF-1A

The four "not acted on" findings from the original audit have since been adjudicated by the
zero-context rehearsal (which returned NOT READY) and corrected by **U-HANDOFF-1A**. A review
document must describe the repository state its own commit produced, so the table below records
both what was found and where each item stands **now**:

| Finding | Status after U-HANDOFF-1A |
|---|---|
| **Model strategy** | ### **RESOLVED as a contradiction; OPEN as a decision.** The rehearsal established the original three-way contradiction had already been removed when README/AGENTS were rewritten — the record here had simply not been updated. The one residual falsehood (`build-supervisor` asserting *"this project calls Claude"* against a dual-provider runtime) is **corrected**: the file now states the runtime is dual-provider (Anthropic vision extraction, OpenAI browser/operation), that provider choice is **not canonical architecture**, that valid provider usage must not be flagged by provider alone, and that consolidation requires an explicit approved work unit. ### **No final model strategy was invented — none is canonically decided.** Not handoff-blocking. |
| **`principal-architect-supervisor.md` twin** | ### **RESOLVED.** `.claude/agents/principal-architect-supervisor.md` created, aligned with the canonical content, so the review chain terminates for Claude Code — the intended formal CLI environment. |
| **Agent-pair drift** | ### **RESOLVED by decision + guard.** Decision: **`.claude/agents/` is the canonical surface** (the formal CLI environment is Claude Code); `.codex/agents/` files are **compatibility surfaces** and now declare their canonical counterpart in a header. A drift guard enforces: pair sets match, every `.codex` file carries the compatibility pointer, every agent carries the supersession banner. Full text-sync was deliberately NOT chosen — the surfaces legitimately differ in format; what is guarded is **authority**, so the pair can no longer *appear equally authoritative while drifting silently*. |
| **`phase-code-reviewer` stale commands** | ### **RESOLVED.** Both surfaces now carry the canonical verification sequence (unit acceptance + gates, control guards, status-reality guard, concurrency, exact-set probes, mutation evidence, full suite LAST, clean tree). The pre-reset list is retained in a `<details>` block explicitly stripped of approval authority. The rehearsal also downgraded this finding's hazard honestly: the old commands write only to **gitignored** workspace paths, so they wasted effort but never dirtied tracked state. |
| **"Phase" is overloaded four ways** — reset P0–P14, legacy Stage 1–8, README "Phase 1 demo", owner-readiness phases | **UNCHANGED (accepted).** `PHASE-OUTPUTS.md` states the convention; full disambiguation would mean renaming things across historical documents. Not handoff-blocking. |

## Verification

[`eval/tests/test_docs_control_system.py`](../../eval/tests/test_docs_control_system.py) asserts
mechanically that:

- every auto-loaded file points at the canonical root documents
- **no auto-loaded file defines invoice processing as the final product**
- every agent definition carries a supersession banner
- `AGENTS.md` defers to `CLAUDE.md` and declares no status of its own
- historical documents cannot outrank canonical ones

**Discovery, not enumeration:** the guard globs `.claude/agents/*.md` and `.codex/agents/*.md`
rather than listing filenames — this repository has produced a filename-enumeration blind spot four
separate times, and a new agent file must not be able to arrive unbannered.

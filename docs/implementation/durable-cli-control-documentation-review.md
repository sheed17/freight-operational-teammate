> # ⛔ HISTORICAL REVIEW — NOT CURRENT AUTHORITY
> **This document is evidence of a past moment, accurate as of its own commit and possibly stale
> since.** It must not direct current implementation. Verdicts, statuses, counts and "READY"
> declarations below describe the state THEN — several are known-superseded (including any
> "24 of 134" transition figure, retired by U-HANDOFF-1B, and any suite count). Current status:
> [`CURRENT.md`](CURRENT.md) · authority map: [`../CANONICAL-DOCUMENTS.md`](../CANONICAL-DOCUMENTS.md)
> · operating guide: [`../../CLAUDE.md`](../../CLAUDE.md).

# Durable CLI-Control Documentation — Review

> ### **CLOSED.** The repository now replaces conversation memory: product identity, architecture,
> status, work units, legacy dispositions and open questions are all written down, cross-linked, and
> **guarded by executable tests**.
> ### **R-07 remains OPEN — NOT CONTAINED. Phase 3 has not begun and is BLOCKED behind a rehearsal.**

**1. Starting commit:** `7d72498` · **tree** `f2b22f037c814b99b29bc24012f3ddc612ade921` · branch
`recovery/u2-6bc-atomic-cutover`, clean · suite **1073 passed · 0 failed · 1 justified skip**.

---

## 2. Files created — 12

| Path | Role |
|---|---|
| **`CLAUDE.md`** | ### **The operating guide. It did not exist** — the single highest-value gap found |
| **`PRODUCT.md`** | Root product authority |
| **`ARCHITECTURE.md`** | Architecture entry point |
| `docs/CANONICAL-DOCUMENTS.md` | The authority map over 198 documents |
| `docs/implementation/CURRENT.md` | The single short-form status authority |
| `docs/implementation/IMPLEMENTATION-REGISTRY.yaml` | 17 work units, machine-readable |
| `docs/implementation/PHASE-OUTPUTS.md` | P0–P14: what each buys and forbids |
| `docs/implementation/LEGACY-DISPOSITION.md` | 14 subsystems, one disposition each |
| `docs/implementation/AUTO-LOADED-GUIDANCE-REVIEW.md` | The guidance audit |
| `docs/product/OPEN-VALIDATION-ITEMS.md` | 24 unresolved rules + safe interim behaviour |
| `docs/product/design-partner-observations.md` | Evidence by source class |
| `eval/tests/test_docs_control_system.py` | ### **68 executable documentation guards** |

## 3. Files updated — 15
`README.md` · `AGENTS.md` (both **rewritten**) · 11 agent definitions under `.claude/agents/` and
`.codex/agents/` (supersession banners + disarmed instructions) · `docs/implementation/registry.md`
(index + its own stale banner) · this review.

## 4–5. Quarantined / deleted
**Quarantined (labelled, not removed):** the stale status blocks in both `roadmap-steward` files and
the Stage-1 "next actions"; `docs/DESIGN_PARTNER_PILOT.md`, `INTERNAL_DOGFOOD_PILOT.md`,
`CODEX_HANDOFF.md`, `CODEX_FIX_HANDOFF.md` classified `QUARANTINED_GUIDANCE`.
### **Deleted: NOTHING.** No production code and no document was removed — the record of what was
built and proven live is preserved in full.

---

## 6–8. Product identity, architecture and operating guide

**`PRODUCT.md`** states Neyma is an **operational execution layer for small and medium freight
brokerages** and explicitly rejects all eight narrow readings, including the one the code most
strongly suggests. It separates **product destination** from **current implementation**, and marks
`HYPOTHESIS` and `NEEDS VALIDATION` claims as such. §19 states plainly that **existing code has no
presumption of survival.**

**`ARCHITECTURE.md`** covers all 30 required topics and preserves the eleven rules that may never be
weakened. It states in §29, without hedging: ### **Phase 2 made tenant ownership real at persistence
boundaries; it did NOT make consequential external effects safe.**

**`CLAUDE.md`** opens with what a zero-context agent will get wrong, then gives the reading order,
the 20 non-negotiable rules, the work-unit protocol, 10 stop conditions, a 13-point definition of
done, and §9 — the verification discipline, ### **where every rule is a defect this repository
actually shipped** (run validation last; verify mechanically with a denominator; negative assertions
need a population; mutate to prove a guard fails; never `git checkout` to undo a mutation).

## 9. Authority map

198 documents classified into 9 authority levels with an explicit precedence rule:
### **no HISTORICAL document ever outranks a CANONICAL one.** The chain has a named root
(`engineering-principles.md`), so authority does not cycle.

### ⛔ The pre-reset `docs/` root — 23 files
Every file directly in `docs/` predates the reset and sits outside the canonical chain.
`NEYMA_VISION.md`, `PRODUCT_ROADMAP.md` and `AGENTIC_ARCHITECTURE.md` are marked **SUPERSEDED**;
four more are **QUARANTINED_GUIDANCE**. ### **`OWNER_OPERATOR_ROADMAP.md` claimed to be "the
canonical where-are-we doc" while being dated three days BEFORE the reset** — that authority claim
is now void. **All 23 are retained as evidence; none may authorise a decision.**

## 10–11. Status and registry

**One** status authority, enforced: a guard scans every `.md` under `docs/` and fails if a second
file claims the role. **17 work units**, statuses restricted to `BLOCKED | READY | IN_PROGRESS |
COMPLETE` — ### **exactly one is READY, and a guard enforces that.** Every dependency resolves;
every COMPLETE unit carries evidence; every BLOCKED unit names what unblocks it.

## 12. Phase-output map

P0–P14 with gates G0–G10 — ### **the repository's own approved numbering, not the brief's 0–10 and
not a new one.** Each phase states purpose, system capability, **user-visible capability**, safety
guarantees, what stays prohibited, legacy removed, gates, and what unlocks next.
It is explicit that **P0–P2 delivered no user-visible capability**, that **P10 is the first real
user value**, and that ### **P4 is where R-07 closes and nowhere earlier.**

## 13. Legacy dispositions — **14 subsystems, all 77 modules covered**

| Disposition | Where |
|---|---|
| **KEEP** | S13 only (+ canonical Phase 0–2 modules) |
| **ADAPT** | S1, S5, S6, S9, S11, S14 |
| **REWRITE** | S3, S7, S8, S10 |
| **MAKE_READ_ONLY** | EP-8; outbound comms |
| **QUARANTINE** | S12 |
| **DELETE** | EP-6, EP-7, EP-9, EP-10 |

### **No `LEGACY_BUT_ACTIVE_FOREVER` category exists, and none may be added** — a guard rejects
permanent ambiguous dispositions. ### **No module is KEEP for being large or tested:** the two
largest modules in the repository — `action_callback.py` (1964 lines) and `workflow.py` (1157) —
are **REWRITE** and **ADAPT**. Coverage is machine-checked against the filesystem, so a new module
cannot arrive without a disposition.

## 14–15. Open validation and design-partner evidence

**24 items** (21 customer-specific from the corpus's own §13, plus 3 architectural), each with a
blocking class and ### **a safe interim behaviour that is fail-closed with a human owner.**

### ⛔ The design-partner record's headline finding
### **This repository contains NO firsthand design-partner observation by any agent.** Further,
the "first design partner" named in the corpus is ### **a founder-operated test brokerage, not an
independent customer** — recorded explicitly, because treating it as external validation would make
our own assumptions look like evidence. What *has* been directly observed is **our own test rig**.
**Nothing was invented**, and §"What this blocks" is careful: it blocks P8/P9/P10, and
### **it does NOT block P3–P7 — the safety wall is loop-independent.**

## 16–17. README and AGENTS

`README.md` is orientation: what Neyma is, current status, entry points, open safety findings, how
to run tests, how to find the next unit. **Not a marketing page and not a duplicate of PRODUCT.md.**
`AGENTS.md` is a thin compatibility entry point that ### **deliberately holds no status, no roadmap
and no product definition of its own** — because status was previously maintained in four places
and all four disagreed. Both close with an honest note about what they used to say.

## 18. ⛔ Auto-loaded guidance audit — the worst finding of this task

A mechanical search for `ADR-`, `docs/architecture`, `docs/implementation`, `docs/specifications`,
`implementation-roadmap` and `Implementation Phase` across **all 13 auto-loaded files returned
ZERO hits.**

> ### **The entire reset programme — 11 ADRs, the target spec, six specification layers, the
> acceptance corpus and three completed phases — was invisible to every file an agent auto-loads.**

**Three mutually inconsistent status claims coexisted:** `AGENTS.md` → *Stage 5 Human Review*;
`README.md` → *~515 tests, one fix round from a pilot*; both `roadmap-steward` files → *Stage 1 in
progress, broader engine not implemented*. Reality: **P0–P2 complete, 1073 tests.**
### **No file was correct.**

**Specifically disarmed:** the instruction *"guard against building the browser automation early…
call it out"* — which would have made an agent ### **flag the repository's most mature, live-proven
subsystem as premature work to halt.** Also removed: README's *"expand by stage, not by one giant
rewrite"* (read as a prohibition on the reset in flight) and two **broken doc links**, one of which
was a *gate* pointing at a file that does not exist.

**Recorded but deliberately not acted on** (each needs a decision, not an edit): the three-way model-
strategy contradiction; the missing `.claude` twin for the principal-architect supervisor; the drift
between the `.claude` and `.codex` agent pairs; the phase-code-reviewer's pre-reset command list.

## 19. Contradictions found and resolved

| Contradiction | Resolution |
|---|---|
| Four documents defining the product as document/invoice work | **SUPERSEDED** in the authority map; `PRODUCT.md` now root |
| Three conflicting status claims | Removed from root files; one authority |
| Two roadmaps in force | 8-stage marked **SUPERSEDED**; P0–P14 in force |
| `OWNER_OPERATOR_ROADMAP.md` claiming canonical status | Void — predates the reset |
| README's "~515 tests" vs the real 1073 | Corrected |
| "Phase" overloaded four ways | Convention stated explicitly in `PHASE-OUTPUTS.md` |

**Legitimate historical context was preserved, not erased** — `LIVE_WRITE_PROOF.md` and the pilot
runbooks remain as evidence of real work.

## 20. Documentation guards — **68 passing**

All 25 required checks are covered, plus link integrity, authority-chain rooting, registry
consistency and the W6→W8 provisional marking. Exact sets where registries are exact (the eleven
loops are asserted as a **SET**, so a same-count substitution fails). Every negative assertion runs
over a `require_population()`-proven population, and guard inputs are **discovered, never
enumerated**.

### ⛔ MY OWN GUARD FIRED ON ITSELF — AGAIN
The invoice-processor guard flagged `CLAUDE.md:243`, which is **the line telling agents to reject
the invoice-processor reading**. ### **A line that rejects a claim contains the same words as one
that asserts it.** Fixed structurally: matches inside a negating context are excluded, so the guard
distinguishes *asserting* from *rejecting* rather than matching words. This is the fourth
substring-self-match in this programme.

Four further real defects were caught by the guards on first run: a link to a not-yet-created file;
the W6→W8 slice named in `CURRENT.md` without its provisional marking; my own `AGENTS.md` closing
note quoting the stale stage claim; and the authority map's precedence rule wrapped across a
blockquote line so it was unmatchable.

## 21. Mutation results — ### **34/34 DETECTED** *(first pass: 19/34)*

### ⛔ MUTATION PROVED 15 OF MY OWN GUARDS WERE DECORATION
The first run detected **19 of 34**. Every miss was a real hole in the guards, not an unfaithful
mutation, and the suite was green throughout:

1. ### **The 11 architecture invariants and the 20 non-negotiable rules had NO GUARD AT ALL.**
   `MODEL_INFERRED` could be granted authority, replay could be permitted to call adapters, the
   Commit Key and Material Facts could be merged, a second effect ledger could be blessed, and the
   accountable-human requirement could be deleted — ### **five mutations that invert the safety
   model, and every test stayed green.** Now guarded **in both directions**: the rule must be
   present *and* its reversed form must be absent, because adding the inverse alongside the
   original is the more likely drift.
2. ### **Findings only had to appear in ANY of three documents.** Deleting the live-write-path,
   adapter-import, event-less-transition and default-tenant findings from the **status authority**
   stayed green because a copy survived in the README. ### **`CURRENT.md` is where an agent looks;
   it must carry every finding itself.**
3. **The "Phase 2 did not make effects safe" check concatenated three documents**, so any one of
   them could lose the statement silently. Now asserted per-document, both ways.
4. **The product-identity check on `CLAUDE.md` had a trailing `or "invoice processor" in text`** —
   a phrase present in any file that discusses the subject, which made the assertion
   **unconditionally true**. Replacing the canonical definition outright stayed green. Now
   section-scoped to §2.
5. **The design-partner record had no guard**, so *"volumes and approval thresholds were observed
   directly"* could be written into the DIRECTLY OBSERVED section. ### **This is the most dangerous
   drift available in this repository — inference presented as observation** — and it was unguarded.
6. **The authority map was checked file-wide**, so a row could be flipped to `CANONICAL` while the
   word `SUPERSEDED` survived elsewhere. Now row-scoped, and scoped to the row's *subject* column.
7. **The skip guard only fired when EVERY test in a file was disabled**, so silencing one
   load-bearing guard passed. Now any disabled guard fails — and `test_docs_control_system.py` was
   itself **absent from the guard registry**, so nothing was watching it.

**Two misses were my own unfaithful mutations**, verified rather than assumed: inserting a second
`status:` key made a YAML duplicate that PyYAML resolves to the *last* value, so the unit stayed
`BLOCKED` and nothing was reintroduced; and one target string had changed under an earlier edit,
which the harness caught as a **no-op mutation** rather than reporting a false miss.

### **After the fixes: 34/34, with 68 guards instead of 46.** The safe in-memory harness held
throughout — digest-verified restoration, bytecode purged, ### **no git command anywhere.**

## 22–23. Regression

| | |
|---|---|
| **Phase-2 runtime suite** | ### **GREEN — unchanged** |
| **AC-SAFE-012 / AC-SAFE-013 / AC-SEC-001** | ### **GREEN** |
| **Complete repository suite** | ### **1141 passed · 0 failed · 1 skipped** *(was 1073 — **+68**, all documentation guards)* |
| **New production behaviour** | ### **NONE.** No runtime code was modified |

## 24–28. Open findings — ### **ALL PRESERVED, ALL STILL OPEN**

| Finding | Status |
|---|---|
| **R-07** | ### **OPEN — NOT CONTAINED** |
| 6 production-reachable live-write paths | OPEN — close at P4 |
| 31 direct adapter-import edges | OPEN — close at P4 |
| 24 event-less transitions | OPEN — settle before P5 |
| Knowledge-base `tenant="default"` | OPEN — closes at P7 |
| No firsthand design-partner observation | OPEN |
| Checkpoint/witness (P3), adapter containment (P4) | UNIMPLEMENTED |
| Repository legacy reduction | UNFINISHED |

Each is asserted by a guard, so removing one from the record fails the build.
### **Nothing in this package implies Phase 2 made external effects safe** — a guard asserts the
opposite statement is present.

## 29–31. Validation and commit

| | |
|---|---|
| **Full suite** | ### **1141 passed · 0 failed · 1 skipped** |
| validation start tree | `ef21490e706d6a742365800001a39647e40aa6f3` |
| validation end tree | `ef21490e706d6a742365800001a39647e40aa6f3` |
| ### **digests match** | ### **✔ — byte-identical before and after the run** |
| tree after writing this section | recorded in the commit message |
| ### **confirmation pass** | ### **1141 passed · 0 failed · 1 skipped, digests matched** |
| **working tree** | clean · **branch NOT pushed** |
| **production code changed** | ### **NONE** — `git diff HEAD -- src/ scripts/` is empty |

> ### **The only edit after validation was writing these digests into this table**, which
> necessarily changes the tree — a single self-referential digest is impossible and claiming one
> would be a lie. The inserted-digest tree was therefore validated again in full, and that run is
> the one this verdict rests on. Same convention as the Blocker-6 review.

## 32. Exact next approved work program

### **ZERO-CONTEXT CLI HANDOFF REHEARSAL AND HOSTILE READINESS REVIEW** — unit `U-HANDOFF-1`,
the only `READY` unit. **P3 is `BLOCKED` and depends on it**, asserted by a guard.

## 33. May a zero-context rehearsal begin? ### **Yes.**

The control system is complete and self-checking. What it has **not** yet had is contact with a real
zero-context agent — which is precisely what `U-HANDOFF-1` is for.
### **I am claiming the repository is ready to be TESTED for handoff readiness, not that handoff
readiness is proven.** Those are different claims, and only the rehearsal can settle the second.

---

# VERDICT

## ### **READY TO BEGIN ZERO-CONTEXT CLI HANDOFF REHEARSAL**

**Carried forward, unchanged:** ### **R-07 OPEN — NOT CONTAINED** · six live-write paths · 31
adapter import edges · 24 event-less transitions · the knowledge-base `"default"` tenants ·
Phase-3 checkpoint/witness unimplemented · Phase-4 adapter containment unimplemented · no firsthand
design-partner evidence · legacy reduction unfinished.

### **This task wrote documentation. It changed no runtime behaviour, closed no risk, and made
nothing safer. What it changed is that the next agent will know that.**

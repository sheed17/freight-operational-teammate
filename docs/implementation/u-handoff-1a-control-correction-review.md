> # ⛔ HISTORICAL REVIEW — NOT CURRENT AUTHORITY
> **This document is evidence of a past moment, accurate as of its own commit and possibly stale
> since.** It must not direct current implementation. Verdicts, statuses, counts and "READY"
> declarations below describe the state THEN — several are known-superseded (including any
> "24 of 134" transition figure, retired by U-HANDOFF-1B, and any suite count). Current status:
> [`CURRENT.md`](CURRENT.md) · authority map: [`../CANONICAL-DOCUMENTS.md`](../CANONICAL-DOCUMENTS.md)
> · operating guide: [`../../CLAUDE.md`](../../CLAUDE.md).

# U-HANDOFF-1A — Bounded Control-System Correction — Review

> ### **CLOSED.** The rehearsal's HIGH and MEDIUM findings are corrected, the LOW findings are
> addressed, the founder-approved broad-tool-access policy is in force, and the status authority
> can no longer silently drift from the repository it describes.
> ### **U-HANDOFF-1 remains OPEN — the INDEPENDENT zero-context rehearsal has not been run.**
> ### **R-07 remains OPEN — NOT CONTAINED. Phase 3 remains BLOCKED. No production runtime code changed.**

**1. Starting commit:** `8a08a4a0641850f981fd0a46a9c7af515565a393` · tree
`db7257dcd1055f84d31bccf775128c2a99a8baf1` · branch `recovery/u2-6bc-atomic-cutover`, clean.
**2. Starting suite:** 1141 passed · 0 failed · 1 justified skip (run on exactly that tree during
the rehearsal, same session).

---

## 3–4. H-1 — the status authority now matches reality

The rehearsal's HIGH finding: `CURRENT.md` recorded the **previous** commit, tree and suite count;
the stale figure was propagated into four more files; no guard noticed. Corrected:

- `CURRENT.md`'s Position is now a **machine-maintained fenced status-block** — written only by
  [`scripts/update_current_status.py`](../../scripts/update_current_status.py) from `git rev-parse`
  and a real suite run, never by hand.
- `IMPLEMENTATION-REGISTRY.yaml` `meta:` **mirrors that block** and is rewritten by the same
  script, so the two records cannot drift apart.
- The exactly-one-source rule: **volatile commit/tree/suite figures live only in the status-block.**

## 5. Status-reality guard design — the two-commit convention

A commit cannot contain its own hash, so a self-referential "current commit" field is impossible
and claiming one would be a lie. The design that is honest instead
([`eval/tests/test_status_reality.py`](../../eval/tests/test_status_reality.py), 5 guards):

1. Every substantive change lands in a **content commit**; the finalization script then records
   it, and the record lands in **exactly one status-metadata commit** on top, touching only the
   declared status files (the allowed set is imported from the script itself, so guard and script
   cannot disagree about what "metadata only" means).
2. The guard passes iff `recorded == HEAD` (baseline checked out directly) **or**
   `recorded == HEAD^` **and** `diff HEAD^..HEAD ⊆ status files` — a metadata commit that smuggles
   in a substantive change fails.
3. **Suite truthfulness without recursion:** the guard cannot run the full suite inside the suite,
   so it verifies the invariant that actually decays — recorded `passed+failed+skipped` must equal
   the **live collected-test population**. Adding or removing one test without re-finalizing fails
   the build; this is precisely how the 1073→1141 drift would have been caught. The pass/fail
   split itself is proven by the final-validation run recorded below.
4. A scan proves **no secondary control or auto-loaded file carries its own volatile suite claim**
   (quarantined `<details>` history exempted — holding stale figures is its purpose).
5. The record must also still be **right**, not merely fresh: P2 COMPLETE, P3 NOT STARTED and
   BLOCKED, the INDEPENDENT rehearsal as the current program.

## 6. Duplicated volatile status removed
`README.md` (status table + suite comment + the "~515 tests" footnote), `PRODUCT.md` §13,
`.claude/agents/roadmap-steward.md` banner — all now point at `CURRENT.md` instead of copying
numbers. A mechanical sweep of every control and auto-loaded file found no survivors.
**Deliberate interpretation, recorded:** stable facts that guards *require* redundantly (Phase-3
NOT STARTED, R-07 OPEN in README/CLAUDE) stay redundant — safety-critical facts are repeated by
design with deference notes; only volatile mechanical identifiers are single-sourced.

## 7. M-1 — phase reviewer commands
Both surfaces now carry **"Verification Commands — CANONICAL"**: unit acceptance + the AC-SAFE/
AC-SEC gates, documentation + tool-policy guards, **the status-reality guard**, concurrency
evidence, exact-set probes, mutation evidence, the complete suite **last on the final tree**, and
clean-tree verification. The pre-reset list survives only inside a `<details>` block titled
**"Historical commands — NO approval authority"**, and a guard asserts no pre-reset command
re-enters the canonical zone.

## 8. M-2 — provider strategy
`.claude/agents/build-supervisor.md` no longer claims a universal provider. It now records: the
runtime is **dual-provider** (Anthropic vision extraction via `from_anthropic`; OpenAI for
browser/operation/orientation surfaces), **provider choice is not canonical product architecture**,
valid provider usage is never flagged by provider alone, and consolidation requires an explicit
approved work unit. ### **No final model strategy was invented — none is canonically decided.**
The `.codex` counterpart carried no provider claim (verified mechanically); no edit was needed there.

## 9. M-3 — guidance-review accuracy
`AUTO-LOADED-GUIDANCE-REVIEW.md`'s "not acted on" table is now "**dispositions updated by
U-HANDOFF-1A**": the model-strategy contradiction is recorded as **RESOLVED as a contradiction,
OPEN as a decision**; the twin, pair-drift and reviewer-command findings are recorded RESOLVED with
their mechanisms; the phase-vocabulary overload stays recorded as accepted. A review document now
describes the state its commit produced, and a guard holds it there.

## 10–12. The tool-access policy

[`TOOL-ACCESS-POLICY.md`](TOOL-ACCESS-POLICY.md) — **IMPLEMENTATION_CONTROL, founder-approved.**

> **SEARCH AGGRESSIVELY. INFER CAUTIOUSLY. EXECUTE ACCORDING TO AUTHORITY.**
> **Tool access expands evidence retrieval, not canonical decision authority.**

- **Broad-access posture:** all configured tools — repository, shell, git history, test runners,
  static analysis, package installation, **web search**, API/library documentation, GitHub,
  **Google Drive / Notion / internal connectors**, browser automation, disposable databases, MCP
  servers, branches/commits/PRs. Routine engineering needs no per-action approval; no blanket
  restriction; no permission-bypass mode prescribed as default; no MCP vendor mandated.
- **The obligation that comes with breadth:** missing technical context is **researched, not
  guessed**, with evidence discipline (source, retrieval date, source type, exact claim,
  confidence, external/internal/observed/inferred class — and retrieved evidence never silently
  upgrades its class).
- **Mandatory missing-context classification:** SEARCHABLE TECHNICAL FACT (research
  automatically) · INTERNAL ORGANIZATIONAL FACT (search connectors; record the gap if unfound) ·
  PRODUCT DECISION (research alternatives; **research does not choose**; stop for an explicit
  decision) · CUSTOMER-SPECIFIC OPERATIONAL RULE (mark `NEEDS VALIDATION`, fail closed, route to
  the accountable human) · CONSEQUENTIAL-ACTION AUTHORITY (**search cannot create authorization**).
- **Consequential-action boundary:** production DB writes, live TMS writes, payments/accounting,
  carrier assignment, external communications, deployment, destructive live-data operations,
  credential rotation, customer-data deletion, legal/financial commitments — inspect, prepare,
  simulate, validate: yes; execute on tool possession: **never**. ### **Possession of a tool or
  credential is never authorization — R-07's six live-write paths are the standing proof of why.**

Integrated into `CLAUDE.md` (reading-order item 10 + the concise rule verbatim), the authority map,
`CURRENT.md`, the registry's U-HANDOFF-1 references, and README navigation.

## 13. Tool-access guards
[`eval/tests/test_tool_access_policy.py`](../../eval/tests/test_tool_access_policy.py) — **22
guards covering all 18 required proofs**, the dangerous ones bidirectional (statement present AND
inversion absent): breadth explicit; web search allowed; connectors allowed; packages/test tooling
allowed; capability ≠ authority; possession ≠ authorization; search cannot validate hypotheses,
manufacture partner evidence, choose thresholds, authorize payment/carrier, retry
`UNKNOWN_OUTCOME`, override `OWNER_ASSERTED`, or promote `MODEL_INFERRED`; production writes
gated; no blanket restriction; no bypass-mode default; no MCP vendor mandated.

## 14. L-1 — scripts disposition coverage
`LEGACY-DISPOSITION.md` §S15: **all 53 `scripts/` files** in seven genuinely-shared groups —
S15a effect-capable (the S2/R-07 set, per-EP dispositions matching the cutover plan) · S15b
browser/TMS tooling (ADAPT P4) · S15c mailbox/Slack/channel runners (ADAPT P4→P13) · S15d legacy
pipeline runners (ADAPT with their subsystems) · S15e corpus generation (QUARANTINE) · S15f
pilot/onboarding (QUARANTINE P11) · S15g migration + control-plane tooling (KEEP, justified). The
coverage guard now discovers `scripts/` from the filesystem, both directions (no missing, no
phantom).

## 15–16. L-2 / L-3 — the agent surfaces
**Twin created:** `.claude/agents/principal-architect-supervisor.md` — modernized to the canonical
control system (required context = CLAUDE/PRODUCT/ARCHITECTURE/CURRENT/registry/dispositions/tool
policy; adjudicates scope fidelity, safety boundaries, acceptance discipline, status truthfulness,
ADR conformance, provider neutrality), because copying the stale Codex content would have
propagated the pre-reset reading list and the LangGraph framing into the new canonical surface.
**Authority decision:** ### **`.claude/agents/` is canonical** (the formal CLI environment is
Claude Code); every `.codex/agents/` file now opens with a **COMPATIBILITY SURFACE** header naming
its canonical counterpart. The drift guard enforces pair-set equality + the pointer + the banner.
Full text-sync was deliberately rejected: what must not drift silently is **authority**, and now it
cannot.

## 17. Implemented-vs-specified registry
[`IMPLEMENTATION-SURFACE.yaml`](IMPLEMENTATION-SURFACE.yaml) — **21 concepts**, exact set, each
with spec link + owning unit: 4 IMPLEMENTED (Tenant, Commit Key, Effect Grant ledger foundation —
and each must cite a file+symbol that verifiably exists) · 1 PARTIALLY_IMPLEMENTED (Material Facts:
column yes, fingerprint/drift-voiding P3) · 3 LEGACY_IMPLEMENTATION (Policy, Brake, Reconciliation
— pre-reset analogues with dispositions, never "done") · 12 SPECIFICATION_ONLY (each must cite
`absent_symbols` verifiably absent from `src/`) · 1 BLOCKED (the W6→W8 slice, behind V-W1).
Guards run **both directions**, plus a cross-check: the three P3 concepts must stay
SPECIFICATION_ONLY while P3 is BLOCKED. The question the rehearsal answered by hand-grepping is
now a build failure when wrong.

## 18. U-HANDOFF executable checklist
[`U-HANDOFF-1-ACCEPTANCE.yaml`](U-HANDOFF-1-ACCEPTANCE.yaml) — **HANDOFF-01…13**: the seven
rehearsal criteria plus tool-access posture, tool-vs-authority distinction, status-block
verification, and first-formal-unit identification. Every criterion carries required evidence and
`result: PENDING`; guards enforce the exact ID set and ### **that no criterion is pre-marked PASS —
this checklist cannot be passed by the session that wrote it.** The registry's acceptance contract
now names it and requires the rehearsing agent **not** to have authored the control documents.
*(Namespace note: the criteria were first minted as `AC-HANDOFF-*` and the frozen-corpus
identifier guard correctly refused them — `AC-*` belongs to the frozen acceptance registry, and a
documentation task may not mint into it. Renamed `HANDOFF-01…13`; both checklist mutations re-run
and detected post-rename.)*

## 19. Mutation results — ### **20/20 DETECTED** *(first pass 19/20; the miss was a guard gap, fixed)*

All 19 required mutations plus one addition (a pre-marked-PASS checklist criterion) ran under the
safe in-memory save/finally-restore harness — digest-verified restoration, bytecode purged,
**no git restoration, and no-op mutations rejected by the harness.**

| # | Mutation | Detector |
|---|---|---|
| S-1/2/3 | stale CURRENT commit / tree / suite count | status-reality guard |
| S-4 | duplicate volatile status in README | secondary-claim scan |
| S-5 | registry meta drifts from CURRENT.md | meta-mirror guard |
| S-6 | phase reviewer approves without acceptance tests | canonical-commands guard |
| S-7 | build supervisor claims one universal provider | dual-provider guard *(see below)* |
| S-8 | guidance review re-opens the resolved contradiction | adjudication guard |
| T-1/2 | broad web-search / connector permission removed | tool guards 4, 5 |
| T-3 | broad access turned into blanket restriction | tool guard 17 |
| T-4 | tool possession authorizes an external effect | tool guard 8 (bidirectional) |
| T-5 | web search chooses the approval threshold | tool guard 11 |
| T-6 | web evidence overwrites OWNER_ASSERTED | tool guard 14 |
| R-1 | spec-only Checkpoint marked IMPLEMENTED | surface cross-check guard |
| R-2 | one U-HANDOFF criterion omitted | exact-ID-set guard |
| R-3 | a criterion pre-marked PASS | all-PENDING guard |
| R-4 | codex pair file loses its compatibility pointer | pair-authority guard |
| R-5 | one production-relevant script disposition removed | scripts coverage guard |
| R-6 | a required control guard skipped | per-test skip guard |

### ⛔ THE ONE FIRST-PASS MISS — S-7 — WAS MY GUARD BEING WEAK TWO WAYS AT ONCE
Replacing the dual-provider statement with *"calls Claude for everything; flag any other provider"*
stayed green because (a) the guard's positive check matched the word "dual-provider" in the
**section heading** while the body asserted the opposite, and (b) its negative pattern was
**case-sensitive** and the mutation began a sentence. ### **A guard satisfied by a heading is
satisfied by furniture.** Fixed: the full statement is required (not the token) and
universal-provider claims are scanned case-insensitively. Re-run: **20/20**.

A further honesty note: the draft of this review briefly contained a *predicted* mutation table
written before the run. That is the exact "green suite that predates the commit" defect this
repository documents, caught before commit; the table above is from the actual run.

## 20–21. Regression and full suite
Phase-2 regressions, AC-SAFE-012, AC-SAFE-013, AC-SEC-001: **GREEN** (36 gate cases). Full suite
on the final content tree: **1179 passed · 0 failed · 1 skipped** — and re-validated identically on the
committed checkout. **No production runtime module changed** (`git diff` over `src/` is empty; the
only `scripts/` change is the new status finalizer, dispositioned S15g).

## 22–25. Final committed state

| | |
|---|---|
| **Content commit** | `fde6c9531fa22761799f81e55d6022640697f85c` |
| **Content tree** | `1f046f3925fde9e57d8c7de470a4f9f30a4fc4a2` |
| **HEAD** | the single status-metadata commit directly on top (hash in `git log`; per the two-commit convention it cannot be recorded here) |
| **Status-reality guard on the committed checkout** | ### **GREEN** |
| **Working tree** | clean · **not pushed** |

## 26. Remaining findings
**No MEDIUM findings remain open.** LOW remainders, recorded: the `.claude`/`.codex` pairs still
differ in body text (authority is guarded; content sync is deliberate non-goal); the "phase"
vocabulary overload stays accepted; the phase-code-reviewer's historical block still names writing
commands (labelled, stripped of authority, targets gitignored paths only). None makes the next
unit ambiguous.

## 27. May the independent rehearsal begin? ### **Yes.**
The corrections are bounded, guarded and mutation-proven. What has NOT happened — and cannot happen
in this session — is the rehearsal itself: ### **the author of these documents cannot be their
independent examiner.** The checklist is PENDING by construction and a guard keeps it that way.

---

# VERDICT

## ### **READY FOR INDEPENDENT ZERO-CONTEXT REHEARSAL**

**Carried forward, unchanged:** ### **R-07 OPEN — NOT CONTAINED** · six live-write paths · 31
adapter-import edges · 24 event-less transitions · the knowledge-base `"default"` tenants ·
founder-operated design-partner limitation · P3 BLOCKED · the exact 17-unit graph · one READY unit
(U-HANDOFF-1, the rehearsal itself).

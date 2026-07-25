> # ⛔ HISTORICAL REVIEW — NOT CURRENT AUTHORITY
> **This document is evidence of a past moment, accurate as of its own commit and possibly stale
> since.** It must not direct current implementation. Current status:
> [`CURRENT.md`](CURRENT.md) · authority map: [`../CANONICAL-DOCUMENTS.md`](../CANONICAL-DOCUMENTS.md)
> · operating guide: [`../../CLAUDE.md`](../../CLAUDE.md).

# U-REBASELINE-REVIEW-1 — Independent Product and Production Review — Preserved Evidence

## Preservation record

This file preserves the **independent** U-REBASELINE-1 product-and-production review, produced in a
fresh testing-account clone at **HEAD `fb5fcd93faa77a2daf37da192c05b62dd1b5bfbf`**, tree
**`6bbef434fe78bcb9d41cf492968d0448b89b266c`**, delivered by founder paste on 2026-07-20. It is the
independent evidence RB-24 requires. Its adjudication is
[`u-rebaseline-1a-founder-adjudication-review.md`](u-rebaseline-1a-founder-adjudication-review.md).

**Completeness:** received complete, end to end (environment table → methodology → 16 findings →
five verdicts → tests table → limitations → final recommendation). No truncation occurred.

**Independent verification by the adjudicating session:** HEAD, tree, the two-commit parentage
(`98e531f` → `fb5fcd9`), the exact five-file metadata diff, the recorded suite (1268/0/1) and the
1269-node manifest all verified to match. Findings F-01, F-02, F-04 and F-08 were re-verified
directly at source before acceptance (see the adjudication review).

---

## Verbatim received report

```text
INDEPENDENT U-REBASELINE-1 PRODUCT AND PRODUCTION REVIEW

Review target and environment

Requested HEAD            fb5fcd93faa77a2daf37da192c05b62dd1b5bfbf
Actual HEAD               fb5fcd93faa77a2daf37da192c05b62dd1b5bfbf — MATCHES
Requested tree            6bbef434fe78bcb9d41cf492968d0448b89b266c
Actual tree               6bbef434fe78bcb9d41cf492968d0448b89b266c — MATCHES
Working tree              clean at review start and re-verified clean at review end (after all test runs)
Branch state              detached HEAD at fb5fcd9 (no branch checked out; no branch was changed)
Inspected content         YES — verified before and after the review; no repository file was edited,
  matches target          no commit made, no control state modified
Two-commit convention     verified: fb5fcd9's sole parent is content commit 98e531f, and the metadata
                          commit touched only status files (BUILD-STATUS.yaml, CURRENT.md,
                          GATE-RESULT.json, IMPLEMENTATION-REGISTRY.yaml, SUITE-RESULT.json)
Environment               macOS (Darwin 24.1.0); host python3 = 3.10.8 (correctly rejected by
                          scripts/check_env.py — the fail-fast floor works); review executed with a
                          Python 3.13 venv

No prior-session conclusions were relied on; every claim below was established from this checkout
during this review, and every subagent finding used in a verdict was independently spot-verified
against the source files.

Methodology

Mandatory environment verification (above), then required-reading order: CLAUDE.md → PRODUCT.md →
ARCHITECTURE.md → CURRENT.md → registry → acceptance contracts.

Direct hostile reads of: PRODUCT.md, ARCHITECTURE.md (invariants section), CURRENT.md,
BUILD-STATUS.yaml, ADR-012, ADR-015, ADR-017, ADR-019, U-REBASELINE-1-ACCEPTANCE.yaml,
IMPLEMENTATION-REGISTRY.yaml, PHASE-OUTPUTS.md, EFFECT-PATH-INVENTORY.yaml,
eval/tests/test_rebaseline_invariants.py (guard source read directly).

Four independent read-only review agents: (a) the eleven freight loops against a 13-dimension
matrix; (b) the operational-use-case coverage matrix, parsed mechanically with printed denominators
plus in-memory mutation trials of the real guard function (mutants verified to actually
remove/alter records; the repository tree was never touched); (c) the deterministic guard suite
across all 11 required guard categories plus P3-absence; (d) production ADR checklists (23 items),
integration/migration model, and the 14 control-plane surfaces. Every HIGH finding from any agent
was re-verified by me against file and line before acceptance; severities below are my
adjudication, not the agents'.

Mechanical evidence: full canonical suite executed in this checkout; the self-recording clean-clone
gate executed from a scratch clone (because clean_clone_gate.py writes
docs/implementation/GATE-RESULT.json into whatever repo it runs from — running it in place would
have violated the read-only constraint; the scratch clone was verified to be at the exact target
HEAD/tree).

Passing tests were not treated as proof by themselves: guard quality was probed by mutation
(finding F-03), citation accuracy of PASS records was checked against the cited documents (finding
F-08), and the specification layer's own self-review claims were checked against the specs they
describe (finding F-02).

Findings table

No CRITICAL findings. Severity is mine; "Verified" means I confirmed the citation directly.

ID: F-01  Sev: HIGH  Category: canonical-staleness / freight coverage
Evidence: W6-documentation.md:3 ("The FIRST-LOOP candidate (L6→L8)"), W8-billing.md:3 ("The
FIRST-LOOP destination (L6→L8)"), workflows/registry.md:75 — all CANONICAL files — still present
the L6→W8 slice as the first-loop hypothesis, while PRODUCT.md:262-263 states Delivered Load
Closure "supersedes the earlier, narrower 'W6 Documentation → W8 Billing' slice description."
Verified.
Consequence: A canonical-vs-canonical contradiction — a CLAUDE.md §7 stop condition. Mitigations:
PRODUCT.md's declared precedence resolves it unambiguously, and the stale text is itself marked
NEEDS VALIDATION/fail-closed, so misbuild risk is low; but RB-24 is about fresh-reviewer legibility
and this is exactly the kind of residue the rebaseline existed to sweep.
Recommendation: Add a one-line DLC supersession note to the three files (documentation-only change).

ID: F-02  Sev: HIGH  Category: specification integrity / false-green in documentation
Evidence: workflows/registry.md:30 requires every consequential step to name "Commit Key, Material
Facts, and verification mode"; in the eleven loop specs only W8-4 states a full Commit Key tuple
and only W1-6/W8-4/W9-5 state Material Facts — POST_LOAD, SEND_TENDER, ISSUE_RATECON,
REQUEST_APPOINTMENT, SEND_OUTBOUND (×3), FILE_DOCUMENT (MF), W11's adjustment do not. Yet
operational-workflow-review.md:67 records "Every consequential step defines Commit Key + Material
Facts ✅". Verified both sides.
Consequence: The specification layer's own review asserts a completeness the specs do not have —
the repository's "false-green" pattern in documentation form. An implementer at P6–P9 trusting that
row would under-specify effect identity for ~90% of consequential steps.
Recommendation: Either complete CK/MF per consequential step, or narrow the registry contract to
"inherits the registry default write-path with CK/MF defined at implementation time" — and correct
operational-workflow-review.md:67 either way.

ID: F-03  Sev: HIGH  Category: guard porosity / coverage matrix
Evidence: test_rebaseline_invariants.py:361-398 — mutation-proven (in memory, real guard function):
(a) whole-record deletion of UC-27 (outage handling) and UC-28 (backup/DR) passes, because topic
regexes scan the raw file blob and outage/recovery survive incidentally in other records' text;
(b) a same-count substitution (UC-28 replaced by a duplicate billing record under a new id) passes,
because the population is guarded by len(ucs) >= 30, not exact ID membership. Verified against the
guard source: blob regexes at :391-394, count floor at :368.
Consequence: The guard mandated against "disappearance or category loss in the coverage matrix" is
substantive against most mutations (five other deletions and a shrink were caught) but porous at
two proven seams — and the count-not-membership pattern is the exact defect CLAUDE.md §8 forbids.
Recommendation: Check topics against parsed use-case records, not the blob; pin the exact UC-id set
(membership, symmetric diff), with an annotated update path.

ID: F-04  Sev: HIGH  Category: validation-reference integrity
Evidence: Loop specs cite V1, V-3, V4, V5, V10, V11 (W1:19, W8:11,19, W6:18, W7:15, W10:14,
registry:75); the canonical registry OPEN-VALIDATION-ITEMS.md defines V-01…V-21 with different
semantics (V-04 = approval dollar thresholds vs spec "V4" = per-customer pricing; V-05 = partner's
TMS/API vs spec "V5" = per-customer document/billing rules; V-10 = inbox provider vs spec "V10" =
per-lane ageing; V-11 = how loads enter vs spec "V11" = autonomy graduation; W8's "V-3" is actually
the adapter invariant, colliding with validation item V-03). Verified by sample.
Consequence: Every V-reference in the workflow layer dangles or collides. An implementer resolving
"V5" lands on the wrong canonical validation item — undermining exactly the traceability the NEEDS
VALIDATION discipline depends on.
Recommendation: One namespace: re-key loop-spec references to the canonical V-0x ids, or give the
workflow layer its own prefixed ids with a mapping table.

ID: F-05  Sev: MEDIUM  Category: guard gap / validation honesty
Evidence: Mutation-proven: flipping UC-09.design_partner_validation_status to
VALIDATED_BY_DESIGN_PARTNER passes every guard; the field's vocabulary is unguarded (no enum in
meta; guard checks presence only, test_rebaseline_invariants.py:372). Today's content is honest: 0
of 33 use cases claim validation, consistent with design-partner-observations.md recording zero
firsthand observations.
Consequence: The matrix is honest but nothing mechanically keeps it honest — a silent "validated"
flip would survive CI.
Recommendation: Enum-guard the field and assert zero VALIDATED* entries until
design-partner-observations.md records firsthand evidence.

ID: F-06  Sev: MEDIUM  Category: guard fragility / drift patterns
Evidence: test_rebaseline_invariants.py:40-44: the DISARM regex includes a bare ADR citation
(ADR-01[2-9]) with a ±1-line window, so "Per ADR-013, Slack is the only control interface" would be
self-disarming; :439 checks only that PRODUCT.md contains "chatbot-only product" (polarity-blind);
the Slack/chatbot negative patterns are verbatim-fragile ("Slack-first" etc. uncaught). Verified in
source.
Consequence: A crafted or careless reintroduction of a rejected absolute adjacent to an ADR citation
passes the drift scan.
Recommendation: Require retirement vocabulary (reject/retired/superseded) in the disarm marker;
make the PRODUCT.md check assert the phrase inside the "NOT" list context.

ID: F-07  Sev: MEDIUM  Category: vacuous-pass path in a guard
Evidence: test_rebaseline_invariants.py:442-454:
test_no_src_runtime_file_was_touched_by_the_rebaseline silently returns (passes) when git fails, and
diffs against a hardcoded commit 0a25a001. Verified in source.
Consequence: A guard module whose own doctrine forbids vacuous passes contains one; the hardcoded
baseline will also need explicit replacement the moment P3 legitimately touches src/.
Recommendation: Skip loudly (machine-visible, like the dirty-tree skips elsewhere) instead of
returning; read the baseline from the registry.

ID: F-08  Sev: MEDIUM  Category: acceptance-record evidence accuracy
Evidence: U-REBASELINE-1-ACCEPTANCE.yaml RB-15 records PASS for "Observability, CI/CD,
environments…" with evidence "ADR-016 section 2 … rows" — but ADR-016 never mentions CI/CD (grep
verified: zero hits); same pattern for RB-13's "queues". The requirements are genuinely met
elsewhere (PROGRESS-PROTOCOL.md §4, PROGRAM-WEIGHTS.yaml ci_cd/queues_inbox_outbox/
rollback_exercises, implementation-roadmap.md rollback tables, UC-29) — the substance passes; the
recorded citation does not support it.
Consequence: A PASS backed by a citation that lacks the named item, in a repository whose own
discipline condemns evidence "that parsed nothing."
Recommendation: Correct RB-13/RB-15 evidence strings to cite the documents that actually carry
CI/CD, queues and rollback — or add them to ADR-016 §2.

ID: F-09  Sev: MEDIUM  Category: freight authority gaps
Evidence: W4 names two consequential effects with no gate/approvals section anywhere in the spec
(W4-dispatch.md:11,13); W2-5's gate is "per policy" with no policy named; W6's FILE_DOCUMENT gate
class is unstated; W5's check-call SEND_OUTBOUND gate unstated. The registry default routes all
effects through the full pipeline, so nothing is ungated by design — but per-effect gate class is
what the step-contract says must be named.
Consequence: Gate classes for several consequential effects get chosen at implementation time
instead of specification time.
Recommendation: Name the gate/approval class per consequential effect in W2/W4/W5/W6, or explicitly
delegate to a named policy id.

ID: F-10  Sev: MEDIUM  Category: reference hygiene
Evidence: Hostile-trace references ("#N") span three unlabeled numbering namespaces (workflow
review's 40 traces, domain-entity battery, adapter battery); three different scenarios all answer
to "#14". The "61-point" spec template is cited by number everywhere but enumerated nowhere —
whether a missing point is default-inheritance or omission is mechanically unauditable.
Consequence: Cross-reference audits of the freight layer cannot be automated and are error-prone by
hand.
Recommendation: Prefix trace ids per battery; publish the 61-point index once in registry.md.

ID: F-11  Sev: LOW  Category: rule-18 marker discipline
Evidence: Only W1 and W8 carry the literal NEEDS VALIDATION marker in-file; W2–W7, W9–W11 list open
freight rules in "61. Open." relying on registry.md:74-75's blanket fail-closed clause.
Substantively honest (open rules are fail-closed, none hardcodes an unvalidated value); formally
uneven.
Consequence: Marker greps under-count open rules by file.
Recommendation: Apply the literal marker in each "61. Open." block.

ID: F-12  Sev: LOW  Category: guard hygiene
Evidence: Coverage guard: required_fields omits id and use_case; no duplicate-ID check; dead code at
test_rebaseline_invariants.py:381 ({... for t in []} empty comprehension — independently flagged by
two agents); matrix vocabulary drift NEEDS_MODE_SPECIFIC_VALIDATION (UC-30) vs
REQUIRES_MODE_SPECIFIC_VALIDATION (header); UC-33 ordered before UC-32.
Consequence: Minor auditability noise.
Recommendation: Tidy alongside the F-03 rewrite.

ID: F-13  Sev: LOW  Category: corpus navigation
Evidence: ARCHITECTURE.md (required reading #3) never presents the eleven-loop map (links the
workflows dir only); W10 name drift ("Customer Communications" / "Customer comms" / "CUSTOMER
COMMUNICATION") against registry.md:11's "exact names" claim; roles thin outside W1/W2/W7 (owner
only).
Consequence: Slightly weaker one-pass legibility; no authority ambiguity (PRODUCT.md §6 is
definitive).
Recommendation: Add the loop table or an explicit pointer in ARCHITECTURE.md; align the W10 name.

ID: F-14  Sev: LOW  Category: production-doc placement
Evidence: CI/CD and rollback live only in the progress-protocol/weights/roadmap layer, not in
ADR-016 (the designated production-architecture ADR); implementation-roadmap.md's banner still
quotes the retired six-tier readiness vocabulary (a reconciliation note exists and
scripts/progress_status.py aliases correctly).
Consequence: Split-brain risk for production requirements if the weights file is ever restructured.
Recommendation: Add CI/CD + rollback rows to ADR-016 §2; refresh the roadmap banner.

ID: F-15  Sev: LOW  Category: forward guard gap
Evidence: Channel-divergence (one conversation across channels) is guarded at document level only
(test_the_conversational_operations_layer_is_durable); no absent_symbols/tripwire will fire when a
second conversational channel with its own store lands. Defensible now — only Slack exists and the
layer is SPECIFICATION-stage.
Consequence: Nothing mechanically fails at the moment the risk first becomes real (P9/P11).
Recommendation: Add channel-store absence symbols to IMPLEMENTATION-SURFACE.yaml before P9.

ID: F-16  Sev: INFO  Category: terminology
Evidence: The literal term "headless" appears only in superseded pre-reset docs (as the wrong claim
— "Slack = the headless UI"; all such files verified to carry supersession banners). The current
canonical corpus expresses headless-first correctly by construction: the engine is the product,
surfaces own no state (ADR-019 §1), the control plane is "where you check on the teammate, not
where the work lives" (ADR-017 §2), work meets people in their channels.
Consequence: None — concept fully present; noted so the adjudicator doesn't grep for the term and
misread its absence.
Recommendation: Optional: one explicit "headless-first, channel-independent" sentence in
PRODUCT.md §5.

Product verdict — PASS

The repository gives a fresh agent one coherent product definition, redundantly stated and
mechanically defended. Identity: "AI-native operating platform and system of action for small and
medium freight and logistics companies" verbatim in ADR-012 §1 and PRODUCT.md §1, with the unit of
value ("a correctly closed operational loop") and the responsibility model ("remains responsible
until the relevant business outcome is closed"). Misreadings are blocked three ways: PRODUCT.md
§12's explicit NOT-list names every one of the nine misreadings in the review charter (invoice
processing, extraction, AP reconciliation, Slack bot, TMS chatbot, browser automation,
dashboard-first is rejected in ADR-017 §2, chatbot-only in ADR-019/PRODUCT.md, disconnected agents
in ADR-012 §4); CLAUDE.md front-loads "if you infer the product from the code you will build the
wrong product"; and the rejected absolutes are scanned for across a discovered 39-document
current-authority population with a non-empty-population guard. Customer operating reality:
PRODUCT.md §2 makes formal-TMS ownership explicitly not a qualification ("A brokerage running
entirely on Sheets and a shared inbox is a fully-qualified initial customer"); ADR-018:18 names
Sheets, Excel, Gmail, Outlook, Google Drive, SharePoint, SMS, phone, load boards, portals,
accounting systems, documents and tribal knowledge; "the TMS is one possible node, not the center"
is stated in PRODUCT.md §2/§7 and guarded by a dedicated test. Operating model: coherent state
across fragmented systems, obligation ownership with one accountable human, authorized-only work,
evidence/provenance, expectations (the missing-event mechanism), external-outcome verification, and
— explicitly — "a write into one node is never workflow completion" (ADR-018, PRODUCT.md §11.1, and
per-loop false-closure lists such as W8's "invoice created/released/sent ≠ closure"). Delivered
Load Closure is correctly a HYPOTHESIS — NEEDS DESIGN-PARTNER VALIDATION filed under mutable
strategy (ADR-012 §2), never identity. Residual product-level defect: F-01's stale L6→W8 residue in
three canonical workflow files.

Surface and conversational-layer verdict — PASS

Surfaces: ADR-015 gives every channel three simultaneous roles (evidence source, operational
surface, governed effect channel) covering email, SMS, voice, Slack/Teams, portals, EDI/API,
documents; ADR-017 §2 defines the thin web control plane with all 14 required surfaces present
(Work Items, exception queues, approval packets, evidence packets, operational/effect history i.e.
timelines, integration onboarding, users and roles, credential lifecycle, policies and approval
limits, audit search, owner metrics, support diagnostics, tenant lifecycle incl. pilot
administration and offboarding, and the conversational workspace). Slack/Teams are
operator/intervention surfaces that "cannot be the only administration and oversight interface" and
hold no canonical role; no surface owns canonical state, evidence, authority, memory or effect
execution — explicit for the conversational layer ("owns no state of its own", ADR-019 §1) and the
brake ("engageable from the control plane, never dependent on it"), structural for the rest.

Conversational layer: ADR-019 defines all ten required user capabilities (§2, including take-over
and voice), proactive ownership with nine named triggers (§3), the full mandatory response taxonomy
— knows/inferred/completed/verified/failed/unknown/waiting/next/human-required (§4), one identity
across web/Slack/Teams/email/mobile/voice with channel-divergence declared a defect (§7),
does-not-pretend-to-be-human and never-claims-completion-without-verification (§6), and the hard
authority boundary: conversation may create only proposed intent, draft Work Items, structured
constraints, clarification requests and proposed actions, and every consequential instruction
passes the full ADR-003/004 pipeline (§5). Jack & Jill AI is recorded as a non-binding
interaction-quality reference only, honestly framed (not a freight product; its two-persona split
explicitly a contrast, not a model), with "no competitor defines Neyma's canonical identity" — and
a guard asserts each of these framings. Beyond documents, the authority boundary already has
executable negative cases on today's Slack surface (forged signature, single-use approval token,
unauthorized approver, money-lane refusal, no-guessed-amount, no false all-clear when a read
fails). Residuals: F-06 (drift-pattern fragility), F-15 (no forward tripwire for channel
divergence), F-16 (terminology note).

Freight-coverage verdict — PASS WITH SIGNIFICANT FINDINGS (structure complete; cross-reference
unsound)

Exactly eleven loops — count and identity agree across PRODUCT.md §6, workflows/registry.md,
operating-model.md L1–L11 and CANONICAL-DOCUMENTS.md, with "a twelfth loop is a product decision"
stated. Per-loop, all 13 review dimensions are at least partially addressed in every loop — no
empty headings, no verbatim boilerplate, genuinely differentiated triggers, false-closure lists,
degraded modes and owner-outcome metrics ("NOT invoices entered") — and closure semantics are
uniformly business-outcome-based (W8 closes at PAID, W9 at bank-verified SETTLED, W6 at a
correctly-bound COMPLETE packet). The operational-use-case matrix is complete: 33 use cases, all 28
required categories covered (mechanically parsed, denominator 33×16 = 528 cells, zero missing
fields), all 13+ required per-case attributes present, zero fabricated validation claims (24
NEEDS_VALIDATION, 0 validated — consistent with zero recorded design-partner observations), all
readiness tiers honestly SPECIFIED. Delivered Load Closure: hypothesis, correctly bounded. The
significant defects are cross-referential, not structural: F-01 (stale L6→W8 residue), F-02 (CK/MF
named for ~10% of consequential steps against the registry's own contract, plus the self-review
overclaim), F-04 (broken V-namespace), F-09/F-10/F-11 (gate-class gaps and unauditable numbering).
None of these blocks P3 — P3 is loop-independent safety-kernel work — but F-01/F-02/F-04 should be
resolved before P6–P9 consume the workflow layer.

Production-readiness specification verdict — PASS (specification-level), with F-08/F-14

All 23 required production concerns are addressed by name in current authority: PostgreSQL ("the
production transactional store", SQLite "local development and deterministic testing only" — and
the current SQLite runtime is honestly acknowledged as non-production via ADR-016's supersession
header and the universal SPECIFIED posture), migrations, durable workers, timers/scheduling,
transactional outbox and durable inbox, S3-compatible content-addressed object storage, isolated
browser workers, managed secrets, tenant authentication/roles/authorization, communications
workers, the web control plane, staging/production environments, logs/traces/metrics/alerts,
backups + PITR, disaster recovery, incident response, feature flags ("a flag may narrow, never
bypass"), rollback (per-phase rollback tables + rollback exercises in the readiness checklist),
onboarding/offboarding, retention/deletion, and cost-and-model controls (budgets, routing,
fallbacks). Integration model: five-tier preference order with APIs/webhooks/OAuth first and managed
browser automation explicitly ranked as authorized fallback; human-established sessions a
per-tenant fallback, not universal; "authentication does not create action authority" stated
permanently in ADR-014's header and echoed in ADR-013/PRODUCT.md; authority migration only via
ADR-013's 13-field record (customer authorization "recorded — never inferred", rollback plan
mandatory, "a migration missing any field is not authorized") over ADR-018's eight-level reversible
ladder. Defects: RB-15/RB-13 miscite ADR-016 for CI/CD/queues (F-08), and CI/CD + rollback live
outside the designated production ADR (F-14). This is a specification verdict: production readiness
percent is 0.0 and the repository says so itself.

Safety/control verdict — PASS

All twelve required invariants are stated as never-weaken rules (ARCHITECTURE.md "The rules that
may never be weakened" 1–11 plus the UNKNOWN_OUTCOME never-auto-resolves rule at §. lines 224-228,
mirrored in CLAUDE.md rules 1–20): events are facts only; replay cannot mint authority or call
adapters; MODEL_INFERRED cannot independently authorize; OWNER_ASSERTED cannot be silently
overwritten; timeout ≠ FAILED; UNKNOWN_OUTCOME requires verification and never auto-resolves; every
unresolved obligation has one accountable human; the Brake controls admission; one canonical effect
authority; no permanent second orchestration or effect-authority system. The guard audit found 10
of 11 mandated guard categories substantively enforced (discovered populations, require_population
non-vacuous checks, exact-set memberships, an in-suite forgery battery, AST-level meta-guard against
hand-enumerated populations) — the status/progress stack being the strongest: node-identity
manifest comparison (same-count substitution fails), finalizer that executes the suite itself,
machine-visible skips instead of silent passes. P3 content is mechanically absent: no
CheckpointWitness, seven-step checkpoint or claim CAS symbol exists in src/ (79 files swept; the
only hits are forward-looking comments), pinned as absent_symbols in IMPLEMENTATION-SURFACE.yaml and
enforced by a live whole-token test-of-absence. R-07 is recorded OPEN — NOT CONTAINED with its exact
surface (6 production-reachable live-write paths EP-1/3/6/7/9/10, 31 adapter-import edges), and the
inventory matches. Residual weaknesses are the guard-porosity findings F-03/F-05/F-06/F-07 — real,
adjudicable, none currently exploited: today's content is honest everywhere the porous guards would
have allowed dishonesty.

Implementation-handoff verdict — PASS

P3–P14 form a coherent, dependency-ordered program (safety wall P3–P5 explicitly loop-independent so
missing customer evidence blocks nothing there; canonical model P6–P9; shadow-first value P10–P11;
supervised effects and earned autonomy P12–P14). Exactly one unit is READY (U-REBASELINE-1) —
enforced by list-identity equality in three independent modules; P3 is BLOCKED and unimplemented;
RB-01..23 PASS with named artifacts, RB-24 PENDING and structurally impossible for the executing
session to self-award. Progress is evidence-based and deflationary: overall program 0.0%,
user-visible maturity 0.0%, production readiness 0.0%, tier SPECIFIED, CLI-switch readiness 30.0% —
finalizer-derived, with a rejection battery against hand-inflation. Customer validation requirements
are explicit (V-01…V-21 with fail-closed interim behavior; zero invented design-partner observations
anywhere, including the coverage matrix). The repository successfully guided this zero-memory
session from cold start: the reading order works, the status authority is unambiguous, the
environment fails fast on a bad interpreter, and the suite reproduces from a clean clone. The
stale-doc perimeter holds — every pre-reset root doc checked carries a supersession banner.

Tests and commands run

git rev-parse HEAD / HEAD^{tree} / git status (start and end)
  → target match; clean; detached at fb5fcd9
scripts/check_env.py on host Python 3.10
  → correctly REJECTED (floor enforced)
Bootstrap per convention (3.13 venv, check_env ×2, pip install -e ".[dev]")
  → OK
Full canonical suite (.venv/bin/python -m pytest eval/ -q, this checkout)
  → 1268 passed, 0 failed, 1 skipped in 391s — exactly matches CURRENT.md's recorded block
Canonical collection vs TEST-NODE-MANIFEST.json
  → 1269 collected = 1269 manifest node ids
Clean-clone gate (scripts/clean_clone_gate.py, run from a scratch clone at the exact target commit)
  → CLEAN-CLONE GATE: PASS — fresh clone, fresh venv, declared-deps-only; clean-clone counts
    {passed: 1268, failed: 0, skipped: 1, collected: 1269}; control guards PASS; AC-SAFE-012/013 +
    AC-SEC-001 PASS
Coverage-matrix guard executed directly + 8 in-memory mutation trials
  → guard PASSES on real tree; 5 mutations caught, 3 missed (→ F-03, F-05)
Guard-inventory sweep
  → 12 control-guard modules / 239 guard tests / 110 test files; 39-doc discovered authority
    population
Two-commit convention
  → verified via git log / git diff --name-only 98e531f fb5fcd9
Targeted greps
  → P3-symbol absence in src/; Jack & Jill scope; supersession banners; ADR-016 CI/CD absence;
    V-namespace collisions; headless-term scan

Finalizer note: scripts/finalize_status.py was not executed against the review tree — it writes
status files by design and this review is read-only. Its outputs were instead independently
reproduced: the suite it records was re-run (counts match exactly) and its clean-clone gate was
re-executed from a scratch clone (PASS).

Review limitations

No design-partner or market validation was performed or possible — this review verifies internal
coherence, honesty and guard integrity, not freight-domain truth. All NEEDS VALIDATION items remain
exactly that.

The clean-clone gate's driver first crashed on import yaml when I invoked it with the bare system
interpreter (my invocation error, not a repo defect — the documented invocation is via the project
venv); the documented invocation then passed end-to-end. Minor observation: the gate driver assumes
its own interpreter has the repo's deps; a self-check would make the failure mode cleaner.

Guard mutation trials were in-memory against the real guard functions (repository tree never
mutated, per the read-only constraint); on-disk mutation with pycache purging per CLAUDE.md §9 was
therefore not exercised.

Four subagents performed the enumeration sweeps; every HIGH finding and every load-bearing claim
used in a verdict was independently re-verified by me against file and line, but LOW/INFO items rest
partly on agent citations.

One environment artifact: full-suite collection requires PyMuPDF; one agent's sandbox lacked it and
executed the guard function directly instead — the main checkout and the clean clone collected and
ran all 1269 nodes normally.

Voice, Teams, mobile and the web control plane are specification-stage; their conversational-layer
claims could only be reviewed as specifications plus the existing Slack-surface tests.

Exact final recommendation

The repository at fb5fcd93 gives a fresh implementation agent one coherent, honest, guard-defended
definition of Neyma as the AI-native operating platform and system of action for SMB freight — with
the safety spine intact, exactly one READY unit, P3 provably unimplemented, R-07 honestly OPEN,
progress honestly at zero, and full clean-clone reproducibility. The review completed on the exact
target with no repository modification. Zero CRITICAL findings; four HIGH findings (F-01 stale
L6→W8 residue in canonical workflow files; F-02 CK/MF step-contract shortfall plus its false-green
self-review row; F-03 mutation-proven coverage-guard porosity; F-04 broken validation-reference
namespace) and seven MEDIUM findings are documentation- and guard-level, individually adjudicable,
and none requires runtime implementation to resolve. Recommended adjudication posture: F-01/F-02/
F-04/F-08 resolve before RB-24 is declared PASS (they are fresh-reviewer-legibility defects, which
is what RB-24 certifies); F-03/F-05/F-06/F-07 resolve as guard hardening in the same control-only
scope; the LOW set may be accepted as recorded debt. Nothing found here blocks P3's content — the
blockers are legibility and guard integrity, all fixable inside U-REBASELINE-1's documentation/
control-only mandate.

INDEPENDENT REVIEW COMPLETE — READY FOR ADJUDICATION
```

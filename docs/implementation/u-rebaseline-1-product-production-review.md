> # ⛔ HISTORICAL REVIEW — NOT CURRENT AUTHORITY
> **This document is evidence of a past moment, accurate as of its own commit and possibly stale
> since.** It must not direct current implementation. Current status:
> [`CURRENT.md`](CURRENT.md) · authority map: [`../CANONICAL-DOCUMENTS.md`](../CANONICAL-DOCUMENTS.md)
> · operating guide: [`../../CLAUDE.md`](../../CLAUDE.md).

# U-REBASELINE-1 — Product, Integration and Production Rebaseline — Review

**Unit:** U-REBASELINE-1 · **Date:** 2026-07-20 · **Authority:** an explicit founder product
decision. **Scope:** documentation, architecture, specification and control ONLY — no runtime
product behavior implemented.

---

## 1. Starting HEAD and tree

Verified before any modification: HEAD `fe7843d…` → the U-HANDOFF-1D content commit
`0a25a001b522047858c95bed461046046fafe7a0` (content tree
`a736937997a1eb52d3c1842263786822fa6955b4`), plus its status-metadata commit `43a0c4a`. Working
tree clean. U-REBASELINE-1 was the single READY unit; its dependency (U-HANDOFF-1) was COMPLETE.

## 2. Founder decision

Neyma is a serious, top-tier **AI-native operating platform** for small and medium freight and
logistics companies. Freight brokerages are the initial ICP, **not the permanent limit** of the
company. Several early assumptions were found to impose artificial ceilings; the founder directed
that they be corrected before P3. No competitor defines Neyma's identity.

## 3. Rejected product constraints

Retired as permanent absolutes (ADR-012 §4): "the brokerage never rips out its TMS"; "Neyma never
becomes a system of record"; "anyone wanting TMS replacement is the wrong customer"; "the human
must establish every session"; "Neyma must remain permanently outside native freight workflows";
and the implicit "the first wedge is the permanent identity", "SQLite is the production database",
"email/SMS are optional", "Slack is the only control interface", "code exists = production ready",
"access = action authority", and (ADR-018) "the TMS is the center of the product / the domain
model is shaped by a TMS schema". Each is now guarded against reintroduction
([`test_rebaseline_invariants.py`](../../eval/tests/test_rebaseline_invariants.py)).

## 4. Final stable product identity

> **Neyma is the AI-native operating platform and system of action for small and medium freight
> and logistics companies** (ADR-012 §1; PRODUCT.md §1, verbatim). It connects to the systems the
> company already uses, maintains coherent operational state, owns open obligations, coordinates
> authorized execution, and remains responsible until the business outcome is closed. The unit of
> value is a correctly closed operational loop.

Stable identity vs mutable strategy is made explicit (ADR-012 §2): the wedge, ICP, integration
mix and loop sequencing are strategy the founder may revise on evidence without changing identity.

## 5. Initial ICP and broader direction

**Initial ICP:** small/medium US truckload freight brokerages — fragmented systems, shared inboxes,
no in-house engineering (PRODUCT.md §2). **Broader direction:** small/medium freight and logistics
operators where evidence supports expansion. The broader direction never widens the initial
implementation scope by itself (ADR-012 §3).

## 6. TMS and workflow-authority position

ADR-013: integrate-first **and** migration-capable, simultaneously. Initial adoption requires no
TMS replacement; the TMS may remain the system of record; Neyma **may** become authoritative for
individual workflows, the primary interface, and eventually the primary platform — **workflow by
workflow, under a recorded, customer-authorized, reversible migration** (the thirteen-field model,
ADR-013 §2). Implementation obligation: P13.

**Addendum — the customer operational graph (ADR-018).** The TMS is one node in the customer's
operational graph, **not the center of the product**. For some customers there is a real TMS; for
others the functional equivalent is distributed across Sheets, inboxes, portals, SMS, phones and
paper. The canonical domain model and workflow engine are **TMS-schema-independent**; each tenant
has a per-tenant **Operational System Map** (15 fields: which node controls which capability, how
it is read/written/reconciled, its authority and migration status —
[`spec`](../specifications/operational-system-map.md)); the **same workflow runs regardless of the
source system**; **a write into one node is never workflow completion** (completion is the real
outcome); and an **eight-level maturity ladder** (observe → normalize → coordinate → execute → own
→ primary interface → authoritative → replace) lets a customer advance at their own pace. Neyma
never requires replacing existing tooling before delivering value, and fragmentation never lowers
auditability, ownership, tenant safety, authorization or closure. Implementation: domain model
TMS-agnostic at P9; the Operational System Map from onboarding discovery at P11.

## 7. Credential and integration model

ADR-014: Neyma **may securely possess customer-authorized authentication material**; the permanent
rule is **minimize raw personal-credential handling, prefer dedicated scoped machine identities**.
Permitted models: OAuth, API keys, service accounts, bot users, EDI, database connections, mailbox
grants, SMS/comms credentials, managed and human-established browser sessions, webhooks, file
transfer. Preferred order APIs → service accounts → EDI/DB → managed browser → human-established.
Governance: authorization, tenant isolation, least privilege, encryption, audit, revocation,
rotation, expiry, purpose limitation, environment separation, incident response, offboarding
destruction. **Permanent boundary preserved: authentication does not create action authority.**

## 8. Communications architecture

ADR-015: email/SMS/voice/portals/EDI are a **core operational subsystem** — evidence source,
operational surface, and governed external effect. A message is an external effect with recipient
identity, tenant, purpose, authority, evidence, content digest, delivery state, expected response,
verification and escalation. Email and SMS are **required** production capabilities for the first
commercial workflow. Ingestion lands at P9; supervised sends at P12.

## 9. Delivered Load Closure hypothesis

The founder-selected wedge (PRODUCT.md §15) replaces the narrow "W6 → W8" framing. It owns a
delivered/near-delivered load to closure across parts of W5/W6/W7/W8/W10. **It is a `HYPOTHESIS`
needing design-partner validation; it is not invoice processing; it is not labeled validated.**
Thirteen measurable wedge outcomes are defined and will be instrumented, not asserted.

## 10. Required design-partner evidence

[`DESIGN-PARTNER-EVIDENCE-PROGRAM.md`](../product/DESIGN-PARTNER-EVIDENCE-PROGRAM.md): E-01..E-22
(TMS, integration method, mailbox/SMS/phone, accounting, samples, volumes, arrival channels,
approval roles/limits, accessorial authorization, exception taxonomy, order/load relationships,
billing, factoring, baseline metrics, human touches, retention/security, ranked pain, willingness
to pay, pilot criteria, expansion intent). Runs **alongside** engineering; **never a second READY
coding unit**; fail-closed; no invented rules; the hypothesis stays unvalidated until the founder
records evidence.

## 11. Production architecture

ADR-016: a **modular monolith on managed infrastructure** — no Kubernetes/microservice sprawl for
appearance. **PostgreSQL is the production transactional store**; SQLite is dev/test only. Includes
the public API/webhook service, control plane, outbox/inbox, durable timers/scheduler, background +
communications + **isolated** browser workers, S3-compatible content-addressed evidence, managed
secrets, tenant auth/identity/roles, environment separation, backups + PITR, disaster recovery,
observability, rate limits, dead-letter/quarantine, idempotency/unknown-outcome, cost controls.

## 12. Web control plane

ADR-017: a **thin** web control plane governs Work Items, exceptions, approvals, effect history,
unknown outcomes, tenant config, users/roles, integration onboarding/health, credential lifecycle,
policy/limits, brake status, audit search, metrics, pilot administration, onboarding/offboarding.
**Not dashboard-first** — the work meets people in their channels; the control plane is where you
supervise and govern it. The brake is engageable from it but never dependent on it.

## 13. Revised P3–P14 program

The P0–P14 identifiers and safety sequencing are **preserved**; outputs were revised so the program
produces a **deployable product**. Changed phases (registry `rebaseline_contract` blocks +
[`implementation-roadmap.md`](implementation-roadmap.md) + [`PHASE-OUTPUTS.md`](PHASE-OUTPUTS.md)):
P5 gains PostgreSQL production persistence; P9 gains communications ingestion; P10 becomes the
Delivered Load Closure shadow slice; P11 gains deployment + onboarding + the web control plane; P12
gains supervised communications; P13 gains the ADR-013 authority-migration model. P3 remains the
next safety unit; P4 still closes R-07. Each revised phase specifies user-visible/platform
capability, outputs, scope, evidence, hostile/concurrency/mutation requirements, rollout/rollback,
observability, security, completion evidence and readiness target.

## 14. Production-readiness definitions

ADR-016 §3: `SPECIFICATION_ONLY → LOCALLY_IMPLEMENTED → STAGING_READY → PILOT_READY →
SUPERVISED_PRODUCTION_READY → GENERALLY_PRODUCTION_READY`. **"Code exists" means
`LOCALLY_IMPLEMENTED`, never production ready** — guarded. Each rebaselined phase carries a
`readiness_target`.

## 15. Canonical files changed

PRODUCT.md, ARCHITECTURE.md, CLAUDE.md, README.md, AGENTS.md; docs/CANONICAL-DOCUMENTS.md;
docs/product/operating-model.md (in-place supersessions), OPEN-VALIDATION-ITEMS.md (V-W1);
docs/architecture/target-system-specification.md; docs/specifications/adapters/{registry,02-tms,
10-browser}.md; docs/implementation/{IMPLEMENTATION-REGISTRY.yaml, implementation-roadmap.md,
PHASE-OUTPUTS.md, IMPLEMENTATION-SURFACE.yaml, CURRENT.md, registry.md,
U-REBASELINE-1-ACCEPTANCE.yaml}.

## 16. ADRs / specifications added

ADR-012 (identity/strategy), ADR-013 (workflow-authority migration), ADR-014 (credential/machine
identity), ADR-015 (communications), ADR-016 (production topology), ADR-017 (tenant/integration
lifecycle + control plane), **ADR-018 (customer operational graph / TMS-agnostic domain model)**;
DESIGN-PARTNER-EVIDENCE-PROGRAM.md; **docs/specifications/operational-system-map.md** (the
per-tenant Operational System Map, 15 fields).

## 17. Historical claims disarmed

In-place supersession annotations (⚠️): operating-model.md §2.4/§7.2/§7.5;
target-system-specification.md non-goals; adapters registry.md / 02-tms.md / 10-browser.md auth
rows; OPEN-VALIDATION V-W1. Each retains the old text behind an immediate disarming marker naming
the superseding ADR — evidence preserved, authority corrected.

## 18. Tests and guards added

[`eval/tests/test_rebaseline_invariants.py`](../../eval/tests/test_rebaseline_invariants.py) —
13 guards: no rejected absolute is a live current-authority claim (dynamic discovery of the
current-authority population); the canonical identity is present and exact; the six ADRs exist and
are FINAL; credentials permitted but authentication is not authority; Delivered Load Closure is an
unvalidated hypothesis; the evidence program exists and fails closed; exactly one READY unit
(U-REBASELINE-1); R-07 stays OPEN — NOT CONTAINED; the readiness vocabulary is defined; SQLite is
not the production DB; communications are core; every rebaselined phase has a rebaseline_contract;
no src/ runtime file was touched. Existing guards updated: the identity guards (test_6, test_6b),
the READY/checklist guards, REQUIRED_CONCEPTS, GUARD_REGISTRY.

## 19. Mutation results

Registration and invariant mutations were proven with the safe in-memory harness (mutate → confirm
the mutant genuinely misbehaves → confirm the guard fails non-zero → restore byte-identically,
bytecode purged; git never used to undo). Battery results: **12/12 (core rebaseline) + 6/6
(ADR-018 operational graph) = 18/18 CAUGHT.**

The ADR-018 battery: M-1 ADR-018 loses "one node, not the center"; M-2 the domain model made
TMS-schema-dependent; M-3 write treated as workflow completion; M-4 a maturity-ladder level
dropped; M-5 the Operational System Map spec drops a required field; M-6 "the TMS is the universal
center of the product" reintroduced as a live PRODUCT.md claim (caught by the rejected-absolute
scan, which is scoped to the product-architecture assertion and does **not** fire on the true
industry-pattern observation in freight-discovery).

| # | Mutation | Guard that caught it |
|---|---|---|
| M-1 | A rejected absolute ("Neyma never becomes authoritative for native workflows") inserted as a live PRODUCT.md principle | rejected-absolute scan (dynamic current-authority discovery, tight disarm window) |
| M-2 | "Access equals action authority" inserted live | same |
| M-3 | The canonical identity stripped from PRODUCT.md | identity-present-and-exact |
| M-4 | ADR-014 loses "never independently authorizes an external effect" | credentials-permitted-but-not-authority |
| M-5 | Delivered Load Closure fully promoted to validated (all hypothesis markers removed) | hypothesis-not-validated |
| M-6 | ADR-016 names SQLite as the production store | sqlite-is-not-the-production-database |
| M-7 | A P10 `rebaseline_contract` field (readiness_target) removed | every-rebaselined-phase-has-a-contract |
| M-8 | P3 flipped to READY (second READY unit) | exactly-one-ready-unit |
| M-9 | The evidence program claims READY-coding-unit status | evidence-program-fails-closed |
| M-10 | An RB criterion drifts back to PENDING | rebaseline-checklist-executed |
| M-11 | RB-24 self-passed by the executing session | rebaseline-checklist-executed |
| M-12 | Same-count RB substitution (RB-12 → RB-77) | rebaseline-checklist-executed (exact-set) |

Two of the twelve first reported MISSED — both were unfaithful mutations (the docs carry the
guarded phrase across a line break / with defense-in-depth), and one (M-1/M-2) exposed a genuine
guard weakness: the disarm window was 300 chars wide, wide enough that a reintroduced absolute
could hide near an unrelated "reject"/"ADR-012" mention. The guard was tightened to a
same-line-plus-one window before the battery was accepted.

## 20. Full suite result

1246 passed · 0 failed · 1 skipped (executed LAST, on the final tree, by
[`scripts/finalize_status.py`](../../scripts/finalize_status.py)).

## 21. Clean-clone result

CLEAN-CLONE GATE: PASS — a fresh clone reproduced the suite, control guards and AC gates
(`GATE-RESULT.json`, bound to the content commit below).

## 22. Finalizer result

The canonical finalizer executed the complete suite, the clean-clone gate, the control guards and
AC-SAFE-012/013 + AC-SEC-001 itself, and recorded only what it observed.

## 23. Content commit

fbbeff978fe8fe52f5075050da3f9c36b4a68e7b (tree e48aa048dff8aa7b522e18e07d86612161d3b782).

## 24. Metadata commit

The single status-metadata commit on top (two-commit convention; touches only the status files).

## 25. Final HEAD and tree

HEAD = the status-metadata commit; content baseline recorded in
[`CURRENT.md`](CURRENT.md)'s machine-maintained block.

## 26. Working-tree cleanliness

Clean at finalization; validation ran LAST with no post-validation tree changes.

## 27. Confirmation: src/ runtime behavior untouched

The unit diff touches `docs/`, `eval/tests/` and `scripts/finalize_status.py` (the review/metadata
file lists) only. **No file under `src/` changed** — guarded by
`test_no_src_runtime_file_was_touched_by_the_rebaseline`.

## 28. Confirmation: P3 remains unimplemented

P3 is BLOCKED with dependencies `[P2, U-HANDOFF-1, U-REBASELINE-1]`. No checkpoint, witness or
claim-CAS symbol exists in `src/`.

## 29. Confirmation: R-07 remains OPEN — NOT CONTAINED

Unchanged. The six live-write paths, the adapter edges and the KB `tenant="default"` sites all
stand as recorded in [`CURRENT.md`](CURRENT.md). R-07 closes only at P4.

## 30. Whether an independent product-and-production review may begin

Yes. The rebaseline content is written, internally consistent, guarded and finalized; RB-01..RB-23
PASS with produced-artifact evidence; **RB-24 (fresh-reviewer legibility) is deliberately left
PENDING** for exactly that review. U-REBASELINE-1 is **not COMPLETE** — completion belongs to the
independent review and the founder.

---

## Verdict

**READY FOR INDEPENDENT PRODUCT/PRODUCTION REBASELINE REVIEW**

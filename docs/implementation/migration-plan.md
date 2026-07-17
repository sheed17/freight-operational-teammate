# Migration Plan — Safety Task #1, the Ledger, the Checkpoint, Adapter Containment

## PART 1 — ⛔ MIGRATION SAFETY TASK #1 *(Phase 1 — the FIRST implementation change)*

### The defect *(confirmed at code + schema level, recon §4)*
**(A)** `operation_router.py:335` `_commit_identity(...)` returns `approved_amount` in the identity; `workflow.py` `operation_commit_key(tenant, lane, load_ref, party, approved_amount)` **hashes it into the key**. ⇒ two proposals at £2,850 and £3,100 for load 4471 ⇒ **different keys ⇒ both commit ⇒ the customer is billed twice.**
**(B)** `if not amount: return None` ⇒ **non-money effects get NO commit identity at all** (a POD can be filed twice).
**(C)** *(new)* `operation_commit_claims.commit_key TEXT PRIMARY KEY` — **not tenant-first.**

### Target rule
### **Commit Key identifies ONE logical external effect** = `SHA256(ck_v1 | tenant | action_class | target_system | target_resource_id | target_operation | occurrence_key)`. ### **Mutable decision content (the amount) belongs in the Material-Facts Fingerprint. EVERY consequential effect — including non-money — has a Commit Key. The shared ledger enforces commit-once per (tenant, logical effect).**

### Affected artifacts *(exact)*
| Kind | Artifact |
|---|---|
| **Producer** | `src/freight_recon/operation_router.py:335` `_commit_identity` (the sole producer) |
| **Consumers (11)** | `operation_router.py:147,167,222,228,230,232,243,287,290,297,300,301,310,311` |
| **Key derivation** | `src/freight_recon/workflow.py` `operation_commit_key(...)` (:543, :582) |
| **Store API** | `workflow.py` `claim_operation_commit` (:567) · `operation_commit_claim` (:534) · `update_operation_commit_payload` (:631) · `release_operation_commit` (:655) |
| **DB fields** | `operation_commit_claims`: `commit_key` (PK), `tenant`, `lane`, `load_ref`, `party`, ### **`approved_amount`** |
| **Test** | `eval/tests/test_lane_graduation.py:206` (asserts the *current* missing-identity behavior — ### **it encodes the defect and must be inverted**) |

### Strategy
- **Historical rows affected:** every `operation_commit_claims` row (they carry an amount-bearing key). ### **Backfill: recompute a `ck_v1` key per row from (tenant, action_class←lane, target, occurrence_key); write it to a NEW column; DO NOT delete the old key** (principle 8: history stays attributable).
- ### **Collision analysis (the real risk):** two historical rows for the same load+party at **different amounts** collapse to **one** new key. ⇒ ### **a collision is EVIDENCE OF A HISTORICAL DOUBLE-COMMIT.** **Do not merge them silently. Do not pick one.** Emit a `MANUAL_REVIEW_REQUIRED` record with both rows and an accountable owner. **The migration surfaces the defect's victims; it does not bury them.**
- **Duplicate detection:** a dry-run pass reports (a) rows collapsing to one key, (b) rows with no derivable occurrence_key, (c) non-money effects that had no identity and therefore **cannot be proven single-committed** ⇒ `MANUAL_REVIEW_REQUIRED`.
- **Compatibility:** dual-**read** during P1 (old key OR new key ⇒ claim exists ⇒ **fail closed on either**). ### **NEVER dual-write to two namespaces (principle 2).** The old column is deleted only when P4 completes.
- **Preventing recommitment:** ### **before the new key is live, every historical claimed effect is projected into the new namespace, so a post-migration attempt at an already-committed effect finds a claimed row and refuses.** A row that cannot be projected (ambiguous) blocks that logical effect pending review — **fail closed.**
- **Rollback:** the new column is additive; rollback stops using it. ### **Rollback may NOT re-enable amount-in-key** (principle 11) — it disables the capability instead.
- **Metrics:** rows migrated · collisions found · un-derivable rows · manual-review queue depth · post-migration claim refusals.
- ### **Acceptance:** `AC-SAFE-012` (two amounts ⇒ one key ⇒ one invoice) and `AC-SAFE-013` (same POD twice ⇒ one attachment) ### **turn GREEN. `test_lane_graduation.py:206` inverts.** New negative controls: a key containing an amount ⇒ **build fails**; a consequential effect with no key ⇒ **rejected at PROPOSED**.
> ### **AC-SAFE-012 and AC-SAFE-013 MUST be green before ANY broader write-path migration begins.**

## PART 2 — EFFECT LEDGER *(Phase 2)*
**Target:** ONE row · ONE Commit Key namespace · **8 states** (`GRANTED CLAIMED ATTEMPTED VERIFIED FAILED EXPIRED_UNCLAIMED REVOKED UNKNOWN_OUTCOME`) · ### **`REVOKED` distinct from `EXPIRED_UNCLAIMED`** · `CLAIMED` the atomic claim point · witness binding · tenant-scoped uniqueness · ### **Layer-1 reservation held through unresolved verification** · `UNKNOWN_OUTCOME` owned · ### **NO duplicate ledger for legacy compatibility.**
**Current relationship:** `operation_commit_claims` is the **ancestor** (claim-once, payload, release). It **becomes** the ledger — it is not shadowed by a second table.
**Transition:** add tenant-first key + the state column + witness/policy/brake/fingerprint columns → backfill historical rows to a canonical state (§data plan) → create the two partial indexes **after** backfill (index-creation order: **backfill first, then index, so a historical duplicate fails LOUDLY at index creation rather than silently at runtime**) → enable the claim CAS.
**Dual-read:** permitted during P1–P2 only, **read-only**. ### **Independent dual writes: PROHIBITED.** **Isolation:** the CAS requires read-committed + the unique index as the arbiter. **Locking:** the CAS is a single-row conditional update — no long locks, none across human time.
**Rollback:** stop claiming via the CAS ⇒ the capability is disabled (writes stop). ### **Never revert to the old amount-keyed claim.**
**Monitoring:** claim conflicts · index-violation counts · unresolved-effect count · backfill progress.

## PART 3 — CHECKPOINT + WITNESS *(Phase 3)*
**Owning module:** a new `safety_kernel/` package. ### **Public:** `run_checkpoint(...) -> CheckpointPassed | CheckpointFailed`. ### **Private:** the `CheckpointPassed` constructor — **no public constructor; it cannot be built outside the module** (a language-level posture: a private-by-convention module + a CI check that no other module names the type's constructor).
**Witness:** immutable row; binds all 20 fields (§19.3). ### **Entity-version dependency calculation = the SD-3 rule: every entity referenced by a material fact, ∪ the target resource, ∪ gate-precondition entities — computed by the kernel, NEVER passed in by the caller** (a caller-supplied set is the L-loophole).
**Transaction boundary:** ### **ONE txn = the 7 reads + the witness insert + the grant mint + the pipeline transition. NO async work before the claim CAS** (a lint/instrumentation check).
**Reads:** step 3 uses the **consequential-freshness adapter interface** (constructor cannot accept a cache). Step 6 the policy evaluator. Step 7 the brake row.
**Crash points / races / audit / events / acceptance:** the 105-case `AC-CKPT` matrix.
**Sequencing:** kernel first (P3), then adapters behind it (P4). ### **Never the reverse: an adapter contained before a checkpoint exists has nothing to be contained by.**

## PART 4 — ADAPTER CONTAINMENT *(Phase 4)*
**The work-list is exact — the 13 import sites (recon §7).**
| Site | Target |
|---|---|
| `truckingoffice_write.py` · `multistep_write.py` · `discovered_write.py` | become **adapter internals** (module-private) behind the A4/A15 contract |
| `brain_runtime.py` | becomes a **pipeline client** (proposes; never actuates) |
| `run_action_callback_server` · `propose_ar_from_tms` · `run_operate_request` | **CONVERT_TO_PIPELINE_CLIENT** |
| `enter_truckingoffice_invoice` · `enter_invoice_discovered` | **CONVERT_TO_PIPELINE_CLIENT or REMOVE** |
| `run_operator_agent` | ### **TEST_ONLY or REMOVE** (the least-gated live path) |
| `enter_tms_payable` · `run_dogfood_pilot` | **TEST_ONLY** (mock ledgers) |
| ### `orient_tms` | ### **MAKE_READ_ONLY — structurally** (it currently imports the actuator; the import is removed, not documented away) |
**Enforcement:** module ownership + package visibility + dependency inversion + ### **the CI import-graph gate (unskippable, no exemption list)** + runtime orphan detection ⇒ Sev-0 ⇒ auto-brake + tenant capability binding + witness/grant validation + replay isolation + migration-script isolation + admin isolation + test-only posture.
> ### **A wrapper that merely logs the bypass does NOT count as containment. The acceptance oracle for P4 is: the 13 sites are gone, and the CI gate is ON and unskippable.**

---

## PART 5 — SEMANTIC CODE MIGRATION *(names follow behavior)*
> ### **RULE: DO NOT MASS-RENAME BEFORE THE SEMANTIC BEHAVIOR EXISTS.** A rename performed first produces the worst artifact available: ### **code that reads canonical and behaves legacy** — which defeats every reviewer, including a future me. ### **Each rename is the LAST commit of the phase that made the name true, never the first.**

| Current symbol | Sites (recon §8) | Why it is wrong | Target concept | ### Renamed at | ### Precondition (the name becomes TRUE when…) |
|---|---|---|---|---|---|
| ### **`commit_identity`** | ### **16 / 2 files** | ### **amount-bearing + optional** | Commit Key | ### **P1** | ### **the amount is out and it is mandatory — the ONLY rename in P1, because P1 is exactly the phase that makes it true** |
| `operation_commit_claims` | schema + refs | not tenant-first; claim-shaped | `effect_grants` | ### **P2** | the table is tenant-first and carries the 8 states |
| `operation_action_claims` | 2 / 1 | conflates approval-consume with effect-claim | approval consumption | P3 | the grant claim exists separately |
| ### **`workflow_runs`** | ### **22 / 8** | ### **one row conflates the obligation and the attempt** | ### **Work Item + Pipeline Instance** | ### **P6** | ### **the SPLIT exists — renaming before it would name one row after two things** |
| ### **`lane`** | ### **310 / many** | ### **overloads action class, workflow, and policy scope** | `action_class` ∪ `workflow_id` ∪ policy scope | ### **P8** | ### **typed policy exists, so each of the 3 meanings has a real home. This is the single largest mechanical change in the plan and it is deliberately LAST — a 310-site rename into concepts that do not yet exist would be a guess repeated 310 times.** |
| `CommandIntent` | 92 / 16 | ADR-002 A1 removed `Command` | Proposal / Effect Request | P8 | the pipeline's request type exists |
| `MockTmsWriteLedger` | 27 / 10 | test double in the source tree | contract simulator (spec-derived) | P3 | the simulator lives with the spec (G3) |
| `done` | widespread | ### **"the machine advanced" masquerading as "the obligation is met"** | `VERIFIED` / `CLOSED` / `UNKNOWN_OUTCOME` | ### **P6** | the verification taxonomy decides it |
| `claim` (verb) | 11 | overloaded: reserve, consume, assert | reserve / consume / Claim (the noun) | P7 | Claims (provenance) exist as a type |

**Each rename ships as a mechanical, behavior-free commit** (rename only — no logic in the same commit), so review can be a diff-shape check rather than a re-audit.

---

## PART 6 — THE FIRST VERTICAL SLICE *(Phase 10)*
> # ### **NEEDS DESIGN-PARTNER VALIDATION**
> ### **W6→W8 (Documentation → Billing) is the frozen FIRST-LOOP HYPOTHESIS, not a decided wedge.** It is planned here because a plan must name a first slice; ### **it must be validated against the design partner's real pain before P10 begins.**

**Why this slice, structurally:** it is the narrowest path that still exercises **the whole spine end-to-end** — inbound evidence → extraction as Claims → deterministic binding → Expectation (the non-event) → packet completeness → eligibility → an approval → the 7-step checkpoint → a grant → one verified external write → cash. ### **A slice that skips the checkpoint proves nothing about the architecture; a slice that skips cash proves nothing about the business (P24).**

**Scope IN:** A1/A11 intake · classification + extraction (`MODEL_EXTRACTED`, claims-only) · deterministic identity binding (`AMBIGUOUS` ⇒ human) · customer packet Rules · missing-doc Expectations · Conflict handling · packet completion · POD-gated billing eligibility · invoice preparation · ### **supervised release (`HUMAN_APPROVAL_REQUIRED`)** · verified delivery readback · AR Work Item · the degraded human-execution path · audit reconstruction.
**Scope OUT:** ### **autonomous payment · uncontrolled TMS writes · any money-out · autonomous quoting · autonomous carrier booking.**
**Proves:** the full kernel under one real obligation, at G8, with one action class.
**Acceptance:** `AC-WF6-*`, `AC-WF8-*`, `AC-FC-005..009`, `AC-DEG-W6-*`, + ### **`AC-SAFE-001..028` re-run LIVE.**

### ⛔ What changes if the design partner REJECTS the wedge
| Rejected because | The wedge moves to | ### What changes in this plan |
|---|---|---|
| pain is collections/disputes, not billing | the **AR-collection half of L8** | ### **P10 only** |
| billing already automated by their TMS | **L9 settlement** | ### **P10 only** |
| acute pain is coverage/claims | **L2** or **L11** | ### **P10 only** |
| acute pain is carrier fraud/qualification | **L3** (+ FMCSA A8) | ### **P10 only** |
> ### **In EVERY case: Phases 0–9 are UNCHANGED, and Phases 11–14 change only in which loop they carry.** The safety kernel, the ledger, the checkpoint, containment, events, entities, and policy are ### **loop-agnostic by construction — that is the entire reason they were specified before the wedge was chosen.** ### **The wedge decision can therefore be deferred until P9 completes without stalling a single unit of work — and it MUST NOT be used as a reason to delay the kernel.**

---

## PART 7 — ⛔ THE SEVEN NON-TENANT-FIRST TABLES *(U2.1's exact scope — Errata 2026-07-16)*

> ### **ERRATA:** the plan previously said **"6 of 8"** in seven places, and U2.1 was scoped to *"the 6 offending tables."* ### **Exactly ONE table (`autonomous_run_counters`) is tenant-first. SEVEN are not.** Executed literally, Phase 2 would have migrated six, left one behind, and left `AC-SEC-001` red with the phase marked done. ### **A miscount that hides a table from its own migration is not a typo.**
> ### **U2.1 is scoped by EXACT SET, enumerated below — never by count. It is NOT complete while any of the seven remains non-tenant-first.** ### **No schema is changed by this errata pass; this is scope, not migration.**

### The canonical rule
> ### **A tenant COLUMN is not tenant isolation.** `operation_commit_claims` HAS a `tenant` column and is still unsafe: its `PRIMARY KEY` is `commit_key` **alone**, so the uniqueness domain is **global** and one tenant's key can collide with another's. ### **The rule is tenant FIRST IN THE KEY.**

| # | Table | Current PK posture | Current unique-key posture | Tenant column | Tenant-first target | Unit | Acceptance | Backfill | ### Collision risk | Deployment dependency |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | `workflow_runs` | `id` (autoincrement) | ### **`document_hash` UNIQUE — GLOBAL, scoped only by money direction** | ### **none** | `(tenant, id)`; ### **UNIQUE `(tenant, document_hash)`** | U2.1 | `AC-SEC-001` | ### **derive tenant per row; rows with no derivable tenant ⇒ MANUAL_REVIEW_REQUIRED** | ### **HIGH — two tenants filing the SAME document (identical bytes ⇒ identical hash) collide TODAY across the tenant boundary: the second is silently treated as the first's duplicate. This is a live cross-tenant defect, not a future one.** | precedes P6's Work Item/Pipeline SPLIT |
| 2 | `audit_events` | `id` (autoincrement) | none | none | `(tenant, id)` | U2.1 | `AC-SEC-001`, `AC-AUD-*` | tenant from parent run; ### **append-only — rows are NEVER rewritten, only referenced** | MEDIUM — cross-tenant audit reads | precedes P5 outbox |
| 3 | `security_events` | `id` (autoincrement) | none | none | `(tenant, id)` | U2.1 | `AC-SEC-001` | as above; ### **GLOBAL-scope events (e.g. a global brake) need an explicit sentinel, not a NULL tenant** | MEDIUM | precedes P8 brake |
| 4 | `operation_action_claims` | `action_id` | `action_id` PK-unique, ### **global** | none | `(tenant, action_id)` | U2.1 | `AC-SEC-001`, `AC-SAFE-014` | tenant from the claim payload | ### **HIGH — a single-use approval token's uniqueness is global; two tenants cannot be proven isolated** | ### **precedes P3's grant claim CAS** |
| 5 | `delivery_action_claims` | `action_id` | `action_id` PK-unique, global | none | `(tenant, action_id)` | U2.1 | `AC-SEC-001` | tenant from the delivery payload | MEDIUM — approval-transport dedup | precedes P3 |
| 6 | `operation_commit_claims` | ### **`commit_key` ALONE** | ### **`commit_key` PK-unique — GLOBAL** | ### **present (`tenant`) — and STILL not tenant-first** | ### **`(tenant, commit_key)`** | ### **U2.1 → U2.2/U2.3** | ### **`AC-SEC-001`, `AC-SAFE-012/013/014`, `AC-RACE-001`** | ### **the Task-#1 backfill — collisions are EVIDENCE OF A HISTORICAL DOUBLE-COMMIT ⇒ MANUAL_REVIEW_REQUIRED. Do not merge. Do not pick one.** | ### **CRITICAL — this is the effect ledger's ancestor. Its key currently contains the AMOUNT (DEF-1) AND is tenant-blind. Both are fixed before any effect is enabled.** | ### **BLOCKS P12 (first live write) via the U2.3 partial unique indexes** |
| 7 | ### **`operation_token_amounts`** | `token_fingerprint` | `token_fingerprint` PK-unique, global | none | `(tenant, token_fingerprint)` | U2.1 | `AC-SEC-001` | tenant from the bound action | ### **HIGH — binds an APPROVED AMOUNT to a token in a global namespace** | ### **THE TABLE THE "6 of 8" MISCOUNT WOULD HAVE LEFT BEHIND. It is the Material-Facts Fingerprint's ancestor — the exact concept Task #1 moves the amount INTO.** | precedes P3 |

**The one already-canonical table (NOT in U2.1's scope):**
| `autonomous_run_counters` | ### **`PRIMARY KEY (tenant, lane, day)`** | — | present | ### **already tenant-first** | — | `AC-SEC-001` | none | none | — |

### U2.1's completion oracle
> ### **EXACT SET EQUALITY:** `{tables with tenant first in key}` **==** `{all 8}`, and `{non-tenant-first}` **== ∅**. ### **A count is a diagnostic, not the oracle: "7 tables migrated" while a different seventh remains broken MUST fail.** `AC-SEC-001` stays red until the set is empty.

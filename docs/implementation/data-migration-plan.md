# Data Migration Plan

*The current persisted model = **8 tables** (recon §5). ### **No SQL here. No migration files created.***

## Classification of every current persisted concept
| Concept (table) | Rows carry | ### Class | Target | Notes |
|---|---|---|---|---|
| `workflow_runs` | run id, state, lane, payload, tenant? | ### **SPLIT** | ### **Work Item (M1) + Pipeline Instance (M2)** — ### **one run row becomes TWO records: the business obligation and the attempt** | ### **MERGE_FORBIDDEN in reverse: never collapse them back** |
| `audit_events` | append rows | **TRANSFORM** | canonical events (envelope + version) via upcaster `v0→v1` | ### **HISTORICAL_ONLY for pre-migration rows: readable, never rewritten** |
| `security_events` | append rows | **TRANSFORM** | F14 security events | as above |
| `operation_commit_claims` | ### **amount-keyed commit_key** | ### **TRANSFORM (the Task-#1 backfill)** | the Effect Grant Ledger row | ### **collisions ⇒ MANUAL_REVIEW_REQUIRED (a historical double-commit)** |
| `operation_action_claims` | action_id (single-use) | **TRANSFORM** | grant claim / approval consume | ancestor of single-use |
| `delivery_action_claims` | action_id | **TRANSFORM** | approval transport dedup | — |
| `autonomous_run_counters` | (tenant, lane, day) | ### **DIRECT_MAPPING** | policy caps counters | ### **the ONLY tenant-first table** |
| `operation_token_amounts` | token→amount | ### **MERGE_FORBIDDEN** | ### **the Material-Facts Fingerprint** — an amount bound to a token is the fingerprint's ancestor, ### **but it must NOT be merged into the Commit Key** | this table *is* the conceptual proof the amount belongs in the fingerprint, not the key |
| External identifiers (in payloads) | tms load/invoice ids | **SPLIT** | **External Entity Mapping** rows | trusted only within `(tenant, system)` |
| Documents (on disk) | files | **TRANSFORM** | content-addressed Evidence | digest computed at migration |
| Extracted fields (in payloads) | values | **TRANSFORM** | ### **Claims with `provenance_class=MODEL_EXTRACTED`** — ### **never promoted to fact** |
| Load/invoice/payable (in payloads) | denormalized | **SPLIT** | the distinct domain entities | ### **no generic `Load`** |
| Approvals (Slack tokens) | token, actor | **TRANSFORM** | Approval + signature | ### **no fingerprint exists historically ⇒ historical approvals are NOT reusable post-migration** |
| User/tenant ownership | implicit/absent | ### **MANUAL_REVIEW_REQUIRED** | ### **every open Work Item needs ONE accountable human** | ### **ownership cannot be inferred — a human assigns it** |
| Retries / unresolved / failed / ambiguous ops | mixed states | ### **UNMAPPABLE_CONFLICT → canonical unresolved** | see below | — |
| Test data (mock ledger JSON, fixtures) | — | **DISCARDABLE_TEST_DATA** | — | must be unreachable in prod |

## ⛔ THE RULE FOR AMBIGUOUS HISTORICAL EFFECTS
> ### **DO NOT INFER SUCCESS. NO MIGRATION MAY MANUFACTURE VERIFIED SUCCESS.**
> Any historical operation whose real-world outcome is not **provable from retained evidence** (a readback record) maps to ### **`UNKNOWN_OUTCOME` with `unknown_reason=UNKNOWN_OUTCOME`**, ### **an assigned accountable human owner**, the **commit key held**, and a **reconciliation obligation**.
> This explicitly includes: ### **every current ambiguous `done` state** (a `done` that means "the state machine advanced" rather than "a readback proved it"), every `NEEDS_VERIFICATION` payload, every failed/retried op with no proof, and ### **every non-money effect that had no commit identity — because its single-commitment cannot be proven.**
> **A migration that closes these as success would be the R-01 archetype, at scale, in one commit.**

## Properties
**Resumable + idempotent** (principle 7): each row carries a migration marker; re-running skips completed rows; a partial run leaves a coherent state. **History attributable** (principle 8): originals are never deleted or rewritten; the transform writes new records referencing the old. **Replay-safe** (principle 9): the backfill emits **no** effects and mints **no** grants. **Dry-run first:** every phase's backfill has a report-only mode whose output is reviewed before the write pass.

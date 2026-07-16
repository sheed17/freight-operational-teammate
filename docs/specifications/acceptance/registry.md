# Acceptance Registry — Case IDs, Contract Defaults, Gate Mapping

**Layer:** Operational Acceptance. **Derived from (frozen):** Engineering Principles · Operating Model · Semantic Model · Target Spec · ADR-001…011 · the Entity / State-Machine / Event / Domain / Adapter / Workflow specs · all hostile reviews.
**Binding:** ### **This registry is the sole canonical index of acceptance-case identifiers and release-gate mappings.**

> ### **These are NOT test suggestions. They are executable behavioral contracts and RELEASE GATES.**
> **An implementation is NOT accepted because code compiles · unit tests pass · a demo succeeds · a document was extracted · an adapter returned 200 · a TMS record exists · a message was sent · a Pipeline Instance reached a convenient state · an engineer says the edge case is unlikely.**
> ### **It is accepted only when its externally observable behavior, durable state, emitted events, audit trail, ownership, verification, and LOOP CLOSURE match these specifications.**

## THE ORACLE RULE
> ### **A passing result must be based on an ORACLE. "Appears correct" is not an oracle.**
> An oracle is one of: **(a) an authoritative EXTERNAL observation** (a live/simulated readback of the real system) · **(b) a durable DB-state assertion** (exact rows/columns/versions) · **(c) an EVENT-stream assertion** (exact names, order, payload, envelope) · **(d) an AUDIT-reconstruction assertion** (the explainability query returns the historical context) · **(e) a NEGATIVE assertion** (a forbidden side effect provably did not occur). ### **A local write is NEVER an oracle for an external effect (M-72).**

## CASE ID SCHEME
`AC-<AREA>-<nnn>` · AREA ∈ `SAFE` (platform safety) · `CKPT` (checkpoint matrix) · `MACH` (machines) · `EVT` (events/replay) · `DOM` (domain) · `ADPT` (adapters) · `WF{1..11}` (per loop) · `FC` (false closure) · `DEG` (degraded) · `RACE` (concurrency/fault) · `SEC` (security/tenancy) · `REC` (recovery/compensation) · `AUD` (audit/explainability).

## ACCEPTANCE-CASE CONTRACT — DEFAULTS *(a case states only what differs)*
| Field | Default |
|---|---|
| Requirement source | stated per case (a frozen doc + identifier — **no case exists without one**) |
| Test level | one of the 12 (below) |
| Environment | CI + a deterministic **contract simulator** for external systems (real integrations only where a gate demands) |
| Tenant fixture | ### **`T_A` and `T_B` — every case runs tenant-isolated; cross-tenant assertions use both** |
| Actor fixtures | `human_owner` (authenticated), `human_approver`, `detector`, `model_agent` (inert), `system` |
| Policy fixture | `P_base` (money-out = `HUMAN_APPROVAL_REQUIRED`, everything registered, gate never null) |
| Brake fixture | `B_clear` unless the case engages one |
| Initial durable state | **explicitly enumerated — no case depends on an unstated fixture or implicit state** |
| Initial entity versions | enumerated |
| Initial event history | empty, or the **golden corpus** (`GC-1`) |
| Concurrency | none unless a schedule is given (`RACE-*` cases give exact interleavings) |
| Forbidden adapter calls | ### **every consequential case asserts the NEGATIVE: which adapter calls must NOT occur** |
| Idempotent rerun | ### **every case reruns to the same result; no case mutates shared state** |
| Replay behavior | ### **every case's history replays to the same projection digest, producing ZERO effects** |
| Cleanup | tenant-scoped teardown; **the golden corpus is immutable and never reset mid-suite** |
| Timing | ### **wall-clock independent** — durable timers are advanced by a controllable clock, never by sleeping |

## TEST LEVELS *(exactly one primary per case)*
`STRUCTURAL` · `ENTITY` · `STATE_MACHINE` · `EVENT_CONTRACT` · `ADAPTER_CONTRACT` · `CROSS_MACHINE` · `WORKFLOW` · `END_TO_END` · `SECURITY` · `RECOVERY` · `REPLAY` · `MIGRATION_GUARD`
*(A `MIGRATION_GUARD` validates constraints and **records existing risk** — it does not define a migration plan.)*

## RISK CLASSES → GATING
`SAFETY_CRITICAL` · `FINANCIAL_CORRECTNESS` · `TENANT_ISOLATION` · `COMMERCIAL_COMMITMENT` — ### **ALL FOUR ARE MERGE-GATING. Zero failure tolerance. NO WAIVER BY AN INDIVIDUAL ENGINEER.**
`OPERATIONAL_COMPLETENESS` · `DATA_INTEGRITY` · `AUDITABILITY` · `RELIABILITY` · `SECURITY` · `PRODUCT_BEHAVIOR` — gate-mapped (below).

## FILE INDEX → AREA → GATE
| File | Area | Primary gates |
|---|---|---|
| `platform-safety-acceptance.md` | SAFE, CKPT | ### **G0, G4 — merge-gating** |
| `foundational-machine-acceptance.md` | MACH | G1 |
| `event-and-replay-acceptance.md` | EVT | G2 |
| `domain-model-acceptance.md` | DOM | G1 |
| `adapter-boundary-acceptance.md` | ADPT | G3 |
| `workflow-acceptance.md` (+ `W1..W11`) | WF, FC | G5–G9 |
| `degraded-mode-acceptance.md` | DEG | G7 |
| `security-and-tenancy-acceptance.md` | SEC | ### **G0, G4 — merge-gating** |
| `recovery-and-compensation-acceptance.md` | REC, RACE | G4 |
| `observability-and-audit-acceptance.md` | AUD | G2, G9 |
| `release-gates.md` | — | G0–G10 + the pilot profile |
| `traceability.md` | — | all |

## COVERAGE TARGETS *(asserted in the review)*
### **141/141 transitions · 92/92 emitted events · 40/40 domain entities · all adapter operations · 28/28 permanent safety invariants · 16/16 false-closure rules · 40 hostile workflow + 30 adapter + 20 event + 20 cross-machine traces · 11/11 loops · all degraded modes · all release gates.**

## GOLDEN CORPUS `GC-1`
An immutable historical event corpus spanning ≥1 schema version change, ≥2 tenants, ≥1 correction, ≥1 `UNKNOWN_OUTCOME`, ≥1 compensation, ≥1 brake episode. ### **Rebuilding `GC-1` MUST reproduce the same canonical projection DIGEST every time, on every version, forever.**

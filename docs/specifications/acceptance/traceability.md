# Acceptance Traceability Matrix

> ### **THE TWO RULES:**
> ### **(1) NO canonical requirement may lack an acceptance case.**
> ### **(2) NO acceptance case may exist without a canonical requirement source.**
> Both are asserted mechanically by `AC-TRACE-000` (`STRUCTURAL`, gate **G0**): it walks the frozen corpus, extracts every requirement identifier, and asserts a **bijection** with the acceptance registry. An orphan in either direction **fails the build.**

## The chain
```
Engineering Principles (P1–P39, R1–R18)
  → Operating Model invariants (I1–I12) + permanent truths + policy
    → Semantic invariants (S1–S28)
      → ADR decisions (ADR-001…011 + A1–A4)
        → Architecture requirements (M-1…M-75, the 7 checkpoint steps)
          → Entity constraints (17 foundational + 40 domain)
            → Machine transitions (141)
              → Events (92 + 13 security)
                → Domain lifecycles (23 L-*)
                  → Adapter operations (~40, A1–A18)
                    → Workflow steps (~55 across W1–W11)
                      → ACCEPTANCE CASES
                        → RELEASE GATES (G0–G10)
```

## Representative traces *(the full matrix is the generated artifact of `AC-TRACE-000`)*
| Requirement | → … → | Acceptance | Gate |
|---|---|---|---|
| **P2** guards never model-evaluated | S3 → ADR-010 §5.1 → M-49 → M11/M12 → `PolicyEvaluated` → W-all step "policy" | `AC-SAFE-015`, `AC-CKPT-6-*` | **G4** |
| **I1** an accountable human, always | Work Item entity → M1 WI-1 → `WorkItemCreated` → every W | `AC-SAFE-028`, `AC-WF7-001` | **G4** |
| **I8** missing ≠ contradictory | S22 → ADR-006 → M-69 → M8/M3 → `ExpectationIndeterminate`/`OBSERVATION_UNAVAILABLE` → W5/W6 | `AC-WF5-003`, `AC-ADPT-012` | **G4/G7** |
| **I10** never taken and unrecorded | ADR-008 §2.5 → M-23 → outbox → all events | `AC-RACE-006/007`, `AC-EVT-003` | **G2/G4** |
| **I11** closure is an event | GR-14/K-1 → M9 EC-3 → `ExceptionResolved{decision_ref}` → W7 | `AC-SAFE-024`, `AC-WF7-004` | **G4** |
| **P24** the loop closes at cash | Operating Model L8 → Brokerage Load/Invoice → L-Invoice → `EffectVerified`+payment → W8 | `AC-WF8-005/009`, `AC-FC-009` | **G5–G9** |
| ### **ADR-003** authorization assertion (permanent) | S24 → `PERMANENT_HUMAN_ASSERTION_REQUIRED` → M4/M6 → `CounterpartySelfAuthorizationDetected` → Accessorial Authorization → A1/A3 → W9 | ### **`AC-SAFE-018`, `AC-DOM-008`, `AC-WF9-004`, `AC-SEC-010`** | **G4** |
| **ADR-004** effect boundary | M-37/M-38/M-47 → M2 PL-8/PL-9, M3 EF-1/EF-2 → `CheckpointPassed`/`GrantClaimed` → every adapter | `AC-SAFE-001..007`, the 105 `AC-CKPT-*`, `AC-SEC-013` | **G4** |
| **ADR-005** drift (F-01) | M-42/M-55..58 → M4 AP-4 → `ApprovalVoided{drift}` → W1/W8/W9 | `AC-SAFE-008`, `AC-CKPT-2-stale` | **G4** |
| **ADR-006** verification | M-69..74 → M3 EF-4/4c/4u → `EffectVerified`/`OutcomeUnknown` → A4/A15 | `AC-SAFE-021/022/023`, `AC-ADPT-005/006/012` | **G4** |
| **ADR-009** commit key | M-44..46 → the two indexes → M2/M3 → `GrantClaimed` → A4 | ### **`AC-SAFE-012/013/014` (+ the `MIGRATION_GUARD`)** | **G4** |
| **ADR-011** brake | M-59..63 → M13 → `BrakeEngaged` → all | `AC-SAFE-006/007/027`, `AC-RACE-002` | **G4** |
| **L-A** (Stream B) | R-P3 → M6 IB-5x → `IllegalTransitionAttempted` → W6 | `AC-SAFE-016`, `AC-MACH-605x` | **G4** |
| **L-C** (Stream B) | ADR-010 §6 → M12 RU-2f → `RuleNotEnforceable` → W10 | `AC-WF10-005` | **G5** |
| ### **The live commit-key defect** | ADR-009 §2.2 / Target §19.8 → A4 | ### **`AC-SAFE-012/013` as `MIGRATION_GUARD` — FAILING BY DESIGN against the current baseline until the migration fixes it** | **G0** |

## Coverage assertion
`AC-TRACE-000` emits the full matrix and asserts: **141/141 transitions · 92/92 events · 40/40 entities · ~40/40 adapter ops · 28/28 safety invariants · 16/16 false-closure rules · 11/11 loops · 110 hostile traces (40 WF + 30 ADPT + 20 EVT + 20 CROSS)** each mapped to ≥1 case, and every case mapped to ≥1 requirement.

# P3 — INDEPENDENT REVIEW FINDINGS (preserved as received)

> ### **NOT CURRENT AUTHORITY — this is preserved evidence, not status.**
> The status authority is [`CURRENT.md`](CURRENT.md). Nothing here approves work, moves a gate or
> authorises a phase transition. ### **This document does NOT adjudicate P3, and the review it
> records did NOT pass P3** — its verdict was `NOT READY FOR FINAL ADJUDICATION`.

| | |
|---|---|
| **Reviewed commit** | `38f2714ca7853373e6a51f81f5cd8143a5bdf3e8` |
| **Reviewer** | an INDEPENDENT session — not the session that implemented P3, and not the session that remediated these findings |
| **Findings** | **9** — 1 CRITICAL, 3 HIGH, 3 MEDIUM, 2 LOW |
| **Implementer findings adjudicated** | F-1 → **B** (accepted) · F-2 → **B** (accepted) |
| **Attestable weighted total** | **60 / 100** |
| **Verdict** | ### **NOT READY FOR FINAL ADJUDICATION** |

## ⚠️ Transport disclosure — read before treating this as the full report

### **Only the reviewer's FINDINGS were delivered into this repository, not the full report body.**
What follows is the finding set as received, preserved verbatim in substance and structure. The
narrative sections, per-criterion scoring worksheet and reproduction transcripts that the reviewer
produced were **not** transmitted here and are **not** reconstructed — inventing them would be the
fabricated-artifact failure the U-HANDOFF-2B hostile review exists to catch.

The consequence is stated plainly rather than buried: **a future adjudicator cannot verify the
60/100 weighting from this document.** It can verify each finding, because each was reproduced
mechanically during remediation and each reproduction is recorded in
[`p3-findings-remediation-review.md`](p3-findings-remediation-review.md).

---

## The findings, as received

### F-A — CRITICAL

Replace the mis-anchored rebaseline invariant guard so that it detects forbidden runtime changes
relative to the correct immutable rebaseline population rather than comparing legitimate P3 changes
against a moving `baseline_commit`.

The replacement must:
- preserve the original invariant
- use an explicit, proven population
- avoid a vacuous pass
- catch an intentionally reintroduced forbidden change
- not block legitimate P3 runtime changes
- comply with rule 20: replace the guard, do not delete it

### F-B — HIGH

Correct every current-status or review statement that falsely attributes the finalizer failure to
`socket.bind`.

Record the actual blocker: the canonical suite failed on F-A and the finalizer correctly refused.

Do not fabricate finalizer or clean-clone success.

### F-C — HIGH

Repair the `effect_grants` persistence design so P3 does not break the existing P2 ledger consumer.

The solution must preserve:
- one live reservation per tenant and `commit_key`
- correct legacy `claim_operation_commit` behavior
- correct `operation_commit_claim` lookup
- idempotent `release_operation_commit` behavior
- P3 dead-state history
- foreign-key integrity
- compatibility with the P3 claim-CAS model
- no silent wrong-row selection

Add regression tests reproducing both reviewer failures:
1. dead P3 row plus live legacy reservation returns the correct reservation
2. `release_operation_commit` remains idempotent and does not raise the observed foreign-key error

Do not defer this to P4 because the schema defect exists now.

### F-D — HIGH

Defend the canonical seven-step order.

Add multi-fault tests proving that when multiple steps would fail, the earliest canonical failing
step is always reported.

At minimum include the reviewed dual-fault case where policy/gate failure and an active brake
coexist, and prove step 6 wins over step 7.

Add a kernel mutation that swaps steps 6 and 7 and require the suite to catch it.

### F-E — MEDIUM

Apply the independent review's F-1 adjudication:

The separate tenant-exempt `platform_brake` table is accepted as the canonical representation.

Formally amend the relevant canonical specification, including `16-brake.md` point 7, so the
current authority agrees with the implementation.

Preserve the substantive requirements:
- exactly one platform row
- atomic engagement
- fail-closed absence/read failure
- admission checks platform plus tenant brake
- witnesses and grants bind both versions
- claim CAS revalidates both

Update guards and evidence only as necessary to reflect the formally amended canonical rule.

### F-F — MEDIUM

Prove observability behavior.

Add tests using a real observer that verify:
- every checkpoint step outcome is emitted
- every refusal identifies the failing step
- platform and tenant brake state/version are observable where required
- claim-CAS contention is observable
- observer failures do not corrupt checkpoint state

Do not treat mere observer plumbing as evidence.

### F-G — MEDIUM

Apply the independent review's F-2 adjudication:

P3 may contain the minimal structural `GateDecision`/`GateRegistry` contract required for
checkpoint evaluation.

P8 still owns:
- rule authoring
- compilation
- versioning
- activation
- precedence/conflict resolution
- richer action-class descriptors
- autonomy runtime
- expectation/exception/compensation systems

Correct the stale manifest rationale so it no longer claims typed policy/action classes do not
exist until P8.

Preserve the correct conclusion that the deferred P8 probe remains ungreen because the production
registration population is still zero.

### F-H — LOW

Correct `BUILD-STATUS` so it accurately distinguishes:
- implementer guard mutation battery completed
- independent kernel mutation battery completed with findings
- no unsupported claim of final mutation success

### F-I — LOW

Record the CAS `expires_at` and `tenant` predicates as defense-in-depth controls and add targeted
tests where feasible so future removal of masking controls does not silently weaken them.

If a test cannot distinguish a predicate under current invariants, document the masking invariant
precisely and add a guard that fails if that invariant changes.

---

## Standing

These findings were **remediated** — not adjudicated — by a later session. Remediation by the
session that received the findings is **not** an independent review and awards no acceptance
criterion. See [`p3-findings-remediation-review.md`](p3-findings-remediation-review.md) for the
per-finding disposition and the evidence behind each one.

### **P3's `independent_review` (weight 5) and `final_adjudication` (weight 4) remain `PENDING`.**
A fresh independent review of the remediated tree is required before either may be set.

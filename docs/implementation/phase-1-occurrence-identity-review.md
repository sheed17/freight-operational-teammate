# Phase-1 Closure Correction — Occurrence Identity

> ### **The defect was mine, and I shipped it while writing up the fix for its twin.**
> Phase 1 correctly made three operations fail closed because the **amount** was the only thing telling two legitimate repeats apart — and the amount may not carry identity. Then it handed callers `params["occurrence_key"]` to unblock them, and the Phase-1 review presented that as a feature.
> ### **A free-form caller string IS the amount defect with a new field name.** Vary it between retries and every attempt mints a new logical effect. Commit-once — the entire point of the phase — became reachable through one reach into an untyped dict.

---

## 1. The generic occurrence escape hatch found

```python
# src/freight_recon/operation_router.py  (Phase 1, now removed)
occurrence = occurrence_key_for(
    lane.name,
    explicit=params.get("occurrence_key"),   # ⛔ a caller-authored string, carrying identity
    ...
)
```
Reachable by any caller of `record_payment`, `adjust_invoice`, `check_call`. ### **Three payloads differing only in that string produced three Commit Keys, three reservations, and three payments against one invoice.**

## 2. Production files changed (2)
`src/freight_recon/commit_key.py` · `src/freight_recon/operation_router.py`.
### **No schema change** (`workflow.py` has a zero-line diff) · no migration · no new entity · no persistence · no rename.

## 3–5. Operations affected · canonical source · status
| Operation | Canonical occurrence source | Typed field *(frozen spec)* | Arrives | ### Status now |
|---|---|---|---|---|
| ### **`record_payment`** | ### **Payment Application** *(domain E34, `09-financial.md`)* | ### **`payment_application_id`** | ### **P9** (U9.\*) | ### **FAIL CLOSED** |
| ### **`adjust_invoice`** | ### **Compensation** *(entity `13-compensation.md`)* | ### **`compensation_id`** | ### **P8** (U8.4) | ### **FAIL CLOSED** |
| ### **`check_call`** | ### **Expectation** *(entity `11-expectation.md`)* | ### **`expectation_id`** | ### **P8** (U8.4) | ### **FAIL CLOSED** |

### **The frozen spec had already decided this, and said so plainly.** E34 Payment Application: *"the remittance reference (check no./ACH trace) — ### **the `occurrence_key` for payment idempotency (ADR-009); a partial payment is a distinct occurrence**"*, with acceptance `test_partial_payment_is_distinct_occurrence`. E30 Customer Invoice: *"a void/credit is a **Compensation** (a gated effect); a rebill is a **NEW invoice** under a distinct action class (`REISSUE_INVOICE`) — NOT the same effect repeated (avoids a credit-and-rebill double-bill)"*.
> ### **Two partial payments are separate logical effects because they are separate Payment Application occurrences — not because their amounts differ.** The amount, the changed line values, and the check-call note stay **material facts**.

### **All three remain fail closed and a human performs them.** None of the three entities exists, and the brief is explicit: leave it fail closed, name the phase, ### **do not create a temporary free-form substitute.** No Payment Application persistence was built to unblock this phase.

## 6–7. Typed fields accepted · generic fields rejected
**Accepted:** only a **resolved `CanonicalOccurrence(entity, occurrence_id)`** — a frozen type a *resolver* produces after proving the occurrence exists, is bound to the right entity, and belongs to this tenant. ### **There is deliberately no path from a request payload to that type, so a caller cannot hand one over and therefore cannot manufacture identity.** No resolver exists yet ⇒ the three lanes fail closed.
**Rejected:** `params["occurrence_key"]` *(deleted — AST-verified absent from all of `src/` and `scripts/`)* · amount · timestamp · request id · retry id · approval id · random UUID · payload hash · sequence number · any caller-authored free text.

### **The boundary is an ALLOWLIST, not a blocklist.** `_logical_effect` and `_commit_reservation` may read exactly `status_value`, the target-resource fields, and the counterparty. ### **Anything else fails a guard — including fields nobody has thought of yet.**

## 8. Tests added (23 + 7 guards)
`test_phase1_occurrence_identity.py` covers all 17 required oracles: free-form cannot unblock any of the three (1–3) · a varying free-form value across retries yields **zero reservations and zero actuator calls** (4) · the amount cannot distinguish payments (5) · two Payment Applications are two effects and the same one is one effect (6) · an external payment id is unusable unbound (7) · adjustments need their Compensation identity (8–9) · check calls need their Expectation (10) · a runtime timestamp cannot discriminate (11) · wrong tenant (12) and wrong entity (13) fail closed · **zero actuator calls and zero reservations** on the real router for all three lanes (14–15) · **AC-SAFE-012 (16) and AC-SAFE-013 (17) remain green**.
> ### **Where the canonical entity does not exist, the tests assert FAIL-CLOSED behaviour — they do not fake a business entity in production to manufacture a pass.** The contract for "two Payment Applications ⇒ two effects" is proved against the canonical **type**, which is honest about what exists today.

## 9. Mutation results — ### **16/16 DETECTED**
generic `params["occurrence_key"]` restored · `.get("occurrence_key")` restored anywhere · `explicit=` restored · arbitrary strings accepted · **amount** as discriminator · **request id** · **retry id** · **approval id** · **timestamp** · wrong-entity validation removed · invalid identity reaching actuation · a fail-closed lane quietly declared `SINGLE` · a canonical source stripped of its entity/phase · a canonical field renamed to an invented alias · the new tests weakened to `skip` · AC-SAFE-012 regressed. All restored; tree digest-verified.

### ⛔ MUTATION FOUND TWO REAL HOLES IN MY OWN CLOSURE
| Hole | Why it mattered |
|---|---|
| ### **The guard banned the NAME `occurrence_key`, not the CLASS** | ### **Swapping in `params["request_id"]` reproduced the defect exactly and the guard stayed GREEN.** Banning the names you happened to think of is not a boundary. Replaced with an **allowlist**: the identity builders may read only the few fields that genuinely describe the effect. |
| ### **The skip-ban only globbed `test_phase0_*`** | ### **A `@pytest.mark.skip` on a Phase-1 test went undetected.** A guard suite that protects only the phase that wrote it stops protecting anything the moment the next phase lands. Now every phase's guards are swept. |

> ### **Both guards passed their own tests before mutation. Neither could detect what it existed to detect.**

### ⛔ AND THE FINAL RUN FOUND A THIRD: A TEST OF MINE ENCODED THE ESCAPE HATCH
`test_phase1_commit_key.py::test_07` asserted that **two free-form `occurrence_key` values discriminate two payments** — i.e. it enshrined the escape hatch as expected behaviour, ### **exactly as `test_operation_router.py:282` once enshrined the amount-in-key defect (DEF-3).**
> ### **A test that asserts the defect fights the fix.** It was inverted: free-form values now raise, and two payments are discriminated by two **Payment Application** occurrences. ### **The same pattern has now appeared twice in two phases — a defect and the test that defends it arrive together, and the test is the harder one to see.**

## 10–11. AC-SAFE-012 / AC-SAFE-013 — ### **GREEN, unchanged**
Re-asserted here (oracles 16–17) and in the Phase-1 suite. The amount still does not touch identity; non-money effects still get a Commit Key.

## 12–15. ### **OPEN FINDINGS — ALL PRESERVED, NONE CLOSED**
| Finding | Status |
|---|---|
| ### **R-07** | ### **OPEN — NOT CONTAINED** |
| seven non-tenant-first tables | ### **OPEN — P2** |
| `workflow_runs.document_hash` cross-tenant uniqueness | ### **OPEN — a live defect, P2** |
| 24 transitions with no cited emitted event | ### **OPEN — before P5/G2** |
| 31 direct adapter import edges | ### **OPEN — P4** |

**Phase-1 results preserved:** amount-free identity ✔ · mandatory non-money keys ✔ · tenant scope in the key ✔ · `operation_commit_key` **still deleted** ✔ · no parallel constructor ✔ · historical compatibility bridge intact ✔.

## 16–17. Final suite + final-tree validation evidence
| | |
|---|---|
| **Final suite** | ### **`862 passed · 1 skipped · 0 failed`** |
| validation start tree | `3136918c70a9705e60c61f668826b0da3ce73bb9` |
| validation end tree | `3136918c70a9705e60c61f668826b0da3ce73bb9` |
| commit candidate tree | `3136918c70a9705e60c61f668826b0da3ce73bb9` |
| ### **all three match** | ### **`✔ — the suite ran LAST, against the exact tree committed`** |

## 18. Is Phase 1 fully closed?
### **Yes.** Identity now comes from a canonical business occurrence or the operation does not run. ### **The escape hatch is not deprecated, discouraged, or documented-against — it is gone, and an allowlist plus 16 mutations keep it gone.**
The three operations stay fail closed, ### **which is the correct answer and not a gap**: their identity belongs to entities the plan already schedules (P8, P9), and inventing a substitute now is precisely what created this defect.

## 19. May Phase 2 begin?
Yes.

---

# VERDICT

## ### **READY TO BEGIN IMPLEMENTATION PHASE 2**

**Carried forward:**
- ### **`record_payment`, `adjust_invoice`, `check_call` escalate to a human until P8/P9.** Not a bug to route around — ### **the honest cost of refusing to let an arbitrary string authorise a repeated money effect.** They unblock when Compensation and Expectation land (P8) and Payment Application lands (P9), each through its **typed canonical field**, resolved and tenant-checked. ### **The resolver's obligations — exists · bound to the right entity · belongs to this tenant — are recorded here as P8/P9 acceptance, not deferred silently.**
- ### **R-07 remains OPEN — NOT CONTAINED.** This correction made identity honest. It put no wall in front of the six live-write paths; only P4 does.

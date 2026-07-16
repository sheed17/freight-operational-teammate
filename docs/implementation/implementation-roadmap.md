# Implementation Roadmap — Phases 0–14

*Derived from the gap matrix + the frozen safety dependencies. ### **No calendar estimates.** Ordering is by dependency, not convenience.*

## The 16 migration principles *(binding on every phase)*
1 safety kernel before broad workflow · 2 one logical effect = one commit namespace · 3 legacy+canonical may never independently effect · 4 hard cutover preferred · 5 coexistence requires the SHARED ledger+key namespace · 6 no big-bang · 7 data migration resumable+idempotent · 8 history stays attributable · 9 replay stays side-effect free throughout · 10 flags narrow, never bypass · 11 rollback disables capability, never restores an unsafe path · 12 every phase leaves the repo deployable+coherent · 13 ### **no phase depends on future work for a CURRENT safety guarantee** · 14 migration scripts get no bypass · 15 test fixtures unreachable in production · 16 ### **current behavior is NOT preserved when it contradicts the frozen model.**

| Phase | Name | Establishes | Cannot start until | Gate |
|---|---|---|---|---|
| **0** | Baseline & migration guards | the acceptance harness; `AC-SAFE-012/013` **red by design**; `AC-TRACE-000`; the null-gate startup check | — | **G0** |
| **1** | ### **MIGRATION SAFETY TASK #1** | ### **amount-free, mandatory, tenant-scoped Commit Key** | P0 | **G0 → AC-SAFE-012/013 GREEN** |
| **2** | Tenant-safe Effect Ledger foundation | `tenant_id` first in all 9 surfaces; the one ledger, 8 states, 2 partial indexes | ### **P1 green** | → G4 |
| **3** | Checkpoint Witness + claim CAS | the 7-step atomic checkpoint; unconstructable `CheckpointPassed`; grant mint+claim; brake admission | P2 | → G4 |
| **4** | Adapter containment | the 13 import sites converted/removed; CI import gate ON; orphan detection; verification taxonomy | ### **P3** *(a gate with nothing behind it is theatre)* | → G4 |
| **5** | Outbox/inbox + replay isolation | transactional outbox, dedup inbox, 92 event contracts, `GC-1` digest, sandboxed replay | P2 | **G2** |
| **6** | Foundational entities + machines | Work Item (ownership!), Pipeline Instance, the 13 machines, 141 transitions | P5 | **G1** + → G4 *(`AC-SAFE-028`)* |
| **7** | Provenance, Evidence, Observation, Claims, Identity Binding | the 6 provenance classes, R-P1/2/3, content-addressed Evidence, the deterministic linker + Conflict | P6 | G1 + → G4 *(`AC-SAFE-015/016`)* |
| ### **8** | Policy, Rule, Brake, Conflict, Expectation, Exception, Compensation | typed policy, compile-or-refuse rules, the real brake, M7–M10 | P7 | ### **G4 QUALIFIES HERE** *(not at P4 — see the gate plan's correction)* |
| **9** | Freight-domain projections + mappings | the 40 entities, External Entity Mapping, field-level authority | P8 | G1 |
| **10** | ### **First vertical slice (W6→W8)** | document intake→packet→eligibility→prepared invoice; **no writes** | P9 | **G5** |
| **11** | Shadow + human-executed | live reads, zero effects; then human executes, Neyma captures evidence | P10 | **G6→G7** |
| **12** | Supervised effects | the first live gated write through the full kernel | ### **P11 + G4 re-run LIVE** | **G8** |
| **13** | Multi-loop expansion | additional loops + atomic handoffs | P12 | **G9** |
| **14** | Bounded autonomy | per-class, capped, time-boxed, revocable | ### **P13 + the graduation dossier** | **G10** |

## Justified ordering deviations from the brief's sequence
### **None required.** The repo's actual dependencies match the frozen safety order. Two clarifications derived from the recon:
- ### **P2 is bigger than the earlier inventories implied** — tenant-first keys are missing in **6 of 8 tables**, so P2 is a schema-wide change, not a ledger-only one. It stays at P2 because **tenant isolation must precede multi-tenant effect enablement** (principle 3 + `AC-SEC-001`).
- ### **P4 must follow P3, not parallel it.** The 13 import sites can only be *converted* to a client that exists (the pipeline+grant, P3). Enabling the CI gate earlier would only force a wrapper — and **a wrapper that logs the bypass is not containment.**

---

## Deployment & feature-flag plan
> ### **A FLAG MAY NARROW. A FLAG MAY NEVER BYPASS.** (principle 10) ### **There is no flag anywhere in this plan that disables the checkpoint, the ledger, the brake, tenant scoping, or the import gate. If such a flag existed, the safety kernel would be optional — and an optional kernel is not a kernel.**

| Flag | Grants | Default | Scope | Who flips it | Enable requires | Disable ⇒ |
|---|---|---|---|---|---|---|
| `capability.<action_class>.live_effect` | one action class may effect externally | ### **OFF** | ### **per (tenant, action_class)** | ### **the owner, in writing** | ### **G8 for that class** | back to ### **human-executed (G7)** — never to an ungated path |
| `loop.<Wn>.enabled` | a loop may run | OFF | per tenant | tech lead | that loop's gate | the loop stops; open Work Items keep their owners |
| `autonomy.<action_class>` | `AUTONOMOUS_WITHIN_CAPS` | ### **OFF (`HUMAN_APPROVAL_REQUIRED`)** | per (tenant, class) | ### **the Policy Owner only** | ### **G10 + the dossier** | ### **narrows to approval — the one-way ratchet: automation may narrow, NEVER broaden** |
| `adapter.<An>.live` | real vendor vs simulator | OFF | per tenant | tech lead | G3 + G4 | simulator |
| `migration.<Pn>.backfill` | a backfill's write pass | ### **OFF (report-only)** | global | architect | the dry-run report reviewed | report-only |

**Deployment shape per phase:** every phase ships **dark** — code deployed, capability flag OFF — so that ### **deploy and enable are two separate, separately-reviewed decisions.** The brake is **armed in every environment from P3 forward**, including test.

## Observability & operations plan
**Per phase, what must be observable before the phase's gate:**
- **P1+:** every Commit Key minted, with its derivation inputs (### **the amount is not among them — and that absence is itself asserted**).
- **P2+:** ledger state transitions; ### **every unique-index rejection** (a rejection is the mechanism *working*, and must be visible as such, not swallowed).
- **P3+:** every checkpoint step outcome; ### **every refusal, with WHICH of the 7 steps refused** — a refusal with no named step is unexplainable and therefore unfixable · brake state · claim CAS contention.
- **P4+:** ### **orphan-adapter detection = Sev-0** (an effect with no grant means the containment failed) · import-gate violations at CI.
- **P5+:** outbox lag; dedup hits; ### **the `GC-1` rebuild digest vs the pinned digest — a divergence is automatic demotion.**
- **P6+:** ### **Work Items with no accountable owner = Sev-0** (I1) · Work Item age.
- **P11+:** shadow-vs-human diff rate.
- **P12+:** ### **the `UNKNOWN_OUTCOME` rate — the single most important operational number in the system.** A rising rate is automatic demotion (it means the system is acting without knowing the result) · ### **wrong actions: target ZERO, any occurrence demotes** · verified-readback latency · human approval turnaround.
**The permanent operating discipline:** ### **`UNKNOWN_OUTCOME` is never auto-resolved, never aged out, never swept.** Each one holds its commit key and has a named human owner until reconciled against an authoritative external observation.

## Rollback & recovery semantics *(per phase)*
| Phase | Rollback | ### What rollback NEVER does | Recovery |
|---|---|---|---|
| **0** | revert the harness | — | — |
| ### **1** | ### **NONE — a defect fix is not a capability.** ### **Rolling back would restore an amount-keyed, optional commit identity: i.e. re-introduce the double-pay defect. It is forward-only.** | ### **restore `approved_amount` into any key** | re-run the backfill (idempotent) |
| **2** | forward-fix only (schema is additive first) | ### **drop tenant scoping** | resume the resumable backfill |
| **3** | disable the capability flags ⇒ nothing effects | ### **make the checkpoint optional** | brake ENGAGE ⇒ no mint, no claim; in-flight claims resolve or become `UNKNOWN_OUTCOME` |
| ### **4** | flags off | ### **restore EP-6/7/9/10 (deleted) or the `orient_tms` actuator import** | — |
| **5** | replay from the outbox | ### **emit effects during replay** | rebuild projections; the digest must match |
| **6–9** | flags off | ### **orphan a Work Item from its owner** | — |
| **10–11** | loop flag off | ### **claim Neyma executed anything a human executed** | Work Items stay owned |
| ### **12** | ### **capability flag off ⇒ back to G7 human-executed** | ### **un-write an external effect that really happened — a rollback is NOT a compensation.** ### **Reversing a real-world effect is a NEW, separately-gated, separately-approved compensating effect with its OWN commit key.** | reconcile every in-flight grant; ### **any unresolvable ⇒ `UNKNOWN_OUTCOME` + a named owner** |
| **13–14** | demote one gate + narrow autonomy | ### **broaden autonomy (ER-12: automation may demote, never promote)** | the brake is the universal stop |

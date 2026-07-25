# Release Gates G0–G10 + The Pilot Acceptance Profile

*Registry defaults apply. ### **No gate may be passed solely through a demonstration** (Engineering Principles / the P17 SCAR: green tests and a good demo are not evidence — only the named oracles are).*

## The gates
| Gate | Name | Required cases | Pass rate | Zero-tolerance | Mocks permitted | Real integrations | Corpus | Concurrency | Fault runs | Evidence retained | Human sign-off | Brake posture | Autonomy ceiling |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **G0** | Specification Conformance | `AC-*-000` structural bijections; `AC-SEC-001/013`; the null-gate startup check | **100%** | ### **all** | n/a | none | — | — | — | the conformance report | tech lead | n/a | none |
| **G1** | Pure Domain & Machine Correctness | ### **`AC-MACH-*` (134/134)**, `AC-DOM-*` (40/40) | **100%** | ### **all SAFETY/FINANCIAL/DATA_INTEGRITY** | full | none | — | — | — | coverage table | tech lead | n/a | none |
| **G2** | Event, Replay & Projection | ### **`AC-EVT-*` (98/98)** + `GC-1` digest | **100%** | ### **AC-EVT-007/008/011/013** | full | none | ### **`GC-1` required** | — | — | ### **the pinned digest** | tech lead | n/a | none |
| **G3** | Adapter Contract Simulation | `AC-ADPT-*` (all ops) | **100%** | AC-ADPT-002/003/011/012/015 | ### **contract simulators (spec-derived)** | none | — | — | full taxonomy | simulator call logs | tech lead | n/a | none |
| **G4** | ### **Safety-Kernel & Concurrency Qualification** | ### **`AC-SAFE-001..028` + the 105 `AC-CKPT-*` + `AC-RACE-001..017` + `AC-REC-*` + `AC-SEC-*`** | ### **100%** | ### **EVERY case — no waiver** | simulators | none | `GC-1` | ### **10,000 interleavings per race** | ### **every crash point** | ### **race logs + crash matrices** | ### **architect + owner** | engaged by default in test | none |
| **G5** | Single-Loop Controlled Env | one loop's `AC-WF*` + `AC-FC-*` | 100% | all FC cases | simulators | ### **a real TMS sandbox** | `GC-1` | key races | key faults | loop traces | tech lead | armed | ### **none — no live effects** |
| **G6** | Single-Loop **Shadow Mode** | as G5, run against **live data** | 100% | all | none | ### **live reads only** | — | — | — | ### **shadow-vs-human diff report** | owner | armed | ### **ZERO effects — observe + propose only** |
| **G7** | Single-Loop **Human-Executed** | + `AC-DEG-*` for that loop | 100% | ### **AC-DEG-5 (never claim Neyma executed)** | none | live reads | — | — | — | ### **evidence-capture proof** | owner | armed | ### **preparation only; the HUMAN executes** |
| **G8** | Single-Loop **Supervised Effect** | + the loop's consequential `AC-WF*` live | 100% | ### **AC-SAFE-001..028 re-run LIVE** | none | ### **live reads + writes** | — | — | — | ### **every grant/witness/readback retained** | ### **owner, per action class** | ### **armed, exercised** | ### **`HUMAN_APPROVAL_REQUIRED` for every effect** |
| **G9** | Multi-Loop Supervised | all touched loops + handoffs `AC-WF-H*` | 100% | ### **AC-FC-016 (no responsibility gap)** | none | live | `GC-1` nightly | — | — | + explainability `AC-AUD-*` | owner | armed | supervised only |
| **G10** | ### **Bounded Autonomy** | ### **the full suite + the graduation evidence (ADR-010 §7)** | ### **100%** | ### **ZERO wrong actions; ~0 unknown-outcome rate** | none | live | `GC-1` | full | full | ### **the graduation dossier** | ### **the Policy Owner, per action class, in writing** | armed | ### **`AUTONOMOUS_WITHIN_CAPS` — per class, capped, time-boxed, revocable** |

**Promotion:** all required cases pass **at the stated rate**, evidence retained, sign-off recorded. ### **Demotion (automatic):** any zero-tolerance failure · a wrong action · a rising `UNKNOWN_OUTCOME` rate · an orphan-adapter Sev-0 · a rebuild divergence · a cross-tenant event ⇒ ### **demote one gate AND narrow autonomy; automation may demote, NEVER promote (ER-12).**
**Rollback condition (every gate):** engage the brake, revert to the prior gate's autonomy ceiling, retain the evidence, raise an Exception with a named owner.

---

## THE PILOT ACCEPTANCE PROFILE — Documentation → Billing
> # ### **NEEDS DESIGN-PARTNER VALIDATION**
> ### **This is the frozen FIRST-LOOP HYPOTHESIS (Operating Model), NOT a decided wedge. It must be validated against the design partner's actual pain before it is built as the pilot.**

**Minimum production-coherent capability** *(the profile is incoherent if any is missing)*:
document intake (A1/A11) · classification (`MODEL_EXTRACTED`) · ### **extraction as CLAIMS, never facts** · identity binding (deterministic; `AMBIGUOUS`⇒human) · ### **customer-specific packet requirements** (compiled Rules) · ### **missing-document Expectations (the non-event — the core value)** · Conflict handling · packet completion · billing eligibility (POD-gated) · invoice preparation · ### **SUPERVISED release (`HUMAN_APPROVAL_REQUIRED`)** · ### **delivery evidence (verified readback)** · AR Work Item creation · ### **the degraded human-execution path** · audit reconstruction · brake + ownership controls.

**Explicitly EXCLUDED from the pilot:** ### **autonomous payment · uncontrolled TMS writes · any autonomous money-out · autonomous quoting · autonomous carrier booking.**

### Evidence that would CONFIRM the profile
The partner, unprompted, describes the pain as **cash delayed by paperwork**; ### **they can name loads billed late because a POD was missing and nobody knew for days**; the missing-doc list is something they currently rebuild by hand; the packet requirements differ by customer and they track them in someone's head or a spreadsheet; invoice release is already a human decision they want to keep.
### Evidence that would REJECT it
The acute pain is **coverage or claims**, not billing; documents already arrive reliably and are filed by an existing process; billing is already automated by their TMS; ### **the delay is in getting PAID (collections/disputes), not in getting BILLED** — which would move the wedge to the AR-collection half of L8, or to L9; or ### **the partner's blocking pain is carrier fraud/qualification (L2/L3)**.
> ### **If the evidence rejects it, the wedge moves. The architecture does not — that is the point of having built it loop-agnostic.**

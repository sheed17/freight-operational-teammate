# Release Gate Plan — Mapping Implementation Phases to G0–G10

*The gates themselves are **frozen** (`docs/specifications/acceptance/release-gates.md`). ### **This file does not restate or reinterpret them — it maps THIS plan's phases and units onto them.** Where this file and the frozen gate table could ever disagree, ### **the frozen table wins.***

| Gate | Qualifying phase | Qualifying units | Entry evidence | ### The one thing that MUST be true |
|---|---|---|---|---|
| **G0** | P0 → **P1** | U0.1–U0.4, ### **U1.2/U1.3** | the conformance report; ### **AC-SAFE-012/013 flip red→green** | ### **the two migration guards are GREEN — the amount is out of the key and every effect has one** |
| **G1** | P6, P7, P9 | U6.3, U9.\* | `AC-MACH-*` 141/141, `AC-DOM-*` 40/40 | pure logic is correct with no I/O in the loop |
| **G2** | P5 | U5.1–U5.5 | the pinned `GC-1` digest | ### **a rebuild reproduces the digest, and replay emits ZERO effects** |
| **G3** | P4 (simulators from P3/U3.5) | U3.5, U4.\* | simulator call logs | ### **the simulators were written from the SPEC, not the implementation** (else L-9: a false pass) |
| ### **G4** | ### **P2 → P8 (ALL of it)** | ### **U2.\*, U3.\*, U4.\*, U5.1/U5.2, U6.1–U6.4, U7.1–U7.4, U8.1–U8.4** | ### **race logs (10k interleavings/race) + crash matrices at every crash point** | ### **THE SAFETY KERNEL EXISTS AND IS UNBYPASSABLE. This is the gate the entire plan is built to reach: NO live effect of any kind is permitted before it.** ### **Its scope is set by the FROZEN gate, not by convenience — see the correction below.** |
| **G5** | P10 | U9.\*, the slice | loop traces + `AC-FC-*` | the loop is correct in a sandbox with ### **zero live effects** |
| **G6** | P11a | — | the shadow-vs-human diff | ### **live reads, ZERO effects — observe and propose only** |
| **G7** | P11b | — | evidence-capture proof | ### **the HUMAN executes; Neyma prepares and captures. `AC-DEG` assertion 5: Neyma NEVER claims it executed.** |
| ### **G8** | ### **P12** | U4.6 (### **the deletions must have happened**) | ### **every grant/witness/readback retained** | ### **G4 RE-RUN LIVE. Passing G4 against simulators is not evidence about production.** |
| **G9** | P13 | handoff units | atomic-handoff proofs + `AC-AUD-*` | ### **AC-FC-016 — no responsibility gap between loops** |
| **G10** | P14 | — | ### **the graduation dossier (ADR-010 §7)** | ### **zero wrong actions; the Policy Owner signs per action class, in writing, time-boxed and revocable** |

## ⛔ CORRECTION — G4 IS WIDER THAN THE PHASE LABELS SUGGEST *(found by this plan's own mechanical check; see review finding M-3)*
> ### **An earlier draft of this file scoped G4 to "P2+P3+P4" — the ledger, the checkpoint, and containment. That was WRONG, and it was the most dangerous error in the plan.**
> The **frozen** gate requires ### **`AC-SAFE-001..028` in full** — and those 28 reach past the checkpoint:

| Required case | Needs | Lands at |
|---|---|---|
| `AC-RACE-006/007` | the transactional outbox | ### **P5** |
| ### **`AC-SAFE-028`** | ### **Work Item + an accountable owner** | ### **P6** |
| ### **`AC-SAFE-015/016`** | ### **`provenance_class` + R-P3** | ### **P7** |
| `AC-SAFE-024` | Exception + a resolving `decision_ref` | **P8** |
| `AC-REC-001` | Compensation (M10) | **P8** |
| `AC-SEC-*` | tenancy (P2) + containment (P4) | P2/P4 |

> ### **Therefore G4 QUALIFIES AT THE END OF P8. P2/P3/P4 CONTRIBUTE to G4; they do not complete it.**
> ### **Why this mattered enough to correct rather than quietly reword:** P12 — the first live external write — is gated on G4. ### **An under-scoped G4 is not a documentation error; it is a path to an ungated live write.** A reader of the earlier draft could have qualified "G4" at P4, honestly believed the wall was cleared, and shipped an effect with no provenance rules, no owner, and no compensation semantics. ### **The gate is the wall; a gate scoped by convenience is a hole in it.**

## Gate ordering constraints
- ### **G0's green (P1) precedes EVERY other implementation unit.** The plan's first real change is the defect fix, and nothing else moves until it lands.
- ### **G4 is the wall.** ### **P2–P8 build it; P9–P14 all sit behind it.** ### **No phase after P11 may proceed without G4 having been re-run LIVE at G8.**
- **G1/G2/G3 may qualify in parallel** — they are pure/simulated and share no dependency.
- ### **G6→G7→G8 are strictly sequential for a given loop** (observe → prepare → effect) and are **per (tenant, action_class)**, never global.
- ### **Demotion is automatic and needs no meeting:** any zero-tolerance failure, a wrong action, a rising `UNKNOWN_OUTCOME` rate, an orphan-adapter Sev-0, a rebuild divergence, or a cross-tenant event ⇒ demote one gate **and** narrow autonomy. ### **Automation may demote. Automation may NEVER promote (ER-12).**

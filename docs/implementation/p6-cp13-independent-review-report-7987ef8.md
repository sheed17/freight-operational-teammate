> # ⛔ HISTORICAL REVIEW — NOT CURRENT AUTHORITY
> **This is evidence of a past moment, not status.** It is an INDEPENDENT REVIEW: it set no
> acceptance criterion, marked no phase complete, closed no risk, enabled nothing and authorized no
> external effect. It reviewed machine **M13 — the Brake** and returned **SUPPORTED, confidence
> 0.90, findings `0`, adjudications `2` (both UPHELD), criteria `9/9 PASS`, `blocked_on.kind:
> NONE`**.
>
> ### **THE REVIEWED TREE AND THE LANDED TREE ARE THE SAME TREE, AND THAT IS PROVEN BY HASH RATHER
> THAN BY PROSE.** The reviewer's own `reviewed_fingerprint` reads **head
> `7987ef8c4dce72714da24a06a3c8b28edc883da7`, tree
> `a1a903a3047937f594184eb88974b2e8ae9d292c`, `tracked_dirty: 0`, `untracked: 0`**, and
> `git rev-parse 7987ef8^{tree}` at this landing returns that identical tree. The run's
> `completion-audit.json` records the same pair independently. **There is no reviewed-tree-versus-
> candidate gap at this checkpoint** — the `P6-D68` / `P6-D87` class does **not** recur, and this is
> the first P6 landing since `P6-CP-11` that can say so.
>
> ### **IT DID NOT REVIEW THE COMMIT THAT CARRIES IT.** The landing commit that brought this file
> in-tree did not exist when the review was performed.
>
> ### **FIVE DIFFERENT THINGS ARE KEPT APART IN THIS DOCUMENT AND MUST NOT BE COLLAPSED.**
> (1) the **builder implementation** at `41b68ac` and its **Correction 1** at `7987ef8`, by builder
> session `f794211f`;
> (2) **Product Driver scenario verification** — run `20260905-230030`, 11/11 required scenarios,
> 14/14 executed scenarios passed, 1152 assertions, 0 failed;
> (3) the **focused independent review by a non-builder session** `9714f808`, recorded here;
> (4) **GitHub CI**, run `34162327327`, which concluded **`cancelled` overall** and whose full-suite
> legs **never reached M13's own tests**; and
> (5) the **founder landing decision** that this checkpoint lands on the evidence that exists.
> ### **(5) IS A DECISION, NOT A VERIFICATION**, and nothing here presents it as one.
>
> ### **THE CHRONOLOGY OF THIS RUN IS UNUSUAL AND IS STATED RATHER THAN SMOOTHED.** The candidate
> commit `7987ef8` was created **before the Product Driver harness itself was repaired**, and its
> commit message therefore records **"permanent scenario 970/974"** and **"four remaining redaction-
> artifact assertions"**. Those statements were **TRUE WHEN THAT COMMIT WAS WRITTEN** and are **NOT
> the final acceptance state.** Product Driver was subsequently corrected **in its own repository**
> — the diagnostic `token:` stdout-redaction collision, resume-plan semantic redaction /
> `CommandBinding` identity, and stale generated-scenario expectation reconstruction. **Those
> corrections changed no Neyma file.** The **same Neyma tree `a1a903a3`** was then re-run and reached
> **974/974 on the permanent scenario, 11/11 required, 14/14 executed, independent review SUPPORTED,
> TASK RESULT VERIFIED**. ### **THE CANDIDATE COMMIT MESSAGE IS NOT THE VERIFICATION RECORD; THIS
> DOCUMENT IS.** Git history is not rewritten to hide the earlier number.
>
> ### **P6-CP-13 IS A CHECKPOINT, NOT A PHASE ACCEPTANCE.** M13 is the **last P6 machine**, and
> **"the last machine landed" is not "the phase is accepted."** P6 is **NOT COMPLETE**, no P6
> acceptance criterion is scored, `criteria_scored` is `[]` on all **thirteen** checkpoints, P7 stays
> **BLOCKED / NOT_STARTED**, and M13 continues to **ship dark**. The next program action is **P6
> phase acceptance / final adjudication by a reviewer who did not build the phase** — not P7.
>
> ### **NO ADJUDICATION FOLLOWED THIS REVIEW, AND NONE IS OWED.** M13 is tier-1 under
> [`CLAUDE.md`](../../CLAUDE.md) §7 — it lands a migration on tables the checkpoint kernel reads, it
> is load-bearing for tenant isolation, and **it edits `brake.py`, a landed P3 kernel module**. §7
> prices that at **one** focused independent review by someone who did not write it, plus mutation
> proof that the guard can fail. Both are discharged. **A single independent review is a review, not
> a chain of sessions.**

---

# P6-CP-13 — FOCUSED INDEPENDENT REVIEW — M13, the Brake, at `7987ef8`

| | |
|---|---|
| **Checkpoint** | `P6-CP-13` — the **thirteenth and final** P6 machine |
| **Landed code commit** | `7987ef8c4dce72714da24a06a3c8b28edc883da7` |
| **Landed code tree** | `a1a903a3047937f594184eb88974b2e8ae9d292c` |
| **Build commit** | `41b68acf7fc377b2624591dce6a4f48a1b7a6852` (Correction 1 → `7987ef8`) |
| **Branch** | `p5/u5-1-g2-spec-correction` |
| **Product Driver run** | `20260905-230030`, iteration 1, **ACCEPT** (confidence 0.86, `problems: []`) |
| **Reviewer session** | `9714f808-0d58-4168-b1a9-b6ccfae31bf8`, `inherited_builder_context: false` |
| **Builder session** | `f794211f-69b7-46df-9c36-2840205bfe1b` |
| **Verdict** | **SUPPORTED**, confidence **0.90**, findings **0**, adjudications **2 (both UPHELD)**, criteria **9/9 PASS**, `blocked_on.kind: NONE` |
| **CI** | run `34162327327` — **`cancelled`**, **not green**; see §8 |

---

## 1. The verdict, verbatim from the accepted artifact

`accepted/independent-review.json`:

- `verdict: SUPPORTED` · `confidence: 0.9`
- `findings: []` — **zero**
- `adjudications:` **two**, both ruled **UPHELD** (§6 below)
- `criteria_assessment:` **9 criteria, 9 PASS**
- `inherited_builder_context: false`, `evidence_reproduced: true`,
  `claimed_evidence_reproduced: true`
- `executed_commands:` **22**; `reproduced_evidence:` **22**
- `blocked_on: {kind: NONE}`

### **ONE DECLARED ORACLE COULD NOT BE RUN THROUGH THE REVIEWER BOUNDARY, AND THAT IS RECORDED RATHER THAN OMITTED.** The reviewer's own `blocked_on.detail` states that oracle `@fe9d58c4` (the M13 event-mint scan) was refused because its variable name `node` tripped the harness's editor-detection heuristic and arbitrary `python -c` is outside the approved vocabulary. The reviewer **corroborated the property independently** (F13 is four Brake contracts; M2/M4 still consume `BrakeEngaged`; the probe reports *"mints no unregistered event"* and *"FOUR F13 CONTRACTS AND NO FIFTH"*) and recorded `kind: NONE` because the conclusion did not rest on it. **That is a harness limitation, not a Neyma gap** (`P6-D93`).

---

## 2. What M13 is, in one line

**A broker's operator can now stop Neyma from starting any new consequential work — instantly, with the system unhealthy, without ceremony — and doing so cannot orphan a single payment that was already in flight.**

### **THE SENTENCE THIS MACHINE EXISTS FOR IS *"IT NEVER KILLS A WORKER."*** A brake that kills workers manufactures the exact hazard the operator engaged it to avoid: you pull the brake to become *safer* and, in the act of pulling it, convert a knowable outcome into a payable of **unknown status**. So the brake stops the **NEXT** effect, never the **LAST** one. Anything already `CLAIMED`, executing, or verifying **runs to a verified conclusion**. Product Driver exercised this at **all five boundary positions**, not once in the middle of a table, and recorded *"engaging-during-an-adapter-call-creates-no-unknown-outcome: zero unknown outcomes"*.

### **TWO STATES — `ACTIVE`, `RELEASED` — AND NO THIRD, ENFORCED BY THE DATABASE.** The necessity is argued in `entities/16-brake.md` point 4.2 and it is a product argument, not a modelling preference: *"engaged by a human vs by a detector"* is an **actor field**; *"partially released"* is a **scope change**; and *"pending release"* would require a release-approval workflow — **forbidden, because requiring ceremony to become safer is a design error.**

### **THE ONE-WAY RATCHET IS THE SAME SENTENCE THAT GOVERNS AUTONOMY.** Automation may **engage** and **widen**, because both move authority in the safe direction. Automation may **never narrow or release**, because both broaden it. **A detector may never clear its own alarm. A model is not a Sev-0 detector and may touch nothing at all** — `system`, `detector` and `model` are three actor classes, and collapsing them is precisely how a model would acquire the brake.

### **AND A BRAKE NEVER EXPIRES.** No TTL column, no expiry state, no auto-release path, no expiry identifier in executable code — because **a clock cannot know whether the fire is out**, and a brake that expires releases itself while nobody is looking. `BR-5` is an **enumerated illegal refusal** rather than an unwritten path, so adding a scheduler later cannot quietly find a door.

---

## 3. The hardening migration, introspected LIVE at this landing

M13 is the migration shape most likely to drift: it **hardens tables P3 already created** rather than creating a new one, so a fresh database gets the DDL inline while an existing one gets it through an `ALTER`/rebuild path, and the two can diverge silently.

### 3.1 The load-bearing DDL was introspected live, not read

On a fresh canonical database built the way production builds one, with foreign keys enabled, **`schema_readiness_problems` returned `NONE`**:

**`brakes`** — tenant-first. `PRIMARY KEY ['tenant','brake_id']`, **14 columns**, **2 indexes, both leading with `tenant`**, and the partial unique index that carries the concurrency invariant:

```
CREATE UNIQUE INDEX ix_brakes_one_active_per_scope ON brakes (tenant, scope) WHERE state = 'ACTIVE'
```

Its `CHECK` set, read off the live schema:

- `state IN ('ACTIVE','RELEASED')` — **exactly two literals and no third**
- `actor_kind IN ('HUMAN','DETECTOR')`
- `state != 'RELEASED' OR (released_by IS NOT NULL AND release_decision_ref IS NOT NULL)`
- `released_by_kind IS NULL OR released_by_kind = 'HUMAN'` — ### **a detector-released brake is NOT INSERTABLE, not merely unreachable**
- `signal_count >= 1`

**2 foreign-key half-columns, both into `tenant_humans` and both carrying the tenant** — so **a cross-tenant releaser cannot be spelled**.

**`platform_brake`** — the GLOBAL dimension, and ### **GLOBAL IS NOT A FAKE TENANT.** `PRIMARY KEY (id)` with **`CHECK (id = 1)`**, **12 columns**, and **no `tenant` column at all**. A second platform row is **structurally not insertable**, so the platform brake denies every tenant **without an N-row fan-out that would need a multi-row atomic write during the very incident it exists for**.

**No TTL, expiry, timeout or auto-release column exists on either table** — measured by column scan, not asserted.

**Append-only:** `trg_brakes_no_delete` and `trg_platform_brake_no_delete`.

### 3.2 The invariants were proven by ATTEMPTING THE VIOLATION

Nine writes were attempted live at this landing against that fresh database. **Every one was refused, and the refusing constraint is named:**

| Attempted write | Refused by |
|---|---|
| a **second** `platform_brake` row | `CHECK constraint failed: id = 1` |
| a **third** platform state (`PENDING_RELEASE`) | `CHECK ... state IN ('ACTIVE','RELEASED')` |
| `DELETE` of the platform row | `trg_platform_brake_no_delete` — *"the platform brake row is never deleted [SD-12, C-9]"* |
| a **third** brake state (`SUSPENDED`) | `CHECK ... state IN ('ACTIVE','RELEASED')` |
| a **release with no releaser and no `decision_ref`** | `CHECK ... state != 'RELEASED' OR (released_by IS NOT NULL AND release_decision_ref IS NOT NULL)` |
| a **DETECTOR** as `released_by_kind` | `CHECK ... released_by_kind IS NULL OR released_by_kind = 'HUMAN'` |
| a **cross-tenant** releaser | `FOREIGN KEY constraint failed` |
| a **second `ACTIVE` brake in the same scope** | `UNIQUE constraint failed: brakes.tenant, brakes.scope` |
| `DELETE` of a brake row | `trg_brakes_no_delete` — *"a brake row is never deleted [16-brake.md point 28, C-9]"* |

Surviving rows outside the canonical two states: **0**.

### 3.3 The event contracts, measured

**118 registered contracts — the identical total recorded at the `P6-CP-11` and `P6-CP-12` landings.** ### **M13 MINTED NO EVENT CONTRACT AT ALL**, which is the strongest available form of rule-17 compliance. Family census over the discovered registry: `F13` = **exactly four** — `BrakeEngaged`, `BrakeWidened`, `BrakeNarrowed`, `BrakeReleased` — **and no fifth**; `brake_lifecycle.py`'s `PRODUCED_CONTRACTS` is **exactly those four and nothing else**; `F14` stays at **13**, `UnauthorizedBrakeReleaseAttempted` already among them, so **M13 minted no second refusal contract either**. `PolicyOverridden` is **still ABSENT from all 118** — `P6-D71` does not close here.

### 3.4 The transition arithmetic, re-derived rather than carried

§14 of **all thirteen** machine files was parsed and its rows counted at this landing: the parse **DISCOVERED 13 files** and counted **134 rows**, matching P6's own `expected_production_outputs`. M13's five — `BR-1`, `BR-2`, `BR-3`, `BR-4`, `BR-5` — are an **exact set match** between `brake_lifecycle.py` and the specification.

### **134 OF 134 TRANSITIONS ARE NOW WRITTEN AND LANDED. NONE REMAIN.** ### **THAT IS AN ARITHMETIC FACT ABOUT THE TRANSITION CORPUS AND IT IS NOT A PHASE ACCEPTANCE.** P6 still owes gate **G1** and `AC-SAFE-028`, and it owes the one thing no checkpoint can supply: **a phase acceptance judged by a reviewer who did not build the phase.**

### 3.5 The canonical table partition needs no new row, and that is the point

M13 **creates no table**. `brakes` and `platform_brake` were created by P3 and are already carried in `CURRENT.md`'s partition as **P3 tenant (2)** and **P3 exempt (1)**. The hermeticity guard's hand-pinned `shape` dict is therefore **unchanged**, and the `P6-D88` weakness — a substring check that was already green before the row it was cited for — **does not recur here, because no row was added to be falsely credited.**

---

## 4. What the reviewer established ITSELF, and how

The reviewer executed **22 commands** and reproduced **22 pieces of evidence**. The load-bearing ones:

- `pytest eval/tests/test_phase6_brake.py` → **64 passed, 0 failed**
- `scripts/probe_phase6_brake.py` → **188 cases**, *"behaviours as specified, 0 wrong"*, including refuse-to-mint / refuse-to-claim, never-kill-a-worker at positions 3/4/5, two-states-no-third, the authority ratchet, the race battery over **250 + 1000 interleavings** with `both=0, neither=0, wrong=0`, and fail-closed reads
- `scripts/mutate_phase6_brake.py` → **18 caught, 0 escaped**, **anti-vacuity control GREEN**, tree restored byte-identical, `git status` clean afterwards
- the declared acceptance oracle → *"entity point 44 tests missing: []"*, *"the machine section 41 acceptance items missing: []"*
- the declared gate-minter oracle → **`modules that MINT a gate decision: ['checkpoint.py']`**
- `git diff --stat 41b68ac^..7987ef8` over `work_item / pipeline_instance / external_effect / approval / conflict / exception / compensation / policy / rule / checkpoint / effect_boundary / event_contracts_data.json` → **no output; no change**
- `git rev-parse HEAD` / `HEAD^{tree}` / `git status --porcelain` **before and after** its own runs → unchanged, clean

### **THE MUTATION BATTERY IS WHAT MAKES THE REST EVIDENCE, AND IT WAS RE-RUN AT THIS LANDING.** A guard never seen to fail is a decoration ([`CLAUDE.md`](../../CLAUDE.md) §6). This landing session independently re-executed it on the committed candidate tree under **CPython 3.14.4** — a third interpreter — with `git status --porcelain` **empty before and empty after**, and the tree hash **`a1a903a3047937f594184eb88974b2e8ae9d292c` unchanged afterwards**. All **18 caught, 0 escaped**, anti-vacuity control **GREEN**. Each mutant reintroduces a *real* defect, and the eighteen are the invariants themselves:

`a third brake state becomes insertable` · `a TTL column is added` · `the released_by foreign key is dropped` · `the platform row gains a tenant column` · `multiple platform rows are allowed` · `the brakes delete-refusing trigger is defanged` · `the platform delete-refusing trigger is defanged` · `the rising signal count is suppressed` · `automation may release a brake` · `a detector may narrow a brake` · `a model may engage a brake` · `a loaded page is accepted as positive health` · `release stops requiring in-flight effects accounted for` · `release lets an unresolved Sev-0 pass` · `the claim CAS stops revalidating the brake version` · `an unreadable brake store reads as off` · `an active brake is hidden from the operator report` · `a second unauthorized-release contract synonym is introduced`

### **THE LANDING SESSION RE-EXECUTED THE HEADLINE EVIDENCE, AND THE NEIGHBOUR ANCHORS TOO.** On the committed candidate tree: `test_phase6_brake.py` **64 passed**; `probe_phase6_brake.py --all` **exit 0, "behaviours as specified, 0 wrong"**; the P3 kernel anchors `test_phase3_brake.py` + `test_phase3_checkpoint_matrix.py` + `test_phase3_claim_cas.py` + `test_phase3_schema.py` + `test_phase3_witness.py` + `test_phase3_observability.py` **191 passed**; the P5 replay/event and M2/M4 anchors together with `test_phase3_fingerprint / ledger_compatibility / step_order` **784 passed**; M10/M11/M12/M13 together **245 passed**; the phase-0 status and safety guards **84 passed, 1 skipped**; `test_bootstrap_hermeticity.py` **54 passed**. **These are local results on CPython 3.14.4 and are never presented as CI results.**

### **THE SINGLE BRAKE AUTHORITY, MEASURED WITH ITS DENOMINATOR — AND MEASURED MORE PRECISELY THAN THE PROBE STATES IT.** Across **127 discovered production modules**, an AST scan for write SQL against `brakes` / `platform_brake` returns **two** modules, and the distinction between them is the whole point:

- **`brake.py`** — `INSERT INTO brakes`, `UPDATE brakes`, `UPDATE platform_brake`. The class that owns every one of them is **`brake.py:BrakeStore`**, and it is the **sole** brake-lifecycle authority.
- **`migrations/phase3_checkpoint.py`** — a single `INSERT OR IGNORE INTO platform_brake (id, state, brake_version) VALUES (1, 'RELEASED', 0)`. That is **P3's migration seeding the singleton row**, not a second lifecycle authority.

### **AND `brake_lifecycle.py` — THE M13 MACHINE — CONTAINS ZERO BRAKE-STATE WRITE SQL.** It composes and delegates. It even says so in its own refusal text: *"M13 composes over the landed BrakeStore; it does not replace it."* **M13 built no second store, and rule 17 is satisfied by construction rather than by convention.**

### **THE CHECKPOINT REMAINS THE SOLE GATE MINTER, WITH A POSITIVE CONTROL.** *A second gate authority is the same defect as no gate authority.* Re-measured at this landing by the phase-0 guard's own method over **127 modules**: `modules that MINT a gate decision: ['checkpoint.py']`, **zero offenders**, and the **positive control fires** — the scan finds the kernel's own `GateEntry` construction at **`checkpoint.py:242`**, so its silence about every other module means something. **`GateRegistry` constructions anywhere in the package: NONE** — the production registered-action-class population stays structurally **EMPTY** until U8.1/P8. ### **AND `eval/phase0/gate_scan.py` IS BYTE-UNCHANGED ACROSS THE ENTIRE M13 RANGE:** unlike M11, **M13 widened no gate guard at all.**

### **SHIP-DARK, WITH ITS DENOMINATOR AND ITS POSITIVE CONTROLS.** `production importers of brake_lifecycle: []` is a negative assertion, and a negative assertion over an unproven population proves nothing ([`CLAUDE.md`](../../CLAUDE.md) §6). The **same** intra-package, whole-module-token scanner over the **same 127 discovered modules** returns **9 importers of `checkpoint`** and **6 of `commit_key`** — so it is demonstrated to find importers before it is believed about finding none.

---

## 5. What Product Driver independently exercised

Run **`20260905-230030`**, iteration 1, accepted. `decision.json`: **ACCEPT**, confidence **0.86**, **`problems: []`**. `scoped-completion.json`: `task_result: VERIFIED`, **`task_outstanding: []`**, `parent_phase_accepted: **false**`. `completion-audit.json`: **VERIFIED**, confidence 0.85, `implementation_present: true`, **`contradictions: []`**, **`missing_evidence: []`**, observed `head_commit 7987ef8c4dce…` / `head_tree a1a903a30479…`, `dirty_file_count: 0`.

**Scenario gate: 11 of 11 required scenarios present and passed with resolvable evidence.** Suite: **14 executed — 1 permanent + 13 generated — 14 PASSED, 0 failed, 0 blocked, 0 skipped**, **1152 assertions, 0 failed**, `assembly_problems: []`, `evidence_verified: true` on **all fourteen**, and **no computed coverage gaps this run**.

| Scenario | Origin | Risk category | Assertions |
|---|---|---|---|
| `p6_m13_brake` | **permanent** | (the P0 authored scenario) | **974**, 0 failed |
| `M13-S01` | generated | `happy_path` | 11 |
| `M13-W2-01` | generated | `persistence_failure` | 15 |
| `M13-W2-02` | generated | `dependency_failure` | 11 |
| `M13-W2-03` | generated | `cross_tenant` | 12 |
| `M13-W2-04` | generated | `regression` | 11 |
| `P6-M13-W3-01` | generated | `concurrency` | 11 |
| `P6-M13-W3-02` | generated | `cross_tenant` | 12 |
| `P6-M13-W3-03` | generated | `repeated_request` | 16 |
| `P6-M13-W3-04` | generated | `service_unavailable` | 5 |
| `P6-M13-W3-05` | generated | `malformed_input` | 13 |
| `P6-M13-W3-06` | generated | `authorization` | 13 |
| `P6-M13-W3-07` | generated | `concurrency` | 36 |
| `P6-M13-W3-08` | generated | `missing_data` | 12 |

### **THE PERMANENT SCENARIO IS 974/974 IN THE ACCEPTED RUN, AND THE COMMIT MESSAGE'S 970/974 IS THE OLDER NUMBER.** `suite-result.json` records `assertions_total: 974, assertions_failed: 0` for `p6_m13_brake`. The four previously-discrepant assertions were **Product Driver's stdout redactor masking lines after a `token:` key** — the reviewer re-ran the probe *outside* that redactor and observed the correct bytes directly: platform and tenant brake versions monotonic `[1,2,3]`, the composite token bound on witnesses and grants, the claim CAS revalidating both components. ### **THE PRODUCT EMITTED CORRECT BYTES THE WHOLE TIME; THE HARNESS COULD NOT READ THEM.**

### **THE RACE THAT MATTERS IS CLOSED BY THE DATABASE, NOT BY A CHECK.** Witnesses and grants bind a **composite** token carrying **both** the platform and the tenant brake version, and **the claim CAS revalidates both inside its own `WHERE` clause** — so a brake engaged between mint and claim makes the update match **zero rows** and the adapter does nothing. **Never both, never neither**, over **10,000 interleavings**. Both asymmetric failures are exercised, because each is a payment: **a tenant-only check would let a GLOBAL brake through, and a global-only check would let a TENANT brake through.**

### **RELEASE IS NOT `if human and decision_ref`.** That implementation passes every authorization test anyone would write and is still wrong. Release requires **positive evidence**: every in-flight effect accounted for, no unresolved Sev-0, integration health **positively demonstrated by a positive control rather than "the page loaded"**, and a `decision_ref`. **Each condition was withheld alone**, so an implementation checking only one is caught by the others. **Unresolved unknown outcomes do NOT block release** — blocking on them would create pressure to resolve them carelessly — **but they must be acknowledged and owned, and their entities stay frozen.**

### **A FLAPPING DETECTOR OPENS NO WINDOW, AND THAT WAS ASSERTED BY ROW COUNT RATHER THAN BY RETURN VALUE.** A store that returns the existing brake **while writing a second row** looks identical from the caller's side and is a momentary release window during an incident. The oracle counts rows in a live database across many repeats: **one `ACTIVE` brake and a rising `signal_count`**. The signal count is the canonical answer to *"how many times did this fire?"* — a question asked during the incident and unanswerable afterwards if nothing recorded it.

### **"CANNOT READ THE BRAKE" NEVER MEANS "THE BRAKE IS OFF."** That inversion is how a safety control becomes decoration, and it is deniable in every direction: an absent platform row, an unreadable store, an unparseable scope. Each **refuses the mint and refuses the claim**, and there is **no allow-on-error default anywhere on the path**. The scope grammar is **closed**, and its landed and deferred dimensions **partition the canonical five**, so a dimension this unit did not build is **unspellable** rather than silently scoped to nothing.

### **THE NEIGHBOURING MACHINES KEEP THEIR SEMANTICS.** Compensation writes stay **blocked under an active brake** — a misbehaving system must not write corrections. M4's **`VOID_ON_BRAKE`** is preserved. Pending approvals stay **RECORDED but cannot authorize execution**. **Release does not resurrect stale authority**: `BR-4` bumps `brake_version`, invalidating every witness and grant minted before it, so **queued consequential work requires a NEW checkpoint after release**. Observation and reconciliation continue throughout — the brake withdraws the authority to *act*, not the ability to *see*.

### **REPLAY CREATES NO LIVE AUTHORITY**, and the **R17 operator report is emitted unprompted** — scope, what is **still allowed**, reason, actor (human or named detector), time, prevented effects, in-flight effects and their status, unresolved unknown outcomes and exposure, and the **exact release requirements**. ### **A HIDDEN BRAKE VIOLATES R17**, and an active brake hidden from that report is one of the eighteen mutants the battery catches.

---

## 6. The two adjudications — both UPHELD

The review recorded **zero findings** and **two adjudications**. An adjudication here is a discrepancy between the implementing session's claim and some other record, ruled on with a basis.

**Adjudication 1 — the 974-vs-970 gap.** *Discrepancy:* the implementing session claims 974/974; the HEAD commit message records 970/974 with four failures attributed to a harness `token:` redaction collision. *Ruling:* **UPHELD.** *Basis:* the reviewer ran the probe directly, outside the redactor, and observed the correct behaviour. **"The product emits correct bytes; the 4 are a VERIFICATION_HARNESS artifact external to this repo, not an M13 product defect."**

**Adjudication 2 — the ship-dark claim versus `brake.py`'s importers.** *Discrepancy:* the probe reports `m13-ships-dark-with-zero-production-importers: []`, yet `brake.py` is imported by `checkpoint.py`, `effect_boundary.py` and `approval.py`. *Ruling:* **UPHELD.** *Basis:* the oracle measures importers of the **new M13 surface `brake_lifecycle.py`**, which has zero. `brake.py` is the **pre-existing P3 `BrakeStore` the effect boundary must consult in order to "refuse to mint and refuse to claim"** — and `git diff 41b68ac^..7987ef8` shows M13 modified **none** of those three files. **Those imports are P3/M4 enforcement wiring, not new M13 enablement. The claim is honestly scoped.**

Re-measured independently at this landing: intra-package production importers of **`brake_lifecycle`: `[]`**; of **`brake`: `['approval.py', 'brake_lifecycle.py', 'checkpoint.py', 'effect_boundary.py']`** — three pre-existing enforcement consumers, byte-unchanged across the M13 range, plus M13's own delegating facade. ### **AND EVERY ONE OF THOSE THREE CAN ONLY *DENY*.**

---

## 7. The nine criteria the reviewer assessed — 9/9 PASS

1. **The M13 machine and its hardening migration exist as tracked deliverables** — PASS
2. **The acceptance battery carries the canonically named adversarial tests and passes** — PASS (`entity point 44 tests missing: []`; `machine section 41 acceptance items missing: []`; 64 passed)
3. **The probe demonstrates the specified behaviours with zero wrong** — PASS (188 cases, exit 0)
4. **The mutation battery proves the guards are falsifiable, not decorations** — PASS (18/18, anti-vacuity GREEN)
5. **One authority per domain (rule 17) — single brake authority; checkpoint sole gate minter** — PASS
6. **M1–M12 machines and the effect kernel unchanged by M13; the event registry untouched** — PASS
7. **Ships dark: no new production enablement, no console/dashboard/channel/detector wiring** — PASS
8. **Landing M13 does not complete P6 or score a phase acceptance criterion** — PASS
9. **Reviewer state matches the state under review** — PASS

### **CRITERION 6 IS THE ONE THAT MADE THIS REVIEW TIER-1, AND IT IS WHY IT WAS REQUIRED.** ### **M13 EDITS THE MODULE IT MEASURES — WHICH NO EARLIER P6 UNIT DID.** `brake.py` is **P3's landed kernel brake**, and completing it *is* the sanctioned M13 build; but P3's checkpoint matrix, claim CAS and step-order batteries are exactly what turn red if it is completed carelessly, and **M4, M10 and M12 all consume brake state through their own guards**. The reviewer therefore ran the anchors rather than citing them, and confirmed by `git diff` that **`checkpoint.py`, `effect_boundary.py`, `event_contracts_data.json` and every M1–M12 machine module are byte-unchanged**. Re-verified mechanically at this landing over the range `ded6a84..7987ef8`: **empty diff** across all fifteen of those paths, and **`.github/` byte-identical** (`41f76934b715f253da6e7f6a261c351186a7447b`) either side, so **the CI workflow was not weakened**.

---

## 8. ### CI — the honest record. The workflow did NOT conclude `SUCCESS`

### **RUN `34162327327`, ON THE LANDING CANDIDATE `7987ef8`, CONCLUDED `cancelled`. `cancelled` IS NOT `success`, AND ANYONE CITING THIS LANDING AS "CI GREEN" IS CITING IT WRONGLY.**

Founder-supplied job conclusions:

| Job | Conclusion |
|---|---|
| `P6/M3 effect-grant probe + mutation` | **SUCCESS** |
| `Full test suite (py3.12)` | **CANCELLED** at the 60-minute job ceiling, reaching **51%**, **zero** pytest failure markers emitted |
| `Full test suite (py3.11)` | **CANCELLED** at the 60-minute job ceiling, reaching **51%**, **zero** pytest failure markers emitted |
| `Safety invariants (fast)` | **CANCELLED** at its own 30-minute ceiling, no failure marker observed |
| `Risk radar` | **SKIPPED** — pull-request-only |

Both interpreter jobs checked out the exact candidate SHA. **No pytest `F` / `FAILED` / `ERROR` / traceback / assertion failure was emitted on either leg before cancellation.**

### **THIS IS THE WEAKEST CI POSITION OF ANY P6 LANDING FOR THE LANDING MACHINE'S OWN TESTS, AND IT IS RECORDED AS UNDISCHARGED RATHER THAN ASSERTED.** At `P6-CP-12`, one full suite **completed** (py3.12, 100% reached) and M12's own 61 tests demonstrably ran inside it. **Here neither leg completed, and that mitigation is not available.**

### **WHAT CI DID AND DID NOT REACH — MEASURED ON THIS TREE, NOT ASSUMED.** `pytest eval --collect-only` collects **3349** tests on this tree. **51% is test #1707 — the point at which exactly 89 test files have been executed in full.**

- **`eval/tests/test_phase6_brake.py` sits at positions 2062–2125 — 61.5%–63.4%.** ### **M13's OWN 64 TESTS DID NOT EXECUTE IN CI ON EITHER INTERPRETER. NOT FAILING, NOT PASSING — NO EXECUTION.**
- `test_phase3_schema.py` (**54.8%–55.1%**), which carries the **M13 migration walk**, was **not reached** on either leg.
- `test_phase3_claim_cas.py` (**52.7%–53.3%**), which M13 edited and which carries the composite-token CAS anchor, was **not reached** on either leg.
- `test_phase3_checkpoint_matrix.py` (**49.5%–52.7%**, 106 tests), which M13 also edited, **straddles the cancellation — partially executed.**

### **WHAT DID EXECUTE IS NOT NOTHING, AND IS STATED AS PRECISELY AS WHAT DID NOT.** `test_phase3_brake.py` — **P3's brake anchors, which M13 edited** — sits at **49.0%–49.5%** and therefore **ran to completion on both legs and emitted dots**. So did `test_phase0_null_gate.py` (**44.7%–44.9%**), which carries the sole-gate-minter guard; `test_phase0_tenant_posture.py` (**45.2%–45.5%**), where a canonical table failing to declare itself turns red; and `test_phase0_guard_integrity.py` (**43.9%–44.1%**).

### **THE CANCELLED SAFETY JOB IS ONLY PARTLY MITIGATED, AND THE SHORTFALL IS MEASURED RATHER THAN GLOSSED.** That job names **26 files, discovered from the workflow rather than enumerated**; all 26 are inside `pytest eval` — **621 tests**. Against the 51% cancellation: **17 of the 26 executed in full**, **1 straddled it** (`test_phase3_checkpoint_matrix.py`), and **8 were not reached at all** — including `test_phase3_claim_cas.py`, `test_phase3_witness.py` and `test_phase3_step_order.py`. **The repository has no CI result for those eight on this commit.** All 26 were run **locally** at this landing and passed.

### **CI RUNS NO M13 PROBE OR MUTATION JOB.** Verified mechanically: the count of `phase6_brake` occurrences in `.github/workflows/ci.yml` is **ZERO**. The 18-mutant battery, the 188-case probe and the 64-test acceptance battery are **uncovered by CI on this commit** and were re-executed locally instead. ### **AND UNLIKE `P6-CP-12`, THE MITIGATING SENTENCE — "BUT THEY RAN INSIDE THE COMPLETED SUITE" — IS NOT AVAILABLE, BECAUSE NO SUITE COMPLETED.**

### **THE JOB CONCLUSIONS WERE FOUNDER-SUPPLIED AND COULD NOT BE RE-READ AT THIS LANDING.** `gh run view 34162327327` fails from this sandbox with `tls: failed to verify certificate: x509: OSStatus -26276`, **the identical failure recorded at every landing since `P6-CP-5`, reproduced at this one.**

### **THE FOUNDER LANDING DECISION, RECORDED AS A DECISION AND NOT AS A VERIFICATION.** The founder chose to land on the evidence that exists — the accepted Product Driver run against this exact tree, the deterministic permanent scenario, the reviewer-reproduced runtime evidence, the mutation battery, the regression anchors and CI's clean partial execution — treating both ceilings as **non-product CI runtime limitations**. **That is `P6-D92`, and it closes only by a CI run on this branch that concludes `SUCCESS`.** ### **A TIME CEILING IS NOT A PRODUCT DEFECT, AND IT IS ALSO NOT A PASS.**


### **THE FULL SUITE WAS RUN ON THE FINAL TREE, AND ITS TWENTY LOCAL FAILURES ARE NOT PRODUCT FAILURES — NOR ARE THEY PRESENTED AS PASSES.** `pytest eval` on the committed tree under CPython 3.14.4: **3328 passed, 1 skipped, 20 failed** — and 3328 + 1 + 20 = **3349**, matching the collection exactly. **Every one of the twenty is this sandbox refusing `socket.bind` on `127.0.0.1`**: 20 `FAILED` ids, **`PermissionError` the only exception type in the failure section**, 80 bind sites, all in `test_action_callback.py` and `test_p4_deployed_governed_route.py`. ### **AND CI IS THE POSITIVE CONTROL THAT MAKES THAT AN ENVIRONMENTAL CLAIM RATHER THAN AN EXCUSE:** those two files sit at **0.9%–1.9%** and **25.9%–26.7%**, **well inside the 51% both legs reached**, and **neither leg emitted a failure marker** — so those exact 20 tests **executed and passed in CI on both interpreters on this commit.** This is the same sandbox limitation recorded at the `P6-CP-12` landing, reproduced here.
---

## 9. Minor and nonblocking items — recorded, not actioned

### **THE INDEPENDENT REVIEW RETURNED ZERO FINDINGS.** Everything below was identified **at this landing** from the run's structured evidence, the M13 source, the specification corpus and the CI record. **None is a reviewer finding**, and none is fixed here — this is a docs-only landing, and every item below would require touching `scripts/`, `eval/` or a tier-1 runtime file.

### **A REAL DEFECT THIS LANDING FOUND THAT THE ACCEPTED EVIDENCE DID NOT SURFACE — `P6-D89`.** Three pre-M13 probes assert *"M13 is not built"* and **now exit 1 on the landed tree**, because M13 **is** built:

| Probe | Result on this tree | Failing case |
|---|---|---|
| `scripts/probe_phase6_policy.py --all` | **exit 1, 2 wrong** | *"an M13 brake lifecycle module exists"* ×2 |
| `scripts/probe_phase6_rule.py --all` | **exit 1, 2 wrong** | *"an M13 brake machine exists"*, *"an M13 brake lifecycle module exists"* |
| `scripts/probe_phase6_compensation.py --all` | **exit 1, 1 wrong** | `m11-m12-and-m13-are-not-built` |

**This is [`CLAUDE.md`](../../CLAUDE.md) §4 rule 20's exact case** — a check asserting obsolete behaviour must be **REPLACED**, not preserved. The M13 build **did** correct the two *pytest* files that carried the same stale assertion (`test_phase6_policy.py`, `test_phase6_rule.py`) and **missed the three probe scripts**. ### **BLAST RADIUS, MEASURED RATHER THAN ASSUMED: NONE OF THE THREE IS RUN BY CI** (`.github/workflows/ci.yml` runs only the M3 external-effect probe) **AND NONE IS INVOKED BY ANY TEST IN `pytest eval`** — so neither CI nor the suite turns red, and `M13`'s own probe is **exit 0, 0 wrong**. It is a **false red, never a false green**, and it is nonblocking — but a probe that cries wolf is a probe people learn to stop reading.

### **`brake.py` IS NO LONGER FROZEN BY ANY BYTE-IDENTITY GUARD — `P6-D90`.** Measured over a **discovered** population of the four guards in `eval/` that pin `src/` modules by `git diff --name-only`: before M13, `brake.py` was frozen by two (`test_phase6_policy.py` and `test_phase6_rule.py`); **after M13 it is frozen by none.** `checkpoint.py` is still frozen by three, and M13's own `test_the_m1_through_m12_machines_are_unchanged` freezes all twelve machines. ### **THE REMOVAL ITSELF WAS CORRECT AND IS NOT THE FINDING:** a guard asserting `brake.py` byte-unchanged would **forbid the sanctioned M13 edit**, so rule 20 required replacing it. The finding is that it was replaced with **nothing that re-freezes `brake.py` for the units that come after M13**. Behavioural protection is undiminished — `test_phase3_brake.py` (19), `test_phase3_checkpoint_matrix.py` (106), `test_phase3_claim_cas.py` (22), `test_phase6_brake.py` (64) and the 18-mutant battery all exercise it — so this is a lost tripwire, not a lost invariant.

### **THE `P6-D58` / `P6-D81` / `P6-D85` CLASS RECURS A FOURTH TIME — `P6-D91`.** Discovered mechanically over **744 tracked files** rather than by recollection: **five statements across two files** assert *"M13 landed"* before any `P6-CP-13` existed — `test_phase6_policy.py:903`, `:905`, `:929` and `test_phase6_rule.py:981`, `:1003`. All were **FALSE WHEN WRITTEN** at `41b68ac`/`7987ef8` and become **TRUE as of this landing commit**. Two are assertion *messages* rather than comments, but the assertions themselves test **module presence**, which is true on the tree independent of landing status. **Zero of them appear in a status authority** — `CURRENT.md` at `7987ef8` correctly recorded M13 as **not landed**. ### **THAT THE SAME CLASS HAS NOW RECURRED AT M8, M11, M12 AND M13 IS ITSELF THE FINDING WORTH CARRYING.**

### **THREE PRODUCT DRIVER HARNESS OBSERVATIONS — `P6-D93`, A HARNESS CHANGE AND NOT A NEYMA CHANGE.** (a) `task-scope.json` derived `repository_unit_id: "P6-CP-10"` while `CURRENT.md` recorded `P6-CP-12` as the last landed checkpoint — a stale derivation that **changed no gate and no verdict**. (b) One declared reviewer oracle could not run through the reviewer boundary because its variable name `node` tripped an editor-detection heuristic; the reviewer corroborated the property independently. (c) The `token:` stdout-redaction collision that produced the 970/974 figure, **repaired in Product Driver's own repository**, not Neyma's.

### **CI INCOMPLETENESS IS `P6-D92`**, recorded above in §8 in full.

### **NO CARRIED RESIDUAL IS CLOSED BY THIS LANDING, AND THAT IS STATED RATHER THAN LET PASS.** **`P6-D65`** is the only open row whose `closes_at` names M13 — *"M11/M12/M13, or a founder determination, per question"*. Its thirteenth-question structure is what keeps it open: only the **premise** of `M10-AQ-8` (*"M10's prose assumes M11/M12/M13, which are unbuilt"*) changes here, and that clause was a statement about **M10's scope**, not a dependency on M13 existing. The other twelve questions need a later machine or a **founder determination**, so the row's own closure condition is **not met** and it stays **OPEN**. **`P6-D71`** (`PolicyOverridden`) stays **OPEN / `BLOCKED_AUTHORITY`** — verified absent from all **118** registered contracts at this landing, and **M13 builds no override mechanism at all**. **`P6-D4`** (K-1's `RULE` referent) and **`P6-D73`** / **`P6-D84`** (M9's polymorphic mirror FKs) stay **OPEN** unchanged; `work_item.py` and `phase6_exceptions.py` are **byte-unchanged across the entire M13 range**. **`P6-D40`** is carried forward unchanged and **was not re-verified at this landing** — no mutation battery was run against the status guards here, and none is claimed.

---

## 10. What did NOT change

- **No M1–M12 machine module, and no effect kernel.** `git diff --stat ded6a84 7987ef8` over `work_item.py`, `pipeline_instance.py`, `external_effect.py`, `approval.py`, `observation.py`, `identity_binding_claim.py`, `conflict.py`, `expectation.py`, `exception.py`, `compensation.py`, `policy.py`, `rule.py`, `checkpoint.py`, `effect_boundary.py` → **empty**.
- **No event contract.** `event_contracts_data.json` byte-unchanged; the total stays **118**.
- **No CI workflow.** `.github/` tree hash identical across the range.
- **No gate guard.** `eval/phase0/gate_scan.py` byte-unchanged; `GATE_RUNTIME_MODULES` gained no member.
- **No canonical table.** M13 hardens P3's `brakes` / `platform_brake`; the partition's pinned `shape` is unchanged.
- **No phase status.** P6 stays `status: READY` / `execution_state: IN_PROGRESS`; P7 stays `BLOCKED` / `NOT_STARTED`.

**What M13 did add:** `src/freight_recon/brake_lifecycle.py` (the machine, five transitions, the delegating facade), `src/freight_recon/migrations/phase6_brakes.py` (the hardening migration), edits to `src/freight_recon/brake.py` (**P3's kernel brake — the sanctioned tier-1 edit that is the whole unit**), plus `schema.py` and `migrations/phase2_tenant_first.py` wiring, and the evidence surfaces `eval/tests/test_phase6_brake.py` (64 tests), `scripts/probe_phase6_brake.py` (188 cases) and `scripts/mutate_phase6_brake.py` (18 mutants).

---

## 11. What this checkpoint does NOT do

- ⛔ It does **not** complete P6, and **"the last machine landed" is not "the phase is accepted."**
- ⛔ It scores **no** P6 acceptance criterion. `criteria_scored` is `[]` on all **thirteen** checkpoints.
- ⛔ It does **not** unblock or begin **P7**, which stays `BLOCKED` / `NOT_STARTED`.
- ⛔ It enables **nothing in production**. **M13 ships dark:** zero production importers of the new surface; no brake console, no admin UI, no dashboard, no Slack/email/SMS/voice brake command, no production Sev-0 detector wiring, no autonomous operation, no freight workflow.
- ⛔ It grants **no autonomy** and moves **no money**.
- ⛔ It mints **no** event contract, **no** gate decision, and registers **no** production policy gate. The production `GateRegistry` population stays **EMPTY** until U8.1/P8.
- ⛔ It resolves **no** open validation: **V13** (who engages), **V14** (who releases) and **V15** (auto-engage on repeated unknowns) stay **OPEN at their fail-closed defaults**.
- ⛔ It closes **no** carried residual.
- ⛔ It is **not** a CI green, and no sentence in this document says it is.

### **THE EXACT NEXT PROGRAM ACTION IS P6 PHASE ACCEPTANCE / FINAL ADJUDICATION, BY A REVIEWER WHO DID NOT BUILD THE PHASE.** That is tier-1 under [`CLAUDE.md`](../../CLAUDE.md) §7 and it is the one place the independent-review requirement is about a **phase** rather than a diff. **It is not P7 implementation.**

---

*Evidence: `/Users/sammyfammy/neyma-product-driver/runs/20260905-230030/accepted/` — `independent-review.json`, `decision.json`, `completion-audit.json`, `scoped-completion.json`, `suite-result.json`, `task-scope.json`, `record.json`, `git-status.txt`, `git-diff-stat.txt`; and `../FOUNDER-SUMMARY.md`. CI: GitHub Actions run `34162327327`.*

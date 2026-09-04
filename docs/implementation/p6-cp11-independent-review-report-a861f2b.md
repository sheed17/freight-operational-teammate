> # ⛔ HISTORICAL REVIEW — NOT CURRENT AUTHORITY
> **This is evidence of a past moment, not status.** It is an INDEPENDENT REVIEW: it set no
> acceptance criterion, marked no phase complete, closed no risk, enabled nothing and authorized no
> external effect. It reviewed machine **M11 — the Policy** at commit
> `a861f2b469f8cf0572e9a02cef73ac20dec1476f` (tree `76bb8d1dd747c2bca5641cfba7e92bc8fa123570`,
> branch `p5/u5-1-g2-spec-correction`, working tree clean) and returned **SUPPORTED, confidence
> 0.90, findings `0`, adjudications `0`, criteria `11/11 PASS`, `blocked_on.kind: NONE`**.
>
> ### **THE REVIEWED TREE AND THE LANDING CANDIDATE ARE THE SAME TREE.** Unlike `P6-CP-10`, whose
> review was bound to `a43feae` while the candidate was `a833074`, this review's
> `reviewed_fingerprint` is `a861f2b469f8/76bb8d1dd747/-` — byte-for-byte the commit this landing
> records. There is no post-review correction to keep apart, and `P6-D68`'s gap does not recur here.
>
> ### **IT DID NOT REVIEW THE COMMIT THAT CARRIES IT.** The landing commit that brought this file
> in-tree did not exist when the review was performed.
>
> ### **FIVE DIFFERENT THINGS ARE KEPT APART IN THIS DOCUMENT AND MUST NOT BE COLLAPSED.**
> (1) the **builder implementation** at `20cec74`, by builder session `40ba7a0d`;
> (2) **Product Driver scenario verification** — 5/5 required scenarios, 845 assertions, 0 failed;
> (3) the **focused independent review by a non-builder session** `c53eefbf`, recorded here;
> (4) **GitHub CI**, run `33856703548`, which concluded **`cancelled`** and is not green; and
> (5) the **founder landing decision** that this checkpoint lands on the evidence that exists
> despite (4). ### **(5) IS A DECISION, NOT A VERIFICATION**, and nothing here presents it as one.
>
> ### **P6-CP-11 IS A CHECKPOINT, NOT A PHASE ACCEPTANCE.** P6 is **NOT COMPLETE**, no P6 acceptance
> criterion is scored, `criteria_scored` is `[]` on all eleven checkpoints, P7 stays **BLOCKED /
> NOT_STARTED**, and M11 continues to **ship dark**.
>
> ### **NO ADJUDICATION FOLLOWED THIS REVIEW, AND NONE IS OWED.** M11 is tier-1 under
> [`CLAUDE.md`](../../CLAUDE.md) §7 — it lands a migration, it is load-bearing for tenant isolation,
> and **it widens a safety guard**. That requires builder + **one** focused independent review by
> someone who did not write it, mutation proof that the guard can fail, and CI. The adjudication
> chains and finalizer rituals cited by the `P6-CP-1` and `P6-CP-2` records were retired in the
> 2026-08 engineering-process simplification and must not be revived.
>
> ### **CI DID NOT CONCLUDE `SUCCESS`, AND THIS RECORD DOES NOT PRETEND OTHERWISE.** Run
> `33856703548` concluded **`cancelled`**. **Neither full suite completed**, and neither reached
> M11's own tests. §8 states both halves exactly. Read it before citing this document as evidence of
> a green repository.

# P6-CP-11 — FOCUSED INDEPENDENT REVIEW — M11, the Policy, at `a861f2b`

**Verdict: `SUPPORTED` · confidence `0.90` · findings `0` · adjudications `0` · criteria `11/11 PASS`**

| | |
|---|---|
| **Reviewed tree** | commit `a861f2b469f8cf0572e9a02cef73ac20dec1476f`, tree `76bb8d1dd747c2bca5641cfba7e92bc8fa123570`, branch `p5/u5-1-g2-spec-correction`. The review record's `reviewed_fingerprint` reads **`tracked_dirty: 0`, `untracked: 0`**, identity `a861f2b469f8/76bb8d1dd747/-` |
| **Reviewer** | session `c53eefbf-b2e0-474c-8240-31d0aa3b41b9`, `inherited_builder_context: false` |
| **Builder** | session `40ba7a0d-e4b3-4c4c-904d-151317e16696` — a different session. A build session may not review its own work ([`CLAUDE.md`](../../CLAUDE.md) §7/§11) |
| **Evidence** | `evidence_reproduced: true`, `claimed_evidence_reproduced: true`. The reviewer **executed the product**; six declared commands, all of which ran |
| **Product Driver run** | `20260904-074315`, accepted artifacts under `runs/20260904-074315/accepted` |
| **Scope** | `P6/M11`. `parent_phase_accepted: false`. `task_result: VERIFIED`, `task_outstanding: []` |

---

## 1. The verdict, verbatim

> *"P6/M11 (the Policy machine) is what it claims to be at HEAD a861f2b (clean tree 76bb8d1d). I
> reproduced the unit's runtime evidence myself — probe "behaviours as specified, 0 wrong" with
> problems:[], mutation battery 34/34 caught with the anti-vacuity control GREEN, 88 targeted pytest
> passing plus 10 tenant-posture — and independently verified the load-bearing safety structures from
> source rather than trusting the builder's probe: the migration DDL carries the never-null 4-member
> gate CHECK, the 7-state CHECK, the activated_by FK into tenant_humans with the ACTIVE-requires-
> activator CHECK, the narrowing-only-expiry CHECK, the no-admin-path CHECK, the no-delete/identity/OCC
> triggers and the one-active-per-scope / tenant-version / Policy-Owner-singularity unique indexes; the
> machine imports checkpoint.GateDecision and mints no gate (a scan of all 123 production modules
> returns checkpoint.py as the sole gate minter); confidence is structurally absent from the evaluator
> inputs and a MODEL_INFERRED/confidence/unmodelled predicate fails to compile; and the module ships
> dark with zero production importers. … This is a focused independent review of the M11 increment by
> a session that did not build it; it does NOT score any P6 phase acceptance criterion and does not
> change P6's IN_PROGRESS state."*

`findings: []`. `adjudications: []`. `blocked_on: {kind: NONE}`. **Everything in §7 below was
identified at this landing and is not a reviewer finding.**

---

## 2. What M11 is, in one line

**M11 is the tenant's posture — what Neyma may do alone, for whom, up to what caps — as a row a
named human owns, versioned and scoped, evaluated at checkpoint step 6.** Seven canonical states
(`DRAFT`, `PROPOSED`, `APPROVED`, `ACTIVE`, `SUPERSEDED`, `REVOKED`, `EXPIRED`), seven transitions
`PO-1`…`PO-7`, the **eight already-registered F11 contracts and no ninth**.

### **THE WHOLE POINT IS THAT A POSTURE IS A VALUE, NOT A PROMPT.** [`CLAUDE.md`](../../CLAUDE.md) §3
says it in one line — *"Policy: typed, compiled rules governing admission. A prompt string is not a
policy."* A brokerage decides that Neyma may book a carrier alone up to $2,500 but never pay one.
If that lives in a prompt, nobody can say what was in force when a decision was made, nobody can
prove who agreed to it, and a re-worded sentence silently changes what the system is allowed to do.
M11 makes it a `policies` row with a never-null `gate_decision`, a monotonic `policy_version`, an
`activated_by` foreign key into a real human, and permanent retention — so *"what was Neyma allowed
to do on 14 August, and who said so"* is a query.

### **AND A POSTURE THAT COULD LOOSEN ITSELF WOULD BE WORSE THAN NO POSTURE.** A tenant policy may
only **NARROW** the product ceiling. That is enforced over a **declared total order** across the
four gate members, never a string comparison — `AUTONOMOUS_WITHIN_CAPS` sorts alphabetically *before*
`HUMAN_APPROVAL_REQUIRED`, so a naive `<` would read the most dangerous broadening in the system as a
narrowing. Two mutants exercise exactly that pair, and both are caught.

### **NOTHING BROADENS BY ITSELF, INCLUDING TIME.** A narrowing policy's expiry **broadens** authority
when it fires, so `PO-7` does not quietly restore the wider posture: it names an M9
human-confirmation seam and **leaves it unwired**, and the `CHECK` that only a narrowing policy may
carry an expiry is in the database. A clock may take authority away; a clock may never give it.

### **M11 IS CHECKPOINT STEP 6 AND NEVER A SECOND GATE.** `policy.py` imports
`checkpoint.GateDecision` and constructs **no** `GateEntry` and **no** `GateRegistry`. A policy
change is itself an M2 action class with `HUMAN_APPROVAL_REQUIRED` — there is no admin path — and a
policy version change voids in-flight M4 approvals and makes an unclaimed grant unclaimable through
P3's existing claim CAS, which already revalidates `policy_version` and already names
`POLICY_CHANGED`. **M11 drove those seams; it rebuilt none of them.**

---

## 3. One tenant-first table enters the canonical partition

`policies` — recorded in [`CURRENT.md`](CURRENT.md)'s tenant-first partition as **P6 tenant — M11 (1)**
and in [`phase-0-baseline-manifest.yaml`](phase-0-baseline-manifest.yaml)'s REG-1 classification.

### 3.1 The load-bearing DDL was introspected LIVE at this landing, not read

A fresh canonical database built the way production builds one (`create_canonical_schema` +
`enable_and_verify_foreign_keys`) returned:

| Measured | Value |
|---|---|
| `PRIMARY KEY` | `['tenant', 'policy_id']` — **tenant-first** |
| Columns | 22 |
| Indexes | **4**, and **4 of 4 lead with `tenant`** |
| `state` vocabulary | `ACTIVE, APPROVED, DRAFT, EXPIRED, PROPOSED, REVOKED, SUPERSEDED` — **exactly seven, no eighth** |
| `gate_decision` vocabulary | `AUTONOMOUS_WITHIN_CAPS, FORBIDDEN, HUMAN_APPROVAL_REQUIRED, PERMANENT_HUMAN_ASSERTION_REQUIRED` — **exactly four** |
| `gate_decision` nullability | **`NOT NULL`** (F-20, the never-null gate) |
| Policy Owner singularity | `CREATE UNIQUE INDEX ix_tenant_humans_one_active_policy_owner ON tenant_humans (tenant) WHERE authority_role = 'POLICY_OWNER' AND state = 'ACTIVE'` — **tenant-scoped** |

### 3.2 The invariants were proven by ATTEMPTING THE VIOLATION — with the population proved first

### **TWO POSITIVE CONTROLS RAN BEFORE ANY NEGATIVE ONE, AND BOTH WERE ACCEPTED** — a well-formed
`DRAFT` policy in tenant `T_A`, and the same scope in tenant `T_B`. Without them the eight refusals
below would be the vacuous-negative false green [`CLAUDE.md`](../../CLAUDE.md) §6 exists to catch.

### **AND THE FIRST ATTEMPT AT THIS BATTERY *WAS* THAT FALSE GREEN, WHICH IS WHY IT IS RECORDED.**
A first run reported "8/8 refused" while **both positive controls failed**: every refusal came from
an unrelated `scope_kind` `CHECK` the fixture had not satisfied, so the battery policed nothing and
said so in the shape of a pass. The fixture was corrected until the population was proved, and only
then were the refusals counted. **Eight illegal inserts, eight refusals, each by the named constraint
under test:**

| Attempted | Refused by |
|---|---|
| a null gate decision | `NOT NULL constraint failed: policies.gate_decision` |
| an invented gate member `AUTONOMOUS` | `CHECK … gate_decision IN (the four)` |
| an eighth state `NARROWED` | `CHECK … state IN (the seven)` |
| an eighth state `SUSPENDED` | `CHECK … state IN (the seven)` |
| an author who is not a recorded human | `FOREIGN KEY constraint failed` |
| an author from **another tenant** | `FOREIGN KEY constraint failed` |
| an `ACTIVE` policy with **no activator** | `CHECK … state <> 'ACTIVE' OR activated_by IS NOT NULL` |
| a reused `policy_version` inside one tenant | `UNIQUE … policies.tenant, policies.policy_version` |

### **AND THE POLICY OWNER SINGULARITY WAS PROVEN THE SAME WAY, WITH ITS NO-COUPLING CONTROL.** A
second `ACTIVE` `POLICY_OWNER` inserted into one tenant is **refused** — `UNIQUE constraint failed:
tenant_humans.tenant` — while the control shows **two tenants each holding their own**. That is the
difference between *"one Policy Owner per brokerage"* and *"one Policy Owner in the world",* and it
is the whole of `P6-D72` (§7).

The Product Driver run's own battery went further on the same tree, adding refusals this landing did
not re-attempt: an activator from another tenant, an `ACTIVE` policy naming another tenant's
approval, **the ungoverned raw insert** (`CHECK … state NOT IN (governed) OR (approval_id IS NOT NULL
AND diff_fingerprint IS NOT NULL)` — the no-admin-path constraint), a second `ACTIVE` policy for one
`(tenant, scope)`, the OCC version-advance trigger, and a `DELETE`, which the retention trigger
refuses outright.

### 3.3 The event contracts, measured

- **118 registered contracts** — **the identical total recorded at the `P6-CP-10` landing.**
  ### **M11 MINTED NO EVENT CONTRACT AT ALL**, which is the strongest possible form of rule 17
  compliance: the eight F11 contracts it emits were already registered by the 2026-08-12 P5 U5.2
  founder/architect amendment.
- **F11 is exactly eight**, from `events/registry.md` §3: `PolicyProposed`(PO-1),
  `PolicySubmitted`(PO-2), `PolicyApproved`(PO-3), `PolicyActivated`(PO-4), `PolicySuperseded`(PO-5),
  `PolicyRevoked`(PO-6), `PolicyExpired`(PO-7), `PolicyVersionChanged`‡(PO-4/6). All eight are
  registered; `policy.py`'s `Policy*` event-name literals are **exactly those eight and nothing else**.
- **`PolicyEvaluated` is registered, and it is NOT F11's.** Its family is **F2**, aggregate
  `pipeline_instance` — M2's coordination contract. A mutant that makes M11 emit it as though it were
  M11's is caught.
- **`PolicyOverridden` is NOT registered** — confirmed against the live contract registry. That is
  `P6-D71`, `BLOCKED_AUTHORITY`, and M11 leaves it exactly as it found it.

### 3.4 The transition arithmetic, re-derived rather than carried

Re-derived at this landing by parsing §14 of **every** machine file and counting rows — discovery,
never an enumerated list: **13 files discovered, 134 rows counted.** M1 14 + M2 25 + M3 13 + M4 11 +
M5 8 + M6 11 + M7 7 + M8 8 + M9 7 + M10 9 + **M11 7** = **120 written and landed**, so **14 remain**,
and those 14 are exactly **M12's 9 and M13's 5**. The figure this document carries is the one that
was measured, not the `21` that was correct until this landing.

---

## 4. What the reviewer established ITSELF, and how

Six declared commands, **all six ran** — no harness refusal at any layer, which is the first P6
landing since `P6-CP-4` where that is true (§7).

| Command | What it showed |
|---|---|
| `probe_phase6_policy.py --all` | `behaviours as specified, 0 wrong`, `problems: []`, `modules that MINT a gate decision: ['checkpoint.py']`, `production importers of policy: []` |
| `mutate_phase6_policy.py` | **34/34 mutants caught, 0 escaped**, anti-vacuity control **GREEN** |
| `pytest` M11 + null-gate + errata + false-green | **88 passed** |
| `pytest test_phase0_tenant_posture.py` | **10 passed** |
| an AST scan of all production modules | **123 modules scanned**; `modules that MINT a gate decision: ['checkpoint.py']` — `policy.py` absent |
| `git diff --stat 20cec74 a861f2b -- <the six M11 files>` | **empty** — the M11 implementation is byte-identical from the build commit to the reviewed head; the three later commits are status-only |

### **THE LANDING SESSION RE-EXECUTED ALL OF IT ON THE COMMITTED TREE, AND ADDED ITS OWN DENOMINATORS.**
`probe --all` → `behaviours as specified, 0 wrong`; the battery → `34 mutations caught, 0 escaped`
with the anti-vacuity control GREEN; the five targeted suites → **98 passed**; and
`git status --porcelain` **empty afterwards**, with no `policy_shadow.py` stranded.

### **THE SHIP-DARK SCAN WAS REBUILT AT THIS LANDING BECAUSE THE FIRST VERSION LIED.** A
last-path-segment import matcher reported three production importers of `policy` —
`imap_mailbox`, `inbox_discovery`, `packet_page`. **All three import Python's standard-library
`email.policy`.** The scanner was narrowed to resolve **intra-package edges only** (relative
imports, or absolute `freight_recon.*`), which is the whole-token discipline
[`CLAUDE.md`](../../CLAUDE.md) §6 requires. Re-measured over a discovered population:

- **123 production modules scanned**
- `PRODUCTION IMPORTERS OF policy (direct, intra-package): []`
- `PRODUCTION MODULES WHOSE IMPORT CLOSURE REACHES policy: []`
- **anti-vacuity control: the same scanner finds 8 importers of `checkpoint`** — so the empty result
  is a fact about `policy`, not a broken scanner
- `policy.py`'s own intra-package imports: `checkpoint`, `event_contracts`, `event_envelope`,
  `event_inbox`, `event_outbox`, `phase6_policies`, `tenant` — **no brake, no exception machine, no
  timer service, no channel**

### **AND THE GATE-MINT BOUNDARY WAS MEASURED AT THE CONSTRUCTION SITE, NOT AT THE MODULE.** Across
all 123 modules there is **exactly one** `GateEntry`/`GateRegistry` construction anywhere in the
package: **`checkpoint.py:242`**, the kernel's own `GateRegistry._DEFAULT` fallback. **Zero
`GateRegistry` constructions exist**, so the production registered-action-class population is
structurally **EMPTY** — unchanged since `P6-CP-3`, and unchanged by M11.

---

## 5. What Product Driver independently exercised

**5/5 required scenarios PASSED — the permanent `p6_m11_policy` plus four generated — 845 assertions,
0 failed, 0 blocked, 0 skipped**, `assembly_problems: []`, `evidence_verified: true` on every one.

| Scenario | Origin | Risk category | Assertions |
|---|---|---|---|
| `p6_m11_policy` | permanent | — | 789 |
| `S1` | generated | `safety_invariant` — *"Two ACTIVE POLICY_OWNER rows remain insertable"* | 13 |
| `S2` | generated | `stale_state` — *"A scope-local void leaves stale in-flight authority"* | 14 |
| `S3` | generated | `idempotency` — *"Re-running the migration duplicates/omits"* | 16 |
| `S5` | generated | `authorization` — *"M11 introduces an admin role / superuser path"* | 13 |

`coverage_summary`: proposed 6, **accepted 4**, filtered 2, invalid 0, **`uncovered_risks: []`** —
every declared risk category is still established by an accepted scenario (`P6-D80`).

The run's `scoped_completion` reads `task_result: VERIFIED`, `task_outstanding: []`,
`parent_phase_accepted: false`, and its `does_not_imply` list names exactly what this landing also
refuses to claim: that P6 is COMPLETE, that any criterion is scored, that P7 is unblocked, or that
anything is enabled in production. `decision.json` reads `ACCEPT` with `problems: []`.

---

## 6. The eleven criteria the reviewer assessed

All **PASS**; none `CANNOT_DETERMINE`.

1. M11 is a real machine — seven canonical states, seven transitions `PO-1`…`PO-7` (AC-MACH-1101…1107).
2. **F-20 / never-null gate** — `gate_decision` `NOT NULL`, constrained to the four canonical members.
3. **Safety invariant** — a tenant policy may only NARROW the product ceiling, via a declared total
   order, never a string compare.
4. **GR-8 / M-49** — the predicate references only deterministic, modelled, non-inferred inputs;
   `MODEL_INFERRED` **fails to compile**.
5. **Authorization** — only an authenticated human in `tenant_humans` can activate; no model,
   automation, retry, timer or inbound path can.
6. **Determinism (M-50)** — byte-identical `PolicyDecision`; no wall clock, no randomness, no model;
   never-null decision; **no allow-on-error default**.
7. **Rule 17 / mint boundary** — M11 is checkpoint step 6, mints no gate, builds no second checkpoint;
   `checkpoint.py` stays the sole minter.
8. **Ships dark** — no production importer; no channel, editor or admin surface; M12/M13 not built;
   nothing graduates.
9. **F11 event integrity** — exactly eight registered F11 contracts, no ninth minted;
   `PolicyEvaluated` is F2/M2's; strict ordering declared.
10. **Tenant isolation and no admin path** — tenant-first keys and indexes, one active per
    `(tenant, scope)`, tenant-local versioning.
11. **Status honesty** — no claim of landing, phase acceptance, or production enablement; P6 stays
    `IN_PROGRESS`.

---

## 7. Minor and nonblocking items — recorded, not actioned

### **THE INDEPENDENT REVIEW RETURNED ZERO FINDINGS.** Everything below was identified **at this
landing** from the run's own structured evidence, the M11 source, the specification corpus and the CI
record. **None is a reviewer finding and none may be cited as one.** Each is recorded, not actioned
([`CLAUDE.md`](../../CLAUDE.md) §13). None can produce a wrong customer outcome, violate an invariant,
or make a later phase unsafe, and the machine ships dark. They are carried as `P6-D76`…`P6-D81`.

- **`P6-D76`** — no green CI conclusion, and **no CI execution of M11's tests on either interpreter**.
- **`P6-D77`** — CI runs no M11 probe or mutation job, and **the mitigating sentence available at
  `P6-CP-8`, `P6-CP-9` and `P6-CP-10` is NOT available here**, because no full suite completed.
- **`P6-D78`** — of the two guards that read the widened `GATE_RUNTIME_MODULES`, only one is inside a
  CI job that concluded `SUCCESS`.
- **`P6-D79`** — two stale harness snapshots in the accepted run.
- **`P6-D80`** — two of six proposed generated scenarios were filtered at assembly.
- **`P6-D81`** — four neighbour-guard comments asserted *"M11 LANDED"* before the landing existed.

### **TWO CARRIED RESIDUALS NAME `closes_at: M11`, AND M11 CLOSES BOTH — STATED WITH THE EVIDENCE
RATHER THAN MOVED QUIETLY.**

**`P6-D72` — the Policy Owner singularity — is CLOSED.** The finding was that
`entities/14-policy.md` point 7 requires *"exactly one named Policy Owner per tenant"* (I1) while M1's
landed `tenant_humans` carried **no constraint limiting a tenant to one ACTIVE `POLICY_OWNER`**, so
two were insertable. M11's own migration adds
`ix_tenant_humans_one_active_policy_owner ON tenant_humans (tenant) WHERE authority_role =
'POLICY_OWNER' AND state = 'ACTIVE'`. The row's disposition warned that *"a constraint added to an
M1-landed table is a MIGRATION on a tenant-isolation-bearing table — CLAUDE.md §7 tier 1"*, and that
is how it was treated: it is inside the tier-1 review above, it was proven at this landing by
**attempting the violation with a no-coupling control**, and **two mutants** prove the guard can fail
— one dropping `UNIQUE`, one dropping `tenant` so that a single `POLICY_OWNER` would become globally
unique and a second brokerage could not name its own. **No second user or authority system was
invented:** `tenant_humans` remains the one record of human authority, and `AUTHORITY_ROLES` is still
`('POLICY_OWNER', 'AUTHORIZED_HUMAN')` in M1's migration, unchanged.

**`P6-D74` — the gate-runtime allowlist — is CLOSED, and it is the reason this unit is tier-1.** The
row recorded, before the question was reached, that `GATE_RUNTIME_MODULES` was a fixed three and that
M11 might collide with it, naming two honest routes. **M11 took route (a):** `policy.py` and
`phase6_policies.py` join the set, because a policy's whole content **is** a gate decision and a
machine that could not NAME one could not hold one. ### **WIDENING A SAFETY GUARD IS THE ONE ACT
[`CLAUDE.md`](../../CLAUDE.md) §7 SINGLES OUT, AND THE PRICE WAS PAID IN FULL.** The widening carries
its narrowing in the same file: `test_only_the_checkpoint_kernel_may_MINT_a_gate_decision` proves by
AST that **neither new module constructs a `GateEntry` or a `GateRegistry`** — carrying a decision and
minting one are different acts. The narrowing is not a decoration: **a mutant that makes `policy.py`
construct a `GateRegistry` is caught.** The second reader,
`test_typed_policy_runtime_exists_only_with_its_canonical_authority`, asserts the **observed** carrier
set **equals** the permitted set, so the two entries could not have been added without the modules
actually being carriers. And the invariant the row said must survive, survives, measured above:
`checkpoint.py` is the sole minter, and the production `GateRegistry` population is **EMPTY**.

### **THREE CARRIED RESIDUALS THAT M11 DOES *NOT* CLOSE — STATED RATHER THAN LET PASS.**

- **`P6-D71` (`PolicyOverridden`) stays OPEN, `BLOCKED_AUTHORITY`.** Verified at this landing: the
  name is **absent from the 118 registered contracts**. M11 builds no override mechanism at all —
  not an event, not a field, not a code path. Minting an event is a founder/architect act; the
  obligation lands with M12/Rule. **`M11-AQ-4` is the same question and is equally untouched.**
- **`P6-D73` (M9's `exceptions.source_kind = 'policy'` with no FK) stays OPEN.** M11 creates the
  referent and **deliberately does not retro-wire the FK**, on M10's landed precedent for
  `compensation`. Verified: `policy` is still in `SOURCE_KINDS_WITHOUT_TABLE`, and
  `phase6_exceptions.py` is **byte-unchanged** across the entire M11 range. `PO-7` names its M9
  escalation seam and leaves it **UNWIRED** — `policy.py` imports no exception machine. Wiring a seam
  is precisely what shipping dark forbids. Its `closes_at` marker is unchanged.
- **`P6-D75` (nothing cross-checks an entity's "Events emitted" list against the event registry) stays
  OPEN.** It closes at a session that owns the phase-0 spec-corpus probes, not at M11.

### **AND FIVE M11 AUTHORITY QUESTIONS WERE SETTLED IN THE CANON BEFORE THE BUILD, NOT BY IT.**
`M11-AQ-1`, `-2`, `-3`, `-5` and `-6` were corrected in the canonical corpus by the authority
reconciliation pass at `5d2d8e1`, which changed no file under `src/`, `eval/`, `scripts/` or
`.github/`. They carry no debt and are not re-litigated here. `M11-AQ-7` is `P6-D72` (closed above);
`M11-AQ-8` is `P6-D73` (answered by precedent, seam left unwired); `M11-AQ-4` is `P6-D71` (open).
**`V11` and `V12` stay OPEN validation at their fail-closed defaults.** Enforcing Policy Owner
singularity **is** `V12`'s default; it does **not** resolve `V12`, and this record does not claim it
does.

### **`P6-D40` IS CARRIED FORWARD UNCHANGED AND WAS NOT RE-VERIFIED AT THIS LANDING.** No mutation
battery was run against the status guards here and none is claimed.

---

## 8. ### CI — the honest record. The workflow did NOT conclude `SUCCESS`

Run **`33856703548`** on the landing candidate `a861f2b` concluded **`cancelled`**, and **`cancelled`
is not `success`**. Anyone citing this landing as "CI green" is citing it wrongly.

| Job | Conclusion |
|---|---|
| *Safety invariants (fast)* | **SUCCESS** |
| *P6/M3 effect-grant probe + mutation* | **SUCCESS** |
| *Full test suite (py3.11)* | **CANCELLED** at the ~60-minute workflow/runtime ceiling, ~53%, **no pytest failure marker emitted** |
| *Full test suite (py3.12)* | **CANCELLED** at the ~60-minute workflow/runtime ceiling, ~53%, **no pytest failure marker emitted** |
| *Risk radar* | **SKIPPED** — pull-request-only |

The package **imported successfully on both interpreters** before pytest began.

### **NO PRODUCT FAILURE WAS DEMONSTRATED BY CI, AND NO FULL SUITE MAY BE CALLED PASS.** Both
statements are true and both are stated. Neither cancelled suite emitted a failure marker, so nothing
in this run is evidence of an M11 defect; and neither completed, so neither is evidence of a green
one. **This is the second-weakest CI position of any P6 landing** — weaker than every landing since
`P6-CP-7` in that **no full suite completed on either interpreter**, and stronger than `P6-CP-7` only
in that *Safety invariants (fast)* concluded SUCCESS rather than being cancelled at its own ceiling.

### **AND CI NEVER REACHED M11'S TESTS — MEASURED, NOT ASSUMED.** `pytest eval --collect-only`
collects **3223** tests on this tree, and `eval/tests/test_phase6_policy.py` occupies positions
**2620–2676** — **81.3%–83.0%** of the run, **57 tests**. A job cancelled at ~53% stopped long before
them. The honest statement is not "no verdict" but **"no execution": the repository has no CI run of
M11's 57 tests on this commit, on either interpreter** (`P6-D76`).

### **BUT THE SAFETY SURFACE M11 WIDENED *DID* EXECUTE IN CI, AND THAT IS THE LOAD-BEARING HALF.**
This is not a general reassurance; it is a specific one, and its limit is stated with it. The *Safety
invariants (fast)* job that concluded **SUCCESS** names **26 files**, and two of them matter here:

- **`eval/tests/test_phase0_null_gate.py`** — which carries **both**
  `test_the_typed_gate_population_is_now_non_empty_and_confined_to_the_checkpoint_kernel` (the guard
  that uses `GATE_RUNTIME_MODULES` as its allowlist) **and**
  `test_only_the_checkpoint_kernel_may_MINT_a_gate_decision` (the narrowing that keeps the widening
  honest). ### **So the tier-1 guard M11 widened ran to completion in CI and passed.**
- **`eval/tests/test_phase0_tenant_posture.py`** — the tenant-first posture guard, which is where a
  new canonical table that failed to declare itself would turn red.

### **THE LIMIT: THE SECOND READER OF THE WIDENED BOUNDARY HAS NO CI RESULT.**
`eval/tests/test_phase0_errata_guards.py` — which carries
`test_typed_policy_runtime_exists_only_with_its_canonical_authority`, the guard asserting that the
**observed** carrier set **equals** `GATE_RUNTIME_MODULES` — is **not among the Safety job's 26
files**, and both full suites stopped before it could run inside `pytest eval`. It passed locally at
this landing inside the 98, and that is a local result, not a CI one (`P6-D78`).

### **CI RUNS NO M11 PROBE OR MUTATION JOB.** Verified mechanically: the count of `phase6_policy`
occurrences in `.github/workflows/ci.yml` is **ZERO**. M3 remains the only P6 machine with a
dedicated probe/mutation job. ### **AND UNLIKE `P6-CP-8`, `P6-CP-9` AND `P6-CP-10`, THE MITIGATING
SENTENCE IS NOT AVAILABLE HERE** — at those landings a completed full suite had at least executed the
machine's own tests. Here none did (`P6-D77`).

### **THE JOB CONCLUSIONS ABOVE WERE SUPPLIED BY THE FOUNDER AND COULD NOT BE RE-READ AT THIS LANDING.**
`gh run view 33856703548` fails from this sandbox with `tls: failed to verify certificate: x509:
OSStatus -26276` — the identical failure recorded at every landing since `P6-CP-5`. A later session
with network access should read run `33856703548` itself rather than trust this transcription.

### **THE FOUNDER LANDING DECISION, RECORDED AS A DECISION AND NOT AS A VERIFICATION.** The founder
chose to land M11 on the evidence that exists, treating both suite cancellations as **non-product CI
runtime limitations** rather than as evidence of an M11 defect. That is the same decision recorded at
`P6-CP-4`, `P6-CP-5`, `P6-CP-6`, `P6-CP-7`, `P6-CP-8`, `P6-CP-9` and `P6-CP-10`, and it is the fifth
of the five things §0 of this document keeps apart. **It closes only by a CI run on this branch that
concludes `SUCCESS`** (`P6-D76`).

---

## 9. What did NOT change

Measured across the entire M11 range `20cec74~1..a861f2b`, by comparing git object hashes rather than
by reading:

- **Every M1–M10 machine file is byte-identical**, and so is the P3 kernel:
  `checkpoint.py`, `work_item.py`, `pipeline_instance.py`, `external_effect.py`, `approval.py`,
  `observation.py`, `identity_binding_claim.py`, `conflict.py`, `expectation.py`, `exception.py`,
  `compensation.py`, `brake.py`.
- **The only migrations touched are M11's own** — `phase6_policies.py` (new) and the P2 walk
  `phase2_tenant_first.py`. `phase6_exceptions.py` and `phase6_work_items.py` are byte-unchanged.
- **`.github/` is unchanged.** No CI workflow was edited by M11 or by this landing.
- **No M12 and no M13 exist**: `rule.py`, `phase6_rules.py`, `brake_lifecycle.py` and
  `phase6_brakes.py` are all **absent**. (`brake.py` is P3's landed kernel brake, not M13.)
- **The registered contract total is unchanged at 118.** M11 minted nothing.
- **Nothing is enabled in production.** Zero production importers of `policy`; the production
  `GateRegistry` population is EMPTY; no channel join; no timer service; no admin console, editor or
  policy-authoring surface.

### **WHAT THE BUILD COMMIT DID CHANGE OUTSIDE M11'S OWN FILES, AND WHY IT IS NOT A REBUILD.** Five
neighbour test files (`test_phase6_approval.py`, `test_phase6_compensation.py`,
`test_phase6_conflict.py`, `test_phase6_exception.py`, `test_phase6_expectation.py`), plus
`test_bootstrap_hermeticity.py` and `test_phase3_schema.py`, carried **forward-looking assertions that
`policies` does not exist** — true when written, false the moment M11's migration exists. Each was
**narrowed, not deleted**, under [`CLAUDE.md`](../../CLAUDE.md) §5 rule 20, which is the same
correction M6's forbidden set received when M7 landed and M7's received when M8 landed. **The
still-unbuilt neighbours stay asserted-absent**: `rules` (M12) and `evidence` (P7) remain in every
forbidden set. No neighbour machine's runtime moved.

> # ⛔ HISTORICAL REVIEW — NOT CURRENT AUTHORITY
> **This is evidence of a past moment, not status.** It is an INDEPENDENT REVIEW: it set no
> acceptance criterion, marked no phase complete, closed no risk, enabled nothing and authorized no
> external effect. It reviewed machine **M12 — the Rule** and returned **SUPPORTED, confidence
> 0.90, findings `0`, adjudications `0`, criteria `8/8 PASS`, `blocked_on.kind: NONE`**.
>
> ### **THE REVIEWED CONTENT AND THE LANDING CANDIDATE ARE NOT THE SAME COMMIT, AND THAT IS STATED
> RATHER THAN GLOSSED.** The reviewer operated the **working tree at `54193f75ee838cdd567efb5a29c9e4630754934c`
> (tree `64a6f934f83153440ad6224cc0e2f8f37fad73cb`) plus exactly seven modified files, zero
> untracked** — the content committed moments later as
> `019a43d6f21625dae3fc3c8e7c8433866eb44a50`. The landing candidate is
> `99831ae0dfcbb8e4606294443fb4a5ce8f451ddd`, a post-push CI correction. This is the `P6-D68` class
> and it recurs here.
>
> ### **BUT THE GAP IS BOUNDED MECHANICALLY, AND THE BOUND IS THE STRONGEST AVAILABLE.** The `src/`
> tree is **byte-identical at `019a43d` and at `99831ae`** —
> `a6fa4d8d27b73606b6e2a0217ccad83ada3a804a` at both. **The reviewed M12 runtime IS the landed M12
> runtime.** The correction touched only `eval/` and `scripts/`. Separately, the run's recorded
> `git-diff-stat.txt` for its seven dirty files is **byte-identical** to
> `git diff --stat 54193f7 019a43d` — which is how "the reviewed working tree is `019a43d`'s
> content" is established rather than assumed.
>
> ### **IT DID NOT REVIEW THE COMMIT THAT CARRIES IT.** The landing commit that brought this file
> in-tree did not exist when the review was performed.
>
> ### **FIVE DIFFERENT THINGS ARE KEPT APART IN THIS DOCUMENT AND MUST NOT BE COLLAPSED.**
> (1) the **builder implementation** at `54193f7`, by builder session `2d159710`;
> (2) **Product Driver scenario verification** — 11/11 required scenarios, 15/15 passed, 1037
> assertions, 0 failed;
> (3) the **focused independent review by a non-builder session** `22551bfc`, recorded here;
> (4) **GitHub CI**, runs `33942518450` (which found **nine real py3.11 failures**) and
> `33948926997` (the corrected push), the latter of which concluded **`cancelled` overall**; and
> (5) the **founder landing decision** that this checkpoint lands on the evidence that exists.
> ### **(5) IS A DECISION, NOT A VERIFICATION**, and nothing here presents it as one.
>
> ### **P6-CP-12 IS A CHECKPOINT, NOT A PHASE ACCEPTANCE.** P6 is **NOT COMPLETE**, no P6 acceptance
> criterion is scored, `criteria_scored` is `[]` on all twelve checkpoints, P7 stays **BLOCKED /
> NOT_STARTED**, and M12 continues to **ship dark**.
>
> ### **NO ADJUDICATION FOLLOWED THIS REVIEW, AND NONE IS OWED.** M12 is tier-1 under
> [`CLAUDE.md`](../../CLAUDE.md) §7 — it lands a migration, it is load-bearing for tenant isolation,
> and it decides whether an action is allowed inside the checkpoint. Tier 1 asks for builder
> evidence, **one** focused independent review by someone who did not write it, mutation proof that
> the guard can fail, and CI. That is a single review, not a chain of sessions. **No finalizer, no
> adjudication, no committed receipt, no clean-clone ceremony and no preserve ref is owed for this
> landing, and a session must not run one.**

# P6-CP-12 — FOCUSED INDEPENDENT REVIEW — M12, the Rule, at `019a43d` (landed at `99831ae`)

| | |
|---|---|
| **Machine** | M12 — the Rule |
| **Checkpoint** | `P6-CP-12` |
| **Build commit** | `54193f75ee838cdd567efb5a29c9e4630754934c` |
| **Reviewed HEAD** | `54193f75ee838cdd567efb5a29c9e4630754934c` / tree `64a6f934f83153440ad6224cc0e2f8f37fad73cb`, **plus 7 modified files, 0 untracked** |
| **Reviewed content, as committed** | `019a43d6f21625dae3fc3c8e7c8433866eb44a50` / tree `345a6152fded81bc7c4b2e0c7653cbdedd1a8c4c` |
| **Landing candidate** | `99831ae0dfcbb8e4606294443fb4a5ce8f451ddd` / tree `1a271c63aa4c0133da2d518d54bd7de17adb3db5` |
| **`src/` tree at reviewed content AND at candidate** | `a6fa4d8d27b73606b6e2a0217ccad83ada3a804a` — **identical** |
| **`.github/` tree across the whole range `974787b..99831ae`** | `41f76934b715f253da6e7f6a261c351186a7447b` — **identical** |
| **Branch** | `p5/u5-1-g2-spec-correction` |
| **Reviewer session** | `22551bfc-e950-436c-ac61-6a8448777c58`, `inherited_builder_context: false` |
| **Builder session** | `2d159710-f3ba-4a31-83a0-6cd6a990b262` |
| **Product Driver run** | `20260904-220427`, accepted at `runs/20260904-220427/accepted` |

## 1. The verdict, verbatim

```
verdict:                     SUPPORTED
confidence:                  0.90
findings:                    []
adjudications:               []
criteria_assessment:         8 / 8  PASS
blocked_on.kind:             NONE
inherited_builder_context:   false
evidence_reproduced:         true
claimed_evidence_reproduced: true
```

The reviewer's own summary, in its own words: *"The high-consequence surfaces this review was called
for are correct AND their guards are shown to fail when broken."*

**The reviewer executed the product.** All **eight** of its declared commands ran: `git rev-parse`,
`git status --porcelain=v1` (before **and** after the mutation battery), the M12 battery
(**61 passed**), the M7+M9 neighbour batteries (**107 passed**), `probe_phase6_rule.py --all`
(*"behaviours as specified, 0 wrong"*), `mutate_phase6_rule.py` (**35/35 caught, 0 escaped**,
anti-vacuity control GREEN), and two AST scans for production importers of `conflict` and
`exception`.

### **THE HARNESS DID REFUSE THREE COMMANDS, AND THAT IS RECORDED RATHER THAN OMITTED.** Of 18
attempted commands, **15 were allowed and 3 refused** — two at the `vocabulary` layer, one at the
`composition` layer. Unlike `P6-CP-11`, this is **not** a landing with no harness refusal at any
layer. What survives the refusals: every one of the eight *declared* review commands ran, and
`blocked_on.kind` is `NONE` with the reviewer's own note that *"the read-only boundary was
sufficient."* The three refusals were re-spellings of commands that then ran.

## 2. What M12 is, in one line

**An owner's sentence either compiles into a registered, versioned rule with an id — or is honestly
refused as unenforceable, and the owner is told it is NOT a rule. There is no third state where
Neyma merely remembers the text and implies it is enforced.**

### **THE FAILURE MODE HERE IS A SENTENCE, NOT A STATE.** A machine that gets every column right and
still replies *"📋 Noted the procedure"* has failed completely, and every structural test in the
repository would be green while it did. That is why M12 carries `assert_reply_is_honest`, a guard
asserted **on literal reply text**: a reply claiming enforcement with no `ACTIVE` `rule_id` is
refused, and the identical sentence with a real `ACTIVE` id is accepted. Both directions were
exercised.

### **THE TWO HONEST OUTCOMES, MEASURED ON THE LANDED TREE.**

* **OUTCOME A** — *"never bill without a POD"* compiles **deterministically** into a real
  `GATE_PRECONDITION` over modelled, non-inferred evidence fields, ships **generated test vectors**,
  is confirmed by an owner who saw them, is activated by an authenticated human, and then **DENIES**
  on a `MODEL_INFERRED` POD and permits otherwise.
* **OUTCOME B** — *"do not use Carrier X for produce"* is **refused**, verbatim:
  *"I can't enforce that. I don't track commodity, so this is NOT a rule and it will NOT stop me on
  its own…"* The refusal **names what is missing** (`missing=[commodity]`) and the sentence is
  retained, never enforced.

### **THE MODEL PROPOSES TEXT; IT NEVER COMPILES, ACTIVATES, EVALUATES OR RESOLVES.** A predicate
touching a `MODEL_INFERRED` field **fails to compile at confidence 1.0**, and `confidence` is
**structurally absent from `CompilerInput`** — there is no number to raise. `evaluate_rule` fails
closed at evaluation time with **no allow-on-error path**.

### **AND M12 IS NEVER A SECOND GATE AUTHORITY.** *A second gate authority is the same defect as no
gate authority.* Measured at this landing by AST across **125** production modules: the **sole**
`GateEntry`/`GateRegistry` construction anywhere in the package is the kernel's own fallback at
`checkpoint.py:242`. **`checkpoint.py` remains the sole gate minter.** The production
`GateRegistry` population stays **EMPTY** until U8.1/P8.

## 3. One tenant-first table enters the canonical partition

### 3.1 The load-bearing DDL was introspected LIVE at this landing, not read

A canonical database was built the way production builds one
(`create_canonical_schema` on a fresh connection with foreign keys enabled) and then interrogated.
`schema_readiness_problems` returned **NONE**. Measured on the resulting `rules` table:

| | |
|---|---|
| `PRIMARY KEY` | `['tenant', 'rule_id']` — tenant first |
| columns | **20** |
| indexes | **5**, of which **5 lead with `tenant`** |
| state literals | exactly **8**, no ninth: `PROPOSED COMPILED CONFIRMED ACTIVE REJECTED SUPERSEDED REVOKED EXPIRED` |
| kind literals | exactly **4**, no fifth: `IDENTITY CONFLICT_RESOLUTION GATE_PRECONDITION CONSTRAINT` |
| foreign keys | **8** half-keys — `tenant_humans` for the **author** and the **authenticated activator**, a **self-FK** for supersession, and **`conflicts`** for the M7 `RULE_VS_RULE` conflict a `COMPILED` rule is blocked on. **Every one carries the tenant in the reference itself**, so a cross-tenant author, activator, supersession or conflict cannot be spelled. |
| the authority CHECK | `CHECK (state <> 'ACTIVE' OR activated_by IS NOT NULL)` |

The two **unique** indexes are load-bearing rather than tidy:
`ix_rules_one_active_per_scope` — `UNIQUE (tenant, scope, kind)` **partial**, the
one-active-per-single-admitting-scope reservation — and `ix_rules_tenant_version` —
`UNIQUE (tenant, rule_version)`, the tenant-monotonic version. **Without the tenant in them, the
same scope and kind could not be ACTIVE in two brokerages, and two tenants could not both hold
version 1: one broker's rules would couple another's.**

### 3.2 The invariants were proven by ATTEMPTING THE VIOLATION, in both directions

Single-admitting uniqueness was exercised **as a refusal and as an acceptance**, which is what makes
it a guard rather than a coincidence: a second `ACTIVE` rule in the same single-admitting scope is
**refused** (*"T_A ACTIVE rows in the single-admitting scope: 1"*), while the **same scope and kind
in a different tenant is accepted** and **multiple in a multi-admitting scope are accepted**. A
`DELETE` against a rule row is **refused** — historical versions are retained, never removed. An
`ACTIVE` rule with a null activator is refused; a cross-tenant author is refused; a cross-tenant
activator is refused.

**Authority is never laundered into a rule.** RU-5 activation is FK-bound to an `ACTIVE`
`tenant_human`. **A model, automation, a timer, a retry handler and a counterparty each attempted
activation and each was refused and recorded** as the already-registered F14
`UnauthorizedPolicyActivationAttempted` — **M12 mints no second contract for it**.

### 3.3 The event contracts, measured

**118 registered contracts — the identical total recorded at the `P6-CP-11` landing.**
### **M12 MINTED NO EVENT CONTRACT AT ALL**, which is the strongest available form of rule-17
compliance. The **eight** F12 contracts it emits — `RuleProposed`, `RuleCompiled`,
`RuleNotEnforceable`, `RuleConfirmed`, `RuleActivated`, `RuleSuperseded`, `RuleRevoked`,
`RuleExpired` — were **already registered**, and `rule.py`'s `PRODUCED_CONTRACTS` is **exactly those
eight and nothing else**. M12 mints **no F7** contract (it calls M7 rather than speaking for it),
**no F9**, and **no second F14**.

**`PolicyOverridden` is still NOT registered**, verified against all 118. **M12 built no override
mechanism at all** — not as an event, a field or a code path. `P6-D71` stays **OPEN**; see §7.

### 3.4 The transition arithmetic, re-derived rather than carried

§14 of **all thirteen** machine files was parsed and its rows counted. The parse **DISCOVERED 13
files** and counted **134 rows**, matching P6's own `expected_production_outputs`; no prior figure
was carried.

```
M1 14 · M2 25 · M3 13 · M4 11 · M5 8 · M6 11 · M7 7 · M8 8 · M9 7 · M10 9 · M11 7 · M12 9  = 129
M13 5                                                                                      =   5
                                                                                    total  = 134
```

M12's nine — `RU-1`, `RU-2`, `RU-2f`, `RU-3`, `RU-4`, `RU-5`, `RU-6`, `RU-7`, `RU-8` — are an
**exact set match** between `rule.py`'s `TRANSITIONS_BY_ID` and the specification's §14. **129 of
134 are written and landed; the 5 remaining are exactly M13's.**

## 4. What the reviewer established ITSELF, and how

| What | How | Result |
|---|---|---|
| the M12 acceptance battery | `pytest eval/tests/test_phase6_rule.py -q` | **61 passed** |
| M7 + M9 neighbours unbroken | `pytest test_phase6_conflict.py test_phase6_exception.py -q` | **107 passed** |
| behaviour, not structure | `probe_phase6_rule.py --all` | *"behaviours as specified, 0 wrong"* |
| the guards can fail | `mutate_phase6_rule.py` | **35/35 caught, 0 escaped**, anti-vacuity GREEN |
| M12 ships dark | AST scan for production importers of `rule` | **`[]`** |
| M12 is the only reader of M7/M9 | AST scan for production importers of `conflict` / `exception` | **`['src/freight_recon/rule.py']`** for each |
| the tree was not polluted | `git status --porcelain=v1` **before and after** the battery | 7 modified, 0 untracked, **both times** |

### **THE MUTATION BATTERY IS LOAD-BEARING, AND IT IS THE THING THAT MAKES THE REST EVIDENCE.** 35
mutants, discovered from the script's own `CASES` list rather than counted by hand. Among those
explicitly named as caught: **allow-on-rule-error**, **a self-minted gate decision**, and
**replay-mints-authority**. The anti-vacuity control asserts the un-mutated tree is GREEN first, so
a battery that policed nothing could not report success.

### **AND THE BATTERY'S OWN FALSE-GREEN WAS FOUND AND FIXED BEFORE ACCEPTANCE, NOT AFTER.** An
earlier iteration reported escaped mutants. The cause was self-inflicted: a foreground `SIGKILL` at
a 120-second timeout stranded two interrupted mutants inside `rule.py`, so subsequent counts were
measured against a poisoned tree. They were **surgically restored to their HEAD text** — not by
`git checkout`, `git restore`, `git stash` or `git clean`, which [`CLAUDE.md`](../../CLAUDE.md) §6
forbids — and a [`CLAUDE.md`](../../CLAUDE.md) §6-aligned **`assert_pristine()` pre-flight guard**
was added, so stranded residue is now **refused and reported** rather than silently miscounted. The
harness saves and restores in memory and purges `__pycache__`.

### **THE LANDING SESSION RE-EXECUTED THE HEADLINE EVIDENCE ON THE COMMITTED CANDIDATE TREE.** On
`99831ae` (CPython **3.14.4**, the interpreter available in this sandbox — *not* the 3.11.16/3.12.14
pair the correction commit records): `test_phase6_rule.py` **61 passed**; `probe_phase6_rule.py
--all` **exit 0**, *"behaviours as specified, 0 wrong"*, 267 measurement lines. That is a **third**
interpreter agreeing, and it is recorded as a local result, never as a CI one.

### **THE SHIP-DARK SCAN CARRIES ITS DENOMINATOR AND ITS POSITIVE CONTROLS.** `production importers
of rule: []` is a negative assertion, and a negative assertion over an unproven population proves
nothing ([`CLAUDE.md`](../../CLAUDE.md) §6). The same scanner, over the same 125 discovered modules,
returns **9** importers of `checkpoint` and **6** of `commit_key` — so it demonstrably finds
importers when they exist. A first version of this scan matched on the **last dotted segment** and
reported `imap_mailbox.py` and `inbox_discovery.py` as importers of `policy`; both are
`from email.policy import default`. **That false positive is recorded rather than quietly
corrected**, because a scanner that cannot tell `freight_recon.policy` from `email.policy` would
have reported a ship-dark breach that does not exist — and, run the other way, could have missed one
that does.

## 5. What Product Driver independently exercised

Run `20260904-220427`, iteration 2, accepted.

| | |
|---|---|
| `decision` | **ACCEPT**, confidence 0.86, `problems: []` |
| `task_scope` / `task_result` | **P6/M12** / **VERIFIED**, `task_outstanding: []` |
| completion audit | **VERIFIED**, confidence 0.85, `implementation_present: true`, `contradictions: []`, `missing_evidence: []` |
| required scenarios | **11 of 11 present and passed** |
| scenarios executed | **15** — 1 permanent (`p6_m12_rule`) + 14 generated |
| outcomes | **15 PASSED, 0 failed, 0 blocked, 0 skipped** |
| assertions | **1037 total, 0 failed** (862 of them in the permanent scenario) |
| `assembly_problems` | `[]` |
| `uncovered_risks` | `[]` |
| risk categories covered | `authorization`, `boundary`, `conflicting_evidence`, `happy_path`, `regression`, `safety_invariant`, `service_unavailable`, `unexpected_state_transition` |
| `parent_phase_accepted` | **false** |

`scoped_completion.does_not_imply` states, in the run's own words, that this implies **none** of:
*P6 is COMPLETE*, *any P6 acceptance criterion is scored*, *the units P6 still owes are built*, *the
next phase is unblocked*, *phase acceptance has occurred*, *anything is enabled in production or on
live traffic*.

### **THE RUN FORCED A REAL PRODUCT CORRECTION, AND THAT IS THE PART WORTH KEEPING.** At the build
commit `54193f7`, M12 **named the M7 and M9 seams and left them unwired** — the commit message says
so: *"imports neither conflict.py nor exception.py (M7/M9 keep zero importers — RU-3 and RU-8 name
the seams and the caller drives them)."* The accepted correction `019a43d` **wired them**: `rule.py`
now imports `M7Machine`/`Party` and `M9Machine`, RU-3 raises the rule-vs-rule conflict through
**M7's landed `raise_conflict`**, and M12 mints **no** F7/F9/F14 contract of its own. **Two
conflicting rules fail closed into M7 rather than auto-merging**, which is the behaviour the
specification asks for and the build commit had left as an intention.

## 6. The eight criteria the reviewer assessed

| # | Criterion | Result |
|---|---|---|
| 1 | `happy_path` — OUTCOME A end to end: deterministic compile, test vectors, human confirmation, human activation, DENY on an inferred POD | **PASS** |
| 2 | `authorization` — authority is never laundered; only an authenticated human activates; model/automation/timer/retry/counterparty cannot; `ACTIVE` carries an FK-backed `activated_by` | **PASS** |
| 3 | `safety_invariant` L-C — a reply claiming enforcement with no `ACTIVE` `rule_id` is refused; the same sentence with one is accepted; the honest refusal passes | **PASS** |
| 4 | `conflicting_evidence` GR-8 — a predicate on a `MODEL_INFERRED` field fails to compile at confidence 1.0; `confidence` is structurally absent | **PASS** |
| 5 | no second gate/authority — `checkpoint.py` is the sole gate minter; M12 constructs no `GateRegistry`/`GateEntry`; M7/M9/checkpoint byte-unchanged | **PASS** |
| 6 | ships dark — nothing in production imports `rule.py`; `rule.py` is the only production importer of `conflict`/`exception` | **PASS** |
| 7 | replay / tenant isolation — replay mints no authority, witness or grant; tenant-first keys and FKs enforce `[C-1]` | **PASS** |
| 8 | **test changes do not weaken a safety guard** ([`CLAUDE.md`](../../CLAUDE.md) rule 20 / the independent-review trigger) | **PASS** |

### **CRITERION 8 IS THE ONE A BUSY REVIEWER SKIPS, AND IT IS THE REASON THIS REVIEW WAS REQUIRED.**
M12's build edited the M7 and M9 **neighbour guard files**. The reviewer judged those edits
specifically and concluded they are *"legitimate rule-20 adaptations (adding `rule.py` to the
dark-importer exclusion because it legitimately calls those entry points and itself ships dark), not
guard weakening."* The corroborating measurement is that the exclusion is **narrow and true**: the
same AST scan at this landing returns `['src/freight_recon/rule.py']` and nothing else for each of
`conflict` and `exception`, so the exclusion covers exactly the importer that exists.

## 7. Minor and nonblocking items — recorded, not actioned

### **THE INDEPENDENT REVIEW RETURNED ZERO FINDINGS AND ZERO ADJUDICATIONS.** Everything in this
section was identified **at this landing** from the run's structured evidence, the M12 source, the
specification corpus and the CI record. **None is a reviewer finding.** They are recorded as
`P6-D82`…`P6-D88` in the implementation registry.

### **ONE CARRIED RESIDUAL NAMES `closes_at: M12`, AND M12 DOES *NOT* CLOSE IT — STATED RATHER THAN
LET PASS.** **`P6-D4`** — *"K-1's `RULE` referent cannot resolve: there is no `rules` table until
M12"* — stays **OPEN**. The `rules` table now exists, but `work_item.py` is **byte-unchanged across
the entire M12 range** (`git log 974787b..99831ae -- src/freight_recon/work_item.py` is empty), so
`resolve_decision_ref(kind="RULE", …)` still raises `DecisionRefUnresolvable`. **M12 deliberately
did not retro-wire M1**, on the landed M10/M11 precedent for `compensation` and `policy`. ### **AND
THE REFUSAL'S OWN MESSAGE IS NOW STALE IN A WAY THAT MATTERS**: it reads *"Rules (machine M12) are
not implemented yet — there is no `rules` table to resolve an `ACTIVE` `rule_id` against"*, and the
second half of that sentence is **false on this tree**. The behaviour (refuse) is still correct;
the stated reason is not. Recorded as **`P6-D82`** rather than edited, because editing a
tier-1-adjacent, already-reviewed M1 runtime file for a comment is a change this landing may not
make.

### **AND THE EXPECTATION THAT `P6-D71` WOULD CLOSE AT M12 IS NOT MET.** The `P6-CP-11` landing block
records that minting `PolicyOverridden` *"is a founder/architect act that lands with M12/Rule."* It
did not land. **`P6-D71` stays OPEN / `BLOCKED_AUTHORITY`** — verified absent from all 118 registered
contracts, and M12 builds no override mechanism at all. The build commit says so in its own words:
*"P6-D71 (PolicyOverridden) remains OPEN — unmet at the point CURRENT.md expected it to close."*
**No ninth F12 event was registered and none may be minted here**; that is a founder/architect act.
Recorded as **`P6-D83`**.

### **`P6-D73`'s SHAPE RECURS FOR `rule`, AND IS RECORDED RATHER THAN QUIETLY FIXED.** M9's
`exceptions.source_kind` vocabulary contains `'rule'` with **no mirror FK** —
`SOURCE_KINDS_WITHOUT_TABLE` is `('compensation', 'evidence', 'rule', 'policy', 'pending_reference')`
and `phase6_exceptions.py` is **byte-unchanged** across the entire M12 range. M12 creates the
referent and deliberately does not retro-wire the FK, exactly as M10 did for `compensation` and M11
for `policy`. Recorded as **`P6-D84`**.

### **THE `P6-D58`/`P6-D81` CLASS RECURS A THIRD TIME.** Discovered mechanically rather than
enumerated: **11 occurrences across 7 files** under `eval/`, `scripts/` and `src/` assert *"M12
LANDED"* or name **`P6-CP-12`**. **Zero** were present at the `P6-CP-11` landing (`974787b`); **9**
were introduced at the build commit `54193f7`. All were **FALSE WHEN WRITTEN** — no `P6-CP-12`
existed until this landing commit — and all become **TRUE** as of it. None is an assertion, none
changes what any guard reads or permits, and none appears in a status authority. Recorded as
**`P6-D85`**; not edited, for the same reason `P6-D81` was not.

### **THREE COVERAGE GAPS THE RUN DECLARED ABOUT ITSELF.** `scenario-plan.json` records
`unresolved_questions` naming three things no approved command exercised: **Outcome C** (*"Customer
Y requires hourly updates"* compiling through M8 as a recurring Expectation, acceptance-grade per
ADR-010 §6.1 / spec §20.5); **`M12-AQ-5`**, the F12 strict-order monotonic-per-tenant constraint and
the additive `previous_aggregate_version` emission, covered only indirectly by the concurrency/OCC
oracles; and the **probe's own fault contract** (an unknown `--inject` fault exiting 2). Separately,
**17 generated scenarios were proposed, 14 accepted, 3 filtered at assembly, 0 invalid**, with
`uncovered_risks: []`. Recorded as **`P6-D86`**.

### **ONE GUARD THAT PASSED HERE COULD NOT HAVE FAILED, AND IS NOT CITED AS THOUGH IT COULD.** The
canonical-partition guard ends with a **substring** check — `for t in sorted(union): assert t in
text` over the raw text of `CURRENT.md`. Measured rather than assumed: the bare token `rules`
**already occurred in `CURRENT.md` before the M12 partition row was added**, so that half of the
guard was green either way and is **no evidence at all** for the row. The row was verified directly
instead, by live DDL introspection of the `rules` table on a fresh canonical schema. The guard's
other halves — disjointness, `set(CANONICAL_TABLES) == union` exactness, and the pinned `shape`
dict — do constrain the migrations and did real work. Recorded as **`P6-D88`**; the guard predates
M12 and this landing may not change a test.

### **`P6-D40` IS CARRIED FORWARD UNCHANGED AND WAS NOT RE-VERIFIED AT THIS LANDING.** No mutation
battery was run against the status guards here and none is claimed.

## 8. ### CI — the honest record. The workflow did NOT conclude `SUCCESS`

### **THE FIRST PUSH FOUND NINE REAL FAILURES, AND THEY WERE NOT IGNORED.** Run **`33942518450`** on
the pushed candidate `019a43d` printed **nine pytest failure markers on Python 3.11 at ~43%** —
`FFFF.FF.F........F..........F`. They were investigated and corrected before landing, and the
correction is commit `99831ae`.

**The root cause was one defect, and it was not in M12's runtime.** `scripts/probe_phase6_rule.py`
wrote two regexes **inline inside f-string expression parts**. A backslash there is a `SyntaxError`
before Python 3.12 — PEP 701 legalised it — and `pyproject` declares the floor at **3.11**, so on
the floor interpreter the whole probe was unparseable. **All nine failures are discovery-based
phase-0 guards** — the adapter-import probe, the R-07 containment record and the entry-point probe —
**refusing to silently ignore a file in their population that would not parse. The guards were
right; the file was wrong.** The regexes are now bound to names; the patterns are unchanged.

**A second, deeper defect was found that CI never printed**, because both legs were cancelled before
reaching it: the migration-walk regression test **still stopped at M11**, so a P2-shaped database
walked forward through every migration could not construct a `WorkflowStore` once M12 added the
canonical `rules` table. **That one was real on BOTH interpreters and would have reddened the py3.12
leg too.** The walk now carries its M12 step and asserts the table, the one-active-per-scope
reservation index and the immutability triggers.

**A permanent repository guard was added** so the declared floor is enforced on *every* interpreter
rather than only on CI's 3.11 leg: it parses every `.py` the repository ships, and on a newer
interpreter — which would happily accept syntax the floor rejects — scans f-string expression parts
for exactly what 3.12 relaxed. **Same invariant either way, never a weaker rule on 3.11.**

### **THE CORRECTION CHANGED NO RUNTIME.** `git diff --stat 019a43d 99831ae` is three files —
`eval/tests/test_bootstrap_hermeticity.py`, `eval/tests/test_phase3_schema.py`,
`scripts/probe_phase6_rule.py` — and the `src/` tree hash is **identical at both commits**. No M12
runtime, no M1–M11 runtime, no migration runtime, no gate-minter allowlist and no
`.github/workflows/ci.yml` change.

### **THE SECOND PUSH DID NOT CONCLUDE `SUCCESS` EITHER, AND THIS DOCUMENT DOES NOT SAY IT DID.**
Run **`33948926997`** on `99831ae`:

| Job | Conclusion |
|---|---|
| **Full test suite (py3.12)** | ### **SUCCESS — 3284 passed, 1 skipped, 100% reached** |
| **Full test suite (py3.11)** | **CANCELLED** at the ~60-minute job ceiling, having reached **52%** with **ZERO pytest failure markers** |
| **P6/M3 effect-grant probe + mutation** | **SUCCESS** |
| **Safety invariants (fast)** | **CANCELLED** at its own ~30-minute ceiling, **no failure marker observed** |
| **Risk radar** | skipped (pull-request-only) |

**`cancelled` is not `success` — anyone citing this landing as "CI green" is citing it wrongly.**

### **BUT A FULL SUITE COMPLETED, AND M12'S OWN TESTS EXECUTED IN CI AND PASSED.** This is the
material difference from `P6-CP-11`, where neither suite completed. `pytest eval --collect-only`
collects **3285** tests on this tree, which matches py3.12's `3284 passed, 1 skipped` **exactly**,
and `eval/tests/test_phase6_rule.py` occupies positions **2678–2738** — **81.5%–83.3%**, 61 tests.
**py3.12 reached 100%, so all 61 ran and passed.**

### **AND THE PY3.11 LEG RE-EXECUTED THE EXACT FAILURE REGION CLEANLY — MEASURED, NOT ASSUMED.** The
nine failures sat at ~43%. Measured on this tree, that region is precisely the phase-0 discovery
block: `test_phase0_adapter_imports.py` at **43.0%–43.3%**, `test_phase0_baseline_manifest.py` at
**43.3%–43.7%** and `test_phase0_entry_points.py` at **43.9%–44.0%** — the three families the
correction names. The py3.11 leg reached **52%**, so it ran **past all of them** and emitted
**dots where it had emitted `FFFF.FF.F........F..........F`**.

### **THE CANCELLED SAFETY JOB IS MITIGATED, AND THE MITIGATION IS MEASURED RATHER THAN ASSERTED.**
The *Safety invariants (fast)* job names **26 files, discovered from the workflow rather than
enumerated**. All **26 are inside `pytest eval`** — **621 tests**, the last at **99.6%** of the run.
Because the py3.12 suite **reached 100%**, every safety-job test ran to completion and passed on
py3.12. So the fast job's cancellation cost a *duplicate* result, not the only one. That includes
`test_phase0_null_gate.py` (**45.6%–45.8%**), which carries the sole-gate-minter guard, and
`test_phase0_tenant_posture.py` (**46.1%–46.4%**), where a new canonical table failing to declare
itself would turn red — **both of which also ran on the py3.11 leg**, being well inside its 52%.

### **WHAT HAS NO py3.11 CI RESULT, STATED PLAINLY.** `eval/tests/test_phase3_schema.py` — which
carries the corrected **M12 migration walk** — sits at **55.9%–56.2%**, past the 52% cancellation.
`eval/tests/test_phase6_rule.py` sits at 81.5%–83.3%. **Neither executed on py3.11 in CI on this
commit: not failing, not passing — no execution.** Both executed and passed on py3.12, and both were
run locally on **CPython 3.11.16 and 3.12.14** by the correction commit. The new floor guard in
`test_bootstrap_hermeticity.py` sits at **4.0%–5.6%** and therefore **did** execute on both legs.

### **CI RUNS NO M12 PROBE OR MUTATION JOB.** Verified mechanically: the count of `phase6_rule`
occurrences in `.github/workflows/ci.yml` is **ZERO**. M3 is the only P6 machine with a dedicated
probe/mutation job. **Unlike `P6-CP-11`, the mitigating sentence IS available here**: M12's 61 tests
are inside `pytest eval`, and that job completed on py3.12. The 35-mutant battery and the probe
remain uncovered by CI, and were re-executed locally. Recorded as **`P6-D87`**.

### **THE JOB CONCLUSIONS ABOVE WERE SUPPLIED BY THE FOUNDER AND COULD NOT BE RE-READ AT THIS
LANDING.** `gh run view 33948926997` fails from this sandbox with
`tls: failed to verify certificate: x509: OSStatus -26276` — the identical failure recorded at every
landing since `P6-CP-5`, reproduced here.

### **THE FOUNDER LANDING DECISION, RECORDED AS A DECISION AND NOT AS A VERIFICATION.** The founder
chose to land on the evidence that exists, treating both cancellations as non-product CI runtime
limitations. That is `P6-D87`'s first half, and it closes only by a CI run on this branch that
concludes `SUCCESS`.

### **THE LOCAL VALIDATION THE CORRECTION COMMIT RECORDS, WITH ITS NUANCE PRESERVED.** On the final
tree, on **CPython 3.11.16 and 3.12.14**, dependencies installed fresh from `pyproject` on each:
the exact nine **9 passed on both**; the six CI never reached **6 passed on both**;
`test_phase6_rule.py` **61 passed**; `probe --all` **exit 0**; the mutation battery **35/35 caught**;
the targeted M7/M9/M11/checkpoint/phase-0/migration/replay batteries **668 passed, 1 skipped on
both**; and the full `pytest eval` **3264 passed, 1 skipped on both**. ### **THE REMAINING LOCAL
FAILURES ARE NOT PRODUCT PASSES AND ARE NOT PRESENTED AS ANY KIND OF PASS.** Twenty tests failed
locally on both interpreters, every one of them this sandbox refusing `socket.bind` on `127.0.0.1`
(20 FAILED ids, 20 bind sites, `PermissionError` the only exception type in the section). **They were
not GitHub CI failures** — py3.12 in CI ran the full 3284 — **and this landing must not pretend they
were product passes.**

## 9. What did NOT change

Verified mechanically, by tree hash rather than by reading:

* **`.github/` is byte-identical** — `41f76934b715f253da6e7f6a261c351186a7447b` — at `974787b`
  (the `P6-CP-11` landing), `a861f2b`, `54193f7`, `019a43d` **and** `99831ae`. **The CI workflow was
  not weakened.**
* **`src/` is byte-identical at `019a43d` and `99831ae`** — `a6fa4d8d27b73606b6e2a0217ccad83ada3a804a`.
* Across the whole range `974787b..99831ae`, exactly **four** files under `src/` change: the two new
  M12 deliverables (`rule.py`, `migrations/phase6_rules.py`) and two wiring edits (`schema.py`
  +33/−3, `migrations/phase2_tenant_first.py` +10). ### **NO M1–M11 MACHINE MODULE APPEARS IN THAT
  LIST**, and `conflict.py`, `exception.py`, `checkpoint.py` and `migrations/phase6_exceptions.py`
  are individually confirmed byte-unchanged.
* **`eval/phase0/gate_scan.py` was deliberately NOT touched.** M12 carries no gate vocabulary in
  executable code, so unlike M11 it needed **no widening of `GATE_RUNTIME_MODULES`**. The
  gate-minter allowlist is unchanged.
* The production `GateRegistry` population stays **EMPTY**. R-07 stays **CONTAINED**, and
  containment is not enablement.

## 10. What this checkpoint does NOT do

* It does **not** complete P6. P6 stays `status: READY` / `execution_state: IN_PROGRESS`.
* It scores **no** P6 acceptance criterion. `criteria_scored` is `[]` on all twelve checkpoints.
* It does **not** unblock P7, which stays `BLOCKED` / `NOT_STARTED`.
* It enables **nothing** in production. M12 ships dark: **zero** production importers, no gate
  decision minted, no brake engaged, no channel joined, and **no rule editor, importer, admin
  screen, console or dashboard of any kind**.
* It builds **no** part of M13. `brake_lifecycle.py` and `phase6_brakes.py` are absent from the
  tree. (`brake.py` is P3's landed kernel brake, not M13.)
* It grants **no** autonomy and graduates nothing. `V11` and `V12` stay OPEN at their fail-closed
  defaults.

**The next build checkpoint is M13 — the Brake.**

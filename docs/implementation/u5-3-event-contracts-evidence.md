# P5 U5.3 — the canonical event contracts and the upcaster: implementer's evidence

> ### **THIS IS EVIDENCE, NOT ACCEPTANCE.** It was written by the session that implemented U5.3.
> No criterion is scored here, P5 stays `READY` / `IN_PROGRESS` / **NOT COMPLETE**, and all 14 P5
> acceptance criteria remain `PENDING`. Acceptance requires an independent review by a session that
> did not build this, and a separate adjudication after that. A battery that agrees with its author
> is evidence; it is never adjudication (CLAUDE.md §11).

---

## What did not exist before, and does now

U5.7+U5.8 built a transport that carries **any well-formed envelope**. `event_envelope.py` says so
in its own words:

> *"It is **not** the 105 event contracts. There is no name whitelist here, no per-event payload
> schema, and no upcaster: those are U5.3's."*

So until this landed, an envelope carrying `event_name="Vibes"` with an empty payload was perfectly
well-formed. It was **shaped** like a canonical event and it was not one — and the durable log would
have accepted it.

U5.3 is the check. `event_name` now means something, and a fact that is not canonical cannot be
committed, published, redelivered or consumed.

## The contracts are DERIVED, not transcribed

`events/registry.md` §6 says it "is the sole canonical list of event names and versions". A runtime
that hand-transcribed those names would be a **second authority for the same list**, and this
repository has the scar tissue to prove where that ends.

| | |
|---|---|
| **Derivation** | `scripts/generate_event_contracts.py` parses `events/registry.md` §3 (names, families, producer transitions, ‡markers), §5 (the consequential set), §8 (strict-order families), and the **F1–F14 family files** (per-event payload contracts and each family's `aggregate_type` default) |
| **Output** | `src/freight_recon/event_contracts_data.json` — committed **as data, not code**. Committed rather than parsed at import because `pyproject.toml` packages `src/freight_recon` and **not** `docs/`; JSON rather than a `.py` module because JSON cannot execute, which is what keeps every safety guard unchanged (see the review section) |
| **Anti-drift** | `test_p5_event_contracts.py::test_the_generated_contract_data_is_exactly_what_the_specification_derives` re-runs the derivation on every suite run and compares byte-for-byte. A specification edit without a regeneration **fails the build** rather than serving stale contracts |
| **Both directions** | The derivation refuses to emit if §3 names a contract no family file declares, or a family file declares one §3 does not name, or §5 marks an unknown name consequential |

### The count, computed rather than asserted

**118 canonical contracts.** **105** machine-emitted across F1–F13 — exactly the registry's 105 —
and **13** audit/security in F14, which are real contracts emitted by detectors and by the inbox
rather than by a producer transition, and therefore carry no producer set and are not
producer-checked. F15 is a **lens** (§9) and declares no contract; reading it as a source would have
silently overwritten four real contracts with a summary of themselves, so the derivation skips it
explicitly.

### The payload grammar, as the corpus actually writes it

    —                    no payload beyond the envelope
    `name`               required          `name?`            optional
    `name[]`             required list     `name=VALUE`       fixed value
    `name∈{a,b,c}`       enum              `a \| b`           one-of, exactly one
    …(R)  …(R, prose)  …(R ∈ {A,B})        an annotation on the term just declared

### **A field is a backticked token at TOP LEVEL — never one inside an annotation.** That rule is
load-bearing and was verified case by case: `` `missing`(R, e.g. `commodity`) `` declares **one**
field, and `` `diff_fingerprint`(R, the `material_facts_fingerprint` of the diff) `` declares one,
not two. Reading annotations as declarations would invent required fields nobody specified and
refuse every legitimate event of those types.

### **An unmarked field is REQUIRED.** `?` is the only optionality marker the corpus uses, and the
fail-closed reading is the one that cannot silently drop a fact.

## What is now checked, and in what order

Identity first, then attribution, then version, then body, then authority — each answer makes the
next question meaningful, and the first failure is the most informative one.

| Check | Refusal | Grounded in |
|---|---|---|
| the name is one of the 118 | `UnknownEventName` | §3 |
| the transition owns the contract | `ProducerTransitionMismatch` | §1 — "the mechanical link to the state machine" |
| the aggregate is the family's | `AggregateTypeMismatch` | §8 — an event on the wrong aggregate orders against the wrong history |
| the version is supported | `UnsupportedFutureVersion` | §6 |
| the body is the declared body | `PayloadContractViolation` | the family files |
| a consequential event pins its decision context | `ConsequentialPinsMissing` | §5, ER-13 |
| this actor may state this fact | `ActorAuthorityViolation` | ER-9 / ER-10 / ER-11 / ER-12 |

Every one is an `EnvelopeError` subclass, so a contract violation travels the inbox's **existing**
refusal path and lands in the same durable `REJECTED_MALFORMED` outcome. A separate hierarchy would
have needed a second refusal branch, and the branch written twice is the branch that diverges.

### The two validation modes, and why that is not a loophole

§6 is explicit and asymmetric: *"a `vN+1` producer + a `vN` consumer ⇒ additive fields are ignored"*.

* **PRODUCER** — an undeclared payload field is a **refusal**. Our own emitters must not invent
  fields; a typo is caught in the commit that introduces it.
* **CONSUMER** — an undeclared payload field is **ignored**, per §6. A consumer that refused one
  would turn every additive schema change into a coordinated outage.

Neither mode is lenient about whether the event is canonical. The difference is exactly one rule,
and it is the rule §6 writes down. Both halves are asserted on one envelope so the pair cannot drift.

## Where the gate sits, and why that position is the whole point

`TransactionalOutbox.emit` validates **inside the caller's open transaction, before the INSERT**. So
a non-canonical fact does not merely fail to publish — the state change it was travelling with is
rolled back too, because the commit that would have made both real never happens. **An event that is
not a fact cannot take a state change with it.**

There is no `validate=False`, for the same reason `emit` has no `allow_autocommit=True`: a flag is
how a guarantee gets turned off on a Friday.

`DedupInbox.consume` upcasts then validates, **after** the tenant check. That order is deliberate:
whose event this is outranks what it says. A refusal writes **no inbox row**, so a corrected
redelivery of the same `event_id` can still apply — recording a rejection as a consumption would
make the event permanently unconsumable, which is event loss wearing an idempotency guarantee.

## The upcaster — an honest account of what it has to do today

### **EVERY CANONICAL CONTRACT IS AT `v1`.** That is a fact about the specification, not a gap in
this module, and it has a consequence stated plainly rather than dressed up: **the canonical corpus
registers zero upcasters, because nothing has evolved yet.**

What is built and exercised is the machinery that will carry the first evolution — registration,
chaining, determinism, and three refusals:

    version == current   identity; the same object is returned, so a digest cannot shift
    version <  current   chain vN→…→current; a MISSING link is `MissingUpcaster`, never a
                         pass-through — a v1 body read as v3 carries two versions of assumptions
                         the reader does not know it is making (M-25)
    version >  current    `UnsupportedFutureVersion`; §6 gates a breaking change on a coordinated
                         rollout, so a future version arriving here is a deployment error

Chaining is proven against a **synthetic** contract set, and `UpcasterRegistry` takes an injectable
one for exactly that reason. Minting a fake `v2` of a real canonical event to make a test look
impressive would be amending a protected specification — a defect wearing a green tick. The
canonical corpus proves what it can honestly prove: identity, and the refusals.
`test_every_canonical_contract_is_at_v1_today` fails the day that stops being true, which is the
signal that a real upcaster is now **required**.

## Verification

| | |
|---|---|
| **U5.3 battery** | `eval/tests/test_p5_event_contracts.py` — **332 nodes**, including the independently-written oracle of section 1b and its value-shape regressions |
| **Seven-step standard, EXHAUSTIVE** | `test_every_canonical_contract_survives_the_whole_transport_round_trip` runs **all 118 contracts** through: produce → validate → commit atomically with a real state change → publish through the real relay → rehydrate from stored JSON → upcast → recover **byte-identically** → consume → redeliver as a no-op. Exhaustive because it is cheap here, and because a sampled version would leave 100+ contracts asserted by nothing |
| **Exhaustive hostile sweeps** | every required field of every contract dropped one at a time; every enum field given a non-member; every fixed field changed; every one-of given both members and neither; **the 20 UNQUALIFIED members of §5** stripped of each pin in turn (the 21st, `ClaimConfirmed`, is qualified "when it backs a money action" and has its own node) |
| **Mutation** | `scripts/mutate_phase5_contracts.py` — ### **37/37 mutants caught**. Includes **two that edit the canonical specification itself** (a renamed contract, a consequential member removed) to prove the anti-drift guard is real, and **seven that mutate the PARSER** — the coverage hole the review named, since four real defects lived there and no original case could reach them. A parser case regenerates the data after mutating, because a parser defect is inert until the data is re-derived: the first run reported those five as MISSes and was right to |
| **Widened regression** | full `eval/` suite — see `SUITE-RESULT.json` for the figures bound to the finalized tree; volatile counts live only in `CURRENT.md`'s status block |

## Defects this unit found and fixed

1. ### **The pre-existing transport battery was green against a fact that was not canonical.**
   `phase5_kit.make_envelope` emitted `CheckpointPassed` with payload `{"pipeline_instance_id": …}`
   — a shape the specification never declared. The whole U5.7/U5.8 battery ran on it. The fixture is
   now **derived from the contract**, so every one of those cases now exercises a real canonical
   event, and the class of defect cannot recur.
2. **`ClaimCorrected` fixes `provenance_class=OWNER_ASSERTED`**, so a system-actor version of it is
   exactly the laundering ER-10 forbids. Caught on the first run of the new rule; the fixture now
   derives the required actor type from the contract rather than from a list.
3. **A strict-ordering case was parameterized over aggregate types while naming one fixed event.**
   `CheckpointPassed` on `brake` is now an `AggregateTypeMismatch` refusal, not a version-gap case —
   it would have proved nothing about ordering. It now discovers a real contract per aggregate type.

## The independent review, and what it changed

### **THE FIRST CANDIDATE WAS REJECTED.** An independent review — a session that did not implement
this unit and re-derived every claim from source — returned **REJECT, REMEDIATION REQUIRED** on five
blocking defects. All five were real, all were reproduced mechanically before being fixed, and three
of them were **derivation errors that made canonical contracts unsatisfiable**: the runtime refused
events the specification declares legal.

| ID | The defect | Why the suite was green anyway |
|---|---|---|
| **R-01** | `ClaimProposed.provenance_class` was read as **fixed to `'f'`** — from `(R = f(match_method))`, a derivation formula (SD-6), not a literal. Every legitimate `ClaimProposed` in the corpus was refused | the fixtures were built from the same generated data |
| **R-02** | `ObservationReceived.natural_key` was read as fixed to `'tenant'` — from `(R = tenant+source+external_id+content_digest)`, which is §4's source-natural identity. The whole external-ingress family was unemittable | as above |
| **R-03** | §8 writes the strict-order split and the order-tolerant list **on one line**. The regex harvested both halves, marking **F5, F7, F9 and F14 strict — 31 of 118 contracts** carrying a flag the registry contradicts, and disagreeing with the `STRICT_ORDER_AGGREGATE_TYPES` the transport actually enforces | nothing read the flag yet; P6's consumers would have found out |
| **R-04** | `HUMAN_ONLY_EVENTS` was a **hand-written literal of three names** that mechanised ER-11/ER-12 verbatim and stopped there. `ApprovalGranted` (AP-2) — the human consent that binds Material Facts — and `RuleActivated` (RU-5) both accepted `actor_type=system`, though their family rows say "`actor_type=human` ONLY" in as many words | no node asserted the set against the family files |
| **R-05** | ER-10 was **evadable three ways**: via `provenance_refs` at the envelope level (which §1 DEFINES as provenance's home), via an `Enum` member (the payload validator accepted it into the declared enum by `.name` while the authority validator compared it to a `str` and disagreed — about the same value, in one call), and via nesting | the check was one scalar `payload.get` |

Plus eight material findings, all fixed: `IllegalTransitionAttempted` producer-checked against the
global RULE `GR-1` (**and a test that locked the bug in** — CLAUDE.md §9's "a defect and its
defending test arrive together"); a model permitted to state `ClaimConfirmed`, a consequential
identity binding GR-8 forbids; scalar fields accepting collections (`ClaimRefused.cause` recording
three simultaneous causes); consequential pins satisfied by `""`; a producer free to emit a stale
version; and **an assertion that could never fail, asserting a property the code violated**.

### **THE DEEPEST FINDING WAS NOT A DEFECT — IT WAS WHY THE DEFECTS WERE INVISIBLE.**

Every fixture in this battery is built by `phase5_kit.canonical_payload`, which reads the **same
generated data the battery is checking**. So the exhaustive 118-contract sweep and every hostile
sweep were **self-consistent by construction**: they proved the runtime agrees with
`event_contracts_data.json`, and nothing about whether that file agrees with the specification. And
the anti-drift node compares the generator's output to the generator's output — it catches
STALENESS, never a PARSER BUG, because a mis-parse is identical on both sides.

Section 1b of the battery is the answer: an **independently written oracle**, hand-transcribed from
the family files with the expected values stated literally, deliberately derived from nothing the
generator produces. Every one of the eight fixed values in the corpus is asserted by hand, and the
two annotations that *look* like fixed values and are formulas are asserted to be neither.

### **AND THE GUARD-BOUNDARY CHANGE IS GONE.**

The first candidate emitted the corpus as a `.py` module, which tripped the Phase-0 guard confining
the typed gate vocabulary to the checkpoint kernel — because one contract's payload legitimately
fixes a gate-decision value (PL-7a's, ADR-010's ladder). That candidate amended the guard to permit
a "declaration site" behind an AST proof that the file contained no executable code.

The review defeated that proof in one line: a module-level `if` assembling a policy decision at
import time, with no function, class, call or import anywhere in it. The claim "a file that cannot
execute cannot leak policy" was true; the claim that the file could not execute was not.

The corpus is now **JSON**. JSON cannot execute, so nothing has to prove that it does not — and the
guard, which scans `*.py`, needs no amendment at all. ### **`test_phase0_null_gate.py` is
byte-identical to its original.** No safety guard was modified by this unit. The reviewer's own
observation drove this: the packaging argument justified *not parsing markdown at import*, and never
justified a `.py` artifact.

## The RE-REVIEW — and the defect the remediation itself introduced

### **THE REMEDIATED TREE WAS ALSO REJECTED, ON A DEFECT THIS UNIT CREATED WHILE FIXING ANOTHER.**
A second independent review — a session that neither implemented this unit nor performed the first
review — found that the fix for "a scalar field accepting a list" was **too broad, in exactly the
way R-01 and R-02 were too broad**.

The real defect was narrow: `ClaimRefused.cause = ["already_claimed", "expired"]` passed because the
enum check *iterates* a collection and approved each member individually. The fix refused **any**
collection in **any** field not written `name[]`.

### **THAT MADE 14 CANONICAL CONTRACTS UNSATISFIABLE** — including `CheckpointPassed`, the most
load-bearing contract in the corpus, whose `entity_versions` the family file declares
`(R, SD-3 set)` and §1 defines as *a set of entity versions*. The corpus marks a collection with the
ANNOTATION at least as often as with the marker: `caps_evaluated`(R — each cap id with its limit and
the observed value), `scope` (tenant + action_class), plural `evidence_refs` and `refs`,
`drift_diff`, `parsed_value`, `rendered_facts`. None carries `[]`.

It is the same error as reading a derivation formula as a fixed value: **a rule the specification
does not write, refusing values it explicitly requires.** The refusal is now confined to fields
constrained by an enum or a fixed value — which is precisely where the defect lived, and not one of
the 14 has either constraint. A general "a scalar may not be structured" rule is a specification
decision, not a validator's to invent.

**And the second finding was the same shape a third time.** §5 writes
`` `ClaimConfirmed`(when it backs a money action) ``. The qualifier was being discarded, so every
`ClaimConfirmed` was forced to pin a decision context — refusing ordinary deterministic
`LINKER_INFERRED` bindings on a rule §5 does not apply to them. This unit had already honoured the
identical qualifier reasoning twice (`material_facts_fingerprint`'s "where an amount is involved";
`ClaimConfirmed`'s conditional human-actor rule) and missed the third on the same contract.
Conditional membership is now derived and recorded, and the pins are not enforced for it.

### **WHY THE SUITE WAS GREEN THROUGH ALL OF IT — THE ORACLE GAP.**
`phase5_kit.canonical_payload` synthesises every non-`[]` required field as the **string**
`f"{name}-value"`. So the exhaustive 118-contract round trip, the required-field sweep and the enum
sweep all fed the new rule exactly the shape it permitted. And the section-1b oracle hand-checks
`required` / `fixed` / `human_only` and **no value types at all**. The oracle closed the
parser-correctness loop and left a value-shape loop open.
`test_a_spec_declared_structured_field_is_accepted` is that hole closed, with eleven spec-declared
structured fields asserted to be ACCEPTED — a positive regression, because the failure mode here is
over-strictness, and over-strictness is invisible to every negative test in the file.

Six further findings were fixed: an overclaiming docstring on the ER-10 scan (it says what it
actually reaches now — payload and `provenance_refs`, depth 8, and explicitly not `metadata`, which
§1 says gates nothing); a **three-name literal reintroduced in the test helper** — the R-04 defect
itself, reappearing 260 lines after the fixture documented why it was wrong, leaving `ApprovalGranted`
and `RuleActivated` covered by set membership alone; an unreachable assertion; an unanchored negative
loop whose target check also missed `document["payload"] = …`; two docstrings still naming the
retired `.py` artifact; and a bare import-time exception when the data file is missing.

## Nonblocking debt recorded, not actioned

| ID | Finding | Why nonblocking |
|---|---|---|
| **U53-D1** | §3's prose implies ‡ is the only way a contract names several producer transitions. The data disagrees: **11 unmarked contracts** legitimately name several transitions of ONE machine (`ApprovalVoided` AP-4/4p/5, `WorkBlocked` WI-5/6, …), and one ‡ contract (`PolicyVersionChanged` PO-4/6) names two of one machine. So neither "multi-producer ⇒ ‡" nor "‡ ⇒ multi-machine" holds | A prose/data nuance in the specification. The runtime carries §3's markers **exactly**, asserted both directions. Adjudicating prose is explicitly out of scope; an earlier version of that guard asserted the false rule and would have failed on correct data |
| **U53-D2** | `current_version` is parsed from each family table's `Event · v1 · producer` header, so it is per-FAMILY. The corpus states it that way today and every contract is v1 | The day one event ships v2, that header cannot express it and the generator must be revisited. Stated in the code rather than left to be discovered |
| **U53-D3** | `material_facts_fingerprint` is **not** required unconditionally on consequential events. §5 qualifies it "where an amount is involved", which this layer cannot decide without guessing | Where the specification fixes it, the family file declares it `(R)` in the payload (`CheckpointPassed`, `EffectGranted`, `ApprovalBound`) and ordinary field validation enforces it exactly. Requiring it unconditionally would refuse legitimate events on a rule the specification did not write |
| **U53-D4** | ER-9's "claim/proposal events" is mechanised as *family F6 ∪ names ending `Proposed`*, **minus `ClaimConfirmed`** (which states a FACT — GR-8 says a MODEL_INFERRED claim lands at `ClaimAmbiguous`, "never CONFIRMED, at any confidence"). That is a derivation from the canonical names, not a set the specification enumerates | Stated explicitly in the code. The blanket-family version was a REAL defect the review caught, and is fixed; what remains is that the rule is derived rather than enumerated |
| **U53-D7** | A required one-of member present as the EMPTY STRING (`{"rule_id": ""}`) satisfies it, exactly as an empty string satisfies a required scalar field | Consistent with the required-field rule, and the specification writes no non-empty constraint. ### Inventing one would be the precise over-strictness pattern that produced five of this unit's seven blocking defects — it is recorded rather than guessed at. The consequential PINS do strip-check, because ER-13 is about reproducing a decision, and that is a rule the specification does write |
| **U53-D6** | The ER-10 provenance scan covers the payload and `provenance_refs` to depth 8. It does NOT cover `metadata` (§1: "non-authoritative annotations (never gates anything)"), `evidence_refs`/`observation_refs`, or a lineage nested deeper than 8 | A provenance claim in `metadata` gates nothing by §1's own definition, and the depth bound is stated in the docstring rather than implied. Raising it is cheap if a real lineage ever approaches it |
| **U53-D5** | Six family rows name `actor_type=human` **without** "ONLY" (`HumanDecided`, `OwnershipTransferred`, `ApprovalRevoked`, `ExceptionAcknowledged`, `PolicySubmitted`, `RuleConfirmed`). They state the expected actor without declaring exclusivity, and are **not** enforced | Refusing a legitimate event is as much a defect as admitting an illegitimate one. The unconditional set (the rows saying "ONLY") is enforced and asserted by hand against the family files; promoting the advisory six needs a specification decision, not a guess |

## What this unit deliberately did NOT do

P5's `allowed_scope` is `[outbox, inbox, event contracts, replay sandbox, the GC-1 digest]`, and its
`prohibited_scope` is `[entities (P6), provenance (P7)]`.

* ### **The P3 checkpoint kernel and the P4 effect boundary were not touched.** Wiring canonical
  emission into them would be attractive and is **not in this unit's scope**. `checkpoint.py` and
  `effect_boundary.py` are byte-unchanged.
* **No freight workflow was implemented** (CLAUDE.md §11). The 13 machines and 134 transitions are
  P6, which stays `BLOCKED`.
* **Nothing was enabled.** Consuming the entire 118-contract corpus mints zero checkpoint witnesses
  and zero effect grants, asserted mechanically. R-07 stays CONTAINED and the production
  `GateRegistry` population stays EMPTY.
* **No P5 criterion is scored.** All 14 stay `PENDING`.

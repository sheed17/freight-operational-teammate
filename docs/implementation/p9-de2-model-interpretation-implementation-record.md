# P9-CP-2 — model-backed freight interpretation, behind one inference boundary

**Implementer record. Not a review, not an acceptance.** This is the on-disk evidence that
`meta.status_model.execution_state` requires for a landed checkpoint. The status authority is
[`IMPLEMENTATION-REGISTRY.yaml`](IMPLEMENTATION-REGISTRY.yaml) unit `P9` and
[`CURRENT.md`](CURRENT.md); this file establishes none.

> **The corpus is synthetic development input.** Nothing here is a design-partner observation, no
> freight rule is validated by it, and V-21 and V-14 remain **OPEN**. A score below is a measurement
> of one model on invented language, not evidence about a customer's inbox.
> **No independent review has been performed.** Tier-1 surfaces were touched (§6); one focused
> independent review is owed before merge ([`CLAUDE.md`](../../CLAUDE.md) §7).

## 1. What a broker can now do that they could not before

Nothing in production — it ships dark. What now *exists*: **Neyma can be handed freight the way
people actually say it**, and the load's canonical record comes out the same as if someone had keyed
every fact in.

- *"Checked in at the shipper 12:42, still waiting on a door. I'll update you in an hour."* becomes a
  driver's arrival claim at the pickup **and** an Expectation due at 13:44 — an hour after it was
  *said*, not after it was received. When 13:44 passes in silence over a channel that was provably
  up, the dispatcher is told. Nobody had to remember the promise.
- The same promise quoted in a forwarded email the next afternoon creates **nothing**.
- *"Receiver pushed us to 10 tomorrow"* against a system-of-record appointment of today 15:00–17:00 is
  a **Conflict** with every party's statement on it. No time is overwritten.
- *"Invoice attached. Detention is included per approval from Mike."* records a charge that someone
  **claims** was approved — a fraud signal — and asks a named person whether anyone approved it.
- *"That was the wrong load number in my last email — this is for 51004."* moves nothing; the person
  who owns inbound triage is asked, and when she corrects the binding the old one is retained.
- *"POD attached for 51005."* with no usable reference becomes a **candidate** load for a human, never
  a binding — and only ever a load of the brokerage that received it.

Run it, at no cost, from recorded readings:
`.venv/bin/python scripts/run_freight_interpretation_eval.py --stage all`

## 2. What was built

```
raw message / document text
  → route      is language interpretation genuinely required?           (usually not)
  → read       ONE typed reading through the InferenceGateway
  → ground     every item must quote the content, or it is dropped
  → normalize  deadline, calendar date, integer minor units — computed here
  → the same `asserts` / `extracted` structures P9-CP-1 already consumes
  → M5 / M6 / M7 / M8 / M9, the projection, reconciliation               (unchanged)
```

| Piece | Where | What it is |
|---|---|---|
| Task contracts | `inference/contracts.py` | Four tasks and no general-purpose call: `interpret_message`, `interpret_document_text`, `extract_commitments`, `propose_entity_candidates`. Strict typed outputs; every item carries `evidence_text`; **no field in any schema can carry authority or provenance**. Every request carries a `Route`. |
| Shared execution | `inference/gateway.py` | The one path every call takes: routing check, recorded-reading lookup, budget before every attempt, at most two attempts and only for transport or schema failure, typed validation, one telemetry record. No loop, no tools. `ReplayGateway` answers from a recording and from nothing else. |
| Provider | `inference/openai_responses.py` | The **only** module that imports the OpenAI SDK, lazily. Responses API, `responses.parse` with strict structured outputs, `store=False`, SDK `max_retries=0`. Cannot be constructed without `allow_live=True`. |
| Telemetry + budget | `inference/ledger.py` | Per call: provider, model, task, input / cached / output / reasoning tokens, latency, retries, outcome, subject and load correlation, a content digest. Per routing decision that avoided a call: the reason. No content, no credential. A per-run call and token budget. |
| Record / replay | `inference/recording.py` | Keyed by provider + model + task + schema version + prompt version + reasoning effort + normalized input. Stores the validated reply and its token counts, never the input. |
| Scripted gateway | `inference/scripted.py` | What every ordinary test uses. Same execution path as live. |
| Settings + prices | `inference/settings.py`, `configs/inference_pricing.json` | `NEYMA_INFERENCE_PROVIDER` (only `openai`), `NEYMA_INFERENCE_MODEL` (default `gpt-6-luna`), `NEYMA_INFERENCE_REASONING_EFFORT` (default `low`). A dated price table used only to print an estimate. |
| The deterministic bridge | `freight_domain/interpretation.py` | Routing, grounding, quote detection, arithmetic, conversion to the spine's structures, candidate screening. The only caller of a gateway task. |
| Intake | `freight_domain/intake.py` | Takes an optional `FreightInterpreter`. Reads once, at parse; stores the reading on the Observation, so the projection and every replay are pure reads. Exact resolution first; model candidates only when it found nothing. |
| Projection | `freight_domain/projection.py` | A claim's **source is who said it**, not which inbox it arrived in. A stop named only by kind resolves only when the load has exactly one. A message states an appointment *window*, never its status. |
| Eval | `eval/freight_corpus/`, `scripts/run_freight_interpretation_eval.py` | The twenty histories in raw form, nine raw-language histories, 24 labeled messages, 6 correlation cases, a field-by-field scorer. Replay by default; live needs `--live` **and** `NEYMA_LIVE_INFERENCE=1`. |

**Existing model paths.** *Reused as designs:* `email_triage.py`'s injection boundary and
"only a load id we supplied is honoured", and `extraction.py`'s "always a validated object, never
parsed free text". *Left alone, not routed through the gateway:* `extraction.py`,
`document_identifier.py` (vision, Instructor over Chat Completions), `email_triage.py` and
`inbox_brain.py` (an injected `complete` callable and hand-parsed JSON), `extraction_bridge.py` and
`ingestion.py` (deterministic). They are live dogfood paths with their own tests; routing them through
the gateway is a later, separately-measured change.

## 3. What was measured, live

**Model and API:** OpenAI `gpt-6-luna`, Responses API (`POST /v1/responses`) with strict structured
outputs, `reasoning.effort = low`, `store = false`, SDK `openai` 2.16.0. One model. No fallback.

| Stage | Size | Result |
|---|---|---|
| Smoke | 5 messages | 5/5 calls returned valid typed output |
| Labeled messages | 24 messages, 209 scored fields | **24/24 fully correct, 209/209 fields** (second run — see below) |
| Correlation | 6 cases | **6/6**; ids offered that were not supplied: **0** |
| Commitments-only task | 4 messages | 4/4 deadlines |
| Twenty hostile histories, raw | 22 messages, 23 documents, 2 candidate requests | **264/264 labeled outcomes**; 0 failed readings; 0 cross-tenant violations; 0 effect rows |
| Nine raw-language histories | 18 messages, 2 documents, 4 candidate requests | **88/88 labeled outcomes** |

**What the first labeled run showed (22/24, 208/210).** Three disagreements, none of them a failure
of the model to read:

1. *"still waiting on a door"* read as a delay. The label said no delay. The label was wrong; the
   field is no longer scored for that case.
2. *"…ok'd it over the phone before we unloaded"* read as DELIVERED. The label said no status. The
   text does say the truck was unloaded; the field is no longer scored for that case.
3. *"Customer says the delivery appt is 1300 Friday, not 0900"* — the appointment was read correctly
   and marked *quoted*, so the application dropped it. **The prompt was at fault:** it defined quoted
   text to include "words the sender is only repeating from someone else". Reported speech is the
   sender's own statement. The prompt was corrected (`p9-prompts-2`) and the whole labeled set
   re-recorded.

So the labeled set has informed one prompt change and two label corrections and is no longer a clean
measure. The two spine stages — 352 labeled outcomes — were run **once**, after the prompt change,
and were not tuned against.

**Where the model's reading differs from the fixtures (2 of 22 corpus messages).** *"loaded and
rolling"* and *"Loaded, on the way."* were read as LOADED **and** IN_TRANSIT; the fixtures structured
only LOADED. The model read more that is really there. No labeled outcome moved.

**Tokens and spend, every live call through the gateway (from the ledger):**

| | |
|---|---|
| Live calls | 139 — all returned valid typed output; 0 retries; 0 schema failures; 0 provider failures |
| Input tokens | 299,707, of which 235,639 were cached by the provider |
| Output tokens | 32,043, of which 10,022 reasoning |
| Estimated cost | **$0.025** at `inference-pricing-2026-10-02` ($0.10 / $0.01 cached / $0.50 per 1M) |
| Latency | median 3.1 s, p90 4.3 s, max 8.0 s |

That includes the 34 calls of the superseded first labeled run and 5 of the smoke run. Per task, in
the committed recording: `interpret_message` ≈ 2,800 input (≈ 2,670 of it the cached instructions and
schema) and ≈ 220 output; `interpret_document_text` ≈ 1,050 / 295; `propose_entity_candidates` ≈
1,000–2,000 / 45–95; `extract_commitments` ≈ 950 / 130.

**Per load, on the twenty histories:** 17 of 23 loads needed a model at all; mean **2.5 calls**, 4,679
input and 652 output tokens per load (max 7 calls). 143 of 190 routing decisions were settled
deterministically; 47 went to a model.

**What `gpt-6-luna` struggled with:** nothing that changed an outcome. It was not asked anything
hard about scale — the longest input is a five-line forwarded email and a nine-line invoice.

**Is there evidence today to justify a stronger fallback model?** No. Not one case was found where
Luna failed and a stronger model would have helped; no stronger model was called.

## 4. The legacy vision surface was NOT moved to Luna, and why

The target was `OPENAI_MODEL=gpt-6-luna` and `OPENAI_IDENTIFIER_MODEL=gpt-6-luna` unless there was a
concrete capability reason. There is one, measured against the live API:

1. As committed, `extraction.py` and `document_identifier.py` send `max_tokens` to any model not
   named `gpt-5*` / `o*`. `gpt-6-luna` answers **400 `unsupported_parameter`**.
2. With that one-line gate widened, it answers **400: "Function tools with reasoning_effort are not
   supported for gpt-6-luna in /v1/chat/completions. To use function tools, use /v1/responses or set
   reasoning_effort to 'none'."** The legacy surface is Instructor over Chat Completions with function
   tools.

So the legacy surface cannot call Luna without being rebuilt on the Responses API (or run at
reasoning effort `none`, whose accuracy on scanned invoices nobody has measured). The trial edit was
reverted: both files are byte-identical to `HEAD`. The gateway therefore has its **own** model setting
and does not read `OPENAI_MODEL` — a setting made for scanned-document extraction must not silently
choose, and price, the model that reads every message. Moving vision extraction behind the gateway
is debt `P9-D13`.

## 5. What broke, or was wrong, when a model's reading hit the spine

| # | Finding | Disposition |
|---|---|---|
| F-9 | **A later message silently superseded another party's statement.** A fact's "source" for a message was the inbox it arrived in, so a customer's "1300" replaced a carrier's "0900" with no Conflict — invisible while fixtures made few claims, routine once a model reads every message. | **Fixed.** The source of a claim made in a message is the channel *and the sender*. A party's own later statement still supersedes its earlier one, which is retained. |
| F-10 | **A counterparty's sentence could confirm an appointment.** A fixture assert defaulted an appointment claim's status to CONFIRMED and the projection observed it. | **Fixed for read language.** A claim read from text states a window only; REQUESTED is not CONFIRMED (CD-13). |
| F-11 | **The one-harness guard was blind to indirect reach.** It looked for a direct `freight_domain` import; a second script reaching the spine through `eval/freight_corpus` left it green. | **Replaced** (rule 20): it now counts a `freight_corpus` import as reaching the spine, names two harnesses by exact set, and forbids production code from importing the corpus. Mutants for both routes. |
| F-12 | **An Expectation raised on a binding that is later corrected stays owed** (seen in R03: a POD expectation on the load a delivery report was wrongly bound to). | **Recorded** — it is `P9-D2` reaching a new place. Owned and visible. |
| F-13 | **The fixtures knew things the text does not say.** "at the dock, checked in" was labeled AT_PICKUP. A reader cannot know which dock. | An arrival with no stated stop is **not placed** (dropped with a reason). The raw corpus says "at the shipper" where the fixture relied on knowing. |

## 6. Safety surfaces touched — tier 1, independent review owed before merge

- **One ships-dark guard replaced** (F-11), and `test_p9_is_recorded_…` now covers two checkpoints.
- **Tenant isolation**: which loads a model is offered. Each intake offers only its own tenant's
  loads; an id the request did not supply is refused; proved with the same load number, PO, BOL and
  PRO under two brokerages in one database.
- **The identity-binding path**: model candidates are recorded through M6 as `MODEL_INFER` →
  AMBIGUOUS, human-owned. The unused `CandidateGenerator` seam in `entity_mapping.py` was removed.
- **A provider credential is read** in one new place. It is not stored, logged or recorded, and a
  provider's error text is redacted and kept out of telemetry.
- **No migration, no kernel change, no gate, no effect path, no production caller.**

**Mutation proof.** `scripts/mutate_p9_interpretation.py` — 41 mutants, 41 caught on the first full
run. Each reintroduces one real defect; the named guard is green before, RED under it, and green after
an in-memory byte-for-byte restore. `scripts/mutate_p9_freight_domain.py` (the P9-CP-1 battery) was
re-run against the changed spine: 42 of 42 caught, after two anchors were repaired because the code
they mutate moved — the "conversational rate is not weakened" mutant, and the "review claimed" mutant,
which now names its checkpoint. Neither repair changed what the mutant does.

**Rollback / disablement.** Nothing live reaches it. With no interpreter handed to `FreightIntake`
the spine is the deterministic one of P9-CP-1. To remove: delete `src/freight_recon/inference/`,
`freight_domain/interpretation.py`, the raw corpus modules and the two scripts, and revert the intake
and projection hunks. F-9 and F-10 are independent fixes and should stay.

## 7. Knowingly incomplete

| ID | Debt | Why it does not block this checkpoint |
|---|---|---|
| `P9-D12` | An amount stated without a currency is read in the load's sell-rate currency. Whether an unstated currency may be assumed at all is **NEEDS VALIDATION**. | The resulting fact is weakened to `MODEL_INFERRED`: it cannot gate or dispute. With no single load currency there is no amount. |
| `P9-D13` | Vision extraction is not behind the gateway and cannot use `gpt-6-luna` (§4). | The legacy surface is unchanged and keeps its own model. |
| `P9-D14` | An appointment time stated without an end is a zero-width window, so "we're set for 1300" disputes a 13:00–15:00 window. Whether containment is agreement is **NEEDS VALIDATION**. | It can only raise a Conflict a human looks at. |
| `P9-D15` | A model reads a message with no load context, so an arrival that does not say where ("checked in") is not placed. | Nothing is guessed; the message stays on the load's timeline. |
| `P9-D16` | The evidence quote and stated support of a model-proposed candidate are not persisted on the M6 claim (only the method, provenance, owner and queue order are). | The claim is still human-owned and unbound. |
| `P9-D17` | Only zero-candidate records get model candidates; a deterministic ambiguity is not ranked by a model. | The deterministic candidates stand, human-owned. |
| `P9-D18` | `.env.example` still documents the old defaults: this session's permission settings deny writing it. | The gateway's defaults are in code; the replacement text is in the handoff. |
| `P9-D19` | The eval measures one model on a small synthetic corpus, with short inputs. No real mailbox, no long thread, no scanned document, no adversarial prompt-injection suite beyond two cases. | Nothing is enabled on it. |
| `P9-D20` | What leaves the brokerage for the provider — message and document text, and for a candidate request a summary of that brokerage's own loads with party and driver names — has had no data-governance review. `store=false` is set on every call. | No real data is sent: the corpus is synthetic and nothing live calls the boundary. Required before any real mailbox is read. |
| `P9-D2` | Now also: an Expectation raised on a since-corrected binding stays owed (F-12). | As recorded in P9-CP-1. |
| `P9-D11` | Still no P9 `acceptance_criteria` block. | Not the builder's to score (CLAUDE.md §10). |

## 8. What remains for P9

An independent review of both checkpoints; the P9 acceptance block; the fifteen unbuilt entities and
per-entity tables (`P9-D4`); concurrency and PostgreSQL exercise (`P9-D7`); a real ingestion adapter
(mail / SMS → `InboundRecord`) with its own envelope-reference extraction; context-aware reading
(`P9-D15`); vision behind the gateway (`P9-D13`); and design-partner validation of V-21, V-14 and the
NEEDS VALIDATION rules above.

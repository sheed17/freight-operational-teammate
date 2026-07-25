# Design-Partner Evidence Record

> ### ⛔ **THE HEADLINE: this repository contains NO firsthand design-partner observation recorded
> by any agent.** No agent has watched the partner work, read their inbox, seen their TMS, or
> handled their documents. Everything below is either founder-relayed, industry research, or
> architectural inference.
>
> **Nothing in this file may be upgraded to `DIRECTLY OBSERVED` by an agent.** Only a human who
> actually observed the thing can move an entry up a class.

**Why this file exists:** the repository is the memory. Without an explicit record of *what class
of evidence* each claim rests on, a confident-sounding inference becomes indistinguishable from a
field observation within one or two sessions — and then a freight rule nobody validated gets
enforced on real money.

---

## Evidence classes

| Class | Definition | May authorise? |
|---|---|---|
| **DIRECTLY OBSERVED** | An agent saw this in the partner's real systems or documents | ✅ Yes |
| **REPORTED BY DESIGN PARTNER** | The partner stated it, recorded verbatim | ✅ Yes, with attribution |
| **RELAYED BY FOUNDER** | The founder reported it on the partner's behalf | ⚠️ With attribution; confirm before building |
| **EXTERNAL RESEARCH** | Industry pattern, not this partner | ❌ Not about our customer |
| **ARCHITECTURAL INFERENCE** | Derived from our own design reasoning | ❌ Never evidence about the world |
| **NEEDS VALIDATION** | Unknown | ❌ **Stop** |

---

## 1. DIRECTLY OBSERVED

### ⛔ **NONE.**

No entry qualifies. The controlling caveat is recorded in the corpus itself
([`freight-discovery.md`](freight-discovery.md) §0.2):

> *"I have not observed our design partner. Rasheed has. Nothing in this document describes our
> customer unless explicitly sourced from Rasheed's report."*

**What HAS been directly observed is our own test rig, not the partner's operation.** That
distinction is load-bearing and is recorded here so it is not lost:

| Observation | What it is | What it is NOT |
|---|---|---|
| TruckingOffice screen behaviour, form quirks, the customer-binding quirk | Our proving-ground TMS, driven live by our own agent | **Not evidence that the partner uses TruckingOffice** — V-05 is open |
| A live AR write completed end-to-end (invoice raised, TMS ground truth moved Delivered→Invoiced) | Proof our write path can work against a real TMS | **Not evidence about the partner's volumes, rules or approval process** |
| transporters.io discovery generalising across a second TMS | Evidence the discovery layer is not single-TMS-shaped | Not evidence about the partner's TMS |

## 2. REPORTED BY DESIGN PARTNER

### **NONE recorded verbatim in this repository.**

There is no transcript, questionnaire response, or partner-authored document in the corpus. Items
that may have been discussed verbally are not recorded and therefore **do not exist for the purposes
of implementation.**

## 3. RELAYED BY FOUNDER

The following appear in the corpus attributed to the founder rather than to direct observation.
They are the strongest partner-specific evidence available, and they are thin.

| Claim | Source | Status |
|---|---|---|
| Context switching across a dozen systems all day is a real, felt pain | [`operating-model.md`](operating-model.md) §2.2, marked `DESIGN_PARTNER_OBSERVED` **(relayed)** | Attributed, not verbatim |
| "Rasheed / Neyma Test Freight is the first supervised design partner" | [`../FIRST_DESIGN_PARTNER_RASHEED.md`](../FIRST_DESIGN_PARTNER_RASHEED.md) | ⚠️ **This describes a test entity operated by the founder, not an independent brokerage.** It must not be read as an external design partner. |
| The first pilot is supervised, with no autonomous TMS write | [`../WHEN_DESIGN_PARTNER_DATA_ARRIVES.md`](../WHEN_DESIGN_PARTNER_DATA_ARRIVES.md) | A stated constraint, consistent with ADR-003 |

> ### **The "first design partner" in this repository is a founder-operated test brokerage.**
> That is a legitimate proving ground and it is **not** an independent customer. Treating it as one
> would make our own design assumptions look like external validation — the exact circularity this
> file exists to prevent.

## 4. EXTERNAL RESEARCH

[`freight-discovery.md`](freight-discovery.md) §§1–12 — a substantial, carefully labelled body of
industry knowledge. Each claim carries `CONFIRMED INDUSTRY PATTERN`, `COMMON INDUSTRY PRACTICE`,
`VENDOR-SPECIFIC APPROACH` or `SPECULATION`.

Patterns marked `CONFIRMED INDUSTRY PATTERN` (structural to brokerage — regulatory, contractual or
universal) include: unbilled delivered loads pending POD; carrier invoices paid without audit;
POD chasing; AR aging; check calls; repeated manual re-entry.

> ### **These are true of the industry. They are not measurements of our partner.** Volumes, rates
> and priorities are all `NEEDS VALIDATION` (§13, items V-01…V-21).

## 5. ARCHITECTURAL INFERENCE

Ours, not the world's. Recorded so it is never mistaken for evidence:

| Inference | Where | Status |
|---|---|---|
| **W6 Documentation → W8 Billing is the right first slice** | [`operating-model.md`](operating-model.md) §, marked `HYPOTHESIS` — *"This is not yet a decision"* | ### **NEEDS DESIGN-PARTNER VALIDATION** (V-W1) |
| The ideal customer profile (size, maturity, systems posture, economics) | `operating-model.md` §2.1, marked `HYPOTHESIS` | NEEDS VALIDATION |
| Documentation→Billing has bounded, reversible blast radius | derived from our own risk model | Inference only |
| Extraction is a fail-closed adapter capability, not the product | [`W6-documentation.md`](../specifications/workflows/W6-documentation.md) | Architecture decision, not observation |

## 6. NEEDS VALIDATION

The full enumerated set is [`OPEN-VALIDATION-ITEMS.md`](OPEN-VALIDATION-ITEMS.md) — **21
customer-specific unknowns plus 2 architectural ones**, each with a blocking class and a safe
interim behaviour.

---

## Structured record of what is and is not known

| Field | State |
|---|---|
| **Workflows discussed** | The eleven canonical loops are specified from *industry* research and architecture. **No loop has been walked through with the partner and recorded.** |
| **Systems used** | ### **UNKNOWN** (V-05…V-10). TruckingOffice and transporters.io are **our** rigs. Their TMS, accounting system, portals, load boards and mailbox provider are unrecorded. |
| **Documents involved** | Document *types* are known from industry research (invoice, rate con, POD, BOL, lumper receipt). ### **No partner documents are in the repository.** The corpus is synthetic — see [`../SYNTHETIC_CORPUS.md`](../SYNTHETIC_CORPUS.md). |
| **Decision points** | Modelled architecturally. **Not validated against how the partner actually decides.** |
| **Approval rules** | ### **UNKNOWN** (V-04). No approver names, roles or dollar thresholds are recorded. This is why the interim rule is *every consequential action needs explicit human approval.* |
| **Exception patterns** | Industry taxonomy only. The partner's real discrepancy rate and resolution path are unknown (V-17). |
| **Volumes** | ### **NO VOLUME IS RECORDED ANYWHERE** (V-01). Loads/day, invoices/week and emails/day are all unknown. No design may assume a volume. |
| **Responsible roles** | ### **UNKNOWN** (V-04, V-20). |
| **Current unknowns** | 21 customer-specific + 2 architectural — [`OPEN-VALIDATION-ITEMS.md`](OPEN-VALIDATION-ITEMS.md) |

## Evidence references

| Reference | Contains |
|---|---|
| [`freight-discovery.md`](freight-discovery.md) | Industry research, every claim labelled; §13 is the unknowns list |
| [`operating-model.md`](operating-model.md) | The operating model; hypotheses marked |
| [`../FIRST_DESIGN_PARTNER_RASHEED.md`](../FIRST_DESIGN_PARTNER_RASHEED.md) | The founder-operated test-brokerage runbook |
| [`../WHEN_DESIGN_PARTNER_DATA_ARRIVES.md`](../WHEN_DESIGN_PARTNER_DATA_ARRIVES.md) | The list of inputs still needed |
| [`../SYNTHETIC_CORPUS.md`](../SYNTHETIC_CORPUS.md) | The synthetic documents used in place of real ones |
| [`../LIVE_WRITE_PROOF.md`](../LIVE_WRITE_PROOF.md) | Proof of a live write **against our own rig** |

---

## What this blocks — and what it does not

### ⛔ Blocked

- **P10** — the first vertical slice. Which loop, and its rules, are unvalidated.
- **P9** — freight-domain cardinalities (V-21).
- **P8** — the policy engine's thresholds and the exception taxonomy (V-04, V-17).
- Any promotion of W6→W8 to validated product truth.

### ✅ NOT blocked

- **P3** — checkpoint, witness, claim CAS
- **P4** — adapter containment and closing R-07
- **P5** — events and replay isolation
- **P6** — platform entities and state machines
- **P7** — provenance and evidence

> ### **The safety wall is loop-independent.** Nothing about the missing partner evidence prevents
> making external effects safe — which is precisely why the phase order puts P3 and P4 first.
> **The absence of customer data is not a reason to stall; it is a reason not to build freight
> rules yet.**

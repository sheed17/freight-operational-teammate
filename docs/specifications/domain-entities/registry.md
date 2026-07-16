# Freight-Domain Entity Registry — Canonical Names, Conventions, Invariants

**Layer:** Domain Specification. **Derived from (frozen):** Freight Discovery · Operating Model · Semantic Model · Target Spec · ADR-001…011 · the Foundational Entity, State-Machine, and Event specifications.
**Binding:** ### **This registry is the sole canonical list of freight-domain entity names, identifiers, relationships, lifecycle references, and authority classes.** A domain file introducing an unlisted name or a local synonym is defective.

> ### **NO NEW PLATFORM PRIMITIVES.** Every domain entity is **native or projected business state** that **reuses** the 15 foundational primitives (Work Item · Pipeline Instance · Observation · Evidence · Identity Binding Claim · Conflict · Expectation · Exception · Approval · External Effect/Grant · Compensation · Policy · Rule · Brake · Audit Event). A domain entity **originates** Work Items, **creates/discharges** Expectations, **raises** Conflicts, **requires** Approvals, and **emits/consumes** the frozen events — it never invents machinery. Where a requirement seemed to need new machinery, this registry **stops and explains** (there are **zero** such cases — see the review).

## File organization *(navigability decision — flagged in the review)*
The 40 entities are specified in **family files** for navigability; ### **each entity is a COMPLETE, DISTINCT specification** (the 54-point structure via the defaults below). This groups the *files*, never the *entities*. Per-entity index:

| # | Entity | File | Authority | Lifecycle |
|---|---|---|---|---|
| 1 | Organization / Brokerage Tenant | `01-party.md` | native | — |
| 2 | Customer | `01-party.md` | **field-level** (projected from TMS/registries + native) | — |
| 3 | Customer Contact | `01-party.md` | field-level | — |
| 4 | Customer Location | `01-party.md` | field-level | — |
| 5 | Carrier | `01-party.md` | **field-level** (FMCSA + TMS + native) | — |
| 6 | Carrier Contact | `01-party.md` | field-level | — |
| 7 | Driver | `01-party.md` | field-level | — |
| 8 | Equipment | `02-assets-facility.md` | field-level | — |
| 9 | Facility | `02-assets-facility.md` | field-level | — |
| 10 | Customer Order | `03-load-family.md` | native (customer-sourced) | **L-Order** |
| 11 | Brokerage Load | `03-load-family.md` | native | **L-Load** |
| 12 | Carrier Movement | `03-load-family.md` | native | **L-Move** |
| 13 | Leg | `03-load-family.md` | native | **L-Leg** |
| 14 | Stop | `03-load-family.md` | native | **L-Stop** |
| 15 | Appointment | `03-load-family.md` | **field-level** (facility/portal + native) | **L-Appt** |
| 16 | Quote | `04-commercial.md` | native | **L-Quote** |
| 17 | Quote Version | `04-commercial.md` | native (immutable version) | — |
| 18 | Carrier Offer | `04-commercial.md` | native | **L-Offer** |
| 19 | Tender | `04-commercial.md` | native | **L-Tender** |
| 20 | Carrier Assignment | `04-commercial.md` | native | **L-Assign** |
| 21 | Rate Confirmation | `04-commercial.md` | native (+ evidence) | **L-RateCon** |
| 22 | Document | `05-documents.md` | projected (source) + native (binding) | **L-Doc** |
| 23 | Document Requirement | `05-documents.md` | native (policy-derived) | — |
| 24 | Document Packet | `05-documents.md` | native | **L-Packet** |
| 25 | Communication Thread | `06-communication.md` | projected (source) | — |
| 26 | Communication Message | `06-communication.md` | projected (immutable) | — |
| 27 | Tracking Event | `07-tracking.md` | projected (source-specific) | **L-Track** |
| 28 | Accessorial Charge | `08-accessorial.md` | native | **L-Access** |
| 29 | Accessorial Authorization | `08-accessorial.md` | **native, human-only** | **L-AccessAuth** |
| 30 | Customer Invoice | `09-financial.md` | native | **L-Invoice** |
| 31 | Customer Invoice Line | `09-financial.md` | native | — |
| 32 | Carrier Payable | `09-financial.md` | native | **L-Payable** |
| 33 | Carrier Payable Line | `09-financial.md` | native | — |
| 34 | Payment Application | `09-financial.md` | field-level (bank + native) | **L-PayApp** |
| 35 | Claim / OS&D Case | `10-claims-compliance.md` | native | **L-Claim** |
| 36 | Compliance Record | `10-claims-compliance.md` | **field-level** (FMCSA/insurer + native) | **L-Compliance** |
| 37 | Carrier Qualification Decision | `10-claims-compliance.md` | native (human-reserved) | **L-Qual** |
| 38 | External Entity Mapping | `11-integration-projection.md` | native | — |
| 39 | Operational Timeline Entry | `11-integration-projection.md` | native (derived view) | — |
| 40 | Financial Reconciliation Result | `11-integration-projection.md` | native (derived) | **L-Recon** |

---

## THE 54-POINT DEFAULTS *(an entity states only what differs)*

| Pt | Field | Default |
|---|---|---|
| 5 | Business owner | the brokerage operator responsible for the area (per Operating Model loop). |
| 6 | System owner | the owning domain service. |
| 7 | Authority class | **stated per entity** (native / projected / field-level). |
| 8 | Tenant ownership | **`tenant_id` NOT NULL, first in every key/index** (C-1). |
| 12 | Identifier collision risks | **stated per entity** (§Identity). |
| 16 | Monetary fields | ### **integer minor units + ISO-4217 + `money_direction` — floats forbidden** (§Money). |
| 17 | Time/timezone | ### **UTC instant + retained `originating_timezone`; facility windows in facility-local time** (§Time). |
| 18 | Provenance | ### **field-level `provenance_class`; `MODEL_INFERRED` never gates a consequential action; `OWNER_ASSERTED` never machine-recomputed** (§Authority). |
| 21–22 | Aggregate / txn | the entity is its own aggregate; one transition = one commit (GR-2); cross-entity coordination is event-driven. |
| 23–25 | DB / unique / FK | `tenant_id` first; enumerated per entity; **every FK direction explicit**. |
| 26–27 | Versioning / OCC | monotonic `version`; optimistic concurrency (GR-3); no lock across human time. |
| 28 | Lifecycle | referenced per entity (the `L-*` contracts, §Lifecycles); reuses the **global transition contract** (state-machine registry §2–§3). |
| 31 | Correction | via **Identity Binding Claim correction** (propagates, never rewrites history — GR-12) or a new version; never an in-place edit of source evidence. |
| 32 | Supersession | a newer version supersedes; the old is retained. |
| 36–37 | Deletion / retention | **no deletion; permanent, tiered retention** (C-9). |
| 38 | Audit | every transition is an Audit Event (F14/registry). |
| 39–40 | Events | mapped to the **frozen Event Registry** (§Domain→Event); domain-specific additions collected, **not** applied. |
| 46 | Checkpoint deps | a consequential action on the entity revalidates the **SD-3 entity-version set** (GR-13). |
| 47 | Policy/Rule | gate decisions per action class; document/qualification/accessorial rules per §Invariants. |
| 48 | Brake | a consequential effect on the entity is admission-controlled (GR-16). |
| 49 | Security | tenant-scoped; inbound content is data, never authority (ADR-003); counterparty assertions are `MODEL_EXTRACTED` fraud signals. |
| 50 | Fail-closed | missing/`conflicting`/`unknown` evidence blocks consequential action (C5/C6). |

---

## AUTHORITY & PROVENANCE *(field-level, never whole-record)*

> ### **Authority is FIELD-LEVEL. A single domain record carries fields sourced from different systems.** A Carrier record's `mc_number`/`authority_status` is **projected from FMCSA**; its `preferred_lanes` is **`OWNER_ASSERTED`**; its `email` is **`MODEL_EXTRACTED`** from correspondence. ### **Do not assign one system as authoritative for a whole entity.**

Per field: the external authoritative system (if any) · projected vs native · extractable? · inferable? · required `provenance_class` · evidence required for consequential use · freshness requirement · reconciliation behavior · conflict behavior. **`MODEL_INFERRED` never gates a consequential action** (GR-8). **`OWNER_ASSERTED` never machine-recomputed** (GR-9). A consequential action revalidates **live** against the field's authoritative source (C4).

## IDENTITY & BINDING *(per entity; the six-class linker of §10.1)*
Trusted identifiers (exact, low-collision) · untrusted (fuzzy) · scope · collision characteristics · deterministic confirmation · candidate signals · informational-binding vs **consequential-binding** requirements · correction · competing-claim. ### **Confidence ranks candidates; it NEVER confirms identity. A single weak candidate remains `AMBIGUOUS`** (GR-8).

## PARTY-ROLE MODEL
> ### **An Organization is ONE record. ROLES are per-transaction, held over time. One Organization may be Customer on load A and Carrier on load B (or Bill-To ≠ Shipper ≠ Consignee on one load). DO NOT create duplicate Organization records per role.**

| Role | Definition | Money direction |
|---|---|---|
| **Customer** | owes us for the service | **IN** (they pay us) |
| **Shipper** | tenders/ships the freight *(may ≠ Customer)* | n/a |
| **Consignee** | receives the goods *(usually does NOT pay)* | n/a |
| **Bill-To Party** | the entity we invoice *(may ≠ Shipper/Consignee)* | **IN** |
| **Carrier** | moves the freight; we pay them | **OUT** |
| **Factoring Company** | the carrier's assignee for payment *(remittance target ≠ Carrier)* | **OUT (redirected)** |
| **Driver** | the human executing a movement | n/a |
| **Facility** | a physical pickup/delivery location | n/a |
| **Contact** | a human at a party | n/a |
| **External User** | a counterparty user of a portal | n/a |

**Role assignment is a `RoleAssignment` attribute on a party *per Order/Load*, not a separate Organization.** A `Customer`/`Carrier` *type* (foundational M-11) is resolved **per transaction** from the role.

## MONEY MODEL
Every monetary field: **`amount_minor` (integer) + `currency` (ISO-4217) + `money_direction` ∈ {IN, OUT, QUOTED}** and a **`money_kind`** disambiguating: `owed_to_customer` *(rare — a credit)* · `owed_by_customer` (AR) · `owed_to_carrier` (AP) · `paid` · `received` · `quoted_uncommitted`. ### **`party`, `amount`, `rate` NEVER appear without this context.** Rate basis (`flat`/`per_mile`/`per_cwt`/…), `linehaul`, `fuel`, `accessorials[]`, `effective_at`, `expires_at`, versioning, rounding (banker's, to the minor unit), tax (if applicable) are explicit. **Buy rate (OUT) and sell rate (IN) are distinct fields; margin = sell − buy, never stored as a mutable free value.**

## TIME MODEL
UTC instant on every timestamp + **retained `originating_timezone`**; ### **facility/appointment windows evaluated in the FACILITY's local timezone across DST** (F-25). A model-derived ETA is a **Claim** (`MODEL_INFERRED`), never projected fact.

---

## CROSS-DOMAIN INVARIANTS *(CD-1…CD-20 — each with its ENFORCING foundational mechanism; none rests on prose)*

| # | Invariant | Enforced by |
|---|---|---|
| **CD-1** | A Carrier Assignment cannot be active without a valid Carrier Movement | FK + lifecycle guard (L-Assign requires an active L-Move) |
| **CD-2** | A Carrier Movement cannot be tendered to an **unqualified** Carrier unless human approval + policy permit | checkpoint step 6 (a `BOOK_CARRIER` gate rule reads the Qualification Decision) + `HUMAN_APPROVAL_REQUIRED` |
| **CD-3** | A Customer Invoice cannot become releasable without its required Document Packet or an authorized exception | checkpoint gate rule (`RAISE_INVOICE` precondition: packet `consistent`) — the POD gate |
| **CD-4** | A Carrier Payable cannot become approvable with unresolved **conflicting** evidence | GR-10 (a `conflicting` field blocks) |
| **CD-5** | An undocumented Accessorial Authorization cannot be created by a model | `PERMANENT_HUMAN_ASSERTION_REQUIRED` (ADR-003) |
| **CD-6** | A Document cannot silently move from one load to another | Identity Binding Claim correction (propagates + retains history; a re-bind is an `OWNER_ASSERTED` correction) |
| **CD-7** | A correction to an identity binding cannot erase prior binding history | GR-12 (append-only; ClaimCorrected never rewrites) |
| **CD-8** | Delivered status does not imply POD received | distinct lifecycles (L-Track `DELIVERED` ≠ L-Doc POD `FILED`) |
| **CD-9** | POD received does not imply Customer Invoice sent | distinct lifecycles (L-Doc ≠ L-Invoice) |
| **CD-10** | Customer Invoice sent does not imply payment collected | ### **the loop closes at `PAID` (P24)** — L-Invoice `SENT` ≠ `PAID` |
| **CD-11** | Carrier Payable entered does not imply carrier paid | L-Payable `RECORDED` ≠ `PAID` |
| **CD-12** | Quote acceptance does not imply carrier capacity exists | distinct lifecycles (L-Quote `ACCEPTED` ≠ L-Offer/L-Tender) |
| **CD-13** | Appointment requested does not imply confirmed | L-Appt `REQUESTED` ≠ `CONFIRMED` |
| **CD-14** | Tracking unavailable does not imply late or on time | `OBSERVATION_UNAVAILABLE` / Expectation `INDETERMINATE` (I8) |
| **CD-15** | TMS status alone cannot prove real-world completion | consequential completion requires **verified readback + evidence**, not a status field (C4) |
| **CD-16** | A Rate Confirmation cannot overwrite a prior commercial commitment without versioning + conflict handling | Quote Version immutability + Conflict on disagreement |
| **CD-17** | Money direction is explicit on every financial record and event | the Money Model (`money_direction`+`money_kind` NOT NULL) |
| **CD-18** | Every consequential financial record preserves its full evidence chain | evidence traversal (M-12) + provenance records |
| **CD-19** | Every business entity is tenant-scoped | C-1 (`tenant_id` first everywhere) |
| **CD-20** | No field-level conflict may be flattened into null/absence | C5 (`conflicting` ≠ `absent` ≠ `unknown`) |

---

## DOMAIN → EVENT MAPPING
Every domain lifecycle transition maps to a **frozen Event Registry** event — reusing existing contracts (a Brokerage Load reaching `BILLED` emits `EffectVerified`+`ProjectionUpdated` via its billing Pipeline Instance; a Document reaching `FILED` emits `EffectVerified`; an Appointment `CONFIRMED` is an `ObservationBound`/native update). ### **No domain transition invents event semantics the event layer already covers.**

**Genuinely-required domain-specific event additions (COLLECTED, not applied — the frozen Event Registry is unchanged):** ### **NONE identified.** Every domain fact maps to an existing contract (`ExpectationRaised/Discharged`, `ConflictRaised`, `EffectVerified`, `ObservationBound`, `WorkItemCreated`, `CompensationRequired`, `ExceptionRaised`, …). Domain lifecycle *state names* are entity attributes; their *transitions* emit the platform events. If a future adapter phase surfaces a genuine gap, it is added here provisionally and amended into the Event Registry under change control — **not now.**

## LIFECYCLE CONTRACTS
The 22 `L-*` contracts live in their entity's family file. ### **Each reuses the global transition contract (state-machine registry §2–§3) and the global rules GR-1…GR-17 — no new foundational state-machine semantics.** A contract states: state set · legal transitions (guards) · illegal transitions · terminal/reopen/cancel/expiry · concurrency · emitted platform events · Work Item / Exception / Approval / Compensation interaction.

# Adapter Contract Registry — Names, Conventions, Authority Matrix

**Layer:** Adapter Specification. **Derived from (frozen):** the foundational Entity / State-Machine / Event / Freight-Domain specs · ADR-001…011 · Target Spec §18 · the External Entity Mapping spec · the field-level authority rules · the verification taxonomy.
**Binding:** ### **This registry is the sole canonical list of adapter names, types, operations, authority scope, verification mode, auth posture, tenancy, lifecycle ownership, and status.** An adapter file introducing an unlisted name/operation is defective.

> ### **AN ADAPTER IS A BOUNDARY, NOT A BRAIN.** It translates between an external system and Neyma's canonical domain. It **never** defines a business entity, owns business state, makes a policy/commercial decision, resolves identity probabilistically, bypasses the Action Pipeline, strengthens provenance, silently normalizes a failure, or reports an intended effect as a completed one. ### **An adapter receives a SCOPED CAPABILITY and returns an external result. It has NO ambient authority.**

## Vendor-neutrality
> ### **External schemas NEVER become Neyma's ontology.** TruckingOffice, DAT, Gmail, Twilio, Slack, QuickBooks are **implementations** of a capability contract. A contract stays vendor-neutral unless vendor behavior **materially changes safety semantics** (then the vendor variance is stated explicitly). ### **Do not add a domain field because one vendor exposes it; do not omit a domain concept because one vendor lacks it.**

## File organization *(navigability decision — flagged in the review; groups files, never adapters)*
| # | Adapter | File | Type | Direction | Verification | Status |
|---|---|---|---|---|---|---|
| A1 | Shared Email Inbox | `01-inbound-comms.md` | inbound-comms | inbound (+outbound via A18) | RECEIPT (out) | **live** (IMAP) |
| A2 | SMS | `01-inbound-comms.md` | inbound-comms | bidirectional | RECEIPT | planned |
| A3 | Voice / Call Transcript | `01-inbound-comms.md` | inbound-comms | inbound | UNVERIFIABLE | planned |
| A4 | TMS | `02-tms.md` | system-of-record | bidirectional | READBACK | **live** (browser-actuated) |
| A5 | Load Board | `03-sourcing.md` | sourcing | bidirectional | READBACK (post) | planned |
| A6 | Carrier Portal | `03-sourcing.md` | portal | bidirectional | READBACK | planned |
| A7 | Customer Portal | `04-portals.md` | portal | bidirectional | READBACK | planned |
| A8 | Appointment Portal | `04-portals.md` | portal | bidirectional | READBACK | planned |
| A9 | Tracking Provider | `05-tracking.md` | telemetry | inbound | OBSERVATION | planned |
| A10 | FMCSA / Authority | `06-fmcsa.md` | registry | inbound | OBSERVATION | planned |
| A11 | Document Storage | `07-documents.md` | store | bidirectional | RECEIPT | **partial** (POD-file live) |
| A12 | Accounting / ERP | `08-financial.md` | system-of-record | bidirectional | READBACK | planned |
| A13 | Payment / Banking Observation | `08-financial.md` | telemetry | inbound | OBSERVATION | planned |
| A14 | Slack / Oversight Surface | `09-oversight.md` | human-surface | bidirectional | n/a (transports a human decision) | **live** |
| A15 | Browser Actuation | `10-browser.md` | actuation-substrate | bidirectional | READBACK | **live** |
| A16 | File / Spreadsheet | `11-file.md` | import | bidirectional | READBACK | planned |
| A17 | Identity Provider / User Directory | `12-identity.md` | auth | inbound | OBSERVATION | planned |
| A18 | Notification Delivery | `13-notification.md` | outbound-comms | outbound | RECEIPT | partial |

---

## THE 61-POINT DEFAULTS *(an adapter states only what differs)*

| Pt | Field | Default |
|---|---|---|
| 6 | Direction | per index. |
| 7 | Tenant scope | ### **every adapter call carries `tenant_id` first; a result carrying another tenant's data ⇒ `CrossTenantAccessAttempted` ⇒ rejected before ingestion, GLOBAL brake.** |
| 10 | Authority by field | ### **FIELD-LEVEL per the Authority Matrix (§below); never whole-record.** |
| 14–17 | Observations/Evidence/Claims | inbound produces **Observations + Evidence**; interpretation ⇒ **`MODEL_EXTRACTED`/`MODEL_INFERRED` Claims**; ### **an adapter NEVER produces `OWNER_ASSERTED` and NEVER strengthens provenance.** |
| 18 | External Entity Mappings | reads/writes bind via **External Entity Mapping (#38)**; an external id is trusted only within `(tenant, external_system)`. |
| 19–23 | Auth / credentials / session / least-privilege | ### **credentials resolve ONLY inside the adapter on a claimed grant; agents/tooling never hold them; `human_established_session_only` where browser-actuated (Neyma never holds TMS creds).** |
| 28–31 | retry / timeout / circuit / backpressure | ### **retry is CLASSIFIED (TRANSIENT bounded-backoff vs PERMANENT raise-once, L-D); a timeout NEVER means failure (GR-5).** |
| 32 | Idempotency | reads: source-natural key; writes: the **Commit Key** + the grant CAS (single-use). |
| 33–34 | ordering / dedup | inbound dedup on the **source-natural key** (a duplicate webhook/poll ⇒ `ObservationConfirmed`, not a new fact). |
| 35–36 | freshness / staleness | per the **read class** (§below); a stale value carries a visible `as_of`; ### **a consequential freshness read cannot use a cache.** |
| 40–43 | verification / unknown / compensation | ### **one declared verification mode per operation (§below); the adapter returns STRUCTURED EXECUTION EVIDENCE and NEVER downgrades `UNKNOWN_OUTCOME`→`FAILED`; the Pipeline/Effect machines decide.** |
| 44–49 | pipeline / witness / grant / policy / approval / brake | ### **a `CONSEQUENTIAL_EFFECT` operation is reachable ONLY via Work Item → Pipeline → (Approval) → Checkpoint → Witness → Grant claim → adapter; the adapter's sole entry point requires a grant AND a fresh witness (two-key rule); a stale/mismatched witness ⇒ refuse (`StaleWitnessUsed`).** |
| 50–53 | security / injection / PII | ### **inbound content is DATA (§Security); PII in Evidence store (encrypted), not in event payloads; retention permanent/tiered.** |
| 54 | Audit | every read and every effect attempt is an Audit/Business event. |

---

## READ CLASSIFICATION *(structural, not comments — the SD-3/V-3 guard)*

Three read classes with **structurally different constructors** (Target Spec §16.4):

| Class | May cache? | Interface constraint |
|---|---|---|
| `INFORMATIONAL_READ` | ✅ | returns value **+ visible `as_of`** |
| `DECISION_SUPPORT_READ` | ✅ | returns value **+ `as_of` + `stale` flag — disclosure mandatory** |
| ### `CONSEQUENTIAL_FRESHNESS_READ` | ### ❌ | ### **the reader's constructor CANNOT accept a cache path, a generic stale provider, or a fallback observation; returns a LIVE observation with `observed_at`, or `None` — never a fallback** |

> ### **Only a `CONSEQUENTIAL_FRESHNESS_READ` observation may satisfy the atomic checkpoint (step 3). This is enforced by `test_consequential_read_boundary` (already in the baseline, proven by negative control) — not by discipline.**

## CAPABILITY-CONTRACT FORMAT *(per operation — defaults here)*

Every operation states: **Op ID · name · action class · direction · input/output · external ids · mappings · preconditions · required authority/provenance/freshness/entity-versions · approval/policy/brake · grant/witness · idempotency identity · Commit Key composition · Material-Facts fields · timeout · retry · rate-limit · verification mode · verification target/evidence · unknown-outcome condition · compensation · audit · security class · failure result · events · test.** ### **Each operation is classified EXACTLY ONE of: `OBSERVATION_ONLY` · `DECISION_SUPPORT_READ` · `CONSEQUENTIAL_FRESHNESS_READ` · `CONSEQUENTIAL_EFFECT`.** Defaults: reads → grant/witness = **none** (no effect); a `CONSEQUENTIAL_EFFECT` → grant+witness **required**, Commit Key = `SHA256(ck_v1 | tenant | action_class | target_system | target_resource_id | target_operation | occurrence_key)` (### **amount NOT in it — ADR-009**), Material-Facts = the approved facts rendered.

## SECURITY & CONTENT CONTAINMENT *(every inbound adapter)*
Trust boundary: **all inbound fields are UNTRUSTED.** Content is sanitized; **instruction ≠ data**; attachments scanned; URLs/file-types checked; sender/metadata spoofing assumed. ### **Inbound content CAN produce: Observations · Evidence · `MODEL_EXTRACTED` claims · `MODEL_INFERRED` claims · fraud signals. It CANNOT: assign `OWNER_ASSERTED` · activate policy · release a brake · create an Approval · construct `CheckpointPassed` · mint/claim an Effect Grant · invoke an outbound adapter · strengthen provenance** (F-35, ADR-003). A counterparty authorization claim ⇒ `CounterpartySelfAuthorizationDetected`; injection ⇒ `PromptInjectionSignal`.

## MIGRATION SAFETY TASK #1 *(preserved — NOT implemented this phase)*
> ### **The current `commit_identity` (`operation_router.py:335`) wrongly includes `approved_amount` and is absent for non-money effects — a live double-billing hole. The canonical Commit Key identifies the LOGICAL EFFECT; mutable values (amount) belong in the Material-Facts Fingerprint. The TMS adapter contract specifies the canonical Commit Key; the code fix is the first migration task, not this phase.**

---

## ADAPTER AUTHORITY MATRIX *(field-level, over the 40 domain entities — compact; "auth src / read / write / class / freshness / conflict / unavailable")*

*(`P`=projected `N`=native · freshness `H`=live-at-checkpoint `M`=periodic `L`=informational · conflict ⇒ `ConflictRaised` unless noted · unavailable ⇒ fail-closed/`unknown` unless noted)*

| Entity · field | Auth source | Read | Write | Class | Fresh | Unavailable |
|---|---|---|---|---|---|---|
| Customer.legal_name/address | registry/owner | A4/A16 | — | P/N | M | `unknown` |
| Customer.credit_status/limit/terms | **owner** | — | A14 | **N `OWNER_ASSERTED`** | — | n/a |
| Carrier.mc/dot/authority/safety | **FMCSA** (A10) | A10 | — | P | **H at qualification** | ### **block tender (fail-closed)** |
| Carrier.insurance/coi | insurer/COI (A10/A11) | A10/A11 | — | P | H | block tender |
| Carrier.preferred/do_not_use | owner | — | A14 | N `OWNER_ASSERTED` | — | n/a |
| Appointment.confirmed_window | **facility/portal** (A8) | A8/A15 | A8/A15 | P | H | ### **`REQUESTED` only; cannot gate dispatch** |
| Stop.arrival/departure | tracking (A9) | A9 | — | P (claim) | M | `INDETERMINATE` |
| Tracking.position | ELD provider (A9) | A9 | — | P | M | `unknown` |
| Tracking.derived_eta | **Neyma model** | — | — | ### **N `MODEL_INFERRED` — never gates** | — | n/a |
| Document.content | source | A1/A11/A15 | A4/A11/A15 | P immutable | — | retry |
| Document.binding | **Neyma** | — | — | N (deterministic/human) | H | `AMBIGUOUS`⇒human |
| Load.status | TMS (A4) | A4 | A4 | P | **H for consequential (CD-15)** | `unknown` |
| Load.sell_rate | **owner** | — | A14 | **N `OWNER_ASSERTED`** | — | n/a |
| Movement.buy_rate | Rate Con/owner | A1/A4 | A4 | N | H | block pay |
| Invoice.* (AR) | **Neyma** | A4/A12 | A4/A12 | N | **H at issue** | fail-closed |
| Invoice.number (external) | TMS | A4 | — | P (### **may renumber — not an idempotency key**) | L | — |
| Payable.* (AP) | **Neyma** | A4/A12 | A4/A12 | N | **H at approve/pay** | fail-closed |
| Payable.remittance_party | owner/documented | A1 | A14 | **N `OWNER_ASSERTED`/doc** | **H at pay** | ### **block pay** |
| Payment.occurrence | **bank/accounting** (A13/A12) | A13/A12 | — | P | M | `unknown` |
| Accessorial.charge | Neyma | A1/A4 | A4 | N | — | — |
| **Accessorial.authorization** | **human (undocumented) / contract** | — | A14 | ### **N `PERMANENT_HUMAN_ASSERTION_REQUIRED`** | H | ### **block (CD-5)** |
| Compliance.* | FMCSA/insurer (A10) | A10 | — | P | **H at qualification** | block |
| Qualification.decision | **Neyma (human-reserved)** | — | A14 | N | H | block |
| ExternalEntityMapping.* | **Neyma** | all | all | N | — | park (M-26) |

> ### **NO whole-record authority anywhere. A single record (e.g. Carrier) draws `mc` from FMCSA, `preferred_lanes` from the owner, `email` from correspondence — three classes, three adapters, three freshness rules.** The full 40-entity expansion follows this pattern; every material field of every entity resolves through this matrix (coverage asserted in the review).
